"""
TreeBuilder: Main controller for the decomposition-verification loop.
Implements BFS two-phase architecture:
  Phase 1 - BFS expansion (level-by-level decomposition)
  Phase 2 - Bottom-up closure (deepest-to-root codegen + validation)
  Cross-phase feedback loop for INSUFFICIENT_CAPABILITIES / CANNOT_COMPOSE.
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
from models import Node, InputParam, OutputParam, Boundary, StateOperation, SubPRD, AttemptRecord, InterfacePlan, ValidationResult, ValidationError, CompositionFeedback


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
        mapping = {}
        for iface in self.interface_plan.interfaces:
            prefix = iface.interface_id.split(".")[0]
            rid = iface.resource_id
            mapping[rid] = prefix
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

    # ======================================================================
    # Phase 1: BFS Expansion with Immediate Top-Down Codegen
    # ======================================================================

    def _phase1_expand_node(self, node: Node) -> bool:
        """
        Expand a single parent node: decompose (with retry) + conservation check + capability allocation.
        No code generation.
        Returns True if the node was successfully expanded, False if max retries exhausted.
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

            for child in node.children:
                if child.stop_decompose or child.depth >= self.config.max_depth:
                    child.status = "codegen_ready"
                else:
                    child.status = "pending"

            self._log(f"Node expanded: {node.name} -> {len(node.children)} children", node.depth)
            return True

        self._save_snapshot(node, "decompose", retry_count, "failed")
        self._log(f"Max retries reached for expansion: {node.name}", node.depth)
        node.needs_human_intervention = True
        node.status = "human_needed"
        return False

    def _phase1_expand(self, root: Node) -> None:
        """
        Phase 1: BFS level-by-level expansion with immediate top-down codegen.
        Each node is decomposed (if parent) then immediately codegen'd for
        composition verification, before proceeding to the next level.
        This ensures root composition is validated before any child decomposition.
        """
        self._log("--- Phase 1: BFS Expansion with Top-Down Codegen ---", 0)

        current_level = [root]

        while current_level:
            next_level = []

            for node in current_level:
                if node.status in ("codegen_done", "failed", "human_needed"):
                    continue

                # Leaf: codegen directly (marked codegen_ready by parent's expansion)
                if node.status == "codegen_ready" or node.stop_decompose or node.depth >= self.config.max_depth:
                    node.status = "codegen_ready"
                    self._log(f"  Codegen leaf: {node.name} (depth {node.depth})", node.depth)
                    success = self._phase2_codegen_leaf(node)
                    node.status = "codegen_done" if success else "failed"
                    continue

                # Parent: decompose
                if node.status == "pending":
                    self._log(f"  Expanding: {node.name} (depth {node.depth})", node.depth)
                    success = self._phase1_expand_node(node)
                    if not success:
                        node.status = "failed"
                        self._log(f"  Expansion FAILED: {node.name}", node.depth)
                        continue
                    node.status = "expanded"

                # Parent: immediately codegen (composition verification)
                if node.status == "expanded" and node.children:
                    self._log(f"  Codegen parent: {node.name} (depth {node.depth})", node.depth)
                    success = self._phase2_codegen_parent(node)
                    if success:
                        node.status = "codegen_done"
                        self._log(f"  Codegen OK: {node.name}", node.depth)
                    else:
                        node.status = "failed"
                        self._log(f"  Codegen FAILED: {node.name}", node.depth)
                        continue  # Don't enqueue children — wasted if redecompose needed

                # Enqueue children for next level (BFS: level N+1)
                if node.status == "codegen_done" and node.children:
                    for child in node.children:
                        next_level.append(child)

            current_level = next_level

        self._log("--- Phase 1 Complete ---", 0)

    # ======================================================================
    # Phase 2: Bottom-Up Code Generation
    # ======================================================================

    def _phase2_codegen_leaf(self, node: Node) -> bool:
        """
        Generate code for a leaf node with retry loop.
        Adapted from _process_leaf_node. Returns True on success.
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
                    return False

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
                return True

            self._log(f"Leaf code validation failed: {validation.errors}", node.depth)
            previous_code = code
            previous_errors_list = validation.errors
            node.code = ""
            retry_count += 1

        self._save_snapshot(node, "codegen_leaf", retry_count, "failed")
        self._log(f"Max retries reached for leaf node: {node.name}", node.depth)
        node.code = ""
        node.needs_human_intervention = True
        return False

    def _phase2_codegen_parent(self, node: Node) -> bool:
        """
        Generate code for a parent node by composing children.
        Codegen-only part from the current _process_parent_node (no decompose).
        Returns True on success.
        """
        retry_count = 0
        max_retries = self.config.max_decompose_retries

        while retry_count < max_retries:
            self._log(f"Generating parent code for: {node.name} (attempt {retry_count + 1}/{max_retries})", node.depth)

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
                    return False

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
                return True

            self._log(f"Validation failed: {validation.errors}", node.depth)

            if validation.repair_action == "redecompose" or self.validator.should_redecompose(node, validation):
                self._log("Re-decomposition required", node.depth)
                self._save_snapshot(node, "validate", retry_count, "redecompose", validation.errors)
                return False
            elif validation.repair_action == "human":
                node.needs_human_intervention = True
                self._save_snapshot(node, "validate", retry_count, "human", validation.errors)
                return False
            else:
                self._log("Validation errors not requiring re-decomposition", node.depth)
                self._save_snapshot(node, "validate", retry_count, "retry_code", validation.errors)
                retry_count += 1

        self._save_snapshot(node, "codegen_parent", retry_count, "failed")
        self._log(f"Max retries reached for parent codegen: {node.name}", node.depth)
        node.code = ""
        node.needs_human_intervention = True
        return False

    def _phase2_codegen_node(self, node: Node) -> bool:
        """Dispatch codegen to leaf or parent handler."""
        if node.stop_decompose or node.depth >= self.config.max_depth:
            return self._phase2_codegen_leaf(node)
        else:
            return self._phase2_codegen_parent(node)

    def _collect_nodes_by_depth(self, root: Node, reverse: bool = False) -> List[Tuple[int, List[Node]]]:
        """
        Collect all nodes grouped by depth.
        reverse=False: shallowest first (depth 0, 1, 2, ...)
        reverse=True:  deepest first (depth N, N-1, ..., 0)
        """
        depth_map: Dict[int, List[Node]] = {}
        max_depth = [0]

        def walk(node, d):
            depth_map.setdefault(d, []).append(node)
            max_depth[0] = max(max_depth[0], d)
            for child in node.children:
                walk(child, d + 1)

        walk(root, 0)

        if reverse:
            return [(d, depth_map[d]) for d in range(max_depth[0], -1, -1) if d in depth_map]
        else:
            return [(d, depth_map[d]) for d in range(max_depth[0] + 1) if d in depth_map]

    def _phase2_close(self, root: Node) -> None:
        """
        Phase 2: Bottom-up code generation and validation.
        Processes nodes from deepest depth to root.
        """
        self._log("--- Phase 2: Bottom-Up Codegen ---", 0)

        nodes_by_depth = self._collect_nodes_by_depth(root, reverse=True)

        for depth, nodes in nodes_by_depth:
            self._log(f"  Depth {depth}: {len(nodes)} nodes", 0)

            for node in nodes:
                if node.status == "codegen_done":
                    continue
                if node.status in ("failed", "human_needed"):
                    continue
                if node.status not in ("codegen_ready", "expanded"):
                    self._log(f"  Skipping {node.name} (status={node.status})", node.depth)
                    continue

                self._log(f"  Closing: {node.name} (depth {node.depth})", node.depth)
                success = self._phase2_codegen_node(node)

                if success:
                    node.status = "codegen_done"
                    self._log(f"  Codegen OK: {node.name}", node.depth)
                else:
                    node.status = "failed"
                    self._log(f"  Codegen FAILED: {node.name}", node.depth)

        self._log("--- Phase 2 Complete ---", 0)

    # ======================================================================
    # Cross-Phase Issue Resolution
    # ======================================================================

    def _find_node(self, root: Node, node_id: str) -> Optional[Node]:
        """Find a node by ID using DFS traversal."""
        if root.node_id == node_id:
            return root
        for child in root.children:
            result = self._find_node(child, node_id)
            if result:
                return result
        return None

    def _clear_subtree_for_redecompose(self, node: Node) -> None:
        """
        Clear a node's subtree for redecomposition.
        Preserves attempt_history and composition_feedback.
        """
        def _clear_recursive(n: Node):
            n.code = ""
            n.code_file = ""
            n.children = []
            n.children_contracts = {}
            n.validation = ValidationResult()
            n.needs_human_intervention = False
            n.status = "pending"
            n.granted_capabilities = None
            n.requested_capabilities = []

        _clear_recursive(node)

    def _propagate_failures(self, root: Node) -> None:
        """
        Walk bottom-up and mark parents as human_needed if any child is human_needed
        and the parent was not already marked for redecomposition.
        This propagates unresolvable failures (e.g., INSUFFICIENT_CAPABILITIES
        where no ancestor has the missing resource) upward to the root.
        """
        nodes_by_depth = self._collect_nodes_by_depth(root, reverse=True)
        for _depth, nodes in nodes_by_depth:
            for node in nodes:
                if node.status in ("failed", "human_needed", "pending"):
                    continue
                for child in node.children:
                    if child.needs_human_intervention or child.status == "human_needed":
                        self._log(
                            f"Propagating failure: {node.name} ← child '{child.name}' "
                            f"needs human intervention",
                            node.depth
                        )
                        node.needs_human_intervention = True
                        node.status = "human_needed"
                        break

    def _resolve_issues_after_phase2(self, root: Node) -> List[Tuple[str, str, Optional[CompositionFeedback]]]:
        """
        Walk bottom-up, check each failed node, determine which parents need redecomposition.
        Returns list of (parent_node_id, reason, composition_feedback).

        Resolution logic:
        1. For each node, check children:
           a. INSUFFICIENT_CAPABILITIES + parent has resource → parent redecomposes
           b. INSUFFICIENT_CAPABILITIES + parent lacks resource → propagate (post-phase)
        2. For each node, check own status:
           a. CANNOT_COMPOSE or structural validation error → node redecomposes
           b. Other failure → propagate (post-phase)
        """
        nodes_by_depth = self._collect_nodes_by_depth(root, reverse=True)
        issues: List[Tuple[str, str, Optional[CompositionFeedback]]] = []

        for depth, nodes in nodes_by_depth:
            for node in nodes:
                if node.status not in ("failed", "human_needed"):
                    # Check children even if node itself is ok
                    self._check_child_issues(node, issues)
                    continue

                # Check own CANNOT_COMPOSE
                if node.validation and node.validation.repair_action == "redecompose":
                    has_cannot_compose = any(
                        e.error_type == "CANNOT_COMPOSE"
                        for e in (node.validation.structured_errors or [])
                    )
                    if has_cannot_compose or self.validator.should_redecompose(node, node.validation):
                        issues.append((node.node_id, "redecompose_validation", node.composition_feedback))
                        continue

                self._check_child_issues(node, issues)

        return issues

    def _check_child_issues(self, node: Node, issues: List[Tuple[str, str, Optional[CompositionFeedback]]]) -> None:
        """Check children of node for INSUFFICIENT_CAPABILITIES that this node can resolve."""
        for child in node.children:
            if not child.composition_feedback:
                continue
            if not child.composition_feedback.missing_interfaces:
                continue
            if child.status != "failed" and not child.needs_human_intervention:
                continue

            parent_var_names = {gv.variable for gv in node.global_vars}
            can_resolve = False
            for mi in child.composition_feedback.missing_interfaces:
                iface_id = mi.get("interface_id", "")
                parts = iface_id.split(".")
                raw_resource = parts[0] if len(parts) > 1 else iface_id
                resource = self._interface_prefix_map.get(raw_resource, raw_resource)
                if resource in parent_var_names:
                    can_resolve = True
                    self._log(
                        f"PARENT_HAS_RESOURCE: parent={node.name} "
                        f"resource={resource} child={child.name}",
                        node.depth
                    )
                else:
                    self._log(
                        f"PARENT_MISSING_RESOURCE: parent={node.name} "
                        f"resource={resource} child={child.name}",
                        node.depth
                    )

            if can_resolve:
                issues.append((node.node_id, "insufficient_capabilities", child.composition_feedback))
                return  # One child issue triggers parent redecomposition

    # ======================================================================
    # Outer Loop
    # ======================================================================

    def build_tree(self, root_node: Node) -> Node:
        """
        Build the complete decomposition tree.
        BFS level-by-level expansion with immediate top-down codegen.
        Composition verification happens right after each parent's decomposition,
        so root failures are detected before any child work is done.
        Cross-phase issue resolution for INSUFFICIENT_CAPABILITIES.
        """
        self._log("=" * 50)
        self._log(f"Building decomposition tree for: {root_node.name}")
        self._log("=" * 50)

        root_node.status = "pending"
        redecompose_count = 0
        max_redecompose = self.config.max_decompose_retries

        while True:
            # Phase 1: BFS expansion with immediate top-down codegen.
            # Composition verification happens right after each parent's decomposition.
            self._phase1_expand(root_node)

            # Post-Phase 1: check for failures that need redecomposition
            issues = self._resolve_issues_after_phase2(root_node)

            if not issues:
                # Check for unresolvable failures (no ancestor has the missing resource).
                # These propagate upward to mark the tree, but don't re-enter Phase 1.
                self._propagate_failures(root_node)
                self._log("=" * 50)
                self._log("Tree building complete")
                self._log("=" * 50)
                return root_node

            if redecompose_count >= max_redecompose:
                self._log(f"Max redecompose retries ({max_redecompose}) reached", 0)
                for node_id, reason, _feedback in issues:
                    node = self._find_node(root_node, node_id)
                    if node:
                        node.needs_human_intervention = True
                        node.status = "human_needed"
                return root_node

            # Resolve issues: clear subtrees, preserve feedback, re-enter Phase 1
            for node_id, reason, feedback in issues:
                node = self._find_node(root_node, node_id)
                if node:
                    self._save_snapshot(
                        node, "redecompose", redecompose_count,
                        f"redecompose_{reason}",
                        [f"Redecomposing due to: {reason}"]
                    )
                    self._clear_subtree_for_redecompose(node)
                    if feedback:
                        node.composition_feedback = feedback
                    node.status = "pending"

            redecompose_count += 1
            self._log(
                f"Redecomposition round {redecompose_count}/{max_redecompose}: "
                f"resetting {len(issues)} node(s)",
                0
            )

    def save_tree(self, root_node: Node, filename: str = "decomposition_tree.json"):
        """Save the decomposition tree to a JSON file."""
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(root_node.to_json(indent=2))

        self._log(f"Tree saved to: {filepath}")
        return filepath

    def load_tree(self, filepath: str) -> Node:
        """Load a decomposition tree from a JSON file."""
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
