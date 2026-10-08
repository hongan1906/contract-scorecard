from datetime import date

from contractscore.dates import add_years, fmt_date, parse_date, words


def test_roundtrip_all_styles():
    d = date(2024, 3, 9)
    for style in ("dmy", "mdy", "iso"):
        assert parse_date(fmt_date(d, style)) == "2024-03-09"


def test_words_and_misc():
    assert words(45) == "forty-five" and words(14) == "fourteen" and words(30) == "thirty"
    assert parse_date("31 February 2024") is None
    assert add_years(date(2023, 3, 1), 3) == date(2026, 3, 1)
