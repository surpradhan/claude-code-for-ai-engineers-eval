"""Interactive human-labelling tool for Layer 2 assertions.

CLI:
    python -m eval.label results/<timestamp>/results.json --skill rag-eval-harness

Walks layer_2[skill].scenarios[*].assertions[], deduplicating by
(scenario_name, assertion_text). Each unique pair is shown once regardless
of how many judge models scored it (haiku, sonnet, etc.).

Labels persist to results/<timestamp>/human_labels.json. Quit-and-resume
works: re-running picks up from the first unlabeled assertion.

On completion, writes layer_2[skill].human_calibration into results.json.
"""

import json
import sys
from pathlib import Path

import click
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
BEHAVIORS_DIR = REPO_ROOT / "scenarios" / "behaviors"


def _load_polarity_index() -> dict:
    """Build {skill: {scenario_name: {assertion_text: polarity}}} from scenario YAMLs."""
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
    if assertion_text in polarity_map:
        return polarity_map[assertion_text]
    for prefix, polarity in (("must match: ", "must_do"), ("must not match: ", "must_not_do")):
        if assertion_text.startswith(prefix):
            return polarity
    return "unknown"


def _make_key(skill: str, scenario_name: str, assertion_text: str) -> str:
    return json.dumps([skill, scenario_name, assertion_text], ensure_ascii=False)


def _load_labels(labels_path: Path) -> dict:
    if labels_path.exists():
        return json.loads(labels_path.read_text())
    return {}


def _save_labels(labels_path: Path, labels: dict) -> None:
    labels_path.write_text(json.dumps(labels, indent=2) + "\n")


def _compute_agreement(
    skill: str, skill_data: dict, labels: dict
) -> tuple[int, int, "float | None", int, "float | None"]:
    """Return (n_labeled, haiku_n_compared, haiku_agreement, sonnet_n_compared, sonnet_agreement).

    n_labeled is the total labels in the file for this skill.
    haiku_n_compared is the subset that found a matching haiku verdict in results.json —
    the two can differ if results.json is regenerated with different assertion texts after
    labelling, making n_labeled misleading as the N= denominator.
    """
    haiku_agree = haiku_total = 0
    sonnet_agree = sonnet_total = 0

    verdict_lookup: dict = {}
    for scenario in skill_data["scenarios"]:
        sname = scenario["name"]
        for a in scenario["assertions"]:
            key = _make_key(skill, sname, a["assertion"])
            if key not in verdict_lookup:
                verdict_lookup[key] = {}
            verdict_lookup[key][a["judge_model"]] = a["passed"]

    for key, human_passed in labels.items():
        verdicts = verdict_lookup.get(key, {})
        if "haiku" in verdicts:
            haiku_total += 1
            haiku_agree += int(verdicts["haiku"] == human_passed)
        if "sonnet" in verdicts:
            sonnet_total += 1
            sonnet_agree += int(verdicts["sonnet"] == human_passed)

    haiku_agreement = round(haiku_agree / haiku_total, 3) if haiku_total else None
    sonnet_agreement = round(sonnet_agree / sonnet_total, 3) if sonnet_total else None
    return len(labels), haiku_total, haiku_agreement, sonnet_total, sonnet_agreement


def _update_results(results_path: Path, skill: str, human_calibration: dict) -> None:
    data = json.loads(results_path.read_text())
    data["layer_2"][skill]["human_calibration"] = human_calibration
    results_path.write_text(json.dumps(data, indent=2) + "\n")


@click.command()
@click.argument("results_json", type=click.Path(exists=True, path_type=Path))
@click.option("--skill", required=True, help="Skill to label (e.g. rag-eval-harness)")
def main(results_json: Path, skill: str) -> None:
    """Human-label Layer 2 assertions and compute judge-vs-human agreement."""
    data = json.loads(results_json.read_text())

    if "layer_2" not in data or skill not in data["layer_2"]:
        click.echo(f"No layer_2 data for skill '{skill}' in {results_json}", err=True)
        sys.exit(1)

    skill_data = data["layer_2"][skill]
    if skill_data.get("skipped"):
        click.echo(f"Skill '{skill}' was skipped in this run.", err=True)
        sys.exit(1)

    labels_path = results_json.parent / "human_labels.json"
    labels = _load_labels(labels_path)
    polarity_idx = _load_polarity_index()
    skill_polarities = polarity_idx.get(skill, {})

    seen: set[str] = set()
    queue: list[dict] = []
    for scenario in skill_data["scenarios"]:
        if scenario.get("skipped"):
            continue
        scenario_polarities = skill_polarities.get(scenario["name"], {})
        # key encodes (skill, scenario_name, assertion_text), so it is globally
        # unique within a skill. seen alone deduplicates both the calibrate-mode
        # case (haiku + sonnet entries share the same text within one scenario)
        # and any cross-scenario repetition.
        for a in scenario["assertions"]:
            text = a["assertion"]
            key = _make_key(skill, scenario["name"], text)
            if key in seen:
                continue
            seen.add(key)
            judge_entries = [x for x in scenario["assertions"] if x["assertion"] == text]
            queue.append({
                "key": key,
                "scenario_name": scenario["name"],
                "prompt": scenario["prompt"],
                "assertion": text,
                "polarity": _polarity_for(text, scenario_polarities),
                "judge_entries": judge_entries,
            })

    if not queue:
        click.echo(f"No assertions to label for skill '{skill}'.", err=True)
        sys.exit(0)

    total = len(queue)
    skill_keys = {item["key"] for item in queue}
    already_labeled = sum(1 for k in labels if k in skill_keys)
    unlabeled = [item for item in queue if item["key"] not in labels]

    if not unlabeled:
        click.echo(f"All {total} assertions already labeled.")
    elif already_labeled:
        click.echo(f"{already_labeled} of {total} labeled. Resuming from item {already_labeled + 1}.")
    else:
        click.echo(f"{total} assertions to label.")
    click.echo()

    quit_requested = False
    for i, item in enumerate(unlabeled):
        position = already_labeled + i + 1
        click.echo("=" * 60)
        click.echo(f"Assertion {position}/{total}  |  Scenario: {item['scenario_name']}")
        click.echo()
        click.echo(f"User prompt:\n  {item['prompt']}")
        click.echo()
        click.echo(f"Assertion ({item['polarity']}):\n  {item['assertion']}")
        click.echo()
        for entry in item["judge_entries"]:
            verdict = "PASS" if entry["passed"] else "FAIL"
            click.echo(f"Judge ({entry['judge_model']}): {verdict}")
            if entry.get("reason"):
                click.echo(f"  {entry['reason']}")
        click.echo()
        click.echo("Note: raw response text is not stored in results.json.")
        click.echo()

        while True:
            raw = click.prompt("[p]ass / [f]ail / [s]kip / [q]uit-and-save").strip().lower()
            if raw in ("p", "f", "s", "q"):
                break
            click.echo("Enter p, f, s, or q.")

        if raw == "q":
            _save_labels(labels_path, labels)
            click.echo(f"\nSaved {len(labels)} labels to {labels_path} (current item not saved). Run again to resume.")
            quit_requested = True
            break
        elif raw == "s":
            continue
        else:
            labels[item["key"]] = (raw == "p")
            _save_labels(labels_path, labels)

    if not quit_requested:
        click.echo()
        skill_labels = {k: v for k, v in labels.items() if k in skill_keys}
        n, haiku_n, haiku_agreement, sonnet_n, sonnet_agreement = _compute_agreement(
            skill, skill_data, skill_labels
        )
        click.echo("=" * 60)
        click.echo(f"n_labeled: {n}")
        if haiku_agreement is not None:
            click.echo(f"haiku_vs_human_agreement:  {haiku_agreement} (N={haiku_n})")
        if sonnet_agreement is not None:
            click.echo(f"sonnet_vs_human_agreement: {sonnet_agreement} (N={sonnet_n})")

        human_calibration: dict = {
            "n_labeled": n,
            "haiku_n_compared": haiku_n,
            "haiku_vs_human_agreement": haiku_agreement,
            "sonnet_n_compared": sonnet_n,
            "sonnet_vs_human_agreement": sonnet_agreement,
        }
        _update_results(results_json, skill, human_calibration)
        click.echo(f"\nWrote human_calibration to {results_json}")


if __name__ == "__main__":
    main()
