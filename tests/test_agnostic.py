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

# Flag a forbidden word unless it is glued to ASCII alphanumerics on BOTH sides — so snake_case and
# punctuation-adjacent identifiers ARE caught (``run_mosaic_demo``, ``eis_utils``, ``softjax_ops``)
# while genuine longer words are NOT (``heist``, ``mosaicism``). `\b` was the old bug: it counts `_`
# as a word char, so every ``*_mosaic`` / ``mosaic_*`` identifier slipped through. Longer alternatives
# first so a match reports the whole token (``mosaic_diff``, not just ``mosaic``). Case-insensitive.
# (Known residual: a word glued INSIDE camelCase — ``loadEis`` — still slips; closing that without
# false-flagging ``eis`` in ``heist`` needs case-boundary splitting, deferred.)
_BOUND = r"(?<![A-Za-z0-9])(?:{})(?![A-Za-z0-9])"
_CODE_FORBIDDEN = re.compile(
    _BOUND.format("blastema|bool_nca|mosaic_diff|mosaic|softjax|eis"), re.I
)
# The README may name the public reference consumer (attribution) — nothing else.
_DOC_FORBIDDEN = re.compile(_BOUND.format("bool_nca|mosaic_diff|mosaic|softjax|eis"), re.I)

_CODE_DIRS = ("src", "web/src", "templates", "tests", ".github")
_CODE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".css",
    ".sh",
    ".html",
    ".json",
    ".toml",
    ".yml",
    ".yaml",
}
# Root-level manifests/configs a consumer word could hide in, outside the scanned dirs (a leaked name
# in a package description or a CI job would otherwise be invisible).
_ROOT_FILES = ("pyproject.toml", "package.json", "tsconfig.json")


def _code_files():
    for d in _CODE_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for f in sorted(base.rglob("*")):
            if f.is_file() and f.suffix in _CODE_SUFFIXES and "node_modules" not in f.parts:
                yield f
    for name in _ROOT_FILES:
        f = ROOT / name
        if f.is_file():
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
