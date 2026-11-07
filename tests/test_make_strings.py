"""tools/make_strings.py must reproduce the translation files.

The texts live in the generator; a text changed only in a JSON file would be
lost on the next run. Change the generator, then run it (Wärmewacht found
such a gap on 2026-11-07).
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
FILES = ("strings.json", "icons.json", "translations/en.json", "translations/de.json")


def test_generator_matches_files(tmp_path: Path) -> None:
    out = tmp_path / "custom_components" / "speicherwacht"
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "make_strings.py"), str(tmp_path)],
        check=True,
        capture_output=True,
    )
    component = ROOT / "custom_components" / "speicherwacht"
    for name in FILES:
        generated = (out / name).read_text(encoding="utf-8")
        assert generated == (component / name).read_text(encoding="utf-8"), name
