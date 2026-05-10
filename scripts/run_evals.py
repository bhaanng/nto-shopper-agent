"""
CLI entry point for NTO agent evals.

Usage (from nto-agent/ root):
    python scripts/run_evals.py
    python scripts/run_evals.py --customer NTOManaged
    python scripts/run_evals.py --customer NTOManaged --sample 20
    python scripts/run_evals.py --dataset data/nto_eval_dataset.json --output results/run1.json
    python scripts/run_evals.py --workers 5 --metric cognitive_load
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.runner import run_evals, print_report


def main():
    parser = argparse.ArgumentParser(
        description="Run NTO shopper agent evals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--customer",
        default=None,
        metavar="CUSTOMER_ID",
        help="Customer profile to use (e.g. NTOManaged). Defaults to base prompt.",
    )
    parser.add_argument(
        "--dataset",
        default="data/nto_eval_dataset.json",
        metavar="PATH",
        help="Path to the eval dataset JSON file (default: data/nto_eval_dataset.json)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        metavar="N",
        help="Run only the first N cases (useful for quick smoke tests)",
    )
    parser.add_argument(
        "--metric",
        default=None,
        metavar="METRIC_NAME",
        help="Filter dataset to a single metric (e.g. cognitive_load)",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        metavar="PROXY_NAME",
        help="Filter dataset to a single proxy (e.g. constrained_choice_framing)",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Write full JSON results to this file",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        metavar="N",
        help="Number of parallel eval workers (default: 3)",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: dataset not found: {dataset_path}", file=sys.stderr)
        sys.exit(1)

    with open(dataset_path) as f:
        dataset = json.load(f)

    if args.metric:
        dataset = [c for c in dataset if c.get("metric") == args.metric]
        if not dataset:
            print(f"Error: no cases found for metric '{args.metric}'", file=sys.stderr)
            sys.exit(1)

    if args.proxy:
        dataset = [c for c in dataset if c.get("proxy") == args.proxy]
        if not dataset:
            print(f"Error: no cases found for proxy '{args.proxy}'", file=sys.stderr)
            sys.exit(1)

    if args.sample:
        dataset = dataset[: args.sample]

    print(f"Customer  : {args.customer or '(base — no overlay)'}")
    print(f"Dataset   : {dataset_path} ({len(dataset)} cases)")
    if args.metric:
        print(f"Metric    : {args.metric}")
    if args.proxy:
        print(f"Proxy     : {args.proxy}")

    result = run_evals(dataset, customer_id=args.customer, max_workers=args.workers)
    print_report(result)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Results written to {output_path}")


if __name__ == "__main__":
    main()
