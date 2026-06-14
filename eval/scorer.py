"""Hybrid scorer: deterministic regex checks + Claude Code CLI judge.

The judge shells out to `claude -p` so it uses your Claude Max plan
(no separate Anthropic API key required). Tradeoff: ~5x slower than the
direct Anthropic API; ~15 min instead of ~5 min for a full Layer 2 run.

Verified against Claude Code CLI v2.1.175 (2026-06-12):
  - `--model haiku` and `--model sonnet` are accepted as aliases.
  - Judge calls use --disable-slash-commands to prevent global skills from
    loading and influencing the rubric evaluation.
  - --output-format json (flat, no --verbose) is sufficient for judge calls
    since we only need the "result" text, not skill invocation events.
"""

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


JudgeModel = Literal["haiku", "sonnet"]

# Model identifiers passed to `claude -p --model <X>`. Aliases first;
# fall back to full IDs if your CLI requires them.
CLI_MODEL_FLAGS = {
    "haiku": "haiku",
    "sonnet": "sonnet",
}


@dataclass
class AssertionResult:
    assertion: str
    passed: bool
    reason: str = ""
    judge_model: str = "deterministic"


def check_regex(response_text: str, pattern: str, must_match: bool = True) -> AssertionResult:
    """Deterministic check — does the response (not) match a regex?"""
    found = bool(re.search(pattern, response_text, re.IGNORECASE | re.DOTALL))
    passed = found == must_match
    label = "must match" if must_match else "must not match"
    return AssertionResult(
        assertion=f"{label}: {pattern}",
        passed=passed,
        reason=f"Pattern {'found' if found else 'not found'}",
    )


def _run_claude_judge(prompt: str, model: JudgeModel, timeout: int = 60) -> str:
    """Shell out to Claude Code CLI for a judge call.

    Runs from a clean temp directory with NO `.claude/skills/` so the judge
    response isn't itself modulated by any loaded skills. The judge needs to
    behave like a plain Claude, not like a skill-pack-loaded Claude.
    """
    workdir = Path(tempfile.mkdtemp(prefix="claude-judge-"))
    args = [
        "claude", "-p", prompt,
        "--model", CLI_MODEL_FLAGS[model],
        "--output-format", "json",
        "--disable-slash-commands",
    ]
    result = subprocess.run(
        args,
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude CLI judge call failed (exit {result.returncode}): "
            f"{result.stderr[:500]}"
        )

    try:
        payload = json.loads(result.stdout)
        text = payload.get("result") or payload.get("response") or result.stdout
    except json.JSONDecodeError:
        text = result.stdout

    if "session limit" in text.lower() or "rate limit" in text.lower():
        raise RuntimeError(f"claude CLI judge call hit session/rate limit: {text[:120]}")

    return text


def judge(
    response_text: str,
    assertion: str,
    polarity: Literal["must_do", "must_not_do"],
    model: JudgeModel = "haiku",
    user_prompt: str | None = None,
) -> AssertionResult:
    """LLM-judge a fuzzy behavioral assertion against the response."""
    prompt_section = (
        f'USER\'S PROMPT:\n"""\n{user_prompt}\n"""\n\n'
        if user_prompt is not None
        else ""
    )
    rubric = f"""You are evaluating whether a Claude response satisfies a behavioral assertion.

ASSERTION ({polarity}): {assertion}

{prompt_section}CLAUDE'S RESPONSE:
\"\"\"
{response_text}
\"\"\"

For a "must_do" assertion, the response PASSES if it clearly demonstrates the behavior.
For a "must_not_do" assertion, the response PASSES if it does NOT demonstrate the behavior.

Be strict. If the response is ambiguous or only partially demonstrates the behavior, FAIL it.

Respond with exactly one line:
PASS — <one sentence justification>
or
FAIL — <one sentence justification>
"""

    text = _run_claude_judge(rubric, model).strip()
    passed = text.upper().startswith("PASS")
    reason = text.split("—", 1)[-1].strip() if "—" in text else text

    return AssertionResult(
        assertion=assertion,
        passed=passed,
        reason=reason,
        judge_model=model,
    )


def judge_calibrate(
    response_text: str,
    assertion: str,
    polarity: Literal["must_do", "must_not_do"],
    user_prompt: str | None = None,
) -> tuple[AssertionResult, AssertionResult, bool]:
    """Run BOTH Haiku and Sonnet through the CLI. Returns (haiku, sonnet, agreed).

    Used during the 2-week calibration window. The runner aggregates the
    agreement rate across all scenarios. Once it hits >=90%, switch to
    `--judge haiku` and drop Sonnet from the loop.
    """
    haiku_result = judge(response_text, assertion, polarity, model="haiku", user_prompt=user_prompt)
    sonnet_result = judge(response_text, assertion, polarity, model="sonnet", user_prompt=user_prompt)
    agreed = haiku_result.passed == sonnet_result.passed
    return haiku_result, sonnet_result, agreed
