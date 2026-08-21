from src.exporters import render_sdh_text
from src.models import Event, Segment


STYLE = {
    "speaker_labels": {"enabled": True, "show_only_when_needed": True},
    "sounds": {"enabled": True},
}


def test_offscreen_speaker_gets_character_label():
    segment = Segment(id=1, start=1.0, end=2.0, speaker_id="SPEAKER_00", speaker_name_candidate="Carrie", speaker_visible=False, text_raw="Where are you?")
    assert render_sdh_text(segment, STYLE) == "Carrie: Where are you?"


def test_visible_speaker_does_not_get_redundant_label():
    segment = Segment(id=1, start=1.0, end=2.0, speaker_id="SPEAKER_00", speaker_name_candidate="Carrie", speaker_visible=True, text_raw="Where are you?")
    assert render_sdh_text(segment, STYLE) == "Where are you?"


def test_sound_event_is_rendered_before_dialogue():
    segment = Segment(id=1, start=1.0, end=2.0, speaker_id="SPEAKER_00", text_raw="Hello", events=[Event("Door", 0.9)])
    assert render_sdh_text(segment, STYLE) == "[door]\nHello"
