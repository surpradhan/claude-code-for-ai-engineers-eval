"""Subprocess wrapper around the Claude Code CLI.

VERIFY THESE FLAGS against your installed Claude Code version before relying
on results. The CLI moves fast.

Approach: create a temp workdir with `.claude/skills/` symlinked to the skill
pack, then `cd` into it and run `claude -p "<prompt>" --output-format json`.
Claude Code discovers skills via its standard skill discovery, so the loaded
skills appear in the JSON metadata.
"""

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class HarnessResult:
    prompt: str
    response_text: str
    loaded_skills: list[str] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    exit_code: int = 0
    raw_stdout: str = ""
    raw_stderr: str = ""


def run_claude(
    prompt: str,
    skill_pack_path: Path,
    workdir: Optional[Path] = None,
    timeout: int = 180,
) -> HarnessResult:
    """Invoke Claude Code with the given prompt and skill pack.

    Args:
        prompt: The user prompt to send.
        skill_pack_path: Path to the directory containing SKILL.md files
            (typically `<repo>/skill-pack/skills/`).
        workdir: Optional working directory. If None, creates a temp dir.
        timeout: Subprocess timeout in seconds.

    Returns:
        HarnessResult with response text, loaded skills, and tool calls.
    """
    cleanup = False
    if workdir is None:
        workdir = Path(tempfile.mkdtemp(prefix="claude-eval-"))
        cleanup = True

    skills_link = workdir / ".claude" / "skills"
    skills_link.parent.mkdir(parents=True, exist_ok=True)
    if not skills_link.exists():
        skills_link.symlink_to(skill_pack_path.resolve())

    args = ["claude", "-p", prompt, "--output-format", "json"]

    try:
        result = subprocess.run(
            args,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        return HarnessResult(
            prompt=prompt,
            response_text="",
            exit_code=-1,
            raw_stderr=f"TIMEOUT after {timeout}s: {e}",
        )

    response_text = ""
    loaded_skills: list[str] = []
    tool_calls: list[dict] = []

    try:
        payload = json.loads(result.stdout)
        response_text = payload.get("result") or payload.get("response") or ""
        # Exact path to "which skills loaded" depends on Claude Code version.
        # Check `payload` shape on first run and adapt.
        loaded_skills = payload.get("loaded_skills") or _extract_skills_from_payload(payload)
        tool_calls = payload.get("tool_calls") or payload.get("tools_used") or []
    except (json.JSONDecodeError, AttributeError):
        response_text = result.stdout

    return HarnessResult(
        prompt=prompt,
        response_text=response_text,
        loaded_skills=loaded_skills,
        tool_calls=tool_calls,
        exit_code=result.returncode,
        raw_stdout=result.stdout,
        raw_stderr=result.stderr,
    )


def _extract_skills_from_payload(payload: dict) -> list[str]:
    """Best-effort fallback: walk the payload looking for skill invocations.

    Claude Code's JSON output structure for "which skills loaded" may vary;
    look for tool calls named `Skill` or messages mentioning loaded skills.
    """
    skills: set[str] = set()
    for item in payload.get("messages", []):
        for c in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") == "Skill":
                skill_name = (c.get("input") or {}).get("skill")
                if skill_name:
                    skills.add(skill_name)
    return sorted(skills)
