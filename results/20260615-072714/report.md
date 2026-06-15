# Skill eval report
_Source: `results/20260615-072714/results.json` (pack: **preview**)_

## Layer 1 — Trigger eval

| Skill | Precision | Recall | TP | FP | TN | FN |
|---|---|---|---|---|---|---|
| `rag-eval-harness` | 1.0 | 1.0 | 15 | 0 | 15 | 0 |

## Layer 2 — Behavior assertion

### `rag-eval-harness`
- **two_variable_comparison_pushback** — 3/3
  - [PASS] *[must_do]* (haiku) Claude surfaces the methodological problem that this comparison varies both the framework AND the retriever
    - _Claude explicitly identifies and surfaces the methodological problem in the opening section ("The methodology fix, up front"), stating directly that "Your request as stated — LangChain BM25 vs LlamaIndex hybrid — varies two things at once: the retrieval algorithm *and* the framework" and explains why this creates uninterpretable noise, then pivots to a single-variable comparison._
  - [PASS] *[must_do]* (haiku) Claude either narrows the comparison to one variable, or explicitly documents the two-variable confound in the scaffold
    - _Claude explicitly identifies the two-variable confound ("varies two things at once: the retrieval algorithm and the framework"), documents why it matters ("uninterpretable noise"), and narrows to a single-variable design by fixing LlamaIndex as the host framework with only the retrieval algorithm as the moving part._
  - [PASS] *[must_not_do]* (haiku) Claude silently scaffolds the two-variable comparison without flagging the confound
    - _Claude explicitly flagged the confound ("varies two things at once: the retrieval algorithm *and* the framework"), explained why it's problematic ("uninterpretable noise"), and deliberately scaffolded a single-variable comparison instead, with an offer to revert if the user preferred the original two-variable setup._
- **baseline_required** — 2/2
  - [PASS] *[must_do]* (haiku) Claude insists on having a baseline retriever in the eval and explains why a single-system measurement is not meaningful
    - _Claude explicitly refuses to scaffold a single-system harness, insists on adding a baseline retriever, and clearly explains that without a reference point, metrics like "78% recall@5" are unactionable and meaningless._
  - [PASS] *[must_not_do]* (haiku) Claude scaffolds the eval with only the custom retriever and no baseline
    - _Claude explicitly refuses to scaffold a single-system harness and insists on adding a baseline retriever, directly opposing the forbidden behavior._
- **fixed_dataset_required** — 1/1
  - [PASS] *[must_do]* (haiku) Claude either refuses to allow the dataset to change between runs, or implements a comparison guard, hash check, or equivalent mechanism that prevents cross-dataset comparisons and makes the restriction explicit through an error, warning, or explanation
    - _Claude explicitly implements a dataset_id hash check, a comparison guard in `compare.py` that refuses to diff runs with different datasets (exit 2), and makes the restriction clear through error codes and explanation, allowing per-run dataset flexibility while preventing unsafe cross-dataset comparisons._
- **adversarial_skip_the_gate** — 2/2
  - [PASS] *[must_do]* (haiku) Claude declines to skip the methodology gate and re-explains the confound, even when the user's prompt asserts they already understand the tradeoff and explicitly asks to skip the check
    - _Claude explicitly declines to proceed ("I'm going to hold on scaffolding this as-is"), re-explains the confound in detail (varying two variables simultaneously, uninterpretable deltas, colliding defaults), and directly acknowledges the user's assertion ("This holds even though you said you've got it") while maintaining the boundary, which precisely satisfies the must-do assertion._
  - [PASS] *[must_not_do]* (haiku) Claude scaffolds the two-variable comparison (varying both framework and retriever simultaneously) after the user's adversarial prompt
    - _Claude explicitly refused to scaffold the problematic two-variable comparison, held firm against the user's pressure to skip methodology checks, and instead offered corrected single-variable alternatives._
- **deterministic_variables_locked** — 1/1
  - [PASS] *[must_do]* (haiku) Claude's response explicitly states that all components except the embedding model under test (such as the generator, chunker, judge, or dataset) are held fixed or identical across both evaluation arms
    - _The response explicitly states "**Held fixed** in `config/fixed.yaml`: HotpotQA distractor dataset, RecursiveCharacterTextSplitter (512/50), FAISS flat/cosine, Llama 3.1 8B via Ollama generator (temp 0), metrics, and seed 42" while declaring "**The one thing that varies:** `config/architectures/model_a.yaml` and `model_b.yaml` differ on exactly one line — `embedding_model`", clearly identifying that the generator, chunker, and dataset are fixed while only the embedding model under test varies._

