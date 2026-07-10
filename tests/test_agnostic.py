"""The substrate-agnosticism gate — a red test, not a convention.

The kit is public, generic scaffolding shared by private research projects. Nothing
consumer-specific may leak in: no project vocabulary in code or templates, and no research-project
terms in the README beyond the attribution to the (public) reference consumer. If adding a feature
seems to need one of these words, the feature belongs in the consumer, not the kit.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Word-bounded + case-insensitive: "eis" must not flag "heist", "mosaic" not "mosaicism"… but any
# standalone use of a consumer project's vocabulary is a failure.
_CODE_FORBIDDEN = re.compile(r"\b(blastema|bool_nca|mosaic|mosaic_diff|softjax|eis)\b", re.I)
# The README may name the public reference consumer (attribution) — nothing else.
_DOC_FORBIDDEN = re.compile(r"\b(bool_nca|mosaic|mosaic_diff|softjax|eis)\b", re.I)

_CODE_DIRS = ("src", "web/src", "templates", "tests")
_CODE_SUFFIXES = {".py", ".ts", ".css", ".sh", ".html", ".json"}


def _code_files():
    for d in _CODE_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for f in sorted(base.rglob("*")):
            if f.is_file() and f.suffix in _CODE_SUFFIXES and "node_modules" not in f.parts:
                yield f


def test_code_is_substrate_agnostic():
    this_file = Path(__file__).resolve()
    bad: list[str] = []
    for f in _code_files():
        if f.resolve() == this_file:  # the gate itself must spell the forbidden words
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            m = _CODE_FORBIDDEN.search(line)
            if m:
                bad.append(f"{f.relative_to(ROOT)}:{i}: {m.group(0)!r}")
    assert not bad, "consumer vocabulary leaked into kit sources:\n" + "\n".join(bad)


def test_docs_are_substrate_agnostic():
    bad: list[str] = []
    for f in sorted(ROOT.glob("*.md")):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            m = _DOC_FORBIDDEN.search(line)
            if m:
                bad.append(f"{f.name}:{i}: {m.group(0)!r}")
    assert not bad, "research-project vocabulary leaked into kit docs:\n" + "\n".join(bad)


def test_no_absolute_home_paths():
    """Kit files must work on any machine — no baked-in workstation paths."""
    pat = re.compile(r"/home/\w+|(?<![\w./])~/")
    bad: list[str] = []
    for f in [*_code_files(), *ROOT.glob("*.md")]:
        if f.resolve() == Path(__file__).resolve():
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(line):
                bad.append(f"{f.relative_to(ROOT)}:{i}")
    assert not bad, "absolute home paths in kit files:\n" + "\n".join(bad)
