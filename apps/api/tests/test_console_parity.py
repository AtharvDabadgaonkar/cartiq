"""The console IA is declared twice (Python + TypeScript); keep them identical.

The storefront deep-links into the Streamlit console by section key, so a drift
here produces dead links rather than a visible error.
"""

import re
from pathlib import Path

from cartiq_console.sections import SECTIONS, SECTIONS_BY_KEY

REPO_ROOT = Path(__file__).resolve().parents[3]
SECTIONS_TS = REPO_ROOT / "apps" / "web" / "app" / "console" / "sections.ts"


def _ts_section_keys() -> list[str]:
    source = SECTIONS_TS.read_text()
    body = re.search(r"CONSOLE_SECTIONS = \{(.*?)\n\} as const", source, re.DOTALL)
    assert body, "CONSOLE_SECTIONS not found"
    return re.findall(r"^  '?([a-z-]+)'?: \{", body.group(1), re.MULTILINE)


def test_every_typescript_section_exists_in_the_console():
    # Overview is the console's landing page and has no storefront card.
    python_keys = {s.key.replace("_", "-") for s in SECTIONS}
    for key in _ts_section_keys():
        assert key in python_keys, f"{key} is linked from the storefront but has no console page"


def test_phases_agree():
    source = SECTIONS_TS.read_text()
    ts_phases = dict(
        zip(
            _ts_section_keys(),
            [int(p) for p in re.findall(r"^    phase: (\d+),", source, re.MULTILINE)],
            strict=True,
        )
    )
    for key, phase in ts_phases.items():
        section = SECTIONS_BY_KEY[key.replace("-", "_")]
        assert section.phase == phase, f"{key}: console says {section.phase}, web says {phase}"


def test_section_keys_are_unique_and_url_safe():
    keys = [s.key for s in SECTIONS]
    assert len(set(keys)) == len(keys)
    for key in keys:
        assert re.fullmatch(r"[a-z][a-z_]*", key), key


def test_overview_is_the_default_landing_section():
    assert SECTIONS[0].key == "overview"
