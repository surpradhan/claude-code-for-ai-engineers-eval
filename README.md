# claude-code-for-ai-engineers-eval

A test harness for Claude Code skill packs. Built originally for the [Claude Code for AI Engineers](https://github.com/surpradhan/claude-code-for-ai-engineers) pack, but it's generic — point it at any skill pack to verify that:

1. **Triggering works.** Each skill loads on the right prompts and stays silent on near-misses.
2. **Behavior holds.** When a skill loads, Claude actually follows its gates instead of skipping them.

## What it tests

| Layer | What it checks | Cost per run |
|---|---|---|
| 1. Trigger eval | Right skill loads on right prompts | Cents |
| 2. Behavior assertion | When loaded, Claude follows the gates | $1–3 |
| 3. Artifact validation | For scaffolders — does the generated project run? | $5–15 |
| 4. Adversarial + regression | Can engineered prompts skip the gates? | Tracked in 1 + 2 |

## Two sources, two scorecards

This harness runs scenarios against two skill-pack sources:

- **`--source preview`** (default) — the public submodule at `./skill-pack/`. Covers the 2 preview skills: `rag-eval-harness`, `agent-trace-debug`. This is what CI tests, and what the green badge proves.
- **`--source full`** — the full paid pack at `./skill-pack-full/` (gitignored, local-only). Covers all 6 skills.

Scenarios for the 4 paid skills are committed to this repo because they are behavior contracts, not skill content. They simply skip in `--source preview` runs.

## Quick start

```bash
git clone https://github.com/surpradhan/claude-code-for-ai-engineers-eval
cd claude-code-for-ai-engineers-eval

# Pull the open-source preview pack as a submodule
git submodule add https://github.com/surpradhan/claude-code-for-ai-engineers skill-pack
git submodule update --init

pip install -e .
export ANTHROPIC_API_KEY=sk-ant-...

# Public CI scorecard — 2 preview skills
python -m eval.runner --layer 1 --layer 2 --source preview

# Full scorecard — local only, requires the Gumroad pack
mkdir -p skill-pack-full
ln -s ~/path/to/unpacked-gumroad-pack/skills skill-pack-full/skills
python -m eval.runner --layer 1 --layer 2 --source full --judge calibrate
```

Results land in `results/<timestamp>/results.json`. Pipe through `eval/report.py` for a Markdown table.

## Pointing it at your own skill pack

Replace the submodule:

```bash
git submodule deinit skill-pack
git submodule add https://github.com/<you>/<your-pack> skill-pack
```

Then add your prompts to `scenarios/triggers.yaml` and your scenarios to `scenarios/behaviors/<skill_name>.yaml`. See `scenarios/behaviors/rag_eval_harness.yaml` for the format.

## How the judging works

Layer 2 scoring is hybrid:

- **Deterministic** — regex/keyword checks on Claude's response. Free, no judge call.
- **Haiku judge** — fast, cheap LLM-judge against a strict rubric. Default production mode.
- **Sonnet calibration** — for the first two weeks, every fuzzy assertion runs through BOTH Haiku and Sonnet (`--judge calibrate`). Once they agree ≥90% of the time on your scenarios, drop Sonnet (`--judge haiku`) and run Haiku only.

## CI

`.github/workflows/skill-eval.yml` runs Layer 1 on every push and Layer 2 nightly. The badge in the consuming skill pack's README links back here.

## Verify your Claude Code CLI

The harness shells out to `claude -p "<prompt>" --output-format json`. Confirm those flags work on your installed version before running the full suite — Claude Code CLI moves fast and flags evolve. See `eval/harness.py` for the exact invocation.

## License

MIT.
