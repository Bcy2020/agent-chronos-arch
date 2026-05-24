"""
Test script for Phase 3: CodeGenerator LLM.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from api_client import APIClient
from decomposer import Decomposer
from code_generator import CodeGenerator
from models import Node, InputParam, OutputParam, Boundary, ChildContract


def test_leaf_code_generation():
    print("=" * 50)
    print("Test 1: Leaf Node Code Generation")
    print("=" * 50 + "\n")
    
    config = Config.from_env()
    client = APIClient(config)
    generator = CodeGenerator(config, client)
    
    leaf_node = Node(
        node_id="leaf_1",
        name="add_numbers",
        depth=2,
        purpose="Add two numbers and return the result",
        inputs=[
            InputParam(name="a", type="int", description="First number"),
            InputParam(name="b", type="int", description="Second number")
        ],
        outputs=[
            OutputParam(name="result", type="int", description="Sum of a and b")
        ],
        boundary=Boundary(
            in_scope=["addition operation"],
            out_of_scope=["any other operations"]
        ),
        stop_decompose=True,
        stop_reason="Simple operation, can be implemented in <10 lines"
    )
    
    print(f"Leaf node: {leaf_node.name}")
    print(f"Purpose: {leaf_node.purpose}")
    print()
    
    code, errors = generator.generate_with_retry(leaf_node)
    
    if errors:
        print(f"Code generation failed: {errors}")
        return False
    
    print("Generated code:")
    print("-" * 40)
    print(code)
    print("-" * 40)
    print()
    
    return True


def test_parent_code_generation():
    print("=" * 50)
    print("Test 2: Parent Node Code Generation")
    print("=" * 50 + "\n")
    
    config = Config.from_env()
    client = APIClient(config)
    decomposer = Decomposer(config, client)
    generator = CodeGenerator(config, client)
    
    root_node = Node(
        node_id="root",
        name="simple_calculator",
        depth=0,
        purpose="A simple calculator that performs basic arithmetic operations (add, subtract, multiply, divide) on two numbers",
        inputs=[
            InputParam(name="operation", type="str", description="Operation to perform"),
            InputParam(name="a", type="float", description="First operand"),
            InputParam(name="b", type="float", description="Second operand")
        ],
        outputs=[
            OutputParam(name="result", type="float", description="Calculation result"),
            OutputParam(name="error", type="Optional[str]", description="Error message if any")
        ],
        boundary=Boundary(
            in_scope=["basic arithmetic", "error handling for division by zero"],
            out_of_scope=["advanced math", "complex numbers", "history"]
        )
    )
    
    print(f"Root node: {root_node.name}")
    print(f"Purpose: {root_node.purpose}")
    print()
    
    print("Step 1: Decomposing...")
    decomposed_node, decomp_errors = decomposer.decompose_with_retry(root_node)
    
    if decomp_errors:
        print(f"Decomposition failed: {decomp_errors}")
        return False
    
    print(f"Decomposed into {len(decomposed_node.children)} children:")
    for child in decomposed_node.children:
        print(f"  - {child.name}: {child.purpose[:50]}...")
    print()
    
    print("Step 2: Generating parent code...")
    code, code_errors = generator.generate_with_retry(decomposed_node)
    
    if code_errors:
        print(f"Code generation failed: {code_errors}")
        return False
    
    print("Generated parent code:")
    print("-" * 40)
    print(code)
    print("-" * 40)
    print()
    
    return True


def main():
    print("=" * 60)
    print("Phase 3 Tests: CodeGenerator LLM")
    print("=" * 60 + "\n")
    
    config = Config.from_env()
    if not config.api_key:
        print("WARNING: DEEPSEEK_API_KEY not set, skipping tests")
        return
    
    success = True
    
    if not test_leaf_code_generation():
        success = False
    
    print()
    
    if not test_parent_code_generation():
        success = False
    
    print()
    print("=" * 60)
    if success:
        print("All Phase 3 tests completed successfully!")
    else:
        print("Some tests failed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
