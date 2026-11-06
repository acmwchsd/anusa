import pytest

from app.keyword_matching import find_keyword, sound_skeleton


def find_default_keyword(transcript: str):
    return find_keyword(transcript, ["techpreneure"], 0.75)


@pytest.mark.parametrize(
    "transcript",
    [
        "Techpreneure!",
        "Techpreneur.",
        "Okay everyone, tech preneur!",
        "Tech-preneur",
        "Technopreneur.",
        "techprenure",
        "TECHPRENEURE",
        # what Whisper base.en actually wrote for spoken "techpreneure"
        "Okay everyone, Techpreneur",
        "Tchpreneur.",
        "TechPrunner.",
        "Okay everyone, smile, touch Pranir.",
    ],
)
def test_matches_the_ways_whisper_spells_it(transcript):
    assert find_default_keyword(transcript) is not None


@pytest.mark.parametrize(
    "transcript",
    [
        "Entrepreneur",
        "The technician is here",
        "Thank you.",
        "Open the tech printer",
        "",
        "Please take out your textbooks",
        "Our entrepreneur of the week is here.",
        "Don't touch the paper",
        "Teach the partner",
        "The Dutch printer",
    ],
)
def test_ignores_ordinary_speech(transcript):
    assert find_default_keyword(transcript) is None


def test_sound_skeletons():
    assert sound_skeleton("techpreneure") == "TXPRNR"
    assert sound_skeleton("touchpranir") == "TXPRNR"
    assert sound_skeleton("titchprenya") == "TXPRN"
    assert sound_skeleton("knight") == "NT"
    assert sound_skeleton("phonics") == "FNKS"


def test_extra_keywords_work_too():
    keyword_match = find_keyword("Smile Please, Tech Printer.", ["techpreneure", "tech printer"], 0.75)
    assert keyword_match.keyword == "tech printer"


def test_reports_what_was_heard():
    keyword_match = find_default_keyword("so, tech preneur everyone")
    assert keyword_match.heard_text == "tech preneur"
    assert keyword_match.similarity > 0.9
    assert keyword_match.to_json()["heard"] == "tech preneur"
