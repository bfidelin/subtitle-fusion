from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.asr import ASRProvider, build_asr_provider
from src.audio_music import AudioEventProvider, build_audio_event_provider
from src.diarization import DiarizationProvider, assign_speakers, build_diarization_provider, overlap_seconds
from src.exporters import export_ass, export_json, export_srt
from src.fusion import resolve_segment
from src.imdb_index import IMDbIndex
from src.media import extract_audio
from src.models import Event, MediaContext, MusicInfo, PipelineResult, Segment
from src.scoring import load_scoring_config, segment_needs_review
from src.voiceprints import VoiceprintStore, series_key


def load_settings(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_speaker_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    raw = load_settings(path)
    return {str(key): str(value) for key, value in raw.items()}


def _attach_audio_events(segments: list[Segment], events: list, *, music_labels: set[str]) -> None:
    for segment in segments:
        segment_events: list[Event] = []
        music_scores: list[float] = []
        for event in events:
            if overlap_seconds(segment.start, segment.end, event.start, event.end) <= 0:
                continue
            if event.label in music_labels:
                music_scores.append(event.score)
                continue
            segment_events.append(Event(label=event.label, score=event.score, start=event.start, end=event.end, source=event.meta.get("provider")))
        segment.events = segment_events
        if music_scores:
            segment.music = MusicInfo(present=True)


def _identify_speakers(segments: list[Segment], embeddings: dict[str, list[float]], *, store: VoiceprintStore, speaker_map: dict[str, str], min_score: float, min_margin: float, enroll_mapped_speakers: bool) -> dict[str, dict[str, float | str]]:
    identities: dict[str, dict[str, float | str]] = {}
    for speaker_id, embedding in embeddings.items():
        if speaker_id in speaker_map:
            name = speaker_map[speaker_id]
            if enroll_mapped_speakers:
                store.enroll(name, embedding)
            identities[speaker_id] = {"name": name, "score": 1.0}
            continue
        match = store.match(embedding, min_score=min_score, min_margin=min_margin)
        if match:
            identities[speaker_id] = {"name": match.name, "score": match.score}

    if enroll_mapped_speakers and speaker_map:
        store.save()

    for segment in segments:
        identity = identities.get(segment.speaker_id)
        if identity:
            segment.speaker_name_candidate = str(identity["name"])
            segment.speaker_name_confidence = float(identity["score"])
    return identities


def run_pipeline(
    video_path: Path,
    media: MediaContext,
    output_dir: Path,
    settings_path: Path = Path("config/settings.yaml"),
    scoring_path: Path = Path("config/scoring.yaml"),
    audio_analysis_path: Path = Path("config/audio_analysis.yaml"),
    style_path: Path = Path("config/style_rules.yaml"),
    speaker_map_path: Path | None = None,
    *,
    asr_provider: ASRProvider | None = None,
    diarization_provider: DiarizationProvider | None = None,
    audio_event_provider: AudioEventProvider | None = None,
) -> PipelineResult:
    settings = load_settings(settings_path)
    scoring_cfg = load_scoring_config(scoring_path)
    audio_cfg = load_settings(audio_analysis_path)
    style_cfg = load_settings(style_path)

    paths = settings.get("paths", {})
    work_dir = Path(paths.get("work_dir", "data/work"))
    voiceprints_dir = Path(paths.get("voiceprints_dir", "data/voiceprints"))
    work_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_16k = extract_audio(video_path, work_dir / f"{video_path.stem}.16k.wav", sample_rate=16_000)
    asr_cfg = settings.get("providers", {}).get("asr", {})
    diar_cfg = settings.get("providers", {}).get("diarization", {})
    asr = asr_provider or build_asr_provider(asr_cfg)
    diarizer = diarization_provider or build_diarization_provider(diar_cfg)

    asr_result = asr.transcribe(audio_16k)
    diar_result = diarizer.diarize(audio_16k)
    segments = assign_speakers(asr_result.segments, diar_result.turns)

    speaker_map = _load_speaker_map(speaker_map_path)
    voice_cfg = settings.get("voiceprints", {})
    voice_store = VoiceprintStore.load(voiceprints_dir / f"{series_key(media.title)}.json")
    identities = _identify_speakers(segments, diar_result.speaker_embeddings, store=voice_store, speaker_map=speaker_map, min_score=float(voice_cfg.get("min_score", 0.78)), min_margin=float(voice_cfg.get("min_margin", 0.04)), enroll_mapped_speakers=bool(voice_cfg.get("enroll_mapped_speakers", True)))

    audio_events_cfg = audio_cfg.get("audio_events", {})
    if bool(audio_events_cfg.get("enabled", True)):
        audio_32k = extract_audio(video_path, work_dir / f"{video_path.stem}.32k.wav", sample_rate=32_000)
        event_provider = audio_event_provider or build_audio_event_provider(audio_events_cfg)
        events = event_provider.detect_events(audio_32k)
        _attach_audio_events(segments, events, music_labels=set(audio_events_cfg.get("music_labels", ["Music"])))

    if bool(settings.get("pipeline", {}).get("enable_imdb", True)) and media.imdb_title_id:
        imdb_dir = Path(paths.get("imdb_dir", "data/imdb"))
        imdb = IMDbIndex.from_dir(imdb_dir)
        title_candidates = imdb.get_characters_for_title(media.imdb_title_id) + imdb.get_people_for_title(media.imdb_title_id)
        for segment in segments:
            segment.imdb_candidates = title_candidates

    for segment in segments:
        if segment_needs_review(segment, scoring_cfg):
            segment.decision = resolve_segment(segment, scoring_cfg)
            segment.text_corrected = segment.decision.final_text
        else:
            segment.text_corrected = segment.text_raw

    result = PipelineResult(media=media, segments=segments, meta={"asr": asr_result.meta or {}, "diarization": diar_result.meta, "speaker_identities": identities})
    if bool(settings.get("pipeline", {}).get("write_debug_json", True)):
        export_json(result, output_dir / "output.debug.json")
    export_srt(result, output_dir / "output.srt", style=style_cfg)
    export_ass(result, output_dir / "output.ass", style=style_cfg)
    return result
