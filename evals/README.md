## Evals (golden Q&A)

This folder contains a tiny, explainable evaluation harness to show that the LLM answers are:

- **Grounded** in the provided household context (no “I don’t have access to data”).
- **Consistent** with key numbers in the context (basic overlap checks).
- **Stable** across runs (optional deterministic generation settings).

### Files

- `golden_qa.jsonl`: newline-delimited JSON test cases.
- `run_evals.py`: runs the model on all cases and prints a score summary.

### Run

From repo root:

```bash
python evals/run_evals.py
```

### Output contract

The runner assumes the model follows this strict format:

- `Answer: ...`
- `Evidence: ...` (short relevant context lines)

If the answer is not explicitly present in the provided context, the model must reply exactly:

`Not enough data in context to answer.`

### What gets checked

For each golden test case, `run_evals.py` checks:

- forbidden phrases (e.g. “I don’t have access…”)
- required keywords (per the golden file)
- basic numeric overlap sanity (so answers use context numbers when present)

If a case fails, the runner regenerates with constraint feedback up to a small retry limit.

