"""Static checks for the bundled automation blueprint (run locally and in CI).

The texts are rendered with plain Jinja here; tests/ha/test_blueprints.py runs
the blueprint as a real automation in CI. All values are made up.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import jinja2
import pytest
from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA
from homeassistant.components.blueprint.models import Blueprint
from homeassistant.util.yaml import load_yaml

from custom_components.speicherwacht import health
from custom_components.speicherwacht.binary_sensor import CHECKS

from .sim import BERLIN, SUMMER_DAY, at, simulate

ROOT = Path(__file__).parent.parent
BLUEPRINTS = ROOT / "blueprints" / "automation" / "speicherwacht"
FILES = sorted(BLUEPRINTS.glob("*.yaml"))
BEFUND = BLUEPRINTS / "befund_melden.yaml"


def test_blueprints_exist() -> None:
    assert [f.name for f in FILES] == ["befund_melden.yaml"]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_blueprint_is_valid(path: Path) -> None:
    blueprint = Blueprint(
        load_yaml(path),
        expected_domain="automation",
        schema=AUTOMATION_BLUEPRINT_SCHEMA,
    )
    meta = blueprint.metadata
    assert meta["name"].startswith("Speicherwacht")
    # The import button and HA's "re-import" use this URL.
    url = (
        "https://github.com/speicherwacht/integration/blob/main/"
        f"blueprints/automation/speicherwacht/{path.name}"
    )
    assert meta["source_url"] == url
    assert meta["homeassistant"]["min_version"] == "2026.4.0"
    # Both READMEs link the import button to it.
    encoded = url.replace(":", "%3A").replace("/", "%2F")
    for readme in ("README.md", "README.en.md"):
        assert encoded in (ROOT / readme).read_text(encoding="utf-8"), readme


def test_blueprint_offers_only_problem_sensors_of_speicherwacht() -> None:
    data = load_yaml(BEFUND)
    assert set(data["blueprint"]["input"]) == {"checks", "notify_action", "language"}
    selector = data["blueprint"]["input"]["checks"]["selector"]["entity"]
    assert selector["multiple"] is True
    assert selector["filter"] == {
        "integration": "speicherwacht",
        "domain": "binary_sensor",
        "device_class": "problem",
    }


# Problem cases from the simulator, as in tests/test_health.py.
LAST_YEAR = date(2025, 6, 1)
THIS_YEAR = date(2026, 6, 1)
NOW = at(date(2026, 6, 30), 23) + timedelta(minutes=30)
SUNNY_DAY = {**SUMMER_DAY, **dict.fromkeys(range(9, 15), 2.0)}


def _two_years(**this_year: Any) -> list:
    before = simulate(LAST_YEAR, 30, rest_watts=10.0, profile=lambda _d: SUNNY_DAY)
    now = simulate(
        THIS_YEAR - timedelta(days=1),
        31,
        profile=lambda _d: SUNNY_DAY,
        **{"rest_watts": 10.0, **this_year},
    )
    return before + now


def _attributes(check: health.Check) -> dict[str, Any]:
    """As binary_sensor.ProblemSensor shows them."""
    assert check.problem is True
    return {
        **{
            key: round(value, 1) if isinstance(value, float) else value
            for key, value in check.details.items()
        },
        "reason": check.reason,
    }


def _problems() -> dict[str, list[dict[str, Any]]]:
    return {
        "efficiency_drop": [
            _attributes(
                health.efficiency_drop(_two_years(efficiency=0.85), 10.0, BERLIN, NOW)
            )
        ],
        "capacity_low": [
            _attributes(health.capacity_low(_two_years(capacity=7.5), 10.0, NOW)),
            _attributes(health.capacity_low(_two_years(capacity=8.8), 10.0, NOW)),
        ],
        "rest_loss_high": [
            _attributes(health.rest_loss_high(_two_years(rest_watts=25.0), 10.0, NOW)),
        ],
    }


def test_attributes_the_blueprint_reads_exist() -> None:
    """Every `a.<name>` of the message is an attribute of a problem sensor."""
    text = BEFUND.read_text(encoding="utf-8")
    used = set(re.findall(r"\ba\.([a-z_]+)", text))
    problems = _problems()
    assert set(problems) == set(CHECKS)
    known = {key for cases in problems.values() for a in cases for key in a}
    assert used <= known, used - known
    # The keys that tell the three checks apart are unique to their check.
    for key, check in (
        ("current_percent", "efficiency_drop"),
        ("estimate_kwh", "capacity_low"),
        ("max_watts", "rest_loss_high"),
    ):
        owners = {c for c, cases in problems.items() if key in cases[0]}
        assert owners == {check}, key


def _detail(attributes: dict[str, Any], lang: str) -> str:
    """The `detail` variable of the blueprint, rendered with plain Jinja."""
    source = load_yaml(BEFUND)["variables"]["detail"]
    template = jinja2.Environment().from_string(source)
    return template.render(
        trigger={"to_state": {"attributes": attributes}}, lang=lang
    ).strip()


EFFICIENCY = {
    "current_percent": 88.4,
    "previous_year_percent": 92.0,
    "current_days": 27,
    "previous_year_days": 28,
    "threshold_points": 3.0,
    "drop_points": 3.6,
    "reason": None,
}
CAPACITY_LOW = {
    "estimate_kwh": 7.6,
    "year_ago_kwh": None,
    "data_sheet_kwh": 10.0,
    "end_of_life_percent": 80.0,
    "drop_threshold_points": 10.0,
    "share_percent": 76.0,
    "reason": None,
}
CAPACITY_DROP = {
    **CAPACITY_LOW,
    "estimate_kwh": 8.6,
    "year_ago_kwh": 9.8,
    "share_percent": 86.0,
    "drop_points": 12.0,
}
REST_HIGH = {
    "watts": 70.0,
    "previous_year_watts": None,
    "max_watts": 64.0,
    "reason": None,
}
REST_RISE = {**REST_HIGH, "watts": 31.0, "previous_year_watts": 12.0}


@pytest.mark.parametrize(
    ("attributes", "de", "en"),
    [
        (
            EFFICIENCY,
            "letzte 30 Tage 88,4 % statt 92,0 % im Vorjahr (3,6 Punkte weniger)",
            "last 30 days 88.4 % instead of 92.0 % last year (3.6 points less)",
        ),
        (
            CAPACITY_LOW,
            "geschätzt 7,6 kWh, 76 % des Datenblatts (Grenze 80 %)",
            "estimated 7.6 kWh, 76 % of the data sheet (limit 80 %)",
        ),
        (
            CAPACITY_DROP,
            "geschätzt 8,6 kWh, 12 Punkte weniger als vor einem Jahr (9,8 kWh)",
            "estimated 8.6 kWh, 12 points less than a year ago (9.8 kWh)",
        ),
        (REST_HIGH, "70 W (Grenze 64 W)", "70 W (limit 64 W)"),
        (
            REST_RISE,
            "31 W statt 12 W in denselben 30 Tagen des Vorjahres",
            "31 W instead of 12 W in the same 30 days last year",
        ),
    ],
    ids=["efficiency", "capacity_low", "capacity_drop", "rest_high", "rest_rise"],
)
def test_finding_in_words(attributes: dict[str, Any], de: str, en: str) -> None:
    assert _detail(attributes, "de") == de
    assert _detail(attributes, "en") == en


@pytest.mark.parametrize("check", list(CHECKS))
def test_simulated_findings_have_words(check: str) -> None:
    """Real attributes of each check give a text without placeholders."""
    for attributes in _problems()[check]:
        text = _detail(attributes, "de")
        assert text, check
        assert "None" not in text, text
