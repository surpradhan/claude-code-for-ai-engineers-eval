"""Render results.json as a Markdown report.

Usage:
    python -m eval.report results/<timestamp>/results.json > report.md
"""

import json
import sys
from pathlib import Path


def render(results_json: Path) -> str:
    data = json.loads(results_json.read_text())
    source = data.get("source", "unknown")
    out = ["# Skill eval report", f"_Source: `{results_json}` (pack: **{source}**)_", ""]

    if "layer_1" in data:
        out += [
            "## Layer 1 — Trigger eval",
            "",
            "| Skill | Precision | Recall | TP | FP | TN | FN |",
            "|---|---|---|---|---|---|---|",
        ]
        for skill, r in data["layer_1"].items():
            if r.get("skipped"):
                out.append(f"| `{skill}` | — | — | — | — | — | _skipped: {r.get('reason', '')}_ |")
                continue
            out.append(
                f"| `{skill}` | {r['precision']} | {r['recall']} | "
                f"{r['tp']} | {r['fp']} | {r['tn']} | {r['fn']} |"
            )
        out.append("")

    if "layer_2" in data:
        out += ["## Layer 2 — Behavior assertion", ""]
        for skill, payload in data["layer_2"].items():
            out.append(f"### `{skill}`")
            if payload.get("skipped"):
                out.append(f"_Skipped: {payload.get('reason', '')}_")
                out.append("")
                continue
            agreement = payload.get("calibration_agreement_rate")
            if agreement is not None:
                marker = "OK" if agreement >= 0.90 else "BELOW"
                out.append(f"_Haiku/Sonnet agreement rate: **{agreement}** ({marker} 0.90 threshold)_")
                out.append("")
            for s in payload["scenarios"]:
                out.append(f"- **{s['name']}** — {s['score']}")
                for a in s["assertions"]:
                    mark = "PASS" if a["passed"] else "FAIL"
                    out.append(f"  - [{mark}] ({a['judge_model']}) {a['assertion']}")
                    if a.get("reason"):
                        out.append(f"    - _{a['reason']}_")
            out.append("")

    return "\n".join(out)


if __name__ == "__main__":
    print(render(Path(sys.argv[1])))
