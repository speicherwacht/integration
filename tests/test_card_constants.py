"""The card repeats a few names and figures of the Python side; they must
match.

It finds the entities by translation key, names the repair issues and the
reasons of unknown figures, and says what is still missing ("2 of 3
discharges"). A renamed key or a changed threshold would leave it wrong
without an error.
"""

import json
import re
from pathlib import Path

from custom_components.speicherwacht import analysis, health
from custom_components.speicherwacht.binary_sensor import CHECKS
from custom_components.speicherwacht.runtime import ISSUES, NO_RECORDER, NOT_ANALYSED

ROOT = Path(__file__).parent.parent / "custom_components" / "speicherwacht"
CARD = (ROOT / "frontend" / "speicherwacht-card.js").read_text(encoding="utf-8")
STRINGS = json.loads((ROOT / "strings.json").read_text(encoding="utf-8"))


def _list(name: str) -> list[str]:
    match = re.search(rf"const {name} = \[([^\]]*)\];", CARD)
    assert match, f"{name} not found in the card"
    return re.findall(r'"([a-z_]+)"', match.group(1))


def _languages() -> list[str]:
    """The text blocks per language (de, en)."""
    return re.split(r"\n  en: \{\n", CARD.split("const TEXT = {", 1)[1], maxsplit=1)


def test_thresholds_match_the_python_side() -> None:
    match = re.search(
        r"const NEEDS = \{ discharges: (\d+), rest_hours: (\d+), "
        r"operating_days: (\d+), end_of_life: (\d+) \};",
        CARD,
    )
    assert match, "NEEDS not found in the card"
    discharges, rest_hours, days, end_of_life = (int(v) for v in match.groups())
    assert discharges == analysis.MIN_CAPACITY_SAMPLES
    assert rest_hours == analysis.MIN_REST_HOURS
    assert days == health.EFFICIENCY_MIN_DAYS
    assert end_of_life == round(health.CAPACITY_END_OF_LIFE * 100)


def test_checks_and_issues_match() -> None:
    assert _list("CHECKS") == list(CHECKS)
    assert _list("ISSUES") == list(ISSUES)
    for block in _languages():
        for key in (*CHECKS, *ISSUES):
            assert f"{key}:" in block, key


def test_every_reason_has_a_text() -> None:
    reasons = {
        NOT_ANALYSED,
        NO_RECORDER,
        analysis.NO_DATA,
        analysis.NO_SOC,
        analysis.TOO_LITTLE_CHARGE,
        analysis.TOO_FEW_REST_HOURS,
        analysis.SOC_ROSE_AT_REST,
        analysis.TOO_FEW_DISCHARGES,
        health.NO_PREVIOUS_YEAR,
        health.TOO_FEW_DAYS,
    }
    for block in _languages():
        texts = re.search(r"reasons: \{(.*?)\n    \},", block, re.S)
        assert texts, "reasons not found"
        for reason in reasons:
            assert f"{reason}:" in texts.group(1), reason


def test_entities_the_card_reads_exist() -> None:
    """Translation keys the card looks up are entities of the integration."""
    keys = set(re.findall(r'_state\("([a-z_]+)"\)', CARD))
    keys |= set(re.findall(r'_tile\("([a-z_]+)"', CARD))
    keys |= set(re.findall(r'link\("([a-z_]+)"', CARD))
    keys |= set(re.findall(r"_entities\.([a-z_]+)", CARD))
    assert keys >= {"efficiency_year", "capacity_estimate", "rest_loss"}
    known = set(STRINGS["entity"]["sensor"]) | set(STRINGS["entity"]["binary_sensor"])
    assert keys <= known, keys - known
