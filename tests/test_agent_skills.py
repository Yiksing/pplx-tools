"""Repository-local Agent Skill contract tests.
仓库本地 Agent Skill 契约测试。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPOSITORY_ROOT / ".agents" / "skills"
AGENT_POLICY = REPOSITORY_ROOT / "AGENTS.md"
PACKAGE_POLICY = REPOSITORY_ROOT / "pplx_export" / "AGENTS.md"
CORE_POLICY = REPOSITORY_ROOT / "pplx_export" / "core" / "AGENTS.md"
EXPECTED_SKILLS = {
    "audit-docs",
    "design-pplx-change",
    "engineering-principles",
    "external-review-loop",
    "investigation-methodology",
    "maintain-docs-i18n",
    "maintain-mkdocs",
    "manage-test-fixtures",
    "privacy-release-gate",
    "quality-gates",
    "review-pplx-tools",
    "test-pplx-tools",
    "update-docs",
}
FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---(?:\n|\Z)", re.DOTALL)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\((?P<target>[^)]+)\)")
POSSIBLE_SECRET_RE = re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b")
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
MAX_DESCRIPTION_WORDS = 45
MAX_TOTAL_DESCRIPTION_WORDS = 450


def _skill_directories() -> list[Path]:
    return sorted(
        path
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    )


def _frontmatter(path: Path) -> dict[str, str]:
    content = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(content)
    assert match is not None, f"{path} must start with YAML frontmatter"

    loaded = yaml.safe_load(match.group("body"))
    assert isinstance(loaded, dict), f"{path} frontmatter must be a YAML mapping"
    assert all(isinstance(key, str) for key in loaded)
    assert all(isinstance(value, str) for value in loaded.values())
    return loaded


def _body(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(content)
    assert match is not None
    return content[match.end() :]


def _local_markdown_targets(path: Path) -> list[Path]:
    content = path.read_text(encoding="utf-8")
    targets: list[Path] = []
    for match in MARKDOWN_LINK_RE.finditer(content):
        target = match.group("target").split("#", 1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:", "/")):
            continue
        targets.append((path.parent / target).resolve())
    return targets


def test_expected_repository_skills_exist() -> None:
    assert {path.name for path in _skill_directories()} == EXPECTED_SKILLS


@pytest.mark.parametrize("skill_dir", _skill_directories(), ids=lambda path: path.name)
def test_skill_frontmatter_and_trigger_contract(skill_dir: Path) -> None:
    skill_path = skill_dir / "SKILL.md"
    metadata = _frontmatter(skill_path)
    content = skill_path.read_text(encoding="utf-8")

    assert set(metadata) == {"name", "description"}
    assert metadata["name"] == skill_dir.name
    assert SKILL_NAME_RE.fullmatch(metadata["name"])
    assert "Use when" in metadata["description"]
    assert "Do not use" in metadata["description"]
    assert len(WORD_RE.findall(metadata["description"])) <= MAX_DESCRIPTION_WORDS
    assert "[TODO" not in content
    assert len(content.splitlines()) <= 160


def test_skill_description_catalog_has_a_local_token_budget() -> None:
    total = sum(
        len(WORD_RE.findall(_frontmatter(skill_dir / "SKILL.md")["description"]))
        for skill_dir in _skill_directories()
    )
    assert total <= MAX_TOTAL_DESCRIPTION_WORDS


def test_skill_references_are_direct_conditional_and_contained() -> None:
    violations: list[str] = []
    for skill_dir in _skill_directories():
        skill_path = skill_dir / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        for target in _local_markdown_targets(skill_path):
            try:
                target.relative_to(skill_dir.resolve())
            except ValueError:
                violations.append(f"{skill_path}: reference escapes its skill: {target}")
                continue
            if target.parent != (skill_dir / "references").resolve():
                violations.append(f"{skill_path}: reference is not one level deep: {target}")
            if not target.exists():
                violations.append(f"{skill_path}: reference does not exist: {target}")
            link_offset = content.find(str(target.name))
            context = content[max(0, link_offset - 100) : link_offset + 180].lower()
            if "when" not in context:
                violations.append(f"{skill_path}: reference lacks a nearby when-condition")

        for reference_path in sorted((skill_dir / "references").glob("*.md")):
            if _local_markdown_targets(reference_path):
                violations.append(f"{reference_path}: nested local references are not allowed")

    assert not violations, "\n".join(violations)


def test_repository_agent_policy_enforces_progressive_disclosure() -> None:
    policy = AGENT_POLICY.read_text(encoding="utf-8")
    assert "zero or one primary repository skill" in policy
    assert "Do not enumerate or preload every file" in policy
    assert "sequential phases" in policy
    assert "git rev-parse --show-toplevel" in policy
    assert "workdir" in policy


def test_production_package_agent_policy_declares_archive_boundary() -> None:
    policy = PACKAGE_POLICY.read_text(encoding="utf-8")
    required_terms = {
        "production export",
        "raw_entries.json",
        "raw_blocks.json",
        "offline re-rendering",
        "without network access",
        "real cookies",
        "user configuration",
        "privacy release gate",
    }
    missing = sorted(term for term in required_terms if term not in policy)
    assert not missing, "Missing package policy terms: " + ", ".join(missing)


def test_core_agent_policy_declares_sensitive_credential_boundary() -> None:
    policy = CORE_POLICY.read_text(encoding="utf-8")
    required_terms = {
        "Sensitive core boundary",
        "auth",
        "cookies",
        "HTTP transports",
        "session tokens",
        "CSRF",
        "login emails",
        "0o600",
        "atomic",
        "targeted offline tests",
    }
    missing = sorted(term for term in required_terms if term not in policy)
    assert not missing, "Missing core policy terms: " + ", ".join(missing)


def test_skill_bodies_do_not_cascade_to_other_repository_skills() -> None:
    violations: list[str] = []
    for skill_dir in _skill_directories():
        body = _body(skill_dir / "SKILL.md")
        for other_name in EXPECTED_SKILLS - {skill_dir.name}:
            if re.search(rf"(?<![a-z0-9-]){re.escape(other_name)}(?![a-z0-9-])", body):
                violations.append(f"{skill_dir.name} routes to {other_name}")
    assert not violations, "\n".join(violations)


def test_repository_skills_do_not_contain_possible_api_keys() -> None:
    offenders: list[str] = []
    for path in sorted(SKILLS_ROOT.rglob("*")):
        if not path.is_file():
            continue
        if POSSIBLE_SECRET_RE.search(path.read_bytes()):
            offenders.append(str(path.relative_to(REPOSITORY_ROOT)))
    assert not offenders, "Possible API keys found in skill files: " + ", ".join(offenders)
