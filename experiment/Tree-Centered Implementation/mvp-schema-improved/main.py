"""
CLI entry point for the decomposition tree builder.
Usage:
    python main.py --input test_prd.md --output output
    python main.py --input test_prd.md --max-depth 4 --temperature 0.2
"""
import argparse
import json
import os
import sys
from typing import Any, Dict

from config import Config
from tree_builder import TreeBuilder
from api_client import APIClient
from prd_converter import PRDConverter
from models import Node, InputParam, OutputParam, Boundary, GlobalVar, JsonPRD, DataSource, SubPRD, Traceability, StateOperation, AcceptanceCriterion


def create_root_from_prd(prd_path: str, name: str = None, json_prd: JsonPRD = None) -> Node:
    with open(prd_path, "r", encoding="utf-8") as f:
        prd_content = f.read()

    system_name = name or os.path.splitext(os.path.basename(prd_path))[0]
    safe_name = "".join(c if c.isalnum() else "_" for c in system_name)
    safe_name = safe_name[0].upper() + safe_name[1:] if safe_name else "System"

    if json_prd:
        purpose = json_prd.metadata.get("project_name", safe_name)
        data_sources = []
        global_vars = []
        global_state_ops = []
        for i, gss in enumerate(json_prd.global_state_sources):
            ds = DataSource(
                name=gss.source_id,
                category="memory",
                access="read_write",
                data_type=gss.type,
                description=gss.description
            )
            data_sources.append(ds)
            gv = GlobalVar(
                name=gss.source_id,
                type="list",
                access="read_write",
                description=gss.description,
                data_source=gss.source_id,
                data_type=gss.type,
                operations=["read", "write"]
            )
            global_vars.append(gv)
            gso = StateOperation(
                op_id=f"op_root_{i}",
                source_id=gss.source_id,
                op_type="read_then_write",
                target={"item_path": "root", "condition": ""},
                payload={"fields": list(gss.item_schema.keys()) if gss.item_schema else [], "new_value": "derived"},
                constraint=f"manage_{gss.source_id}",
                depends_on=""
            )
            global_state_ops.append(gso)

        root = Node(
            node_id="root",
            name=safe_name,
            depth=0,
            purpose=purpose,
            inputs=[InputParam(name="input", type="Any", description="System input")],
            outputs=[OutputParam(name="output", type="Any", description="System output")],
            boundary=Boundary(
                in_scope=["All functionality described in the input"],
                out_of_scope=["Functionality not described in the input"]
            ),
            data_sources=data_sources,
            global_vars=global_vars
        )
        fr_text = "\n".join(
            f"[{fr.fr_id}] {fr.title}: {fr.description}"
            for fr in json_prd.functional_requirements
        )

        def _build_spec_text(spec: Dict[str, Any], label: str) -> str:
            lines = [f"{label}:"]
            fmt = spec.get("format", "")
            if fmt:
                lines.append(f"  Format: {fmt}")
            desc = spec.get("description", "")
            if desc:
                lines.append(f"  Description: {desc}")
            schema = spec.get("schema", {})
            if schema:
                lines.append(f"  Schema:")
                for k, v in schema.items():
                    lines.append(f"    {k}: {v}")
            examples = spec.get("examples", [])
            if examples:
                lines.append(f"  Examples:")
                for ex in examples:
                    ex_str = json.dumps(ex) if isinstance(ex, dict) else str(ex)
                    lines.append(f"    {ex_str}")
            return "\n".join(lines)

        io_parts = []
        if json_prd.input_spec:
            io_parts.append(_build_spec_text(json_prd.input_spec, "INPUT FORMAT"))
        if json_prd.output_spec:
            io_parts.append(_build_spec_text(json_prd.output_spec, "OUTPUT FORMAT"))
        io_text = "\n\n".join(io_parts)
        description = f"{io_text}\n\nFunctional Requirements:\n{fr_text}" if io_text else f"Functional Requirements:\n{fr_text}"

        tc = json_prd.technical_constraints
        constraints = []
        if tc:
            if tc.storage:
                constraints.append({"constraint_id": "TC-STORAGE", "description": f"Storage: {tc.storage.get('type', 'memory')} - {tc.storage.get('details', '')}"})
            if tc.concurrency:
                constraints.append({"constraint_id": "TC-CONCURRENCY", "description": f"Concurrency: {tc.concurrency.get('model', 'single-user')}, auth_required: {tc.concurrency.get('auth_required', False)}"})
            if tc.ui:
                constraints.append({"constraint_id": "TC-UI", "description": f"UI: {tc.ui.get('type', 'cli')}"})
            if tc.language:
                constraints.append({"constraint_id": "TC-LANGUAGE", "description": f"Language: {tc.language}"})

        root.subprd = SubPRD(
            task_id="root",
            purpose=purpose,
            description=description,
            constraints=constraints,
            acceptance_criteria=[
                AcceptanceCriterion(
                    ac_id=ac.ac_id,
                    description=ac.description,
                    verification_method=ac.verification_method
                )
                for ac in json_prd.acceptance_criteria
            ],
            traceability=Traceability(
                parent_requirement_ids=[fr.fr_id for fr in json_prd.functional_requirements]
            ),
            global_state_operations=global_state_ops
        )
        return root

    lines = [l.strip() for l in prd_content.split("\n") if l.strip() and not l.startswith("#")]
    purpose = " ".join(lines[:10])

    return Node(
        node_id="root",
        name=safe_name,
        depth=0,
        purpose=purpose,
        inputs=[InputParam(name="input", type="Any", description="System input")],
        outputs=[OutputParam(name="output", type="Any", description="System output")],
        boundary=Boundary(
            in_scope=["All functionality described in the input"],
            out_of_scope=["Functionality not described in the input"]
        )
    )


def main():
    parser = argparse.ArgumentParser(
        description="Decomposition Tree Builder - Build decomposition trees from PRD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py --input test_prd.md
    python main.py --input test_prd.md --output my_output --name MySystem
    python main.py --input prd.txt --max-depth 4 --max-children 6
    python main.py --input prd.txt --temperature 0.2 --max-retries 5
        """
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the PRD input file"
    )

    parser.add_argument(
        "--output", "-o",
        default="output",
        help="Output directory for generated files (default: output)"
    )

    parser.add_argument(
        "--name", "-n",
        default=None,
        help="System name (default: derived from input filename)"
    )

    parser.add_argument(
        "--max-depth",
        type=int,
        default=3,
        help="Maximum decomposition depth (default: 3)"
    )

    parser.add_argument(
        "--max-children",
        type=int,
        default=4,
        help="Maximum children per node (default: 4)"
    )

    parser.add_argument(
        "--max-lines",
        type=int,
        default=50,
        help="Lines threshold for semantic stopping (default: 50)"
    )

    parser.add_argument(
        "--temperature", "-t",
        type=float,
        default=0.3,
        help="LLM temperature (default: 0.3)"
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum API retries (default: 3)"
    )

    parser.add_argument(
        "--max-decompose-retries",
        type=int,
        default=3,
        help="Maximum decomposition retries on failure (default: 3)"
    )

    parser.add_argument(
        "--api-key",
        default=None,
        help="DeepSeek API key (or set DEEPSEEK_API_KEY env variable)"
    )

    parser.add_argument(
        "--base-url",
        default="https://api.deepseek.com",
        help="API base URL (default: https://api.deepseek.com)"
    )

    parser.add_argument(
        "--model",
        default="deepseek-chat",
        help="Model name (default: deepseek-chat)"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="API timeout in seconds (default: 120)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--skip-prd-convert",
        action="store_true",
        help="Skip PRD to JsonPRD conversion (use legacy text truncation)"
    )

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    api_key = args.api_key or os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("Error: API key not provided. Set DEEPSEEK_API_KEY environment variable or use --api-key")
        sys.exit(1)

    config = Config(
        api_key=api_key,
        base_url=args.base_url,
        model=args.model,
        max_depth=args.max_depth,
        max_children=args.max_children,
        max_lines_threshold=args.max_lines,
        temperature=args.temperature,
        max_retries=args.max_retries,
        max_decompose_retries=args.max_decompose_retries,
        timeout=args.timeout,
        output_dir=args.output,
        nodes_dir=os.path.join(args.output, "nodes")
    )

    print("=" * 60)
    print("Decomposition Tree Builder")
    print("=" * 60)
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"System: {config.nodes_dir}")
    print()
    print("Configuration:")
    print(f"  max_depth: {config.max_depth}")
    print(f"  max_children: {config.max_children}")
    print(f"  max_lines_threshold: {config.max_lines_threshold}")
    print(f"  temperature: {config.temperature}")
    print(f"  max_retries: {config.max_retries}")
    print(f"  max_decompose_retries: {config.max_decompose_retries}")
    print()

    json_prd = None
    if not args.skip_prd_convert:
        with open(args.input, "r", encoding="utf-8") as f:
            prd_text = f.read()
        api_client = APIClient(config)
        converter = PRDConverter(config, api_client)
        json_prd = converter.convert_and_save(prd_text, args.output)

    root_node = create_root_from_prd(args.input, args.name, json_prd)

    print(f"Root node: {root_node.name}")
    print(f"Purpose: {root_node.purpose[:80]}...")
    if json_prd:
        print(f"Data Sources: {len(json_prd.global_state_sources) if json_prd.global_state_sources else 0}")
    print()

    builder = TreeBuilder(config)

    print("Starting decomposition-verification loop...")
    print("-" * 60)

    result = builder.build_tree(root_node)

    print("-" * 60)
    print()

    tree_filename = f"{root_node.name.lower()}_decomposition_tree.json"
    tree_path = builder.save_tree(result, tree_filename)

    total_nodes = sum(1 for _ in [result]) + sum(len(c.children) for c in result.children)

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Root: {result.name}")
    print(f"Children: {len(result.children)}")
    print(f"Validation: {'PASSED' if result.validation.passed else 'FAILED'}")
    print(f"Tree saved: {tree_path}")

    nodes_dir = config.nodes_dir
    if os.path.exists(nodes_dir):
        files = sorted(os.listdir(nodes_dir))
        print(f"Generated {len(files)} code files in {nodes_dir}/")
        if args.verbose:
            for f in files:
                print(f"  - {f}")

    print("=" * 60)


if __name__ == "__main__":
    main()
