"""
CLI entry point for the decomposition tree builder.
Usage:
    python main.py --input test_prd.md --output output
    python main.py --input test_prd.md --max-depth 4 --temperature 0.2
"""
import argparse
import os
import sys

from config import Config
from tree_builder import TreeBuilder
from models import Node, InputParam, OutputParam, Boundary, GlobalVar


def create_root_from_prd(prd_path: str, name: str = None) -> Node:
    with open(prd_path, "r", encoding="utf-8") as f:
        prd_content = f.read()

    lines = [l.strip() for l in prd_content.split("\n") if l.strip() and not l.startswith("#")]
    purpose = " ".join(lines[:10])

    system_name = name or os.path.splitext(os.path.basename(prd_path))[0]
    safe_name = "".join(c if c.isalnum() else "_" for c in system_name)
    safe_name = safe_name[0].upper() + safe_name[1:] if safe_name else "System"

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

    root_node = create_root_from_prd(args.input, args.name)

    print(f"Root node: {root_node.name}")
    print(f"Purpose: {root_node.purpose[:80]}...")
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
