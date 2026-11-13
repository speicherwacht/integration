"""Static checks for the bundled automation blueprint (run locally and in CI).

The texts are rendered with plain Jinja here; tests/ha/test_blueprints.py runs
the blueprint as a real automation in CI. All values are made up.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import jinja2
import pytest
from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.util import slugify
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
    assert set(data["blueprint"]["input"]) == {
        "checks",
        "notify_device",
        "language",
        "more",
    }
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


def _blueprint() -> Blueprint:
    return Blueprint(
        load_yaml(BEFUND),
        expected_domain="automation",
        schema=AUTOMATION_BLUEPRINT_SCHEMA,
    )


def test_inputs_keep_their_keys_and_only_checks_is_required() -> None:
    """Automations made before the section and the phone keep working."""
    inputs = _blueprint().inputs
    assert set(inputs) == {
        "checks",
        "notify_device",
        "language",
        "extra_actions",
        "notify_action",
    }
    assert [k for k, v in inputs.items() if "default" not in v] == ["checks"]
    assert inputs["notify_action"]["default"] == ""
    assert inputs["language"]["default"] == "de"
    assert inputs["notify_device"]["default"] == ""
    raw = load_yaml(BEFUND)["blueprint"]["input"]["notify_device"]
    assert raw["selector"] == {"device": {"filter": {"integration": "mobile_app"}}}
    assert inputs["extra_actions"]["default"] == []
    assert inputs["extra_actions"]["selector"] == {"action": {}}


def test_more_actions_section_is_collapsed() -> None:
    section = load_yaml(BEFUND)["blueprint"]["input"]["more"]
    assert section["name"] == "Weitere Aktionen (optional) / More actions (optional)"
    assert section["collapsed"] is True
    assert list(section["input"]) == ["extra_actions", "notify_action"]
    description = section["input"]["extra_actions"]["description"]
    assert "{{ title }}" in description
    assert "{{ message }}" in description
    assert "telegram_bot.send_message" in description


def test_texts_are_german_and_english() -> None:
    data = load_yaml(BEFUND)["blueprint"]
    assert data["name"] == "Speicherwacht – Befund melden / Report a finding"
    # A German paragraph, then an English one.
    assert "Englisch.\n\nReports" in data["description"]
    for key, value in _blueprint().inputs.items():
        assert " / " in value["name"], key
        if "description" in value:
            assert " / " in value["description"], key
    assert data["input"]["language"]["name"] == (
        "Sprache der Nachricht / Language of the message"
    )


# The variables of the blueprint, rendered in order with plain Jinja and small
# stand-ins for HA's functions. Names and values are made up.
PHONES = {"phone1": {"name": "Pixel von Max"}}
DEVICE_OF = {"binary_sensor.heimspeicher_wirkungsgrad_unter_vorjahr": "Heimspeicher"}
SENSOR = "binary_sensor.heimspeicher_wirkungsgrad_unter_vorjahr"
CLOCK = datetime(2026, 6, 30, 22, 0, tzinfo=UTC)


def _variables(
    *, entity: str, to: str, before: str | None, off_for: timedelta, **inputs: Any
) -> dict[str, Any]:
    config = BlueprintInputs(
        _blueprint(),
        {
            "use_blueprint": {
                "path": BEFUND.name,
                "input": {"checks": [entity], **inputs},
            }
        },
    ).async_substitute()
    env = jinja2.Environment()
    env.filters["slugify"] = slugify
    env.globals["device_name"] = DEVICE_OF.get
    env.globals["device_attr"] = lambda d, a: PHONES.get(d, {}).get(a)
    env.globals["now"] = lambda: CLOCK
    env.globals["timedelta"] = timedelta
    attributes = {"friendly_name": "Heimspeicher Wirkungsgrad unter Vorjahr"}
    attributes |= EFFICIENCY
    state = {"name": attributes["friendly_name"], "attributes": attributes}
    values: dict[str, Any] = {
        "trigger": {
            "id": "problem" if to == "on" else "fine",
            "entity_id": entity,
            "to_state": {**state, "state": to},
            "from_state": None
            if before is None
            else {"state": before, "last_changed": CLOCK - off_for},
        }
    }
    for key, value in config["variables"].items():
        if isinstance(value, str):
            value = env.from_string(value).render(values).strip()
            value = {"True": True, "False": False}.get(value, value)
        values[key] = value
    return values


def test_device_name_in_the_title_in_both_languages() -> None:
    day = timedelta(days=2)
    de = _variables(entity=SENSOR, to="on", before="off", off_for=day)
    assert de["title"] == "Speicherwacht · Heimspeicher: auffällig"
    assert de["message"] == (
        "Heimspeicher Wirkungsgrad unter Vorjahr: letzte 30 Tage 88,4 % statt "
        "92,0 % im Vorjahr (3,6 Punkte weniger)"
    )
    assert de["fine_title"] == "Speicherwacht · Heimspeicher: wieder in Ordnung"
    en = _variables(entity=SENSOR, to="on", before="off", off_for=day, language="en")
    assert en["title"] == "Speicherwacht · Heimspeicher: conspicuous"
    assert en["message"] == (
        "Heimspeicher Wirkungsgrad unter Vorjahr: last 30 days 88.4 % instead of "
        "92.0 % last year (3.6 points less)"
    )
    assert en["fine_title"] == "Speicherwacht · Heimspeicher: fine again"


def test_without_device_the_title_names_speicherwacht() -> None:
    values = _variables(
        entity="binary_sensor.other", to="on", before="off", off_for=timedelta(0)
    )
    assert values["title"] == "Speicherwacht: auffällig"
    assert values["fine_title"] == "Speicherwacht: wieder in Ordnung"


def test_phone_action_from_the_device() -> None:
    day = timedelta(days=2)
    values = _variables(entity=SENSOR, to="on", before="off", off_for=day)
    assert values["phone_action"] == ""
    values = _variables(
        entity=SENSOR, to="on", before="off", off_for=day, notify_device="phone1"
    )
    assert values["phone_action"] == "notify.mobile_app_pixel_von_max"
    # A device that is gone sends nothing instead of failing.
    gone = _variables(
        entity=SENSOR, to="on", before="off", off_for=day, notify_device="gone"
    )
    assert gone["phone_action"] == ""


@pytest.mark.parametrize(
    ("before", "off_for", "sent"),
    [
        ("off", timedelta(days=1), True),
        ("off", timedelta(hours=23), False),
        ("unknown", timedelta(days=2), False),
        (None, timedelta(days=2), False),
    ],
)
def test_phone_rule_unchanged(
    before: str | None, off_for: timedelta, sent: bool
) -> None:
    values = _variables(entity=SENSOR, to="on", before=before, off_for=off_for)
    assert values["to_phone"] is sent
