"""CLI entry point. Runs Layer 1 (trigger) and Layer 2 (behavior) evals."""

import json
import time
from dataclasses import asdict
from pathlib import Path

import click
import yaml
from rich.console import Console

from eval.harness import run_claude
from eval.scorer import check_regex, judge, judge_calibrate

console = Console()

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = REPO_ROOT / "scenarios"
RESULTS_DIR = REPO_ROOT / "results"

SKILL_PACK_PATHS = {
    "preview": REPO_ROOT / "skill-pack" / "skills",
    "full": REPO_ROOT / "skill-pack-full" / "skills",
}

# Which skills live in which source. Scenarios for "full"-only skills are
# committed to the public eval repo (they're just behavior contracts), but
# running them against the preview source will report "skill not present".
SKILL_SOURCES = {
    "rag-eval-harness": "preview",
    "agent-trace-debug": "preview",
    "paper-reproduce": "full",
    "mcp-server-bootstrap": "full",
    "eval-report-writer": "full",
    "benchmark-scaffold": "full",
}


@click.command()
@click.option("--layer", type=click.Choice(["1", "2"]), required=True, multiple=True,
              help="Which layers to run. Pass multiple times for both: --layer 1 --layer 2")
@click.option("--skill", default=None, help="Filter to one skill (e.g. rag-eval-harness)")
@click.option("--source", "source", type=click.Choice(["preview", "full"]), default="preview",
              help="'preview' = public skill-pack submodule (2 skills). "
                   "'full' = local-only skill-pack-full/ (all 6 skills, requires Gumroad pack).")
@click.option("--judge", "judge_mode",
              type=click.Choice(["haiku", "sonnet", "calibrate"]),
              default="haiku",
              help="Layer 2 judging mode. 'calibrate' runs Haiku+Sonnet in parallel.")
def main(layer: tuple[str, ...], skill: str | None, source: str, judge_mode: str):
    """Run the skill evaluation suite."""
    skill_pack = SKILL_PACK_PATHS[source]
    if not skill_pack.exists():
        if source == "full":
            raise click.ClickException(
                f"--source full requires the paid pack at {skill_pack}. "
                "Unpack the Gumroad zip and symlink: "
                "ln -s <unpacked>/skills skill-pack-full/skills"
            )
        raise click.ClickException(
            f"Skill pack not found at {skill_pack}. Did you run "
            "`git submodule update --init`?"
        )

    run_id = time.strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[dim]Run ID: {run_id}  |  source: {source}  |  pack: {skill_pack}[/dim]")

    all_results: dict = {"source": source}

    if "1" in layer:
        console.rule("[bold cyan]Layer 1 — Trigger eval")
        all_results["layer_1"] = run_trigger_eval(skill, skill_pack, source)

    if "2" in layer:
        console.rule(f"[bold cyan]Layer 2 — Behavior assertion (judge={judge_mode})")
        all_results["layer_2"] = run_behavior_eval(skill, skill_pack, source, judge_mode)

    (out_dir / "results.json").write_text(json.dumps(all_results, indent=2, default=str))
    console.print(f"\n[green]Results saved to {out_dir}/results.json[/green]")


def _skill_in_source(skill_name: str, source: str) -> bool:
    """Is this skill expected to be present given the chosen source?"""
    required = SKILL_SOURCES.get(skill_name)
    if required is None:
        return True  # unknown skill — assume it's there
    return source == "full" or required == "preview"


def run_trigger_eval(skill_filter: str | None, skill_pack: Path, source: str) -> dict:
    triggers = yaml.safe_load((SCENARIOS_DIR / "triggers.yaml").read_text())
    results: dict = {}

    for skill_name, prompts in triggers.items():
        if skill_filter and skill_name != skill_filter:
            continue
        if not _skill_in_source(skill_name, source):
            console.print(f"  [dim]{skill_name} — skipped (requires --source full)[/dim]")
            results[skill_name] = {"skipped": True, "reason": "not in preview pack"}
            continue

        tp = fp = tn = fn = 0
        per_prompt = []

        for prompt in prompts.get("should_trigger", []):
            r = run_claude(prompt, skill_pack)
            loaded = skill_name in r.loaded_skills
            tp += int(loaded)
            fn += int(not loaded)
            per_prompt.append({"prompt": prompt, "expected": True, "loaded": loaded})

        for prompt in prompts.get("should_not_trigger", []):
            r = run_claude(prompt, skill_pack)
            loaded = skill_name in r.loaded_skills
            fp += int(loaded)
            tn += int(not loaded)
            per_prompt.append({"prompt": prompt, "expected": False, "loaded": loaded})

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0

        results[skill_name] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "per_prompt": per_prompt,
        }
        console.print(f"  [bold]{skill_name}[/bold] precision={precision:.2f} recall={recall:.2f}  "
                      f"(TP={tp} FP={fp} TN={tn} FN={fn})")

    return results


def run_behavior_eval(skill_filter: str | None, skill_pack: Path, source: str, judge_mode: str) -> dict:
    behaviors_dir = SCENARIOS_DIR / "behaviors"
    results: dict = {}

    for yaml_file in sorted(behaviors_dir.glob("*.yaml")):
        skill_name = yaml_file.stem.replace("_", "-")
        if skill_filter and skill_name != skill_filter:
            continue
        if not _skill_in_source(skill_name, source):
            console.print(f"  [dim]{skill_name} — skipped (requires --source full)[/dim]")
            results[skill_name] = {"skipped": True, "reason": "not in preview pack"}
            continue

        config = yaml.safe_load(yaml_file.read_text())
        skill_results = []
        agreements: list[bool] = []

        for scenario in config["scenarios"]:
            r = run_claude(scenario["prompt"], skill_pack)
            asserts = []

            for must_do in scenario.get("must_do", []):
                asserts.extend(_score_assertion(r.response_text, must_do, "must_do", judge_mode, agreements))

            for must_not in scenario.get("must_not_do", []):
                asserts.extend(_score_assertion(r.response_text, must_not, "must_not_do", judge_mode, agreements))

            passed = sum(1 for a in asserts if a.passed)
            skill_results.append({
                "name": scenario["name"],
                "prompt": scenario["prompt"],
                "score": f"{passed}/{len(asserts)}",
                "assertions": [asdict(a) for a in asserts],
            })

        results[skill_name] = {
            "scenarios": skill_results,
            "calibration_agreement_rate": (
                round(sum(agreements) / len(agreements), 3) if agreements else None
            ),
        }
        console.print(f"  [bold]{skill_name}[/bold] {len(skill_results)} scenarios "
                      + (f"(Haiku/Sonnet agreement: {results[skill_name]['calibration_agreement_rate']})"
                         if agreements else ""))

    return results


def _score_assertion(response_text: str, spec: dict, polarity: str,
                     judge_mode: str, agreements: list) -> list:
    """Score a single assertion. Spec is either {regex: ...} or {text: ...}."""
    if "regex" in spec:
        must_match = polarity == "must_do"
        return [check_regex(response_text, spec["regex"], must_match=must_match)]

    text = spec["text"]
    if judge_mode == "calibrate":
        h, s, agreed = judge_calibrate(response_text, text, polarity)
        agreements.append(agreed)
        return [h, s]
    return [judge(response_text, text, polarity, model=judge_mode)]


if __name__ == "__main__":
    main()
