from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".agents" / "skills" / "finding-trending-keywords"
SKILL_FILE = SKILL_DIR / "SKILL.md"
REFERENCE_FILE = SKILL_DIR / "references" / "seo-opportunity-filter.md"


def test_finding_trending_keywords_skill_is_codex_discoverable():
    assert SKILL_FILE.is_file(), (
        "repo-level Codex skill must live under "
        ".agents/skills/<name>/SKILL.md"
    )

    text = SKILL_FILE.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"

    frontmatter = match.group(1)
    assert re.search(
        r"^name:\s*finding-trending-keywords\s*$",
        frontmatter,
        re.MULTILINE,
    )
    assert re.search(r"^description:\s*.+$", frontmatter, re.MULTILINE)
    assert "Use when" in frontmatter


def test_finding_trending_keywords_skill_keeps_methodology_in_reference():
    assert REFERENCE_FILE.is_file(), (
        "detailed SEO opportunity methodology belongs in references/"
    )
