"""Consistency checks for manifest.json, hacs.json, pyproject.toml and translations."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from custom_components.speicherwacht import ISSUES
from custom_components.speicherwacht.config_flow import entities_schema
from custom_components.speicherwacht.const import DOMAIN, VERSION
from custom_components.speicherwacht.model import Boundary
from custom_components.speicherwacht.profiles import TEMPLATES
from custom_components.speicherwacht.sensor import DESCRIPTIONS, WARRANTY

ROOT = Path(__file__).parent.parent
INTEGRATION = ROOT / "custom_components" / DOMAIN


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def manifest() -> dict:
    return load(INTEGRATION / "manifest.json")


def test_versions_match() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert manifest()["version"] == VERSION == pyproject["project"]["version"]


def test_domain_matches_folder() -> None:
    assert manifest()["domain"] == DOMAIN == INTEGRATION.name


def test_manifest_key_order() -> None:
    # hassfest requires domain, name first, then the remaining keys sorted.
    keys = list(manifest())
    assert keys[:2] == ["domain", "name"]
    assert keys[2:] == sorted(keys[2:])


def test_hacs_json() -> None:
    hacs = load(ROOT / "hacs.json")
    assert hacs["name"] == manifest()["name"]
    assert hacs["filename"] == f"{DOMAIN}.zip"
    # Batteries are no German speciality: shown in every country.
    assert "country" not in hacs


def _keys(data: object, prefix: str = "") -> set[str]:
    if isinstance(data, dict):
        return {
            k for key, value in data.items() for k in _keys(value, f"{prefix}{key}.")
        }
    return {prefix.rstrip(".")}


def test_translations_complete() -> None:
    strings = load(INTEGRATION / "strings.json")
    assert load(INTEGRATION / "translations" / "en.json") == strings
    assert _keys(load(INTEGRATION / "translations" / "de.json")) == _keys(strings)


def test_every_sensor_translated_and_has_an_icon() -> None:
    strings = load(INTEGRATION / "strings.json")["entity"]["sensor"]
    icons = load(INTEGRATION / "icons.json")["entity"]["sensor"]
    keys = {d.key for d in [*DESCRIPTIONS, WARRANTY]}
    assert set(strings) == set(icons) == keys


def test_every_problem_sensor_translated_and_has_an_icon() -> None:
    from custom_components.speicherwacht.binary_sensor import CHECKS

    strings = load(INTEGRATION / "strings.json")["entity"]["binary_sensor"]
    icons = load(INTEGRATION / "icons.json")["entity"]["binary_sensor"]
    assert set(strings) == set(icons) == set(CHECKS)


def test_issues_translated() -> None:
    assert set(load(INTEGRATION / "strings.json")["issues"]) == set(ISSUES)


def test_entity_form_translated() -> None:
    step = load(INTEGRATION / "strings.json")["config"]["step"]["entities"]
    fields = {str(key) for key in entities_schema({}).schema}
    assert set(step["data"]) == set(step["data_description"]) == fields


def test_selectors_translated() -> None:
    selector = load(INTEGRATION / "strings.json")["selector"]
    assert set(selector["boundary"]["options"]) == {b.value for b in Boundary}


def test_hint_steps_exist() -> None:
    """A template with a counter hint needs its own first step and text."""
    from custom_components.speicherwacht.config_flow import SpeicherwachtConfigFlow

    steps = load(INTEGRATION / "strings.json")["config"]["step"]
    for template in TEMPLATES.values():
        if template.counter_hint:
            assert f"user_hint_{template.key}" in steps
            assert hasattr(
                SpeicherwachtConfigFlow, f"async_step_user_hint_{template.key}"
            )
        if template.note:
            assert f"entities_note_{template.key}" in steps
            assert hasattr(
                SpeicherwachtConfigFlow, f"async_step_entities_note_{template.key}"
            )
