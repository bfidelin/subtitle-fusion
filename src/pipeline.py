from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import re
import yaml

from src.exporters import export_ass, export_compliance_report, export_json, export_srt
from src.fusion import attach_nearby_ocr, resolve_segment
from src.imdb_index import IMDbIndex
from src.media_preflight import MediaPreflightError, probe_media
from src.models import Candidate, MediaContext, PipelineResult, Segment, SpeakerTurn, Word
from src.netflix_style import NetflixStyle, apply_netflix_style, validate_result
from src.scoring import load_scoring_config, segment_needs_review
from src.voiceprints import VoiceprintStore, series_key
from src.whisperx_provider import WhisperXConfig, WhisperXProvider


def load_settings(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_speaker_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return {str(speaker_id): str(name) for speaker_id, name in raw.items() if name}


def build_stub_segments() -> list[Segment]:
    return [
        Segment(
            id=1,
            start=0.0,
            end=2.5,
            speaker_id="Speaker_1",
            text_raw="Murel, on verrouille tout.",
            words=[
                Word(
                    text="Murel",
                    start=0.0,
                    end=0.4,
                    confidence=0.41,
                    flags=["proper_noun_candidate"],
                ),
                Word(text="on", start=0.5, end=0.7, confidence=0.96),
                Word(text="verrouille", start=0.8, end=1.4, confidence=0.95),
                Word(text="tout.", start=1.5, end=1.8, confidence=0.94),
            ],
        )
    ]


def ingest_transcript(
    video_path: Path,
    settings: dict,
) -> tuple[list[Segment], list[SpeakerTurn], dict[str, list[float]], str | None]:
    provider = settings.get("providers", {}).get("asr", "stub")
    if provider == "stub":
        return build_stub_segments(), [], {}, None

    # Prefer an embedded text subtitle when the selected pipeline asks for reuse
    # and the media actually contains a usable track. This gives human-quality
    # timing and wording before any ASR path runs.
    if settings.get("pipeline", {}).get("reuse_embedded_subtitles", False) or provider in {
        "embedded",
        "embedded_subtitle",
        "embedded_subtitles",
    }:
        from src.embedded_subtitle_provider import (
            EmbeddedSubtitleConfig,
            EmbeddedSubtitleProvider,
            EmbeddedSubtitleUnavailableError,
        )

        try:
            cfg = EmbeddedSubtitleConfig.from_mapping(settings.get("embedded_subtitles"))
            run = EmbeddedSubtitleProvider(cfg).transcribe(video_path)
            return run.segments, run.speaker_turns, run.speaker_embeddings, run.language
        except EmbeddedSubtitleUnavailableError:
            if provider in {"embedded", "embedded_subtitle", "embedded_subtitles"}:
                raise ValueError("No embedded text subtitle stream available")

    if provider in {"whisper_http", "remote_whisper", "http_whisper"}:
        from src.whisper_http_provider import WhisperHttpConfig, WhisperHttpProvider

        cfg = WhisperHttpConfig.from_mapping(settings.get("whisper_http"))
        diarization_provider = settings.get("providers", {}).get("diarization")
        if diarization_provider in {"none", "disabled", None, "pyannote_gpu", "senko_gpu", "speakrs"}:
            cfg.diarize = False
        run = WhisperHttpProvider(cfg).transcribe(video_path)
        segments = run.segments
        speaker_turns = run.speaker_turns
        speaker_embeddings = run.speaker_embeddings
        language = run.language

        if diarization_provider == "pyannote_gpu":
            from src.pyannote_gpu_provider import (
                PyannoteGpuConfig,
                PyannoteGpuUnavailableError,
                run_pyannote_diarization,
                segment_by_pyannote_turns,
            )

            try:
                pya_cfg = PyannoteGpuConfig.from_mapping(settings.get("pyannote_gpu"))
                turns, embeddings = run_pyannote_diarization(video_path, pya_cfg)
            except PyannoteGpuUnavailableError as exc:
                raise ValueError(str(exc)) from exc
            speaker_turns = [
                SpeakerTurn(
                    start=float(turn.get("start", 0.0)),
                    end=float(turn.get("end", 0.0)),
                    speaker_id=str(turn.get("speaker", "UNKNOWN")),
                )
                for turn in turns
            ]
            segments = segment_by_pyannote_turns(segments, turns)
            if embeddings:
                speaker_embeddings = embeddings

        if diarization_provider == "senko_gpu":
            from src.pyannote_gpu_provider import segment_by_pyannote_turns
            from src.senko_gpu_provider import (
                SenkoGpuConfig,
                SenkoGpuUnavailableError,
                run_senko_diarization,
            )

            try:
                senko_cfg = SenkoGpuConfig.from_mapping(settings.get("senko_gpu"))
                turns, embeddings = run_senko_diarization(video_path, senko_cfg)
            except SenkoGpuUnavailableError as exc:
                raise ValueError(str(exc)) from exc
            speaker_turns = [
                SpeakerTurn(
                    start=float(turn.get("start", 0.0)),
                    end=float(turn.get("end", 0.0)),
                    speaker_id=str(turn.get("speaker", "UNKNOWN")),
                )
                for turn in turns
            ]
            segments = segment_by_pyannote_turns(segments, turns)
            if embeddings:
                speaker_embeddings = embeddings

        if diarization_provider == "speakrs":
            from src.pyannote_gpu_provider import segment_by_pyannote_turns
            from src.speakrs_provider import SpeakrsConfig, SpeakrsUnavailableError, run_speakrs_diarization

            try:
                speakrs_cfg = SpeakrsConfig.from_mapping(settings.get("speakrs"))
                turns, embeddings = run_speakrs_diarization(video_path, speakrs_cfg)
            except SpeakrsUnavailableError as exc:
                raise ValueError(str(exc)) from exc
            speaker_turns = [
                SpeakerTurn(
                    start=float(turn.get("start", 0.0)),
                    end=float(turn.get("end", 0.0)),
                    speaker_id=str(turn.get("speaker", "UNKNOWN")),
                )
                for turn in turns
            ]
            segments = segment_by_pyannote_turns(segments, turns)
            if embeddings:
                speaker_embeddings = embeddings

        return segments, speaker_turns, speaker_embeddings, language
    if provider != "whisperx":
        raise ValueError(f"Unsupported ASR provider: {provider!r}")

    whisperx_cfg = WhisperXConfig.from_mapping(settings.get("whisperx"))
    diarization_provider = settings.get("providers", {}).get("diarization", "whisperx_pyannote")
    if diarization_provider in {"none", "disabled", None}:
        whisperx_cfg = WhisperXConfig.from_mapping(
            {**settings.get("whisperx", {}), "diarize": False}
        )
    elif diarization_provider != "whisperx_pyannote":
        raise ValueError(f"Unsupported diarization provider: {diarization_provider!r}")

    run = WhisperXProvider(whisperx_cfg).transcribe(video_path)
    return run.segments, run.speaker_turns, run.speaker_embeddings, run.language


def apply_voiceprints(
    segments: list[Segment],
    speaker_embeddings: dict[str, list[float]],
    media: MediaContext,
    settings: dict,
    speaker_map_path: Path | None,
) -> dict[str, object]:
    cfg = settings.get("voiceprints", {})
    if not cfg.get("enabled", True) or not speaker_embeddings:
        return {"enabled": bool(cfg.get("enabled", True)), "matches": {}}

    store_dir = Path(cfg.get("store_dir", "data/voiceprints"))
    store = VoiceprintStore.load(store_dir / f"{series_key(media.title)}.json")
    speaker_map = load_speaker_map(speaker_map_path)

    enrolled: dict[str, str] = {}
    for speaker_id, name in speaker_map.items():
        embedding = speaker_embeddings.get(speaker_id)
        if not embedding:
            continue
        store.enroll(
            name,
            embedding,
            max_samples=int(cfg.get("max_samples_per_character", 12)),
        )
        enrolled[speaker_id] = name
    if enrolled:
        store.save()

    matches: dict[str, dict[str, object]] = {}
    for speaker_id, embedding in speaker_embeddings.items():
        if speaker_id in enrolled:
            matches[speaker_id] = {"name": enrolled[speaker_id], "score": 1.0, "enrolled": True}
            continue
        match = store.match(
            embedding,
            min_score=float(cfg.get("min_score", 0.78)),
            min_margin=float(cfg.get("min_margin", 0.04)),
        )
        if match:
            matches[speaker_id] = {"name": match.name, "score": match.score, "enrolled": False}

    for segment in segments:
        resolved = matches.get(segment.speaker_id)
        if not resolved:
            continue
        segment.speaker_name_candidate = str(resolved["name"])
        segment.speaker_identity_confidence = float(resolved["score"])

    return {"enabled": True, "enrolled": enrolled, "matches": matches}


def run_pipeline(
    video_path: Path,
    media: MediaContext,
    output_dir: Path,
    settings_path: Path = Path("config/settings.yaml"),
    scoring_path: Path = Path("config/scoring.yaml"),
    audio_analysis_path: Path = Path("config/audio_analysis.yaml"),
    style_rules_path: Path = Path("config/style_rules.yaml"),
    speaker_map_path: Path | None = None,
) -> PipelineResult:
    settings = load_settings(settings_path)
    scoring_cfg = load_scoring_config(scoring_path)
    audio_cfg = load_settings(audio_analysis_path)
    style_cfg = load_settings(style_rules_path)
    imdb_dir = Path(settings.get("paths", {}).get("imdb_dir", "data/imdb"))
    imdb = IMDbIndex.from_dir(imdb_dir)
    meta: dict[str, object] = {}

    if settings.get("pipeline", {}).get("enable_media_preflight", True):
        try:
            inventory = probe_media(video_path)
            if media.duration_sec is None:
                media.duration_sec = inventory.duration_sec
            meta["media_preflight"] = {
                "format_name": inventory.format_name,
                "duration_sec": inventory.duration_sec,
                "streams": [asdict(stream) for stream in inventory.streams],
                "text_subtitle_streams": [
                    stream.index for stream in inventory.text_subtitle_streams
                ],
                "image_subtitle_streams": [
                    stream.index for stream in inventory.image_subtitle_streams
                ],
            }
        except (MediaPreflightError, OSError, ValueError) as exc:
            # Preflight is an optimization/evidence stage; failure must not hide a
            # usable ASR path. Record it for diagnosis and continue.
            meta["media_preflight"] = {"error": str(exc)}

    from concurrent.futures import ThreadPoolExecutor

    enable_ocr = bool(settings.get("pipeline", {}).get("enable_ocr", True))
    with ThreadPoolExecutor(max_workers=2) as executor:
        asr_future = executor.submit(ingest_transcript, video_path, settings)
        if enable_ocr:
            try:
                from src.fast_ocr import FastOcrConfig, collect_sparse_ocr

                ocr_future = executor.submit(
                    collect_sparse_ocr,
                    video_path,
                    FastOcrConfig.from_mapping(settings.get("ocr")),
                )
            except Exception:
                ocr_future = None
        else:
            ocr_future = None

        segments, speaker_turns, speaker_embeddings, language = asr_future.result()

    if settings.get("pipeline", {}).get("enable_forced_alignment", False):
        try:
            from src.forced_align_provider import ForcedAlignConfig, align_segments

            fa_cfg = ForcedAlignConfig.from_mapping(settings.get("forced_alignment"))
            if language and str(language).lower() not in {"en", "eng"}:
                meta["forced_alignment"] = {"ran": False, "error": None, "skipped": "language"}
            else:
                segments = align_segments(video_path, segments, fa_cfg)
                meta["forced_alignment"] = {"ran": True, "error": None}
        except Exception as exc:
            meta["forced_alignment"] = {"ran": False, "error": str(exc)}
            if bool(settings.get("pipeline", {}).get("forced_alignment_mandatory", True)):
                raise ValueError(f"forced alignment failed: {exc}") from exc

    # Apply trained phrase/cue resegmentation (optional, deterministic).
    enable_phrase = bool(settings.get("pipeline", {}).get("enable_phrase_segmentation", True))
    min_turn_gap = float(settings.get("pipeline", {}).get("phrase_min_turn_gap", 0.0))
    phrase_mandatory = bool(settings.get("pipeline", {}).get("phrase_segmentation_mandatory", True))
    if enable_phrase:
        try:
            from src.phrase_segmentation import segment_sentences, segment_words

            turn_dicts = []
            for turn in speaker_turns or []:
                if hasattr(turn, "start") and not isinstance(turn, dict):
                    turn_dicts.append(
                        {
                            "start": float(turn.start),
                            "end": float(turn.end),
                            "speaker": str(turn.speaker_id),
                        }
                    )
                elif isinstance(turn, dict):
                    turn_dicts.append(
                        {
                            "start": float(turn.get("start", 0.0)),
                            "end": float(turn.get("end", 0.0)),
                            "speaker": str(turn.get("speaker", turn.get("speaker_id", "UNKNOWN"))),
                        }
                    )
            flattened = []
            for seg in segments:
                if getattr(seg, "words", None):
                    for word in seg.words:
                        flattened.append(
                            {
                                "text": str(getattr(word, "text", "")),
                                "start": float(getattr(word, "start", seg.start)),
                                "end": float(getattr(word, "end", seg.end)),
                                "speaker_id": str(seg.speaker_id)
                                if str(getattr(word, "speaker_id", None)) in ("", "UNKNOWN")
                                else str(getattr(word, "speaker_id", None)),
                                "confidence": getattr(word, "confidence", None),
                            }
                        )
                else:
                    flattened.append(
                        {
                            "text": seg.text_raw,
                            "start": seg.start,
                            "end": seg.end,
                            "speaker_id": seg.speaker_id,
                        }
                    )
            mode = str(settings.get("pipeline", {}).get("phrase_segmentation_mode", "sentence"))
            if mode == "sentence":
                phrase_cues = segment_sentences(
                    flattened, turns=turn_dicts, max_chars=84, max_duration=8.0
                )
            else:
                phrase_cues = segment_words(flattened, turns=turn_dicts, min_turn_gap=min_turn_gap)
            seg_type = type(segments[0]) if segments else None
            if seg_type is not None:
                segments = []
                for cue in phrase_cues:
                    cue_words = []
                    from src.models import Word

                    for word_rec in cue.words:
                        cue_words.append(
                            Word(
                                text=str(word_rec.get("text", "")),
                                start=float(word_rec.get("start", cue.start)),
                                end=float(word_rec.get("end", cue.end)),
                                confidence=word_rec.get("confidence"),
                                speaker_id=cue.speaker_id,
                            )
                        )
                    segments.append(
                        seg_type(
                            id=cue.id,
                            start=cue.start,
                            end=cue.end,
                            speaker_id=cue.speaker_id,
                            text_raw=cue.text_raw,
                            words=cue_words,
                        )
                    )
            meta["phrase_segmentation"] = {"ran": True, "cue_count": len(segments), "error": None}
        except Exception as exc:
            meta["phrase_segmentation"] = {"ran": False, "cue_count": None, "error": str(exc)}
            if phrase_mandatory:
                raise ValueError(f"phrase segmentation failed: {exc}") from exc
    else:
        meta["phrase_segmentation"] = {"ran": False, "cue_count": None, "error": None}
    # Configurable ASR context-term corrections are opt-in and data-driven.
    # Defaults are empty; populate from OCR/Jellyfin/IMDb/Sonarr evidence.

    # Configurable ASR context-term corrections are opt-in and data-driven.
    # Defaults are empty; populate from OCR/Jellyfin/IMDb/Sonarr evidence.
    context_terms = settings.get("context_terms", {}) or {}
    if isinstance(context_terms, dict):
        for segment in segments:
            corrected = segment.text_raw
            for bad, good in context_terms.items():
                if isinstance(bad, str) and isinstance(good, str) and bad.strip():
                    corrected = re.sub(re.escape(bad), good, corrected, flags=re.IGNORECASE)
            if corrected != segment.text_raw:
                segment.text_raw = corrected
                segment.text_corrected = corrected

        if ocr_future is not None:
            try:
                ocr_hits = ocr_future.result()
            except Exception as exc:
                meta["ocr"] = {"error": str(exc)}
                ocr_hits = []
            else:
                for segment in segments:
                    attach_nearby_ocr(segment, ocr_hits)
                    seen = {str(c.name).lower() for c in segment.imdb_candidates}
                    for hit in segment.ocr_hits:
                        if hit.text.lower() in seen:
                            continue
                        seen.add(hit.text.lower())
                        segment.imdb_candidates.append(
                            Candidate(
                                type="ocr",
                                name=hit.text,
                                score=0.0,
                                meta={"ocr_time": hit.time, "ocr_confidence": hit.confidence},
                            )
                        )
                # Optional Jellyfin people candidates from matches against OCR text.
                try:
                    from src.jellyfin_people import JellyfinPeopleIndex, attach_jellyfin_candidates

                    index = JellyfinPeopleIndex.from_paths()
                    if index.rows:
                        attach_jellyfin_candidates(segments, ocr_hits, index, min_occurrences=6)
                        meta["jellyfin_people"] = {
                            "rows": len(index.rows),
                            "candidates": sum(
                                1
                                for s in segments
                                for c in s.imdb_candidates
                                if getattr(c, "type", "") == "jellyfin_person"
                            ),
                        }
                except Exception as exc:
                    meta["jellyfin_people"] = {"error": str(exc)}

                meta["ocr"] = {
                    "hits": len(ocr_hits),
                    "unique_texts": len({hit.text for hit in ocr_hits}),
                    "sparse": True,
                }
        else:
            if enable_ocr:
                meta["ocr"] = {"error": "OCR future was not scheduled"}

    # Add Jellyfin identity candidates even when an episode has no OCR hits.
    try:
        from src.jellyfin_people import JellyfinPeopleIndex, attach_jellyfin_candidates

        jellyfin_index = JellyfinPeopleIndex.from_paths()
        if jellyfin_index.rows:
            for segment in segments:
                words = __import__("re").findall(
                    r"\b[A-Z][A-Za-z]{2,}\b", getattr(segment, "text_raw", "") or ""
                )
                hits = getattr(segment, "ocr_hits", []) or []
                candidates = set(words)
                for hit in hits:
                    for token in re.findall(
                        r"\b[A-Z][a-z]{2,}\b", str(getattr(hit, "text", "") or "")
                    ):
                        candidates.add(token)
                jellyfin_candidates = jellyfin_index.candidates_for_tokens(list(candidates))
                seen = {str(getattr(c, "name", "")).lower() for c in segment.imdb_candidates}
                for candidate in jellyfin_candidates:
                    if candidate.name.lower() not in seen:
                        segment.imdb_candidates.append(candidate)
                        seen.add(candidate.name.lower())
            meta["jellyfin_people"] = {
                "rows": len(jellyfin_index.rows),
                "candidates": sum(
                    1
                    for s in segments
                    for c in s.imdb_candidates
                    if getattr(c, "type", "") == "jellyfin_person"
                ),
            }
    except Exception as exc:
        if "jellyfin_people" not in meta:
            meta["jellyfin_people"] = {"error": str(exc)}

    meta["voiceprints"] = apply_voiceprints(
        segments,
        speaker_embeddings,
        media,
        settings,
        speaker_map_path,
    )

    if media.imdb_title_id:
        title_candidates = imdb.get_characters_for_title(
            media.imdb_title_id
        ) + imdb.get_people_for_title(media.imdb_title_id)
        for seg in segments:
            seg.imdb_candidates = title_candidates

    # Next integrations use the same evidence timeline:
    # - reuse/extract embedded subtitle tracks after quality scoring
    # - shared shot map + sparse OCR
    # - cheap audio scout -> PANNs candidate verification
    # - selective local re-ASR / active-speaker review
    meta["audio_policy"] = {
        "configured": bool(audio_cfg),
        "runtime_wired": False,
        "reason": "scout/verifier cascade is intentionally not run globally yet",
    }

    for seg in segments:
        if segment_needs_review(seg, scoring_cfg):
            seg.decision = resolve_segment(seg, scoring_cfg)
            seg.text_corrected = seg.decision.final_text
        else:
            seg.text_corrected = seg.text_raw

    review_cfg = settings.get("llm_review", {})
    if review_cfg.get("enabled", False):
        try:
            from src.ollama_review import OllamaReviewConfig, review_text

            cfg = OllamaReviewConfig.from_mapping(review_cfg)
            raw_texts = [segment.text_raw for segment in segments]
            reviewed = 0
            accepted = 0
            for index, segment in enumerate(segments):
                if not segment_needs_review(segment, scoring_cfg):
                    continue
                candidate_names = sorted(
                    {candidate.name for candidate in getattr(segment, "imdb_candidates", [])}
                )
                context = (
                    raw_texts[max(0, index - 2) :]
                    if False
                    else raw_texts[max(0, index - 2) : index] + raw_texts[index + 1 : index + 3]
                )
                try:
                    final, changed, reason = review_text(
                        segment.final_text(), candidate_names, context, cfg
                    )
                except Exception as exc:
                    meta["llm_review_warning"] = str(exc)
                    continue
                reviewed += 1
                if changed:
                    accepted += 1
                    segment.text_corrected = final
            meta["llm_review"] = {
                "enabled": True,
                "reviewed": reviewed,
                "accepted": accepted,
                "model": cfg.model,
            }
        except Exception as exc:
            meta["llm_review"] = {"enabled": True, "error": str(exc)}

    netflix_issues = []
    netflix_cfg = style_cfg.get("netflix", {})
    if netflix_cfg.get("enabled", False):
        netflix_style = NetflixStyle.from_mapping(netflix_cfg)
        apply_netflix_style(segments, netflix_style)
        netflix_issues = validate_result(segments, netflix_style)

    result = PipelineResult(
        media=media,
        segments=segments,
        speaker_turns=speaker_turns,
        speaker_embeddings=speaker_embeddings,
        language=language,
        meta=meta,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    export_json(result, output_dir / "output.debug.json")
    export_srt(result, output_dir / "output.srt")
    export_ass(result, output_dir / "output.ass")
    if netflix_cfg.get("enabled", False):
        export_compliance_report(netflix_issues, output_dir / "output.netflix-report.json")
    return result
