"""
Generate prerequisites for routing ablation experiment.
Converts 3 medium PRDs to JSON PRD + Interface Plan using the original pipeline.
"""
import json
import os
import sys
import time

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mvp", "mvp-0.4.4"))

from config import Config
from api_client import APIClient
from prd_converter import PRDConverter
from interface_planner import InterfacePlanner


BENCHMARK_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "benchmark", "test_cases", "medium")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "routing_ablation", "prerequisites")

PRDS = [
    ("order", "order_prd.md"),
    ("grade", "grade_prd.md"),
    ("project", "project_prd.md"),
]


def main():
    # Config from env (same as other test scripts)
    def _env(key, default=""):
        return os.getenv(key) or os.getenv(f"DEEPSEEK_{key.removeprefix('CHRONOS_')}") or default

    config = Config(
        api_key=_env("CHRONOS_API_KEY"),
        base_url=_env("CHRONOS_BASE_URL", "https://api.deepseek.com"),
        model=_env("CHRONOS_MODEL", "deepseek-chat"),
        temperature=float(os.getenv("CHRONOS_TEMPERATURE", "0.3")),
    )

    if not config.api_key:
        print("ERROR: Set CHRONOS_API_KEY (or DEEPSEEK_API_KEY)")
        return 1

    print(f"API: {config.base_url}")
    print(f"Model: {config.model}")
    print(f"Benchmark dir: {BENCHMARK_DIR}")
    print(f"Output dir: {OUTPUT_DIR}")

    client = APIClient(config)
    converter = PRDConverter(config, client)
    planner = InterfacePlanner(config, client)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for prd_name, prd_filename in PRDS:
        prd_path = os.path.join(BENCHMARK_DIR, prd_filename)
        if not os.path.exists(prd_path):
            print(f"ERROR: PRD not found: {prd_path}")
            return 1

        with open(prd_path, "r", encoding="utf-8") as f:
            prd_text = f.read()

        prd_output_dir = os.path.join(OUTPUT_DIR, prd_name)
        os.makedirs(os.path.join(prd_output_dir, ".chronos"), exist_ok=True)

        print(f"\n{'='*60}")
        print(f"  Processing: {prd_name}")
        print(f"{'='*60}")

        # Phase 1: PRD -> JSON PRD
        print(f"  [Phase 1] Converting PRD to JSON...")
        t0 = time.time()
        try:
            json_prd = converter.convert(prd_text)
        except Exception as e:
            print(f"  ERROR in PRD conversion: {e}")
            continue
        elapsed = time.time() - t0
        print(f"  Done ({elapsed:.1f}s)")

        if json_prd is None:
            print(f"  ERROR: PRD conversion returned None")
            continue

        # Save JSON PRD
        prd_json_path = os.path.join(prd_output_dir, ".chronos", "prd.json")
        with open(prd_json_path, "w", encoding="utf-8") as f:
            json.dump(json_prd.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"  Saved: {prd_json_path}")

        # Phase 2: JSON PRD -> Interface Plan
        print(f"  [Phase 2] Generating Interface Plan...")
        t0 = time.time()
        try:
            interface_plan = planner.plan(json_prd)
        except Exception as e:
            print(f"  ERROR in Interface Planning: {e}")
            continue
        elapsed = time.time() - t0
        print(f"  Done ({elapsed:.1f}s)")

        if interface_plan is None:
            print(f"  ERROR: Interface planning returned None")
            continue

        # Save Interface Plan
        plan_json_path = os.path.join(prd_output_dir, "interface_plan.json")
        with open(plan_json_path, "w", encoding="utf-8") as f:
            f.write(interface_plan.to_json(indent=2))
        print(f"  Saved: {plan_json_path}")

        # Summary
        n_fr = len(json_prd.functional_requirements) if hasattr(json_prd, 'functional_requirements') else 0
        n_ifaces = len(interface_plan.interfaces) if hasattr(interface_plan, 'interfaces') else 0
        n_resources = len(interface_plan.resources) if hasattr(interface_plan, 'resources') else 0
        print(f"  Summary: {n_fr} FRs, {n_resources} resources, {n_ifaces} interfaces")

    print(f"\n{'='*60}")
    print(f"  All prerequisites generated in: {OUTPUT_DIR}")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
