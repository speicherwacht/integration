"""The report for a bug report: plain text, empty sections left out."""

from __future__ import annotations

from custom_components.speicherwacht.issue_report import render, settings


def test_render_sections_and_lines() -> None:
    text = render(
        "Speicherwacht 0.1.4, Home Assistant 2026.11.0",
        [
            ("entry", [("template", "own mapping")]),
            ("sources", []),
            ("settings", settings({"capacity": 10.0, "boundary": "battery"})),
        ],
    )
    assert text == (
        "Speicherwacht 0.1.4, Home Assistant 2026.11.0\n"
        "\n"
        "[entry]\n"
        "template: own mapping\n"
        "\n"
        "[settings]\n"
        "boundary: battery\n"
        "capacity: 10.0"
    )


def test_text_and_utc() -> None:
    """Settings in plain text, not Python's spelling (same in all sister projects)."""
    from datetime import UTC, date, datetime, timedelta, timezone

    from custom_components.speicherwacht.issue_report import text, utc

    assert text(True) == "yes"
    assert text(False) == "no"
    assert text(None) == "none"
    assert text([7.94, 8]) == "7.94, 8"
    assert text([]) == "none"
    assert text({"a": 1, "b": None}) == "a 1, b none"
    assert text(date(2026, 1, 1)) == "2026-01-01"
    assert text(0.5) == "0.5"
    moment = datetime(
        2026, 11, 7, 13, 39, 32, 639925, tzinfo=timezone(timedelta(hours=1))
    )
    assert text(moment) == utc(moment) == "2026-11-07 12:39 UTC"
    assert utc(datetime(2026, 11, 7, 12, 0, tzinfo=UTC)) == "2026-11-07 12:00 UTC"
    assert utc(None) == "-"
