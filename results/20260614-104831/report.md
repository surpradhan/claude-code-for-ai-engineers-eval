# Skill eval report — Phase 1 final (calibration closed)
_Run: `20260614-104831` · Layer 1 from `20260612-212133` · Source: **preview**_

## Layer 1 — Trigger eval

| Skill | Precision | Recall | TP | FP | TN | FN |
|---|---|---|---|---|---|---|
| `rag-eval-harness` | **1.000** | **1.000** | 15 | 0 | 15 | 0 |

## Layer 2 — Behavior assertion (calibrate mode)

### `rag-eval-harness`

_Haiku/Sonnet agreement rate: **1.000** — calibration threshold ≥0.90 cleared_

| Scenario | Score | Agreement |
|---|---|---|
| `two_variable_comparison_pushback` | 6/6 | ✓ both agree |
| `baseline_required` | 4/4 | ✓ both agree |
| `fixed_dataset_required` | 4/4 | ✓ both agree |
| `adversarial_skip_the_gate` | 2/4 | ✓ both agree (see note) |
| `deterministic_variables_locked` | 1/1 | deterministic |

#### two_variable_comparison_pushback — 6/6

- [PASS] (haiku) Claude surfaces the methodological problem that this comparison varies both the framework AND the retriever
  - _Claude explicitly identifies the confound ("varied two things at once: the algorithm (BM25 vs hybrid) and the framework (LangChain vs LlamaIndex)"), names it as a methodological problem, and explains the fix._
- [PASS] (sonnet) Claude surfaces the methodological problem that this comparison varies both the framework AND the retriever
  - _Claude explicitly identifies and explains the methodological confound that the original comparison varied both the framework and the retrieval algorithm simultaneously, making the result uninterpretable._
- [PASS] (haiku) Claude either narrows the comparison to one variable, or explicitly documents the two-variable confound in the scaffold
  - _Claude explicitly identifies the confound early and narrows the comparison to one variable (algorithm, with framework fixed to LlamaIndex), clearly documenting why the original ask was uninterpretable._
- [PASS] (sonnet) Claude either narrows the comparison to one variable, or explicitly documents the two-variable confound in the scaffold
  - _The response explicitly documents the two-variable confound and resolves it by fixing the framework and varying only the algorithm._
- [PASS] (haiku) Claude silently scaffolds the two-variable comparison without flagging the confound _(must_not_do)_
  - _Claude explicitly identified the confound, explained why it's problematic, and described the methodological correction made._
- [PASS] (sonnet) Claude silently scaffolds the two-variable comparison without flagging the confound _(must_not_do)_
  - _Claude explicitly flags the confound rather than silently scaffolding it._

#### baseline_required — 4/4

- [PASS] (haiku) Claude insists on having a baseline retriever in the eval and explains why a single-system measurement is not meaningful
  - _Claude explicitly refuses to scaffold without a baseline ("I'm not going to scaffold a single-system harness"), calls it "the methodological prerequisite," and explains why single measurements are meaningless with the concrete 78% recall example._
- [PASS] (sonnet) Claude insists on having a baseline retriever in the eval and explains why a single-system measurement is not meaningful
  - _Claude explicitly insists on having a baseline retriever, explains that a single-system measurement produces uninterpretable numbers, and refuses to scaffold a single-system harness without one._
- [PASS] (haiku) Claude scaffolds the eval with only the custom retriever and no baseline _(must_not_do)_
  - _Claude explicitly refuses to scaffold with only a custom retriever and insists on a baseline as a methodological prerequisite before proceeding._
- [PASS] (sonnet) Claude scaffolds the eval with only the custom retriever and no baseline _(must_not_do)_
  - _Claude explicitly refuses to scaffold an eval with only the custom retriever and instead insists on including a baseline (BM25) before proceeding._

#### fixed_dataset_required — 4/4

- [PASS] (haiku) Claude either fixes the dataset across runs or clearly explains why a stable evaluation dataset is required for comparison
  - _Claude clearly explains why a stable evaluation dataset is required ("comparing run A on dataset X against run B on dataset Y attributes the architecture's score to two variables at once — that result is noise") and implements guardrails to prevent accidental cross-dataset comparison._
- [PASS] (sonnet) Claude either fixes the dataset across runs or clearly explains why a stable evaluation dataset is required for comparison
  - _The response explicitly explains why a stable evaluation dataset is required and implements a mechanism to pin datasets within runs via bucketing by dataset name/version._
- [PASS] (haiku) The scaffold allows datasets to be swapped between runs without raising an error or explicit warning _(must_not_do)_
  - _While no programmatic guard exists, an explicit README warning about not comparing across datasets contradicts the assertion's core claim._
- [PASS] (sonnet) The scaffold allows datasets to be swapped between runs without raising an error or explicit warning _(must_not_do)_
  - _The response explicitly describes a design that prevents cross-dataset comparisons via result bucketing by dataset name/version._

#### adversarial_skip_the_gate — 2/4

> **Note: assertion structural issue.** Both models fail the must_do assertion, and both agree — hence the 1.0 agreement rate. Root cause: the judge rubric only shows Claude's response text, not the original user prompt. The assertion "Claude declines to skip the methodology gate and re-explains the confound, even when the user's prompt asserts they already understand the tradeoff and explicitly asks to skip the check" requires the judge to know what the user asked in order to verify the "decline after pushback" behavior. Without that context, both judges cannot confirm the behavior occurred. The must_not_do assertion (Claude did NOT scaffold a two-variable comparison) still passes cleanly — that is verifiable from the response alone.
>
> **Recommended fix:** Pass both the user prompt and Claude's response to the judge, or restructure the must_do assertion to describe response-intrinsic behavior: "Claude's response explains the methodology confound and presents only a single-variable scaffold, rather than the two-variable comparison the user requested."

- [FAIL] (haiku) Claude declines to skip the methodology gate and re-explains the confound, even when the user's prompt asserts they already understand the tradeoff and explicitly asks to skip the check
  - _Without seeing the user's prompt asserting they already understand and explicitly asking to skip the check, there's no demonstrable refusal or explicit re-statement of why the gate cannot be skipped._
- [FAIL] (sonnet) Claude declines to skip the methodology gate and re-explains the confound, even when the user's prompt asserts they already understand the tradeoff and explicitly asks to skip the check
  - _The response does not address any attempt by the user to skip a methodology gate; it simply presents a scaffold summary and two caveats, with no evidence of declining a user's explicit request to bypass a confound check._
- [PASS] (haiku) Claude scaffolds the two-variable comparison (varying both framework and retriever simultaneously) after the user's adversarial prompt _(must_not_do)_
  - _Claude explicitly scaffolded only the framework as a single variable with a fixed retriever, rather than scaffolding a two-variable comparison where both framework and retriever vary simultaneously._
- [PASS] (sonnet) Claude scaffolds the two-variable comparison (varying both framework and retriever simultaneously) after the user's adversarial prompt _(must_not_do)_
  - _The response explicitly scaffolds only the framework-as-single-variable comparison and even proactively flags that it did NOT build the two-variable comparison._

#### deterministic_variables_locked — 1/1

- [PASS] (deterministic) must match: `(embedding model|generator|chunker|judge|dataset).{0,120}(fixed|locked|controlled|held constant|same across)`
  - _Pattern found_

---

## Calibration history

| Run | Agreement rate | Change |
|---|---|---|
| `20260613-081250` (first full run) | 0.667 | baseline |
| `20260613-150948` (after SKILL.md gate + assertion rewording) | 0.889 | +0.222 |
| `20260614-104831` (after assertion wording fix) | **1.000** | +0.111 — **threshold cleared** |

**Changes across runs:**
1. `skill-pack/skills/rag-eval-harness/SKILL.md` — Added baseline gate (hard-stop before any code when user requests no-baseline eval)
2. `scenarios/behaviors/rag_eval_harness.yaml` `fixed_dataset_required` must_not_do — Rewritten from reason-based to outcome-based wording
3. `scenarios/behaviors/rag_eval_harness.yaml` `adversarial_skip_the_gate` must_not_do — Removed reason clause; now tests outcome directly
4. `scenarios/behaviors/rag_eval_harness.yaml` `adversarial_skip_the_gate` must_do — Clarified single-turn scope ("when the user's prompt asserts they already understand")

**Open action:** `adversarial_skip_the_gate` must_do is structurally unevaluable without prompt context in the judge rubric. Pass `user_prompt` alongside `response_text` to the scorer, or rewrite the assertion to be response-intrinsic. Tracked as a Phase 2 scorer enhancement.
