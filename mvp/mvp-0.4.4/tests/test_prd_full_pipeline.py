"""
Full pipeline PRD acceptance test — MVP 0.4.4.

Reads a PRD markdown file, runs full decomposition pipeline
(PRD conversion → tree build), logs to file + real-time output.

Usage:
    cd mvp/mvp-0.4.4
    python tests/test_prd_full_pipeline.py --prd ../../benchmark/test_cases/medium/order_prd.md

Output: output/prd_pipeline_test/
"""
import argparse
import json
import os
import sys
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from api_client import APIClient
from tree_builder import TreeBuilder
from prd_converter import PRDConverter


def setup_logger(output_dir: str, prd_name: str) -> logging.Logger:
    """Setup dual-output logger: file + console with timestamps."""
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, f"{prd_name}_pipeline.log")

    logger = logging.getLogger("pipeline")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # File handler — full detail
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(fh)

    # Console handler — info and above
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)

    logger.info(f"Log file: {log_path}")
    return logger


def collect_tree_stats(root):
    """Recursively collect tree statistics."""
    stats = {"total": 0, "parents": 0, "leaves": 0, "with_code": 0,
             "needs_human": 0, "routing": 0, "max_depth": 0}

    def walk(n):
        stats["total"] += 1
        stats["max_depth"] = max(stats["max_depth"], n.depth)
        if n.children:
            stats["parents"] += 1
            if n.code:
                stats["with_code"] += 1
            # Detect routing: any child behavior mentions sibling by name
            names = {c.name for c in n.children}
            for child in n.children:
                contract = n.children_contracts.get(child.name)
                if not contract:
                    continue
                bh = (contract.behavior or "").lower()
                for sib in names:
                    if sib != child.name and sib.lower() in bh:
                        stats["routing"] += 1
                        break
        else:
            stats["leaves"] += 1
            if n.code:
                stats["with_code"] += 1
        if n.needs_human_intervention:
            stats["needs_human"] += 1
        for c in (n.children or []):
            walk(c)

    walk(root)
    return stats


def main():
    parser = argparse.ArgumentParser(description="PRD Full Pipeline Test — MVP 0.4.4")
    parser.add_argument("--prd", type=str, required=True, help="Path to PRD markdown file")
    parser.add_argument("--max-depth", type=int, default=5, help="Max tree depth (default: 5)")
    parser.add_argument("--max-children", type=int, default=8, help="Max children per node (default: 8)")
    parser.add_argument("--max-retries", type=int, default=2, help="Max decompose/codegen retries")
    parser.add_argument("--skip-prd-convert", action="store_true", help="Skip PRD conversion (use cached)")
    parser.add_argument("--skip-interface-plan", action="store_true", help="Skip interface planning")
    parser.add_argument("--skip-interface-codegen", action="store_true", help="Skip interface code generation")
    args = parser.parse_args()

    prd_path = Path(args.prd)
    if not prd_path.exists():
        print(f"ERROR: PRD file not found: {args.prd}")
        return 1

    prd_name = prd_path.stem

    # Config
    config = Config(
        max_depth=args.max_depth,
        max_children=args.max_children,
        max_decompose_retries=args.max_retries,
        max_retries=args.max_retries,
        output_dir=os.path.join(os.path.dirname(__file__), "..", "output", "prd_pipeline_test"),
    )
    output_dir = config.output_dir
    logger = setup_logger(output_dir, prd_name)

    logger.info("=" * 60)
    logger.info(f"PRD FULL PIPELINE TEST")
    logger.info(f"PRD: {args.prd}")
    logger.info(f"Config: max_depth={config.max_depth}, max_children={config.max_children}, "
                f"max_retries={config.max_retries}, model={config.model}")
    logger.info("=" * 60)

    api_client = APIClient(config)

    # Connection test
    try:
        ok = api_client.test_connection()
        if not ok:
            logger.error("API connection failed")
            return 1
        logger.info(f"API connection OK (model: {config.model})")
    except Exception as e:
        logger.error(f"API connection error: {e}")
        return 1

    total_start = time.time()

    # Stage 0: PRD Conversion
    if not args.skip_prd_convert:
        logger.info("--- Stage 0: PRD Conversion ---")
        prd_converter = PRDConverter(config, api_client)
        json_prd = prd_converter.convert(str(prd_path))
        prd_cache = os.path.join(output_dir, ".chronos")
        os.makedirs(prd_cache, exist_ok=True)
        with open(os.path.join(prd_cache, "prd.json"), "w", encoding="utf-8") as f:
            json.dump(json_prd.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info(f"PRD converted: {len(json_prd.functional_requirements)} FRs, "
                    f"{len(json_prd.global_state_sources)} data sources, "
                    f"input_spec={json_prd.input_spec is not None}, "
                    f"output_spec={json_prd.output_spec is not None}")
    else:
        # Load cached
        prd_cache = os.path.join(output_dir, ".chronos", "prd.json")
        with open(prd_cache, "r", encoding="utf-8") as f:
            from models import JsonPRD
            json_prd = JsonPRD.from_dict(json.load(f))
        logger.info(f"PRD loaded from cache: {prd_cache}")

    # Stage 1: Interface Planning (optional)
    interface_plan = None
    if not args.skip_interface_plan:
        logger.info("--- Stage 1: Interface Planning ---")
        from interface_planner import InterfacePlanner
        planner = InterfacePlanner(config, api_client)
        interface_plan = planner.plan(json_prd)
        plan_path = os.path.join(output_dir, "interface_plan.json")
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(interface_plan.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info(f"Interface plan: {len(interface_plan.resources)} resources, "
                    f"{len(interface_plan.interfaces)} interfaces")

        # Stage 2: Interface Codegen (optional)
        if not args.skip_interface_codegen:
            logger.info("--- Stage 2: Interface Codegen ---")
            from interface_impl_generator import InterfaceImplementationGenerator
            gen = InterfaceImplementationGenerator(config, api_client)
            generated_dir = os.path.join(output_dir, "generated")
            os.makedirs(generated_dir, exist_ok=True)
            gen.generate(interface_plan)
            logger.info(f"Interface code generated: {generated_dir}")

    # Stage 3: Tree Building (core)
    logger.info("--- Stage 3: Tree Building ---")
    logger.info("")

    # Build root node from PRD
    from main import create_root_from_prd
    root = create_root_from_prd(str(prd_path), json_prd=json_prd)
    logger.info(f"Root node: {root.name} ({len(root.global_vars)} global_vars, "
                f"{len(root.data_sources)} data_sources)")

    builder = TreeBuilder(config=config, interface_plan=interface_plan, api_client=api_client)

    tree_start = time.time()
    root = builder.build_tree(root)
    tree_elapsed = time.time() - tree_start

    # Stats
    stats = collect_tree_stats(root)
    total_elapsed = time.time() - total_start

    logger.info("")
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total elapsed: {total_elapsed:.0f}s (tree build: {tree_elapsed:.0f}s)")
    logger.info(f"Tree nodes: {stats['total']} total "
                f"({stats['parents']} parents, {stats['leaves']} leaves)")
    logger.info(f"Max depth reached: {stats['max_depth']}")
    logger.info(f"Nodes with generated code: {stats['with_code']}/{stats['total']}")
    logger.info(f"Nodes needing human intervention: {stats['needs_human']}")
    logger.info(f"Routing violations: {stats['routing']}/{stats['parents']} parent nodes")
    if stats['parents'] > 0:
        rrate = stats['routing'] / stats['parents'] * 100
        verdict = "PASS" if rrate < 10 else "FAIL"
        logger.info(f"Routing rate: {rrate:.0f}% — Verdict: {verdict}")
    logger.info(f"Conservation violations: {sum(1 for n in _walk_for_conservation(root))}")

    # Save tree
    tree_path = os.path.join(output_dir, f"{prd_name}_decomposition_tree.json")
    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(root.to_dict(), f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Tree saved: {tree_path}")

    # Per-node detail log (to file only)
    _log_node_tree(root, logger)
    return 0


def _walk_for_conservation(root):
    """Helper: yield nodes that have conservation data."""
    if root.global_vars and root.children:
        yield root
    for c in (root.children or []):
        yield from _walk_for_conservation(c)


def _log_node_tree(node, logger, indent=0):
    """Log detailed node tree to DEBUG (file only)."""
    prefix = "  " * indent
    code_flag = " [CODE]" if node.code else ""
    human_flag = " [HUMAN]" if node.needs_human_intervention else ""
    child_info = f" -> {len(node.children)} children" if node.children else " [LEAF]"
    logger.debug(f"{prefix}{node.name} (d={node.depth}){child_info}{code_flag}{human_flag}")
    for child in (node.children or []):
        _log_node_tree(child, logger, indent + 1)


if __name__ == "__main__":
    sys.exit(main())
