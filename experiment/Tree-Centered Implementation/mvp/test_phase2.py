"""
Test script for Phase 2: Decomposer LLM.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from api_client import APIClient
from decomposer import Decomposer
from models import Node, InputParam, OutputParam, Boundary


def test_decomposer():
    print("=" * 50)
    print("Phase 2 Test: Decomposer LLM")
    print("=" * 50 + "\n")
    
    config = Config.from_env()
    
    if not config.api_key:
        print("WARNING: DEEPSEEK_API_KEY not set, skipping test")
        return
    
    client = APIClient(config)
    decomposer = Decomposer(config, client)
    
    root_node = Node(
        node_id="root",
        name="TaskManager",
        depth=0,
        purpose="A simple task management system that allows users to create, list, complete, and delete tasks. Tasks have a title, description, status, and creation timestamp.",
        inputs=[
            InputParam(name="command", type="str", description="User command: create, list, complete, delete"),
            InputParam(name="task_data", type="Optional[dict]", description="Task data for create/complete/delete operations")
        ],
        outputs=[
            OutputParam(name="result", type="dict", description="Operation result with status and data")
        ],
        boundary=Boundary(
            in_scope=["task CRUD operations", "in-memory task storage", "basic validation"],
            out_of_scope=["persistence to disk", "user authentication", "network operations"]
        )
    )
    
    print(f"Root node: {root_node.name}")
    print(f"Purpose: {root_node.purpose}")
    print(f"Depth: {root_node.depth}")
    print()
    
    print("Calling Decomposer LLM...")
    print()
    
    node, errors = decomposer.decompose_with_retry(root_node)
    
    if errors:
        print(f"Decomposition failed with errors: {errors}")
        return
    
    print(f"Decomposition successful!")
    print(f"Number of children: {len(node.children)}")
    print()
    
    for i, child in enumerate(node.children):
        print(f"Child {i+1}: {child.name}")
        print(f"  Purpose: {child.purpose}")
        print(f"  Inputs: {[inp.name for inp in child.inputs]}")
        print(f"  Outputs: {[out.name for out in child.outputs]}")
        print(f"  Stop decompose: {child.stop_decompose}")
        print(f"  Stop reason: {child.stop_reason}")
        print()
    
    print("Children contracts:")
    for name, contract in node.children_contracts.items():
        print(f"  {name}: {contract.purpose[:50]}...")
    
    print()
    print("=" * 50)
    print("Phase 2 test completed!")
    print("=" * 50)


if __name__ == "__main__":
    test_decomposer()
