from src.diarization import SpeakerTurn, assign_speakers, speaker_for_interval
from src.models import Segment, Word


def test_speaker_for_interval_uses_largest_overlap():
    turns = [SpeakerTurn(0.0, 1.0, "A"), SpeakerTurn(1.0, 3.0, "B")]
    assert speaker_for_interval(0.8, 1.8, turns) == "B"


def test_assign_speakers_labels_segments_and_words():
    segment = Segment(id=1, start=0.0, end=2.0, speaker_id="UNKNOWN", text_raw="hello there", words=[Word("hello", 0.1, 0.5), Word("there", 1.2, 1.7)])
    turns = [SpeakerTurn(0.0, 0.8, "A"), SpeakerTurn(0.8, 2.0, "B")]
    assign_speakers([segment], turns)
    assert segment.speaker_id == "B"
    assert segment.words[0].speaker_id == "A"
    assert segment.words[1].speaker_id == "B"
