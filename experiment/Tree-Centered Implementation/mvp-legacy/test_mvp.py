"""
Final integration test for the decomposition MVP.
Uses a synthetic PRD to test the complete decomposition-verification loop.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from tree_builder import TreeBuilder
from models import Node, InputParam, OutputParam, Boundary, GlobalVar


def create_root_from_prd(prd_path: str) -> Node:
    """
    Create a root node from the PRD file.
    """
    with open(prd_path, "r", encoding="utf-8") as f:
        prd_content = f.read()
    
    return Node(
        node_id="root",
        name="PersonalTaskManager",
        depth=0,
        purpose="A command-line task management application that allows users to create, list, complete, and delete tasks. Tasks are stored in memory during the session. The system supports task creation with title and description, task listing with status filtering, task completion marking, and task deletion.",
        inputs=[
            InputParam(name="command", type="str", description="User command: create, list, complete, delete"),
            InputParam(name="task_data", type="Optional[dict]", description="Task data containing title, description, task_id, or status_filter depending on command")
        ],
        outputs=[
            OutputParam(name="result", type="dict", description="Operation result with success status, message, and optional data")
        ],
        boundary=Boundary(
            in_scope=[
                "Task CRUD operations (create, list, complete, delete)",
                "In-memory task storage",
                "Task ID auto-generation",
                "Status filtering for list operation",
                "Input validation and error handling"
            ],
            out_of_scope=[
                "Database persistence",
                "User authentication",
                "Network operations",
                "File I/O",
                "Multi-user support"
            ]
        ),
        global_vars=[
            GlobalVar(name="tasks", type="Dict[int, Task]", access="read_write", description="In-memory task storage"),
            GlobalVar(name="next_id", type="int", access="read_write", description="Auto-increment counter for task IDs")
        ]
    )


def print_summary(root: Node):
    """
    Print a summary of the decomposition tree.
    """
    print("\n" + "=" * 60)
    print("DECOMPOSITION SUMMARY")
    print("=" * 60)
    
    total_nodes = 0
    leaf_nodes = 0
    passed_nodes = 0
    failed_nodes = 0
    
    def count_nodes(node: Node):
        nonlocal total_nodes, leaf_nodes, passed_nodes, failed_nodes
        total_nodes += 1
        if node.stop_decompose:
            leaf_nodes += 1
        if node.validation.passed:
            passed_nodes += 1
        else:
            failed_nodes += 1
        for child in node.children:
            count_nodes(child)
    
    count_nodes(root)
    
    print(f"Total nodes: {total_nodes}")
    print(f"Leaf nodes: {leaf_nodes}")
    print(f"Passed validations: {passed_nodes}")
    print(f"Failed validations: {failed_nodes}")
    print(f"Max depth reached: {root.depth}")
    
    print("\n" + "-" * 60)
    print("TREE STRUCTURE")
    print("-" * 60)
    
    def print_tree(node: Node, indent: int = 0):
        prefix = "  " * indent
        status = "✓" if node.validation.passed else "✗"
        stop = f" [LEAF: {node.stop_reason[:40]}...]" if node.stop_decompose else f" [{len(node.children)} children]"
        print(f"{prefix}{status} {node.name}{stop}")
        for child in node.children:
            print_tree(child, indent + 1)
    
    print_tree(root)
    
    print("\n" + "-" * 60)
    print("GENERATED FILES")
    print("-" * 60)
    
    nodes_dir = "output/nodes"
    if os.path.exists(nodes_dir):
        for f in sorted(os.listdir(nodes_dir)):
            filepath = os.path.join(nodes_dir, f)
            size = os.path.getsize(filepath)
            print(f"  {f} ({size} bytes)")


def main():
    print("=" * 60)
    print("INTEGRATION TEST: Personal Task Manager")
    print("=" * 60)
    print()
    
    config = Config.from_env()
    
    if not config.api_key:
        print("ERROR: DEEPSEEK_API_KEY not set")
        print("Please set the environment variable and try again.")
        return
    
    config.max_depth = 3
    config.max_children = 5
    config.max_lines_threshold = 50
    
    print(f"Configuration:")
    print(f"  Max depth: {config.max_depth}")
    print(f"  Max children: {config.max_children}")
    print(f"  Lines threshold: {config.max_lines_threshold}")
    print(f"  Temperature: {config.temperature}")
    print()
    
    prd_path = "test_prd.md"
    print(f"Loading PRD from: {prd_path}")
    
    root_node = create_root_from_prd(prd_path)
    
    print(f"Root node: {root_node.name}")
    print(f"Purpose: {root_node.purpose[:80]}...")
    print()
    
    builder = TreeBuilder(config)
    
    print("Starting decomposition-verification loop...")
    print("-" * 60)
    
    result = builder.build_tree(root_node)
    
    print("-" * 60)
    print("Decomposition complete!")
    print()
    
    tree_path = builder.save_tree(result)
    print(f"Tree saved to: {tree_path}")
    
    print_summary(result)
    
    print("\n" + "=" * 60)
    print("INTEGRATION TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
