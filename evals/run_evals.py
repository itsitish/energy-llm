"""
Minimal eval runner for energy-llm.

Why this exists:
- Demonstrates basic AI engineering hygiene (golden set + automated checks).
- Verifies that answers stay grounded in the provided context.

This is intentionally lightweight: no external eval frameworks required.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from config import ELECTRICITY_CSV, HUMIDITY_CSV, TEMPERATURE_CSV, WEATHER_CSV, HOME_PROFILE_CSV
from data.loaders import load_elec, load_humidity, load_temperature, load_weather, load_home_profile
from insights import (
    build_household_context,
    humidity_summary,
    peak_usage_times,
    schedule_suggestion,
    tariff_recommendation,
    temperature_summary,
)


EVALS_DIR = Path(__file__).resolve().parent
GOLDEN_PATH = EVALS_DIR / "golden_qa.jsonl"


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    reasons: list[str]
    answer: str


def _load_cases(path: Path) -> list[dict[str, Any]]:
    """Load JSONL eval cases."""
    cases: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cases.append(json.loads(line))
    return cases


def _build_insight_text() -> str:
    """
    Build the exact style of context used in the notebook:
    - aggregated block
    - quick hits
    - simple summaries
    """
    elec = load_elec(ELECTRICITY_CSV)
    hum = load_humidity(HUMIDITY_CSV)
    temp = load_temperature(TEMPERATURE_CSV)
    weather = load_weather(WEATHER_CSV)
    home_profile = load_home_profile(HOME_PROFILE_CSV)

    # Tariff schedule (pence). Kept in sync with notebook defaults.
    tariff_config = {
        "standing_charge_p_per_day": 61.95,
        "base_rate_p_per_kwh": 20.88,
        "offpeak_rate_p_per_kwh": 15.68,
        "peak_rate_p_per_kwh": 38.98,
        "offpeak_windows": ["02:00-05:00"],
        "peak_windows": ["16:00-19:00"],
    }

    parts: list[str] = []
    parts.append(
        build_household_context(
            elec=elec,
            internal_temp=temp,
            internal_humidity=hum,
            weather=weather,
            home_profile=home_profile,
            tariff_config=tariff_config,
        )
    )

    if not elec.empty:
        peaks = peak_usage_times(elec)
        tariff = tariff_recommendation(elec)
        sched = schedule_suggestion(elec)
        parts.append(
            "QUICK HITS\n"
            f"- Peak usage hours: {peaks.get('peak_hours', [])}; peak days: {peaks.get('peak_days', [])}.\n"
            f"- Tariff: {tariff.get('recommendation', '')} (peak share {tariff.get('peak_share')}).\n"
            f"- Schedule: {sched.get('message', '')} Best hours: {sched.get('best_hours', [])}."
        )
    else:
        parts.append("QUICK HITS\n- No electricity data available.")

    t = temperature_summary(temp)
    h = humidity_summary(hum)
    if t.get("message") and "Not enough" not in t["message"]:
        parts.append(t["message"])
    if h.get("message") and "Not enough" not in h["message"]:
        parts.append(h["message"])

    return "\n\n".join([p for p in parts if p]).strip()


def _make_context_block(insight_text: str) -> str:
    """Wrap insight text with grounding instruction + output contract."""
    return (
        "You are an energy advisor. The text below is THIS household's energy data. "
        "Use ONLY this data to answer.\n"
        "If the answer is NOT explicitly present in the context, reply EXACTLY with: "
        "Not enough data in context to answer.\n"
        "Do not invent numbers or facts.\n\n"
        "Output format (follow exactly):\n"
        "Answer: <concise answer>\n"
        "Evidence: <copy 1-3 short relevant context lines>\n\n"
        "--- HOUSEHOLD DATA ---\n"
        f"{insight_text}\n"
        "--- END DATA ---"
    )


def _load_llm_pipeline():
    """
    Load a Transformers pipeline similarly to the notebook.
    Kept as a function so evals can still import without immediately loading a model.
    """
    try:
        import torch
        from transformers import pipeline
    except Exception as e:
        raise RuntimeError("Missing LLM deps. Install from requirements.txt and run again.") from e

    # Default to the same small model used in the notebook if present.
    model_id = "Qwen/Qwen2.5-1.5B-Instruct"

    device = -1
    torch_dtype = None
    if torch.backends.mps.is_available():
        device = "mps"
        torch_dtype = torch.float16
    elif torch.cuda.is_available():
        device = 0
        torch_dtype = torch.float16

    pipe = pipeline(
        "text-generation",
        model=model_id,
        device=device,
        torch_dtype=torch_dtype,
    )

    # Avoid passing GenerationConfig with unsupported flags (prevents warnings).
    gen_kwargs = {
        "max_new_tokens": 180,
        "do_sample": False,
        "pad_token_id": pipe.tokenizer.eos_token_id,
    }
    return pipe, gen_kwargs


def _generate_answer(pipe, gen_kwargs, context: str, question: str, feedback: str | None = None) -> str:
    """Generate an answer using the model chat template if available."""
    content = f"{context}\n\nQuestion: {question}"
    if feedback:
        content += f"\n\n{feedback}\n\nRegenerate the answer now, following the output format exactly."

    messages = [{"role": "user", "content": content}]
    prompt = pipe.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    out = pipe(prompt, **gen_kwargs)[0]["generated_text"]
    # Strip prompt echo
    if out.startswith(prompt):
        out = out[len(prompt) :].strip()
    return out.strip()


def _contains_any(text: str, needles: list[str]) -> bool:
    t = text.lower()
    return any(n.lower() in t for n in needles)


def _contains_none(text: str, needles: list[str]) -> bool:
    t = text.lower()
    return all(n.lower() not in t for n in needles)


def _number_overlap_score(answer: str, context: str) -> float:
    """
    Simple groundedness proxy: how many numeric tokens in the answer also appear in context.
    Returns 0..1 (not a perfect metric, just a sanity check).
    """
    nums_a = set(re.findall(r"[-+]?\d+(?:\.\d+)?", answer))
    if not nums_a:
        return 0.0
    nums_c = set(re.findall(r"[-+]?\d+(?:\.\d+)?", context))
    return float(len(nums_a & nums_c) / max(1, len(nums_a)))


def evaluate_case(*, case: dict[str, Any], answer: str, context: str) -> EvalResult:
    """Run rule-based checks for a single case."""
    reasons: list[str] = []
    must_any = case.get("must_include_any", [])
    must_not = case.get("must_not_include_any", [])

    if must_any and not _contains_any(answer, must_any):
        reasons.append(f"Missing required phrase (any of): {must_any}")
    if must_not and not _contains_none(answer, must_not):
        reasons.append(f"Contains forbidden phrase (one of): {must_not}")

    overlap = _number_overlap_score(answer, context)
    # Only enforce numeric overlap if the answer actually contains numbers.
    if re.search(r"\d", answer) and overlap < 0.4:
        reasons.append(f"Low numeric overlap with context: {overlap:.2f}")

    return EvalResult(case_id=case["id"], passed=(len(reasons) == 0), reasons=reasons, answer=answer)


def main() -> int:
    """Run all eval cases and print a compact report."""
    if not GOLDEN_PATH.exists():
        raise FileNotFoundError(f"Missing eval file: {GOLDEN_PATH}")

    cases = _load_cases(GOLDEN_PATH)
    insight_text = _build_insight_text()
    context = _make_context_block(insight_text)

    pipe, gen_kwargs = _load_llm_pipeline()

    results: list[EvalResult] = []
    max_retries = 3
    for case in cases:
        last_result: EvalResult | None = None
        feedback: str | None = None
        for _attempt in range(max_retries):
            ans = _generate_answer(pipe, gen_kwargs, context=context, question=case["question"], feedback=feedback)
            res = evaluate_case(case=case, answer=ans, context=context)
            last_result = res
            if res.passed:
                break

            # Provide targeted feedback to the model and retry.
            must_any = case.get("must_include_any", [])
            must_not = case.get("must_not_include_any", [])
            reasons = "\n".join([f"- {r}" for r in res.reasons]) if res.reasons else "(no reasons)"
            feedback = (
                "Constraint feedback (your previous answer failed checks):\n"
                f"{reasons}\n"
                f"Required phrases (include at least one): {must_any}\n"
                f"Forbidden phrases (include none): {must_not}\n"
                "Regenerate now. Ensure you explicitly include the required phrases when they are present in the context."
            )

        assert last_result is not None
        results.append(last_result)

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"Eval summary: {passed}/{total} passed")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"- {status} {r.case_id}")
        if not r.passed:
            for reason in r.reasons:
                print(f"  - {reason}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

