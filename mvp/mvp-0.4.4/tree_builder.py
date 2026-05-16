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
from capability_allocator import CapabilityAllocator
from models import Node, InputParam, OutputParam, Boundary, StateOperation, SubPRD, AttemptRecord, InterfacePlan, ValidationResult, ValidationError


class TreeBuilder:
    def __init__(self, config: Config, interface_plan: InterfacePlan = None):
        self.config = config
        self.api_client = APIClient(config)
        self.decomposer = Decomposer(config, self.api_client)
        self.code_generator = CodeGenerator(config, self.api_client)
        self.validator = Validator(config, interface_plan)
        
        self.output_dir = config.output_dir
        self.nodes_dir = config.nodes_dir
        
        self.interface_plan = interface_plan
        self.capability_allocator = CapabilityAllocator(interface_plan) if interface_plan else None
        self.interface_plan_summary = self._build_interface_summary() if interface_plan else ""
        self._interface_prefix_map = self._build_interface_prefix_map() if interface_plan else {}

        if interface_plan:
            self.code_generator.set_interface_plan(interface_plan)
        
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.nodes_dir, exist_ok=True)
    
    def _build_interface_summary(self) -> str:
        lines = []
        for iface in self.interface_plan.interfaces:
            lines.append(f"  - {iface.interface_id}: {iface.signature}")
            if iface.description:
                lines.append(f"    Description: {iface.description}")
        return "\n".join(lines)

    def _build_interface_prefix_map(self) -> dict:
        """Build mapping from resource_id to interface_id prefix.
        E.g., resource "product" → prefix "products" (from "products.get").
        This normalizes LLM output variations (e.g., "product.create" → "products").
        """
        mapping = {}
        for iface in self.interface_plan.interfaces:
            prefix = iface.interface_id.split(".")[0]
            rid = iface.resource_id
            mapping[rid] = prefix
            # If prefix != resource_id, also store prefix→prefix for idempotency
            if prefix != rid:
                mapping[prefix] = prefix
        return mapping
    
    def _allocate_capabilities(self, node: Node) -> None:
        for child in node.children:
            is_leaf = child.stop_decompose or child.depth >= self.config.max_depth
            if not is_leaf:
                continue
            if not child.requested_capabilities:
                continue
            grant, errors = self.capability_allocator.allocate(child)
            if errors:
                self._log(f"Capability allocation failed for '{child.name}': {errors}", node.depth)
                child.needs_human_intervention = True
            else:
                child.granted_capabilities = grant
                self._log(f"Granted {len(grant.granted_interfaces)} interface(s) to '{child.name}'", node.depth)

    def _build_redecompose_context(self, node: Node) -> Dict[str, Any]:
        last_attempt = node.attempt_history[-1] if node.attempt_history else None
        validation = node.validation

        return {
            "previous_errors": validation.errors if validation else [],
            "previous_children": last_attempt.children_snapshot if last_attempt else [c.name for c in node.children],
            "previous_contracts": last_attempt.contracts_snapshot if last_attempt else {k: v.to_dict() for k, v in node.children_contracts.items()},
            "previous_rationale": last_attempt.decomposition_rationale if last_attempt else node.decomposition_rationale,
            "previous_code": last_attempt.generated_code if last_attempt else node.code,
            "validator_report": {
                "error_types": [e.error_type for e in validation.structured_errors] if validation else [],
                "repair_action": validation.repair_action if validation else "redecompose",
                "fix_summary": validation.fix_summary if validation else {},
                "structured_errors": [e.to_dict() for e in validation.structured_errors] if validation else [],
                "composition_feedback": node.composition_feedback.to_dict() if node.composition_feedback else None,
            }
        }

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
    
    def _auto_derive_global_operations(self, node: Node):
        if not node.global_vars:
            return
        if node.subprd and node.subprd.global_state_operations:
            return

        ops = []
        for i, gv in enumerate(node.global_vars):
            op_type_map = {
                "read": "read",
                "write": "write",
                "read_write": "read_then_write"
            }
            ot = op_type_map.get(gv.op, "read_then_write")
            ops.append(StateOperation(
                op_id=f"op_{node.node_id}_{i}",
                source_id=gv.variable,
                op_type=ot,
                target={"item_path": "root", "condition": ""},
                payload={},
                constraint=f"manage_{gv.variable}",
                depends_on=""
            ))

        if not node.subprd:
            node.subprd = SubPRD(global_state_operations=ops)
        else:
            node.subprd.global_state_operations = ops

    def _save_snapshot(self, node: Node, stage: str, attempt: int, decision: str, errors: List[str] = None):
        record = AttemptRecord(
            stage=stage,
            attempt_number=attempt,
            children_snapshot=[c.name for c in node.children] if node.children else [],
            contracts_snapshot={k: v.to_dict() for k, v in node.children_contracts.items()} if node.children_contracts else {},
            decomposition_rationale=node.decomposition_rationale or "",
            generated_code=node.code or "",
            validation_errors=node.validation.errors if node.validation else (errors or []),
            structured_errors=[e.to_dict() for e in node.validation.structured_errors] if node.validation and node.validation.structured_errors else [],
            decision=decision
        )
        node.attempt_history.append(record)

    def _process_leaf_node(self, node: Node) -> Tuple[Node, bool]:
        """
        Process a leaf node: auto-derive global operations, generate code with retry loop.
        Validation errors from previous attempts are fed back into the next code generation.
        """
        self._auto_derive_global_operations(node)
        retry_count = 0
        max_retries = self.config.max_retries
        previous_code = ""
        previous_errors_list = None

        self._save_snapshot(node, "codegen_leaf", retry_count, "started")

        while retry_count < max_retries:
            self._log(f"Generating leaf code for: {node.name} (attempt {retry_count + 1}/{max_retries})", node.depth)

            code, errors = self.code_generator.generate_with_retry(
                node,
                previous_errors=previous_errors_list,
                previous_code=previous_code
            )

            if errors:
                self._log(f"Code generation failed: {errors}", node.depth)
                node.validation.passed = False
                node.validation.errors = errors
                node.code = ""

                if any("INSUFFICIENT_CAPABILITIES" in e for e in errors):
                    self._save_snapshot(node, "codegen_leaf", retry_count, "insufficient_capabilities", errors)
                    node.needs_human_intervention = True
                    return node, False

                self._save_snapshot(node, "codegen_leaf", retry_count, "retry_code", errors)
                retry_count += 1
                continue

            node.code = code
            validation = self.validator.validate(node, code)
            node.validation = validation

            self._save_snapshot(node, "validate", retry_count,
                "passed" if validation.passed else "retry_code",
                validation.errors)

            if validation.passed:
                self._log(f"Leaf code validated successfully", node.depth)
                self._save_node_code(node)
                return node, True

            self._log(f"Leaf code validation failed: {validation.errors}", node.depth)
            previous_code = code
            previous_errors_list = validation.errors
            node.code = ""
            retry_count += 1

        self._save_snapshot(node, "codegen_leaf", retry_count, "failed")
        self._log(f"Max retries reached for leaf node: {node.name}", node.depth)
        node.code = ""
        node.needs_human_intervention = True
        return node, False
    
    def _process_parent_node(self, node: Node) -> Tuple[Node, bool]:
        """
        Process a parent node: decompose, generate code, validate.
        May trigger re-decomposition on failure.
        Before clearing children for re-decomposition, saves a snapshot to preserve evidence.
        """
        retry_count = 0
        max_retries = self.config.max_decompose_retries

        self._save_snapshot(node, "decompose", retry_count, "started")

        while retry_count < max_retries:
            self._log(f"Decomposition attempt {retry_count + 1}/{max_retries}", node.depth)

            if retry_count > 0 or not node.children:
                decomp_context = None
                if retry_count > 0 or node.composition_feedback:
                    decomp_context = self._build_redecompose_context(node)

                node, decomp_errors = self.decomposer.decompose_with_retry(
                    node,
                    max_retries=1,
                    previous_errors=decomp_context,
                    interface_plan_summary=self.interface_plan_summary
                )

                if decomp_errors:
                    self._log(f"Decomposition failed: {decomp_errors}", node.depth)
                    self._save_snapshot(node, "decompose", retry_count, "failed", decomp_errors)
                    retry_count += 1
                    continue

            self._log(f"Decomposed into {len(node.children)} children", node.depth)

            conservation_errors = self.validator.check_conservation(node)
            if conservation_errors:
                self._log(f"Conservation check failed: {conservation_errors}", node.depth)
                node.validation.errors = conservation_errors
                self._save_snapshot(node, "validate", retry_count, "redecompose_conservation", conservation_errors)
                node.children = []
                node.children_contracts = {}
                retry_count += 1
                continue

            if self.capability_allocator:
                self._log(f"Running capability allocation for {len(node.children)} children...", node.depth)
                self._allocate_capabilities(node)

            self._log(f"Generating parent code...", node.depth)
            code, code_errors = self.code_generator.generate_with_retry(node)

            if code_errors:
                if any(e.startswith("CANNOT_COMPOSE") for e in code_errors):
                    node.validation = ValidationResult(
                        passed=False,
                        errors=code_errors,
                        structured_errors=[
                            ValidationError(
                                "CANNOT_COMPOSE",
                                "; ".join(code_errors),
                                node.composition_feedback.to_dict() if node.composition_feedback else {}
                            )
                        ],
                        retry_count=retry_count,
                        repair_action="redecompose",
                        fix_summary=node.composition_feedback.to_dict() if node.composition_feedback else {}
                    )
                    self._save_snapshot(node, "codegen_parent", retry_count, "redecompose", code_errors)
                    node.children = []
                    node.children_contracts = {}
                    retry_count += 1
                    continue

                self._log(f"Code generation failed: {code_errors}", node.depth)
                node.validation.errors = code_errors
                self._save_snapshot(node, "codegen_parent", retry_count, "retry_code", code_errors)
                retry_count += 1
                continue

            node.code = code
            validation = self.validator.validate(node, code)
            node.validation = validation
            node.validation.retry_count = retry_count

            if validation.passed:
                self._log(f"Parent code validated successfully", node.depth)
                self._save_snapshot(node, "validate", retry_count, "passed")
                self._save_node_code(node)
                return node, True

            self._log(f"Validation failed: {validation.errors}", node.depth)

            if validation.repair_action == "redecompose" or self.validator.should_redecompose(node, validation):
                self._log("Re-decomposition required", node.depth)
                self._save_snapshot(node, "validate", retry_count, "redecompose", validation.errors)
                node.children = []
                node.children_contracts = {}
                retry_count += 1
            elif validation.repair_action == "human":
                node.needs_human_intervention = True
                self._save_snapshot(node, "validate", retry_count, "human", validation.errors)
                return node, False
            else:
                self._log("Validation errors not requiring re-decomposition", node.depth)
                self._save_snapshot(node, "validate", retry_count, "retry_code", validation.errors)
                retry_count += 1

        self._save_snapshot(node, "decompose", retry_count, "failed")
        self._log(f"Max retries reached, node processing failed", node.depth)
        node.code = ""
        node.needs_human_intervention = True
        return node, False
    
    def _build_tree_recursive(self, node: Node) -> Node:
        """
        Recursively build the decomposition tree (depth-first).
        Supports redecomposition when children reject with INSUFFICIENT_CAPABILITIES
        but the parent has the missing resource in global_vars.
        """
        max_redecompose = self.config.max_decompose_retries
        redecompose_count = 0

        while True:
            node, success = self._process_node(node)

            if not success:
                self._log(f"Node processing failed: {node.name}", node.depth)
                return node

            if node.stop_decompose:
                return node

            # Process children recursively
            processed_children = []
            for child in node.children:
                child_context = node.get_context_for_child(child.name)
                self._log(f"Processing child: {child.name}", child.depth)
                processed_child = self._build_tree_recursive(child)
                processed_children.append(processed_child)

            node.children = processed_children

            # Check for children that rejected due to INSUFFICIENT_CAPABILITIES
            # and decide: redecompose (if parent has resource) or propagate up
            needs_redecompose = False
            for child in node.children:
                if not child.needs_human_intervention:
                    continue
                if not (child.composition_feedback and child.composition_feedback.missing_interfaces):
                    continue
                parent_var_names = {gv.variable for gv in node.global_vars}
                for mi in child.composition_feedback.missing_interfaces:
                    iface_id = mi.get("interface_id", "")
                    parts = iface_id.split(".")
                    raw_resource = parts[0] if len(parts) > 1 else iface_id
                    resource = self._interface_prefix_map.get(raw_resource, raw_resource)
                    if resource in parent_var_names:
                        self._log(
                            f"PARENT_HAS_RESOURCE_BUT_MISSING_ALLOCATION: parent={node.name} "
                            f"resource={resource} child={child.name} "
                            f"→ redecomposing (attempt {redecompose_count + 1}/{max_redecompose})",
                            node.depth
                        )
                        needs_redecompose = True
                        # Store composition_feedback on parent so decomposer sees context
                        node.composition_feedback = child.composition_feedback
                    else:
                        self._log(
                            f"PARENT_MISSING_RESOURCE: parent={node.name} "
                            f"resource={resource} child={child.name}",
                            node.depth
                        )

            if needs_redecompose:
                if redecompose_count >= max_redecompose:
                    self._log(
                        f"Max redecompose retries ({max_redecompose}) reached for {node.name}",
                        node.depth
                    )
                    node.needs_human_intervention = True
                    return node

                self._save_snapshot(
                    node, "redecompose", redecompose_count,
                    "insufficient_capabilities_redecompose"
                )
                node.children = []
                node.children_contracts = {}
                redecompose_count += 1
                continue

            # Check for other failures (not INSUFFICIENT_CAPABILITIES)
            failed_children = [c.name for c in node.children if c.needs_human_intervention]
            if failed_children:
                self._log(
                    f"Children failed, marking parent '{node.name}' "
                    f"as needs_human_intervention: {failed_children}",
                    node.depth
                )
                node.needs_human_intervention = True

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
