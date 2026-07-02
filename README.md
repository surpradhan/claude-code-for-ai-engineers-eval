# claude-code-for-ai-engineers-eval

A test harness for Claude Code skill packs. Built originally for the [Claude Code for AI Engineers](https://github.com/surpradhan/claude-code-for-ai-engineers) pack, but it's generic — point it at any skill pack to verify that:

1. **Triggering works.** Each skill loads on the right prompts and stays silent on near-misses.
2. **Behavior holds.** When a skill loads, Claude actually follows its gates instead of skipping them.

## Verified by self-test

Last run: 2026-06-20. Source: preview pack. Claude Code CLI v2.1.175.

**Layer 1 — trigger eval (`rag-eval-harness`):** precision **1.000**, recall **1.000** (15 TP / 0 FP / 15 TN / 0 FN).

**Layer 2 — behavior assertion:** 9/9 assertions pass across 5 scenarios, including an adversarial prompt that explicitly asks Claude to skip the methodology gate. Production judge: Haiku. Haiku/Sonnet calibration agreement (from the 2026-06-14 `--judge calibrate` run, prior to switching to Haiku-only): **1.000**. Haiku vs human agreement: **1.000** (N=9, labels in `eval/labels/`).

Re-generate the full report locally: `python -m eval.runner --layer 1 --layer 2 --source preview && python -m eval.report results/<timestamp>/results.json`

## What it tests

| Layer | What it checks | Cost per run |
|---|---|---|
| 1. Trigger eval | Right skill loads on right prompts | Max plan |
| 2. Behavior assertion | When loaded, Claude follows the gates | Max plan |
| 3. Artifact validation | For scaffolders — does the generated project run? | Max plan + Docker |
| 4. Adversarial + regression | Can engineered prompts skip the gates? | Tracked in 1 + 2 |

## Two sources, two scorecards

This harness runs scenarios against two skill-pack sources:

- **`--source preview`** (default) — the public submodule at `./skill-pack/`. Covers the 2 preview skills: `rag-eval-harness`, `agent-trace-debug`. This is what CI tests, and what the green badge proves.
- **`--source full`** — a local, gitignored skill-pack directory at `./skill-pack-full/`. For extending the harness to a private pack.

Scenarios for the 4 non-preview skills are committed to this repo because they are behavior contracts, not skill content. They simply skip in `--source preview` runs.

## Quick start

```bash
git clone https://github.com/surpradhan/claude-code-for-ai-engineers-eval
cd claude-code-for-ai-engineers-eval

# Pull the open-source preview pack as a submodule
git submodule add https://github.com/surpradhan/claude-code-for-ai-engineers skill-pack
git submodule update --init

pip install -e .

# Make sure the `claude` CLI is logged in (it uses your Claude Max plan,
# no separate Anthropic API key required):
claude --version

# Public CI scorecard — 2 preview skills
python -m eval.runner --layer 1 --layer 2 --source preview

# Full scorecard — requires a local skill-pack directory
mkdir -p skill-pack-full
ln -s /path/to/your/local/skill-pack/skills skill-pack-full/skills
python -m eval.runner --layer 1 --layer 2 --source full --judge calibrate
```

Results land in `results/<timestamp>/results.json`. Pipe through `eval/report.py` for a Markdown table.

## Methodology caveats

**Inter-judge agreement is a consistency check, not a ground-truth check.** Haiku and Sonnet can share a blind spot. When they do, they agree, and the agreement rate hides the failure. The fix is to hand-label a sample and score each judge against the human labels.

**Adversarial coverage is thin.** There is one explicitly adversarial scenario per skill right now. That is a known gap. The plan is to paraphrase each adversarial scenario through different framings (impatient PM, research excuse, and so on) and keep the ones that still break the skill.

**Status:** hand-labeled `rag-eval-harness`, Haiku vs human agreement = 1.00 (N=9).

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
- **Haiku judge** — LLM-judge against a strict rubric. Default production mode. Calls `claude -p --model haiku`, runs against your Claude Max plan.
- **Sonnet calibration** — for the first two weeks, every fuzzy assertion runs through BOTH Haiku and Sonnet (`--judge calibrate`). Once they agree ≥90% of the time on your scenarios, drop Sonnet (`--judge haiku`) and run Haiku only.

The judge shells out to the `claude` CLI rather than the Anthropic Python SDK, so no separate API key is required. Tradeoff: ~5x slower than direct API calls (subprocess overhead). A full Layer 2 calibrate run takes ~15 min on the flagship instead of ~5 min via API.

## CI

`.github/workflows/skill-eval.yml` runs Layer 1 on every push and Layer 2 nightly. The badge in the consuming skill pack's README links back here.

## Verify your Claude Code CLI

The harness shells out to `claude -p "<prompt>" --output-format json`. Confirm those flags work on your installed version before running the full suite — Claude Code CLI moves fast and flags evolve. See `eval/harness.py` for the exact invocation.

## License

MIT.
