"""
TreeBuilder: Main controller for the decomposition-verification loop.
Implements depth-first traversal with re-decomposition on failure.
"""
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from api_client import APIClient
from decomposer import Decomposer
from code_generator import CodeGenerator
from validator import Validator
from models import Node, InputParam, OutputParam, Boundary


class TreeBuilder:
    def __init__(self, config: Config):
        self.config = config
        self.api_client = APIClient(config)
        self.decomposer = Decomposer(config, self.api_client)
        self.code_generator = CodeGenerator(config, self.api_client)
        self.validator = Validator(config)
        
        self.output_dir = config.output_dir
        self.nodes_dir = config.nodes_dir
        
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.nodes_dir, exist_ok=True)
    
    def _log(self, message: str, indent: int = 0):
        prefix = "  " * indent
        print(f"{prefix}{message}")
    
    def _save_node_code(self, node: Node):
        if not node.code:
            return
        
        filename = f"{node.node_id}_{node.name}.py"
        filepath = os.path.join(self.nodes_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(node.code)
        
        node.code_file = filepath
        self._log(f"Saved code to: {filepath}", node.depth)
    
    def _process_node(self, node: Node) -> Tuple[Node, bool]:
        """
        Process a single node: decompose, generate code, validate.
        Returns (updated_node, success).
        """
        self._log(f"Processing node: {node.name}", node.depth)
        self._log(f"Purpose: {node.purpose[:60]}...", node.depth)
        
        if node.stop_decompose:
            self._log(f"Stop decomposition: {node.stop_reason}", node.depth)
            return self._process_leaf_node(node)
        
        if node.depth >= self.config.max_depth:
            self._log(f"Max depth reached, treating as leaf", node.depth)
            node.stop_decompose = True
            node.stop_reason = f"Max depth {self.config.max_depth} reached"
            return self._process_leaf_node(node)
        
        return self._process_parent_node(node)
    
    def _process_leaf_node(self, node: Node) -> Tuple[Node, bool]:
        """
        Process a leaf node: generate code directly.
        """
        self._log(f"Generating leaf code for: {node.name}", node.depth)
        
        code, errors = self.code_generator.generate_with_retry(node)
        
        if errors:
            self._log(f"Code generation failed: {errors}", node.depth)
            node.validation.passed = False
            node.validation.errors = errors
            return node, False
        
        node.code = code
        validation = self.validator.validate(node, code)
        node.validation = validation
        
        if validation.passed:
            self._log(f"Leaf code validated successfully", node.depth)
            self._save_node_code(node)
            return node, True
        else:
            self._log(f"Leaf code validation failed: {validation.errors}", node.depth)
            return node, False
    
    def _process_parent_node(self, node: Node) -> Tuple[Node, bool]:
        """
        Process a parent node: decompose, generate code, validate.
        May trigger re-decomposition on failure.
        """
        retry_count = 0
        max_retries = self.config.max_decompose_retries
        
        while retry_count < max_retries:
            self._log(f"Decomposition attempt {retry_count + 1}/{max_retries}", node.depth)
            
            previous_errors = node.validation.errors if retry_count > 0 else None
            
            if retry_count > 0 or not node.children:
                node, decomp_errors = self.decomposer.decompose_with_retry(
                    node, 
                    max_retries=1
                )
                
                if decomp_errors:
                    self._log(f"Decomposition failed: {decomp_errors}", node.depth)
                    retry_count += 1
                    continue
            
            self._log(f"Decomposed into {len(node.children)} children", node.depth)
            
            self._log(f"Generating parent code...", node.depth)
            code, code_errors = self.code_generator.generate_with_retry(node)
            
            if code_errors:
                self._log(f"Code generation failed: {code_errors}", node.depth)
                node.validation.errors = code_errors
                retry_count += 1
                continue
            
            node.code = code
            validation = self.validator.validate(node, code)
            node.validation = validation
            node.validation.retry_count = retry_count
            
            if validation.passed:
                self._log(f"Parent code validated successfully", node.depth)
                self._save_node_code(node)
                return node, True
            
            self._log(f"Validation failed: {validation.errors}", node.depth)
            
            if self.validator.should_redecompose(node, validation):
                self._log(f"Re-decomposition required", node.depth)
                node.children = []
                node.children_contracts = {}
                retry_count += 1
            else:
                self._log(f"Validation errors not requiring re-decomposition", node.depth)
                retry_count += 1
        
        self._log(f"Max retries reached, node processing failed", node.depth)
        return node, False
    
    def _build_tree_recursive(self, node: Node) -> Node:
        """
        Recursively build the decomposition tree (depth-first).
        """
        node, success = self._process_node(node)
        
        if not success:
            self._log(f"Node processing failed: {node.name}", node.depth)
            return node
        
        if node.stop_decompose:
            return node
        
        processed_children = []
        for child in node.children:
            child_context = node.get_context_for_child(child.name)
            self._log(f"Processing child: {child.name}", child.depth)
            
            processed_child = self._build_tree_recursive(child)
            processed_children.append(processed_child)
        
        node.children = processed_children
        return node
    
    def build_tree(self, root_node: Node) -> Node:
        """
        Build the complete decomposition tree from a root node.
        """
        self._log("=" * 50)
        self._log(f"Building decomposition tree for: {root_node.name}")
        self._log("=" * 50)
        
        result = self._build_tree_recursive(root_node)
        
        self._log("=" * 50)
        self._log("Tree building complete")
        self._log("=" * 50)
        
        return result
    
    def save_tree(self, root_node: Node, filename: str = "decomposition_tree.json"):
        """
        Save the decomposition tree to a JSON file.
        """
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(root_node.to_json(indent=2))
        
        self._log(f"Tree saved to: {filepath}")
        return filepath
    
    def load_tree(self, filepath: str) -> Node:
        """
        Load a decomposition tree from a JSON file.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            return Node.from_json(f.read())


def create_root_node_from_prd(prd_text: str) -> Node:
    """
    Create a root node from PRD text.
    Simple extraction - in production, this would use LLM.
    """
    lines = [l.strip() for l in prd_text.split("\n") if l.strip()]
    purpose = " ".join(lines[:5])
    
    return Node(
        node_id="root",
        name="RootSystem",
        depth=0,
        purpose=purpose,
        inputs=[InputParam(name="input", type="Any", description="System input")],
        outputs=[OutputParam(name="output", type="Any", description="System output")],
        boundary=Boundary(
            in_scope=["All system functionality"],
            out_of_scope=["External dependencies not specified"]
        )
    )
