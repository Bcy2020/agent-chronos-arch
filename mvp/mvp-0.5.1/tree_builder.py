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

        ctx = {
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

        if self.config.verbose:
            print("\n" + "=" * 60)
            print("REDECOMPOSE CONTEXT — FEEDING BACK TO LLM")
            print("=" * 60)
            print(f"Node: {node.name}")
            print(f"Previous children: {ctx['previous_children']}")
            print(f"Error types: {ctx['validator_report']['error_types']}")
            print(f"Errors: {ctx['previous_errors']}")
            if ctx['validator_report']['composition_feedback']:
                import json as _json
                print(f"Composition feedback: {_json.dumps(ctx['validator_report']['composition_feedback'], indent=2, ensure_ascii=False)}")
            print("=" * 60 + "\n")

        return ctx

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
    # Phase 1: BFS Expansion with Inline Redecomposition
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

            if self.config.verbose:
                print(f"\n  CHILDREN AFTER DECOMPOSITION [{node.name}]:")
                for c in node.children:
                    ctype = "leaf" if c.stop_decompose else "parent"
                    print(f"    [{ctype}] {c.name}: {c.purpose[:100]}")
                print()

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
        Each node is decomposed, then immediately codegen'd for composition verification.
        If codegen fails with CANNOT_COMPOSE, the node is redecomposed inline
        (no outer round loop needed).
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

                # Parent: decompose + codegen with inline retry
                if node.status == "pending":
                    for attempt in range(self.config.max_decompose_retries):
                        if attempt == 0:
                            self._log(f"  Expanding: {node.name} (depth {node.depth})", node.depth)
                            success = self._phase1_expand_node(node)
                        else:
                            # Redecompose: clear subtree, preserve feedback, re-decompose
                            self._log(f"  Redecomposing: {node.name} (attempt {attempt+1}/{self.config.max_decompose_retries})", node.depth)
                            self._clear_subtree_for_redecompose(node)
                            node.status = "pending"
                            success = self._phase1_expand_node(node)

                        if not success:
                            node.status = "failed"
                            self._log(f"  Expansion FAILED: {node.name}", node.depth)
                            break

                        node.status = "expanded"

                        # Codegen (composition verification)
                        self._log(f"  Codegen parent: {node.name} (depth {node.depth})", node.depth)
                        success = self._phase2_codegen_parent(node)

                        if success:
                            node.status = "codegen_done"
                            self._log(f"  Codegen OK: {node.name}", node.depth)
                            break

                        # Codegen failed → check if redecompose can help
                        if node.validation and node.validation.repair_action == "redecompose":
                            self._save_snapshot(
                                node, "redecompose", attempt,
                                "redecompose_cannot_compose",
                                node.validation.errors or []
                            )
                            # composition_feedback is preserved by _clear_subtree_for_redecompose,
                            # so the next attempt's _phase1_expand_node will use it as context.
                            if attempt < self.config.max_decompose_retries - 1:
                                self._log(f"  Codegen FAILED, redecomposing...", node.depth)
                                continue
                        else:
                            # Non-redecompose failure (syntax, max retries exhausted)
                            self._log(f"  Codegen FAILED (non-redecomposable): {node.name}", node.depth)
                            node.status = "failed"
                            break
                    else:
                        # for-else: loop exhausted without break → max retries reached
                        if node.status != "codegen_done":
                            node.status = "failed"

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

            if self.config.verbose and code:
                print("\n" + "-" * 50)
                print(f"GENERATED CODE [{node.name}]")
                print("-" * 50)
                for line in code.strip().split("\n")[:30]:
                    print(f"  {line}")
                if len(code.strip().split("\n")) > 30:
                    print(f"  ... ({len(code.strip().split('\n'))} total lines)")
                print("-" * 50 + "\n")

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

            if self.config.verbose:
                child_names = {c.name for c in node.children}
                from validator import Validator as _V
                _tmp_v = _V(self.config)
                called = _tmp_v._extract_function_calls(code)
                used = child_names & called
                unused = child_names - called
                print(f"\n  VERBOSE: Child call analysis for [{node.name}]:")
                print(f"    Called functions in code: {sorted(called)}")
                print(f"    Children used: {sorted(used)}")
                print(f"    Children NOT used: {sorted(unused)}")
                print(f"  (end)\n")

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
        """
        nodes_by_depth = self._collect_nodes_by_depth(root, reverse=True)
        for _depth, nodes in nodes_by_depth:
            for node in nodes:
                if node.status in ("failed", "human_needed", "pending"):
                    continue
                for child in node.children:
                    if child.needs_human_intervention or child.status == "human_needed":
                        self._log(
                            f"Propagating failure: {node.name} <- child '{child.name}' "
                            f"needs human intervention",
                            node.depth
                        )
                        node.needs_human_intervention = True
                        node.status = "human_needed"
                        break

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
    # Post-BFS: Remaining Issue Resolution
    # ======================================================================

    def _resolve_insufficient_capabilities(self, root: Node) -> List[Tuple[str, str, Optional[CompositionFeedback]]]:
        """
        Walk bottom-up, check for leaves with INSUFFICIENT_CAPABILITIES
        whose parent has the missing resource → parent redecomposes.
        This is a single-pass fixup after BFS, not a round loop.
        """
        nodes_by_depth = self._collect_nodes_by_depth(root, reverse=True)
        issues: List[Tuple[str, str, Optional[CompositionFeedback]]] = []

        for _depth, nodes in nodes_by_depth:
            for node in nodes:
                self._check_child_issues(node, issues)

        return issues

    # ======================================================================
    # Outer Loop (Single Pass)
    # ======================================================================

    def build_tree(self, root_node: Node) -> Node:
        """
        Build the complete decomposition tree.
        BFS level-by-level expansion with immediate top-down codegen.
        Node-level redecomposition is handled inline during BFS (no round loop).
        Post-BFS: single-pass fixup for INSUFFICIENT_CAPABILITIES.
        """
        self._log("=" * 50)
        self._log(f"Building decomposition tree for: {root_node.name}")
        self._log("=" * 50)

        root_node.status = "pending"

        # BFS expansion with inline redecomposition (no outer round loop).
        # Parent CANNOT_COMPOSE → cleared + redecomposed immediately in _phase1_expand.
        self._phase1_expand(root_node)

        # Post-BFS: handle INSUFFICIENT_CAPABILITIES that need parent redecomposition.
        # This is a single-pass fixup, not a round loop.
        issues = self._resolve_insufficient_capabilities(root_node)
        if issues:
            for node_id, reason, feedback in issues:
                node = self._find_node(root_node, node_id)
                if node:
                    self._save_snapshot(
                        node, "redecompose", 0,
                        f"redecompose_{reason}",
                        [f"Redecomposing due to: {reason}"]
                    )
                    self._clear_subtree_for_redecompose(node)
                    if feedback:
                        node.composition_feedback = feedback
                    node.status = "pending"
            # Re-run BFS for the cleared subtrees (single pass, no round loop)
            self._phase1_expand(root_node)

        # Propagate unresolvable failures upward
        self._propagate_failures(root_node)
        self._log("=" * 50)
        self._log("Tree building complete")
        self._log("=" * 50)
        return root_node

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
