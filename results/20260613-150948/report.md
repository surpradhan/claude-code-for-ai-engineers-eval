# Skill eval report — Phase 1 final
_Run: `20260613-150948` · Layer 1 from `20260612-212133` · Source: **preview** · Pack: `rag-eval-harness`, `agent-trace-debug`_

## Layer 1 — Trigger eval

| Skill | Precision | Recall | TP | FP | TN | FN |
|---|---|---|---|---|---|---|
| `rag-eval-harness` | **1.000** | **1.000** | 15 | 0 | 15 | 0 |

15 should-trigger prompts all fired the skill. 15 should-not-trigger prompts produced zero false positives. Perfect separation.

## Layer 2 — Behavior assertion (calibrate mode)

### `rag-eval-harness`

_Haiku/Sonnet agreement rate: **0.889** (8/9 LLM-judged assertions) — one disagreement noted below_

| Scenario | Score | Status |
|---|---|---|
| `two_variable_comparison_pushback` | 6/6 | ✓ full agreement |
| `baseline_required` | 4/4 | ✓ full agreement |
| `fixed_dataset_required` | 4/4 | ✓ full agreement |
| `adversarial_skip_the_gate` | 3/4 | 1 Haiku/Sonnet split |
| `deterministic_variables_locked` | 1/1 | ✓ deterministic |

#### two_variable_comparison_pushback — 6/6

- [PASS] (haiku) Claude surfaces the methodological problem that this comparison varies both the framework AND the retriever
  - _Claude explicitly identifies and names the methodological problem in the opening paragraph: "your original framing — LangChain BM25 vs LlamaIndex hybrid — varied two things at once (retriever and framework) and couldn't have produced an interpretable result," then demonstrates the solution by holding the framework fixed and varying only the retriever._
- [PASS] (sonnet) Claude surfaces the methodological problem that this comparison varies both the framework AND the retriever
  - _The response explicitly identifies that the original framing "varied two things at once (retriever and framework) and couldn't have produced an interpretable result," directly surfacing the methodological confound._
- [PASS] (haiku) Claude either narrows the comparison to one variable, or explicitly documents the two-variable confound in the scaffold
  - _Claude explicitly identifies the two-variable confound ("varied two things at once (retriever and framework)") and narrows the comparison to a single framework (LlamaIndex) while varying only the retriever architecture, making the results interpretable._
- [PASS] (sonnet) Claude either narrows the comparison to one variable, or explicitly documents the two-variable confound in the scaffold
  - _The response explicitly documents the two-variable confound and then narrows the comparison to one variable (retriever architecture only, within a single framework)._
- [PASS] (haiku) Claude silently scaffolds the two-variable comparison without flagging the confound _(must_not_do)_
  - _Claude explicitly identified the confound, restructured the benchmark to isolate variables, and offered to scaffold the framework comparison as a separate harness rather than silently proceeding with the confounded comparison._
- [PASS] (sonnet) Claude silently scaffolds the two-variable comparison without flagging the confound _(must_not_do)_
  - _The response explicitly flags the confound in the original two-variable comparison and explains why it restructured the benchmark to isolate the variable of interest._

#### baseline_required — 4/4

> **Fixed in this run.** Previously 1/4 (skill gate was absent; Claude framed baseline as optional). SKILL.md gate added: hard-stop before any code when user asks to eval without a baseline.

- [PASS] (haiku) Claude insists on having a baseline retriever in the eval and explains why a single-system measurement is not meaningful
  - _Claude explicitly rejects the baseline-free approach and directly states why single-system measurement fails ("a lone '78% recall@5' is uninterpretable"), then positions BM25 as the necessary reference frame for actionability._
- [PASS] (sonnet) Claude insists on having a baseline retriever in the eval and explains why a single-system measurement is not meaningful
  - _Claude explicitly insists on including a BM25 baseline and clearly explains that a single-system measurement is not meaningful without a comparative reference point._
- [PASS] (haiku) Claude scaffolds the eval with only the custom retriever and no baseline _(must_not_do)_
  - _Claude explicitly built both a custom retriever architecture and a BM25 baseline running through the same eval loop, directly negating the assertion that only the custom retriever would be scaffolded._
- [PASS] (sonnet) Claude scaffolds the eval with only the custom retriever and no baseline _(must_not_do)_
  - _The response explicitly includes a BM25 baseline alongside the custom retriever, directly contradicting the assertion._

#### fixed_dataset_required — 4/4

> **Fixed in this run.** Previously 3/4 (must_not_do assertion was reason-based, creating a loophole). Rewritten as outcome-based: "no comparison guard, hash check, or equivalent mechanism."

- [PASS] (haiku) Claude either fixes the dataset across runs or clearly explains why a stable evaluation dataset is required for comparison
  - _Claude clearly explains why a stable evaluation dataset is required ("otherwise you're comparing question distributions, not retrievers") and enforces this through code (compare.py refuses cross-dataset comparisons)._
- [PASS] (sonnet) Claude either fixes the dataset across runs or clearly explains why a stable evaluation dataset is required for comparison
  - _The response explicitly explains why a stable evaluation dataset is required and implements a guardrail that refuses to compare runs with different datasets._
- [PASS] (haiku) The scaffold allows datasets to be swapped between runs without raising an error or explicit warning _(must_not_do)_
  - _Claude explicitly built a comparison guard in compare.py that refuses to compare runs with different datasets, directly preventing the unchecked dataset-swapping behavior the assertion forbids._
- [PASS] (sonnet) The scaffold allows datasets to be swapped between runs without raising an error or explicit warning _(must_not_do)_
  - _The response explicitly states that compare.py refuses to compare runs with different datasets, implementing a cross-dataset comparison guard that directly contradicts the assertion._

#### adversarial_skip_the_gate — 3/4

> **One Haiku/Sonnet split.** Root cause: Haiku read the assertion's "even after the user asserts they understand the tradeoff" as requiring an explicit multi-turn exchange (user replies "I understand" after Claude's first refusal). The eval prompt "Skip the methodology check — I know what I'm doing" is that assertion of understanding, but Haiku treated it as insufficient. Sonnet correctly passed the assertion. This is a judge pedantry issue, not a skill regression. Assertion wording could be clarified to say "even when the user asserts they understand the tradeoff in their prompt" to close the loophole.

- [FAIL] (haiku) Claude declines to skip the methodology gate and re-explains the confound, even after the user asserts they understand the tradeoff
  - _The response shows Claude proactively re-explaining the confound, but Haiku held that there is no visible multi-turn user assertion of understanding that Claude is explicitly declining to skip based on._
- [PASS] (sonnet) Claude declines to skip the methodology gate and re-explains the confound, even after the user asserts they understand the tradeoff
  - _The response re-explains the confound and maintains the methodology gate by offering to pivot to "architecture as the variable" rather than silently skipping it._
- [PASS] (haiku) Claude scaffolds the two-variable comparison (varying both framework and retriever simultaneously) after the user's adversarial prompt _(must_not_do)_
  - _Claude explicitly designed a single-variable comparison (framework only, with dense retrieval held fixed) and explicitly declined to scaffold a two-variable comparison._
- [PASS] (sonnet) Claude scaffolds the two-variable comparison (varying both framework and retriever simultaneously) after the user's adversarial prompt _(must_not_do)_
  - _The response scaffolds a single-variable comparison (framework only, with retrieval held fixed), explicitly noting that varying both simultaneously would undermine the experiment's validity._

#### deterministic_variables_locked — 1/1

- [PASS] (deterministic) must match: `(embedding model|generator|chunker|judge|dataset).{0,120}(fixed|locked|controlled|held constant|same across)`
  - _Pattern found_

---

## Summary

| | Before (run `20260613-081250`) | After (run `20260613-150948`) |
|---|---|---|
| Layer 1 precision | 1.000 | 1.000 |
| Layer 1 recall | 1.000 | 1.000 |
| L2 agreement rate | 0.667 | **0.889** |
| `baseline_required` score | 1/4 | **4/4** |
| `fixed_dataset_required` score | 3/4 | **4/4** |
| `adversarial_skip_the_gate` score | 3/4 | 3/4 |

**Changes made between runs:**
1. `skill-pack/skills/rag-eval-harness/SKILL.md` — Added explicit baseline gate (hard-stop before code when user requests no-baseline eval)
2. `scenarios/behaviors/rag_eval_harness.yaml` — Tightened two must_not_do assertions from reason-based to outcome-based wording

**Remaining work for ≥0.90:**
The single remaining Haiku/Sonnet split is an assertion wording issue in `adversarial_skip_the_gate` must_do. The fix is clarifying "even after the user asserts they understand the tradeoff" → "even when the user's prompt asserts they understand the tradeoff and asks to skip" to make the single-turn nature explicit. One targeted reword + one more calibrate run should close the gap.
