"""
Test script for Phase 5: TreeBuilder main controller.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from tree_builder import TreeBuilder, create_root_node_from_prd
from models import Node, InputParam, OutputParam, Boundary


def test_tree_builder_simple():
    print("=" * 60)
    print("Phase 5 Test: TreeBuilder - Simple System")
    print("=" * 60 + "\n")
    
    config = Config.from_env()
    
    if not config.api_key:
        print("WARNING: DEEPSEEK_API_KEY not set, skipping test")
        return
    
    builder = TreeBuilder(config)
    
    root_node = Node(
        node_id="root",
        name="SimpleCalculator",
        depth=0,
        purpose="A simple calculator that can add, subtract, multiply and divide two numbers. Returns the result and any error message.",
        inputs=[
            InputParam(name="operation", type="str", description="Operation: add, subtract, multiply, divide"),
            InputParam(name="a", type="float", description="First number"),
            InputParam(name="b", type="float", description="Second number")
        ],
        outputs=[
            OutputParam(name="result", type="float", description="Calculation result"),
            OutputParam(name="error", type="Optional[str]", description="Error message if any")
        ],
        boundary=Boundary(
            in_scope=["basic arithmetic", "division by zero handling"],
            out_of_scope=["advanced math", "complex numbers", "history"]
        )
    )
    
    print(f"Building tree for: {root_node.name}")
    print(f"Purpose: {root_node.purpose}")
    print()
    
    result = builder.build_tree(root_node)
    
    print()
    print("=" * 60)
    print("Tree Structure:")
    print("=" * 60)
    
    def print_tree(node: Node, indent: int = 0):
        prefix = "  " * indent
        status = "✓" if node.validation.passed else "✗"
        stop = f" [STOP: {node.stop_reason}]" if node.stop_decompose else ""
        print(f"{prefix}{status} {node.name} (depth={node.depth}){stop}")
        
        if node.code:
            code_preview = node.code[:100].replace("\n", " ") + "..."
            print(f"{prefix}    Code: {code_preview}")
        
        for child in node.children:
            print_tree(child, indent + 1)
    
    print_tree(result)
    
    print()
    print("Saving tree...")
    tree_path = builder.save_tree(result)
    print(f"Tree saved to: {tree_path}")
    
    print()
    print("Generated code files:")
    for f in os.listdir(builder.nodes_dir):
        print(f"  - {f}")


def main():
    test_tree_builder_simple()
    
    print()
    print("=" * 60)
    print("Phase 5 test completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
