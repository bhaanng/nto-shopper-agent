"""
GEPA optimizer for per-customer prompt overlays.

Usage:
    python scripts/gepa_optimize.py --customer NTOManaged
    python scripts/gepa_optimize.py --customer NTOManaged --max-evals 100

What it does:
- Loads the base system prompt (never modified)
- Loads the customer's current overlay as the seed candidate
- Runs GEPA to iteratively improve the overlay using a test dataset
- Writes the best overlay back to customers/{customer_id}.yaml

The base prompt is never touched. Only the overlay evolves.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Make agent modules importable
sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))

from customer_prompts import (
    get_system_prompt_for_customer,
    load_customer_overlay,
    save_customer_overlay,
)
from nto_agent import NTOAgent

try:
    from gepa.optimize_anything import GEPAConfig, EngineConfig, ReflectionConfig, optimize_anything
except ImportError:
    print("❌  GEPA not installed. Run: pip install gepa pyyaml")
    sys.exit(1)


# ── Evaluation dataset ───────────────────────────────────────────────────────
# Each example has an `input` (user query) and `criteria` (what a good response
# must contain). Add more examples here or load from a JSON file.

DEFAULT_EXAMPLES = [
    {
        "input": "I need waterproof hiking boots for a Pacific Northwest trip",
        "criteria": ["waterproof", "boot", "product"],
    },
    {
        "input": "What's a good lightweight jacket for hiking?",
        "criteria": ["jacket", "lightweight", "product"],
    },
    {
        "input": "I'm hiking the Enchantments in October, what gear do I need?",
        "criteria": ["layer", "waterproof", "boot"],
    },
    {
        "input": "Show me camping tents under $200",
        "criteria": ["tent", "price", "product"],
    },
    {
        "input": "What's the difference between down and synthetic insulation?",
        "criteria": ["down", "synthetic", "temperature"],
    },
    {
        "input": "I need gear for a beginner backpacking trip",
        "criteria": ["pack", "tent", "sleep"],
    },
    {
        "input": "Do you have sustainable or recycled outdoor gear?",
        "criteria": ["recycled", "sustainable", "eco"],
    },
    {
        "input": "I want to build a full hiking kit under $300",
        "criteria": ["jacket", "boot", "pack"],
    },
]


# ── Agent runner ─────────────────────────────────────────────────────────────

def _make_agent(customer_id: str, overlay: str) -> NTOAgent:
    """Spin up an agent with the given overlay injected."""
    from customer_prompts import get_system_prompt, _OVERLAY_SECTION
    from system_prompt import get_system_prompt as base_prompt

    agent = NTOAgent(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        base_url=os.getenv("ANTHROPIC_BASE_URL"),
        scapi_token_url=os.getenv("SCAPI_TOKEN_URL"),
        scapi_client_credentials=os.getenv("SCAPI_CLIENT_CREDENTIALS"),
        scapi_search_url=os.getenv("SCAPI_SEARCH_URL"),
        scapi_site_id=os.getenv("SCAPI_SITE_ID", "NTOManaged"),
        customer_id=None,  # we inject the prompt manually below
    )
    # Override system prompt with base + candidate overlay
    agent.system_prompt = base_prompt() + _OVERLAY_SECTION.format(overlay=overlay.strip())
    return agent


def _score_response(response: dict, criteria: list[str]) -> float:
    """
    Score a response 0–1 based on:
    - Whether the agent returned a valid structured response (0.3)
    - Whether key criteria words appear in the response text (0.7)
    """
    if not isinstance(response, dict) or "response" not in response:
        return 0.0

    score = 0.3  # valid structure

    response_text = " ".join(
        block.get("content", "")
        for block in response.get("response", [])
        if block.get("type") == "markdown"
    ).lower()

    if response_text:
        hits = sum(1 for c in criteria if c.lower() in response_text)
        score += 0.7 * (hits / len(criteria))

    return round(score, 3)


# ── GEPA evaluator ───────────────────────────────────────────────────────────

def make_evaluator(customer_id: str, examples: list[dict]):
    """Return a GEPA-compatible evaluator closure."""

    def evaluate(candidate_overlay: str, batch: list[dict]):
        scores = []
        logs = []

        for ex in batch:
            agent = _make_agent(customer_id, candidate_overlay)
            t0 = time.monotonic()
            try:
                response = agent.chat(ex["input"], max_iterations=3)
                score = _score_response(response, ex["criteria"])
                elapsed = (time.monotonic() - t0) * 1000
                logs.append(f"[{score:.2f}] ({elapsed:.0f}ms) {ex['input'][:60]}")
            except Exception as e:
                score = 0.0
                logs.append(f"[0.00] ERROR: {e} | {ex['input'][:60]}")

            scores.append(score)

        avg = sum(scores) / len(scores)
        side_info = {
            "scores": {"accuracy": avg},
            "log": "\n".join(logs),
            "per_example_scores": scores,
        }
        return avg, side_info

    return evaluate


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run GEPA optimization for a customer overlay")
    parser.add_argument("--customer", required=True, help="Customer ID (e.g. NTOManaged)")
    parser.add_argument("--max-evals", type=int, default=50, help="Max metric calls (default 50)")
    parser.add_argument("--examples", type=str, default=None, help="Path to JSON examples file")
    parser.add_argument("--reflection-lm", type=str, default="openai/gpt-4o", help="LLM for GEPA reflection")
    args = parser.parse_args()

    customer_id = args.customer

    # Load examples
    if args.examples:
        with open(args.examples) as f:
            examples = json.load(f)
    else:
        examples = DEFAULT_EXAMPLES
        print(f"Using {len(examples)} built-in examples (pass --examples path.json to use your own)")

    # Load seed overlay
    seed_overlay = load_customer_overlay(customer_id)
    if seed_overlay is None:
        print(f"⚠️  No overlay found for '{customer_id}', starting from empty seed.")
        seed_overlay = "- Provide helpful, accurate product recommendations for NTO customers."

    print(f"\n🏔️  GEPA Optimizer — customer: {customer_id}")
    print(f"   Max evals: {args.max_evals} | Examples: {len(examples)}")
    print(f"   Reflection LM: {args.reflection_lm}")
    print(f"   Seed overlay ({len(seed_overlay)} chars):\n")
    print("   " + seed_overlay[:200].replace("\n", "\n   ") + ("..." if len(seed_overlay) > 200 else ""))
    print()

    evaluator = make_evaluator(customer_id, examples)

    # Split examples into train / val
    split = max(1, len(examples) * 3 // 4)
    trainset = examples[:split]
    valset = examples[split:]

    result = optimize_anything(
        seed_candidate=seed_overlay,
        evaluator=evaluator,
        objective=(
            "Improve the customer-specific overlay so the agent gives more relevant, "
            "accurate, and helpful outdoor gear recommendations. The overlay should "
            "add useful guidance without conflicting with the base prompt."
        ),
        dataset=trainset,
        valset=valset if valset else None,
        config=GEPAConfig(
            engine=EngineConfig(
                max_metric_calls=args.max_evals,
                parallel=False,  # agent calls are already parallel internally
                capture_stdio=True,
            ),
            reflection=ReflectionConfig(
                reflection_lm=args.reflection_lm,
                reflection_minibatch_size=2,
            ),
        ),
    )

    best_overlay = result.best_candidate
    best_score = getattr(result, "best_score", None)

    print(f"\n✅  Optimization complete.")
    print(f"   Best score: {best_score}")
    print(f"   Best overlay:\n")
    print("   " + best_overlay[:400].replace("\n", "\n   "))

    save_customer_overlay(
        customer_id,
        best_overlay,
        metadata={
            "last_optimized": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "best_score": best_score,
            "optimization_runs": 1,
        },
    )
    print(f"\n💾  Saved to customers/{customer_id}.yaml")


if __name__ == "__main__":
    main()
