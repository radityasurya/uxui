"""Every script invocation in the shipped skill markdown resolves from the skill directory.

Regression test for #474. The skills ship under .claude/skills/<skill>/ and land in
layouts where
neither the project root nor ~/.claude/skills/ is a valid anchor: the plugin cache, a
project's .claude/skills/, ~/.claude/skills/ (--global), or a manual copy. The one anchor
that exists in all of them is the skill's own directory, so documented commands use
`scripts/<file>` for the skill's own scripts and `../<skill>/scripts/<file>` for a
sibling skill (the skills are always installed side by side).

This test extracts every `python|python3|node|bash <path>` invocation from every
markdown file under the skills tree and asserts that the path is skill-relative and names a
file that ships. The core skill's `${CLAUDE_PLUGIN_ROOT}/.claude/skills/...` form is
resolved against the repository root, which is what that variable denotes under a
plugin install - and accepted only in that file, because the sub-skills must stay
portable across install layouts.
"""

import re
import unittest
from pathlib import Path

REPO = next(
    parent for parent in Path(__file__).resolve().parents
    if (parent / "scripts" / "generate-catalog-summary.py").is_file()
)
SKILL_TREES = (".claude/skills",)
# The only file that may use the plugin-root form: hand-authored for the plugin install.
# (Built from segments: this constant is also scanned by path-contract greps.)
PLUGIN_ONLY_FILE = Path(".claude") / "skills" / "search" / "SKILL.md"
# Retired paid-API generators (uxui issue #1): the scripts are deleted, but
# design/references/*.md still documents them until issue #7 rewrites or
# retires those files. Invocations of these paths keep the path-anchor
# checks; only the file-existence check is waived. Drop entries as the
# replacement Generators land.
RETIRED_SCRIPTS: set[Path] = set()
INVOCATION = re.compile(r'(?<![\w/.-])(?:python3?|node|bash)\s+"?([^\s"`\']+\.(?:py|cjs|js|mjs|sh))')
PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}/"


def shipped_invocations():
    for tree in SKILL_TREES:
        for skill_dir in sorted((REPO / tree).iterdir()):
            if not skill_dir.is_dir():
                continue
            for md in sorted(skill_dir.rglob("*.md")):
                for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
                    for match in INVOCATION.finditer(line):
                        yield skill_dir, md, lineno, match.group(1)


def resolve(skill_dir, md, path):
    """Return (target, None) for a skill-relative path, or (None, reason)."""
    if path.startswith(PLUGIN_ROOT):
        if md.relative_to(REPO) != PLUGIN_ONLY_FILE:
            return None, "the ${CLAUDE_PLUGIN_ROOT} form is only valid in the plugin-only core SKILL.md"
        return REPO / path[len(PLUGIN_ROOT):], None
    if path.startswith("scripts/"):
        return skill_dir / path, None
    if path.startswith("../"):
        parts = path.split("/")
        if len(parts) > 3 and parts[2] == "scripts" and (skill_dir.parent / parts[1]).is_dir():
            return skill_dir.parent / parts[1] / "/".join(parts[2:]), None
        return None, "a sibling invocation must be ../<skill>/scripts/<file> and the sibling must ship"
    return None, "not skill-relative (expected scripts/<file> or ../<skill>/scripts/<file>)"


class SkillScriptPathsTest(unittest.TestCase):
    def test_every_shipped_markdown_invocation_resolves_from_the_skill_directory(self):
        problems, seen = [], 0
        for skill_dir, md, lineno, path in shipped_invocations():
            seen += 1
            target, reason = resolve(skill_dir, md, path)
            if reason is None and Path(path) in RETIRED_SCRIPTS:
                continue
            if reason is None and not target.is_file():
                reason = f"no such file: {target}"
            if reason:
                problems.append(f"{md.relative_to(REPO)}:{lineno}: {path} -- {reason}")
        # Guard against a silently broken extractor: the tree carries well over
        # fifty documented invocations.
        self.assertGreater(seen, 50, f"extractor found only {seen} invocations")
        self.assertEqual(problems, [], "\n" + "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
