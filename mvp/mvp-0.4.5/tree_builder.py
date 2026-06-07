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
from models import Node, InputParam, OutputParam, Boundary, StateOperation, SubPRD, AttemptRecord, InterfacePlan, ValidationResult, ValidationError, FailureContext


class TreeBuilder:
    def __init__(self, config: Config, interface_plan: InterfacePlan = None, api_client: APIClient = None):
        self.config = config
        self.api_client = api_client if api_client is not None else APIClient(config)
        self.decomposer = Decomposer(config, self.api_client)
        self.code_generator = CodeGenerator(config, self.api_client)
        self.validator = Validator(config, interface_plan)
        
        self.output_dir = config.output_dir
        self.nodes_dir = config.nodes_dir
        
        self.interface_plan = interface_plan
        self.capability_allocator = CapabilityAllocator(interface_plan) if interface_plan else None
        self.interface_plan_summary = self._build_interface_summary() if interface_plan else ""
        
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
                self._log(f"Prepared {len(grant.candidate_interfaces)} candidate interface(s) for '{child.name}'", node.depth)

    def _build_decompose_context_from_failure(self, node: Node) -> Dict[str, Any]:
        """Build previous_errors dict from last_failure for re-decomposition."""
        if not node.last_failure:
            return {}
        lf = node.last_failure
        ctx: Dict[str, Any] = {}
        if lf.errors:
            ctx["previous_errors"] = lf.errors
        if lf.children_snapshot:
            ctx["previous_children"] = lf.children_snapshot
        if lf.decomposition_rationale:
            ctx["previous_rationale"] = lf.decomposition_rationale
        if lf.generated_code:
            ctx["previous_code"] = lf.generated_code
        validator_report: Dict[str, Any] = {}
        if lf.structured_errors:
            validator_report["structured_errors"] = [e.to_dict() for e in lf.structured_errors]
        if lf.composition_feedback:
            validator_report["composition_feedback"] = lf.composition_feedback.to_dict()
        if lf.fix_summary:
            validator_report["fix_summary"] = lf.fix_summary
        if validator_report:
            ctx["validator_report"] = validator_report
        return ctx

    def _build_decompose_messages(self, node: Node, retry_count: int) -> List[Dict[str, str]]:
        """Build multi-turn messages based on failure type."""
        messages = [
            {"role": "system", "content": self.decomposer._build_system_prompt()},
            {"role": "user", "content": self.decomposer._build_user_prompt(node, interface_plan_summary=self.interface_plan_summary)}
        ]

        if retry_count > 0 and node.last_failure:
            # Add previous assistant message (compact format)
            assistant_content = self._format_decompose_response(node)
            messages.append({"role": "assistant", "content": assistant_content})

            # Add feedback message based on failure type
            feedback_content = self._build_feedback_message(node)
            messages.append({"role": "user", "content": feedback_content})

        return messages

    def _format_decompose_response(self, node: Node) -> str:
        """Format previous decomposition output as compact assistant message.
        Uses last_failure snapshot when node.children has been cleared."""
        # Use live children if available, otherwise fall back to snapshot
        if node.children:
            child_names = [c.name for c in node.children]
            child_map = {c.name: c for c in node.children}
        elif node.last_failure and node.last_failure.children_snapshot:
            child_names = node.last_failure.children_snapshot
            child_map = {}
        else:
            return f"I decomposed {node.name} but produced no children."

        n = len(child_names)
        lines = [f"I decomposed {node.name} into {n} children:"]

        for i, name in enumerate(child_names, 1):
            # Try live node first, then contracts, then snapshot
            child = child_map.get(name)
            contract = node.children_contracts.get(name) if node.children_contracts else None
            if contract:
                purpose = contract.purpose
                signature = contract.signature
            elif child:
                purpose = child.purpose
                signature = child.name
            else:
                purpose = "(unknown)"
                signature = name
            lines.append(f"{i}. {name}: {purpose}. Signature: {signature}")

        rationale = node.decomposition_rationale
        if not rationale and node.last_failure:
            rationale = node.last_failure.decomposition_rationale
        lines.append(f"\nRationale: {rationale}")
        return "\n".join(lines)

    def _build_feedback_message(self, node: Node) -> str:
        """Build feedback message based on failure type."""
        if not node.last_failure:
            return "Please re-decompose."

        stage = node.last_failure.stage

        if stage == "decompose":
            return self._build_truncation_feedback(node)
        elif stage == "codegen":
            if node.last_failure.composition_feedback:
                return self._build_cannot_compose_feedback(node)
            return self._build_codegen_feedback(node)
        elif stage == "validate":
            return self._build_validation_feedback(node)

        return "Please re-decompose."

    def _build_truncation_feedback(self, node: Node) -> str:
        """Truncation re-decomposition feedback."""
        n = len(node.last_failure.children_snapshot)
        max_children = self.config.max_children
        return f"Your previous decomposition produced {n} children, exceeding the limit of {max_children}. Please re-decompose with at most {max_children} children. You can merge children with similar responsibilities or reduce unnecessary splitting."

    def _build_cannot_compose_feedback(self, node: Node) -> str:
        """Step 2 failure re-decomposition feedback."""
        feedback = node.last_failure.composition_feedback
        lines = ["The code review of your previous decomposition did not pass."]

        if feedback.failed_checks:
            lines.append(f"\nFailed checks: {', '.join(feedback.failed_checks)}")

        if feedback.reason:
            lines.append(f"Reason: {feedback.reason}")

        if feedback.suggested_fix:
            lines.append(f"\nSuggested fix: {feedback.suggested_fix}")

        lines.append("\nPlease re-decompose according to the suggestions.")
        return "\n".join(lines)

    def _build_codegen_feedback(self, node: Node) -> str:
        """Other codegen failure re-decomposition feedback."""
        lines = ["Code generation failed for your previous decomposition."]
        lines.append(f"\nErrors:")
        for err in node.last_failure.errors:
            lines.append(f"- {err}")
        lines.append("\nPlease fix the decomposition to resolve these issues.")
        return "\n".join(lines)

    def _build_validation_feedback(self, node: Node) -> str:
        """Validation failure re-decomposition feedback."""
        lines = ["The validation of your previous decomposition did not pass."]
        lines.append(f"\nValidation errors:")
        for err in node.last_failure.errors:
            lines.append(f"- {err}")
        lines.append("\nPlease fix the decomposition to resolve these issues.")
        return "\n".join(lines)

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
        # Use last_failure if available, otherwise use errors parameter
        validation_errors = errors or []
        structured_errors = []
        if node.last_failure:
            validation_errors = node.last_failure.errors
            structured_errors = [e.to_dict() for e in node.last_failure.structured_errors]

        record = AttemptRecord(
            stage=stage,
            attempt_number=attempt,
            children_snapshot=[c.name for c in node.children] if node.children else [],
            contracts_snapshot={k: v.to_dict() for k, v in node.children_contracts.items()} if node.children_contracts else {},
            decomposition_rationale=node.decomposition_rationale or "",
            generated_code=node.code or "",
            validation_errors=validation_errors,
            structured_errors=structured_errors,
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
                # Save failure context
                node.last_failure = FailureContext(
                    stage="codegen",
                    errors=errors,
                    structured_errors=[],
                    generated_code=previous_code,
                )
                node.code = ""
                self._save_snapshot(node, "codegen_leaf", retry_count, "retry_code", errors)
                retry_count += 1
                continue

            node.code = code
            validation = self.validator.validate(node, code)

            if validation.passed:
                self._log(f"Leaf code validated successfully", node.depth)
                self._save_snapshot(node, "validate", retry_count, "passed")
                self._save_node_code(node)
                return node, True

            self._log(f"Leaf code validation failed: {validation.errors}", node.depth)
            # Save failure context
            node.last_failure = FailureContext(
                stage="validate",
                errors=validation.errors,
                structured_errors=validation.structured_errors,
                generated_code=code,
                repair_action=validation.repair_action,
                fix_summary=validation.fix_summary,
            )
            self._save_snapshot(node, "validate", retry_count, "retry_code", validation.errors)
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
        Uses FailureContext to preserve failure information across retries.
        """
        retry_count = 0
        max_retries = self.config.max_decompose_retries

        self._save_snapshot(node, "decompose", retry_count, "started")

        while retry_count < max_retries:
            self._log(f"Decomposition attempt {retry_count + 1}/{max_retries}", node.depth)

            # 1. Decompose stage
            if retry_count > 0 or not node.children:
                if retry_count == 0:
                    # First attempt: three-stage decomposition
                    self._log(f"Starting three-stage decomposition...", node.depth)
                    node, decomp_errors = self.decomposer.decompose_staged(
                        node,
                        interface_plan_summary=self.interface_plan_summary
                    )
                    # Capture message history for potential re-decomposition
                    decomp_messages = getattr(node, '_staged_messages', [])
                else:
                    # Re-decomposition: restart from Stage 1 with full message history
                    prev_messages = None
                    if hasattr(node, '_staged_messages') and node._staged_messages:
                        prev_messages = node._staged_messages
                    elif node.last_failure and node.last_failure.decompose_messages:
                        prev_messages = node.last_failure.decompose_messages

                    decomp_context = self._build_decompose_context_from_failure(node)
                    self._log(f"Re-decomposing with message history ({len(prev_messages or [])} msgs)...", node.depth)
                    node, decomp_errors = self.decomposer.decompose_staged_with_history(
                        node,
                        previous_errors=decomp_context,
                        message_history=prev_messages,
                        interface_plan_summary=self.interface_plan_summary
                    )
                    # Update message history
                    decomp_messages = getattr(node, '_staged_messages', prev_messages or [])

                if decomp_errors:
                    self._log(f"Decomposition failed: {decomp_errors}", node.depth)
                    # Save failure context
                    node.last_failure = FailureContext(
                        stage="decompose",
                        errors=decomp_errors,
                        structured_errors=[],
                        decompose_messages=decomp_messages,
                        decompose_response=self.decomposer.last_response,
                        children_snapshot=[c.name for c in node.children],
                        decomposition_rationale=node.decomposition_rationale,
                    )
                    self._save_snapshot(node, "decompose", retry_count, "failed", decomp_errors)
                    retry_count += 1
                    continue

            self._log(f"Decomposed into {len(node.children)} children", node.depth)

            # 2. Codegen stage
            self._log(f"Generating parent code...", node.depth)
            code, code_errors = self.code_generator.generate_with_retry(node)

            if code_errors:
                if any(e.startswith("CANNOT_COMPOSE") for e in code_errors):
                    # Save failure context
                    node.last_failure = FailureContext(
                        stage="codegen",
                        errors=code_errors,
                        structured_errors=[],
                        decompose_messages=node.last_failure.decompose_messages if node.last_failure else [],
                        decompose_response=node.last_failure.decompose_response if node.last_failure else "",
                        children_snapshot=[c.name for c in node.children],
                        decomposition_rationale=node.decomposition_rationale,
                        generated_code=code,
                        composition_feedback=self.code_generator.last_composition_feedback,
                    )
                    self._save_snapshot(node, "codegen_parent", retry_count, "redecompose", code_errors)
                    node.children = []
                    node.children_contracts = {}
                    retry_count += 1
                    continue

                self._log(f"Code generation failed: {code_errors}", node.depth)
                # Save failure context
                node.last_failure = FailureContext(
                    stage="codegen",
                    errors=code_errors,
                    structured_errors=[],
                    decompose_messages=node.last_failure.decompose_messages if node.last_failure else [],
                    decompose_response=node.last_failure.decompose_response if node.last_failure else "",
                    children_snapshot=[c.name for c in node.children],
                    decomposition_rationale=node.decomposition_rationale,
                    generated_code=code,
                )
                self._save_snapshot(node, "codegen_parent", retry_count, "retry_code", code_errors)
                retry_count += 1
                continue

            node.code = code

            # 3. Conservation check
            conservation_errors = self.validator.check_conservation(node)
            if conservation_errors:
                self._log(f"Conservation check failed: {conservation_errors}", node.depth)
                # Save failure context
                node.last_failure = FailureContext(
                    stage="validate",
                    errors=conservation_errors,
                    structured_errors=[],
                    decompose_messages=node.last_failure.decompose_messages if node.last_failure else [],
                    decompose_response=node.last_failure.decompose_response if node.last_failure else "",
                    children_snapshot=[c.name for c in node.children],
                    decomposition_rationale=node.decomposition_rationale,
                    generated_code=code,
                    repair_action="redecompose",
                )
                self._save_snapshot(node, "validate", retry_count, "redecompose_conservation", conservation_errors)
                node.children = []
                node.children_contracts = {}
                node.code = ""
                retry_count += 1
                continue

            # 4. Capability allocation
            if self.capability_allocator:
                self._log(f"Running capability allocation for {len(node.children)} children...", node.depth)
                self._allocate_capabilities(node)

            # 5. Validate stage
            validation = self.validator.validate(node, code)

            if validation.passed:
                self._log(f"Parent code validated successfully", node.depth)
                self._save_snapshot(node, "validate", retry_count, "passed")
                self._save_node_code(node)
                return node, True

            self._log(f"Validation failed: {validation.errors}", node.depth)

            # Save failure context
            node.last_failure = FailureContext(
                stage="validate",
                errors=validation.errors,
                structured_errors=validation.structured_errors,
                decompose_messages=node.last_failure.decompose_messages if node.last_failure else [],
                decompose_response=node.last_failure.decompose_response if node.last_failure else "",
                children_snapshot=[c.name for c in node.children],
                decomposition_rationale=node.decomposition_rationale,
                generated_code=code,
                repair_action=validation.repair_action,
                fix_summary=validation.fix_summary,
            )

            if validation.repair_action == "redecompose" or self.validator.should_redecompose(node, validation, retry_count):
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
