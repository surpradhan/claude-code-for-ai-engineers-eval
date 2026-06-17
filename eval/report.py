"""Render results.json as a Markdown report.

Usage:
    python -m eval.report results/<timestamp>/results.json > report.md
"""

import json
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
BEHAVIORS_DIR = REPO_ROOT / "scenarios" / "behaviors"
LABELS_DIR = REPO_ROOT / "eval" / "labels"


def _load_human_calibration(skill: str) -> "dict | None":
    labels_file = LABELS_DIR / f"{skill}.json"
    if not labels_file.exists():
        return None
    try:
        return json.loads(labels_file.read_text()).get("calibration")
    except (json.JSONDecodeError, KeyError):
        return None


def _load_polarity_index() -> dict:
    """Build {skill: {scenario_name: {assertion_text: polarity}}} from scenario YAMLs.

    Used to surface (must_do / must_not_do) tags next to each assertion in the
    rendered report — important because PASS on a must_not_do means "Claude
    correctly did NOT do this", which is easy to misread without the label.
    """
    index: dict = {}
    if not BEHAVIORS_DIR.exists():
        return index
    for yaml_file in BEHAVIORS_DIR.glob("*.yaml"):
        skill_name = yaml_file.stem.replace("_", "-")
        try:
            config = yaml.safe_load(yaml_file.read_text()) or {}
        except yaml.YAMLError:
            continue
        skill_index: dict = {}
        for scen in config.get("scenarios", []):
            assertion_map: dict = {}
            for entry in scen.get("must_do") or []:
                key = entry.get("text") or entry.get("regex")
                if key:
                    assertion_map[key] = "must_do"
            for entry in scen.get("must_not_do") or []:
                key = entry.get("text") or entry.get("regex")
                if key:
                    assertion_map[key] = "must_not_do"
            skill_index[scen["name"]] = assertion_map
        index[skill_name] = skill_index
    return index


def _polarity_for(assertion_text: str, polarity_map: dict) -> str:
    """Resolve an assertion text back to its YAML polarity (must_do / must_not_do).

    Handles both LLM-judged text assertions (direct match) and regex assertions
    (scorer wraps the pattern as `must match: <pattern>` or `must not match: ...`).
    """
    if assertion_text in polarity_map:
        return polarity_map[assertion_text]
    for prefix, polarity in (("must match: ", "must_do"), ("must not match: ", "must_not_do")):
        if assertion_text.startswith(prefix):
            return polarity
    return ""


def render(results_json: Path) -> str:
    data = json.loads(results_json.read_text())
    source = data.get("source", "unknown")
    try:
        display_path = results_json.relative_to(REPO_ROOT)
    except ValueError:
        display_path = results_json
    out = ["# Skill eval report", f"_Source: `{display_path}` (pack: **{source}**)_", ""]
    polarity_idx = _load_polarity_index()

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
            human_cal = _load_human_calibration(skill)
            if human_cal is not None:
                h_agreement = human_cal.get("haiku_vs_human_agreement")
                n = human_cal.get("haiku_n_compared", human_cal.get("n_labeled", 0))
                if h_agreement is not None:
                    out.append(f"_Haiku vs human agreement: {h_agreement:.3f} (N={n} labels)_")
                    out.append("")
            skill_polarities = polarity_idx.get(skill, {})
            for s in payload["scenarios"]:
                out.append(f"- **{s['name']}** — {s['score']}")
                scenario_polarities = skill_polarities.get(s["name"], {})
                for a in s["assertions"]:
                    mark = "PASS" if a["passed"] else "FAIL"
                    polarity = _polarity_for(a["assertion"], scenario_polarities)
                    polarity_tag = f" *[{polarity}]*" if polarity else ""
                    out.append(
                        f"  - [{mark}]{polarity_tag} ({a['judge_model']}) {a['assertion']}"
                    )
                    if a.get("reason"):
                        out.append(f"    - _{a['reason']}_")
            out.append("")

    return "\n".join(out)


if __name__ == "__main__":
    print(render(Path(sys.argv[1])))
