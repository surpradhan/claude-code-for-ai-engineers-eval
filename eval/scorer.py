"""Hybrid scorer: deterministic regex checks + LLM-judge (Haiku / Sonnet)."""

import os
import re
from dataclasses import dataclass
from typing import Literal

from anthropic import Anthropic


JudgeModel = Literal["haiku", "sonnet"]
MODEL_IDS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
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


def judge(
    response_text: str,
    assertion: str,
    polarity: Literal["must_do", "must_not_do"],
    model: JudgeModel = "haiku",
) -> AssertionResult:
    """LLM-judge a fuzzy behavioral assertion against the response."""
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    rubric = f"""You are evaluating whether a Claude response satisfies a behavioral assertion.

ASSERTION ({polarity}): {assertion}

CLAUDE'S RESPONSE:
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

    resp = client.messages.create(
        model=MODEL_IDS[model],
        max_tokens=200,
        messages=[{"role": "user", "content": rubric}],
    )

    text = resp.content[0].text.strip()
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
) -> tuple[AssertionResult, AssertionResult, bool]:
    """Run BOTH Haiku and Sonnet. Returns (haiku_result, sonnet_result, agreed).

    Used during the 2-week calibration window. The report aggregates the
    agreement rate across all scenarios. Once it hits >=90%, switch to
    `--judge haiku` and drop Sonnet from the loop.
    """
    haiku_result = judge(response_text, assertion, polarity, model="haiku")
    sonnet_result = judge(response_text, assertion, polarity, model="sonnet")
    agreed = haiku_result.passed == sonnet_result.passed
    return haiku_result, sonnet_result, agreed
