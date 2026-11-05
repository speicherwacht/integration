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
