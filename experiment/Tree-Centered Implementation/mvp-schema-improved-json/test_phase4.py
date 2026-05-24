"""
Test script for Phase 4: Validator + Re-decomposition loop.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from api_client import APIClient
from decomposer import Decomposer
from code_generator import CodeGenerator
from validator import Validator
from models import Node, InputParam, OutputParam, Boundary


def test_syntax_validation():
    print("=" * 50)
    print("Test 1: Syntax Validation")
    print("=" * 50 + "\n")
    
    config = Config.from_env()
    validator = Validator(config)
    
    valid_code = """
def add(a: int, b: int) -> int:
    return a + b
"""
    
    invalid_code = """
def add(a: int, b: int) -> int:
    return a +  # missing operand
"""
    
    ok, errors = validator.validate_syntax(valid_code)
    print(f"Valid code: {ok}, errors: {errors}")
    assert ok
    
    ok, errors = validator.validate_syntax(invalid_code)
    print(f"Invalid code: {ok}, errors: {errors}")
    assert not ok
    
    print("Syntax validation test passed!\n")


def test_interface_validation():
    print("=" * 50)
    print("Test 2: Interface Validation")
    print("=" * 50 + "\n")
    
    config = Config.from_env()
    validator = Validator(config)
    
    node = Node(
        node_id="test",
        name="calculate",
        depth=0,
        purpose="Calculate something",
        inputs=[
            InputParam(name="x", type="int"),
            InputParam(name="y", type="int")
        ],
        outputs=[OutputParam(name="result", type="int")]
    )
    
    good_code = """
def calculate(x: int, y: int) -> int:
    return x + y
"""
    
    bad_code = """
def calculate(x: int) -> int:
    return x
"""
    
    ok, errors = validator.validate_interface_preservation(node, good_code)
    print(f"Good code: {ok}, errors: {errors}")
    assert ok
    
    ok, errors = validator.validate_interface_preservation(node, bad_code)
    print(f"Bad code: {ok}, errors: {errors}")
    assert not ok
    
    print("Interface validation test passed!\n")


def test_full_validation_loop():
    print("=" * 50)
    print("Test 3: Full Validation + Re-decomposition Loop")
    print("=" * 50 + "\n")
    
    config = Config.from_env()
    
    if not config.api_key:
        print("WARNING: DEEPSEEK_API_KEY not set, skipping test")
        return
    
    client = APIClient(config)
    decomposer = Decomposer(config, client)
    generator = CodeGenerator(config, client)
    validator = Validator(config)
    
    root_node = Node(
        node_id="root",
        name="string_processor",
        depth=0,
        purpose="Process a string by cleaning, validating, and transforming it",
        inputs=[
            InputParam(name="text", type="str", description="Input string to process")
        ],
        outputs=[
            OutputParam(name="result", type="str", description="Processed string"),
            OutputParam(name="valid", type="bool", description="Whether input was valid")
        ],
        boundary=Boundary(
            in_scope=["string cleaning", "validation", "transformation"],
            out_of_scope=["file I/O", "network operations"]
        )
    )
    
    print(f"Root node: {root_node.name}")
    print(f"Purpose: {root_node.purpose}")
    print()
    
    print("Step 1: Decomposing...")
    node, decomp_errors = decomposer.decompose_with_retry(root_node)
    
    if decomp_errors:
        print(f"Decomposition failed: {decomp_errors}")
        return
    
    print(f"Decomposed into {len(node.children)} children")
    for child in node.children:
        print(f"  - {child.name}")
    print()
    
    print("Step 2: Generating code...")
    code, code_errors = generator.generate_with_retry(node)
    
    if code_errors:
        print(f"Code generation failed: {code_errors}")
        return
    
    print("Code generated successfully")
    print()
    
    print("Step 3: Validating code...")
    validation = validator.validate(node, code)
    
    print(f"Validation passed: {validation.passed}")
    if validation.errors:
        print(f"Errors: {validation.errors}")
    print()
    
    if not validation.passed:
        print("Step 4: Checking if re-decomposition needed...")
        if validator.should_redecompose(node, validation):
            print("Re-decomposition required - would trigger new decomposition")
        else:
            print("Re-decomposition not needed - code errors can be fixed")
    
    print()
    print("Generated code preview:")
    print("-" * 40)
    print(code[:500] + "..." if len(code) > 500 else code)
    print("-" * 40)


def main():
    print("=" * 60)
    print("Phase 4 Tests: Validator + Re-decomposition Loop")
    print("=" * 60 + "\n")
    
    test_syntax_validation()
    test_interface_validation()
    test_full_validation_loop()
    
    print()
    print("=" * 60)
    print("All Phase 4 tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
