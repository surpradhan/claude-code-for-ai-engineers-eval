"""Subprocess wrapper around the Claude Code CLI.

Verified against Claude Code CLI v2.1.175 (2026-06-12).

Invocation:
    claude -p "<prompt>"
        --output-format stream-json --verbose
            → NDJSON stream; each line is one event.
            → assistant events expose Skill tool_use entries.
            → result event holds the final response text.
        --permission-mode bypassPermissions
            → scaffolding skills can write files without interactive approval.
        --setting-sources project
            → only load the workdir's .claude/skills/; skip ~/.claude/skills/
              so global skill packs don't compete with the pack under test.

Skill detection: look for events with type=="assistant" whose
message.content[] contains a tool_use entry with name=="Skill".
The input.skill field names the skill.

Two execution modes (controlled by stop_after_skill_event):
  - False (default, Layer 2): stream until the result event arrives or timeout.
    response_text is populated from the result event.
  - True (Layer 1): kill the process as soon as the first assistant event
    arrives (Skill invocations appear in the first assistant turn, within
    ~3–5 s). This avoids waiting 10+ minutes for scaffolding to complete
    when we only care about trigger detection.
"""

import json
import subprocess
import tempfile
import threading
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
    stop_after_skill_event: bool = False,
) -> HarnessResult:
    """Invoke Claude Code with the given prompt and skill pack.

    Args:
        prompt: The user prompt to send.
        skill_pack_path: Path to the directory containing SKILL.md files
            (typically `<repo>/skill-pack/skills/`).
        workdir: Optional working directory. If None, creates a temp dir.
        timeout: Subprocess timeout in seconds. Use ~60 for Layer 1
            (stop_after_skill_event=True) and ~600 for Layer 2.
        stop_after_skill_event: If True, kill the process after the first
            assistant event (Skill invocations appear here). Avoids waiting
            for scaffolding to complete during Layer 1 trigger evals.

    Returns:
        HarnessResult with response text, loaded skills, and tool calls.
    """
    if workdir is None:
        workdir = Path(tempfile.mkdtemp(prefix="claude-eval-"))

    skills_link = workdir / ".claude" / "skills"
    skills_link.parent.mkdir(parents=True, exist_ok=True)
    if not skills_link.exists():
        skills_link.symlink_to(skill_pack_path.resolve())

    args = [
        "claude", "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--permission-mode", "bypassPermissions",
        "--setting-sources", "project",
    ]

    loaded_skills: list[str] = []
    tool_calls: list[dict] = []
    response_text = ""
    lines_collected: list[str] = []

    try:
        proc = subprocess.Popen(
            args,
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        return HarnessResult(
            prompt=prompt,
            response_text="",
            exit_code=-1,
            raw_stderr="claude CLI not found in PATH",
        )

    # Read stdout in a background thread so we can enforce a wall-clock timeout
    # without relying on subprocess.run(timeout=) (which doesn't let us inspect
    # partial output before raising).
    stdout_lines: list[str] = []
    stderr_buf: list[str] = []

    def _read_stderr():
        for line in proc.stderr:
            stderr_buf.append(line)

    stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
    stderr_thread.start()

    import time
    deadline = time.monotonic() + timeout

    for line in proc.stdout:
        lines_collected.append(line)
        if time.monotonic() > deadline:
            proc.kill()
            break

        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        t = event.get("type")

        if t == "assistant":
            msg = event.get("message", {})
            content = msg.get("content", []) if isinstance(msg, dict) else []
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_use":
                    name = c.get("name", "")
                    inp = c.get("input") or {}
                    tool_calls.append({"name": name, "input": inp})
                    if name == "Skill":
                        skill_name = inp.get("skill")
                        if skill_name and skill_name not in loaded_skills:
                            loaded_skills.append(skill_name)
                        # For Layer 1: we have what we need; kill to avoid
                        # waiting 10+ min for scaffolding to complete.
                        if stop_after_skill_event:
                            proc.kill()

        elif t == "result":
            response_text = event.get("result") or ""
            break  # natural completion

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    stderr_thread.join(timeout=2)

    exit_code = proc.returncode if proc.returncode is not None else -1
    # A killed process returns -9 (SIGKILL); treat it as success for eval purposes
    # since we may have intentionally killed it after skill detection.
    if exit_code < 0 and (loaded_skills or stop_after_skill_event):
        exit_code = 0

    return HarnessResult(
        prompt=prompt,
        response_text=response_text,
        loaded_skills=loaded_skills,
        tool_calls=tool_calls,
        exit_code=exit_code,
        raw_stdout="".join(lines_collected),
        raw_stderr="".join(stderr_buf),
    )
