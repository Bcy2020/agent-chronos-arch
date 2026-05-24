"""
Test: Single node decomposition flow with full pre-processing pipeline.

Pipeline:
  1. PRD Converter → JsonPRD
  2. Interface Planner → InterfacePlan
  3. Interface Code Generation → interfaces.py
  4. Create root node from JsonPRD
  5. TreeBuilder processes root node (decompose + codegen + validate + redecompose)

All LLM raw inputs and outputs are saved to tests/output/test_decomposition_flow/llm_log/.
"""
import json
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from api_client import APIClient
from code_generator import CodeGenerator
from prd_converter import PRDConverter
from interface_planner import InterfacePlanner
from interface_normalizer import InterfaceNormalizer
from interface_impl_generator import InterfaceImplementationGenerator
from interface_verifier import InterfaceVerifier
from tree_builder import TreeBuilder
from models import Node, InputParam, OutputParam, CompositionFeedback, FailureContext


OUTPUT_DIR = os.environ.get("TEST_OUTPUT_DIR") or os.path.join(
    os.path.dirname(__file__), "output", "test_decomposition_flow"
)
LLM_LOG_DIR = os.path.join(OUTPUT_DIR, "llm_log")
os.makedirs(LLM_LOG_DIR, exist_ok=True)

PRD_PATH = os.environ.get("TEST_PRD_PATH") or os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "benchmark", "test_cases", "medium", "order_prd.md"
)

_call_counter = 0


class LoggingAPIClient(APIClient):
    """APIClient wrapper that logs all LLM requests/responses to files."""

    def chat(self, messages, temperature=None, max_tokens=4096):
        global _call_counter
        _call_counter += 1
        call_id = _call_counter

        # Determine caller identity from stack
        caller_frame = sys._getframe(1)
        caller_func = caller_frame.f_code.co_name
        caller_module = caller_frame.f_globals.get("__name__", "unknown")

        # Save request
        req = {
            "call_id": call_id,
            "caller": f"{caller_module}.{caller_func}",
            "timestamp": time.time(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        req_path = os.path.join(LLM_LOG_DIR, f"{call_id:04d}_request.json")
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump(req, f, indent=2, ensure_ascii=False)

        # Make actual API call
        print(f"  [LLM call #{call_id}] {caller_module}.{caller_func}...")
        start = time.time()
        response_text = super().chat(messages, temperature, max_tokens)
        elapsed = time.time() - start

        # Save response
        resp = {
            "call_id": call_id,
            "elapsed": round(elapsed, 2),
            "response": response_text,
        }
        resp_path = os.path.join(LLM_LOG_DIR, f"{call_id:04d}_response.json")
        with open(resp_path, "w", encoding="utf-8") as f:
            json.dump(resp, f, indent=2, ensure_ascii=False)

        print(f"    done ({elapsed:.1f}s)")
        return response_text


class NarrativeCodeGenerator(CodeGenerator):
    """CodeGenerator with narrative Step 2 VERIFY prompt (from step2_draft_prompt.md)."""

    def _build_system_prompt_for_parent_verify(self) -> str:
        return "You are a decomposition reviewer. Your task is to judge whether the decomposition (the set of children) is valid, using the submitted code as evidence. You are NOT reviewing code quality — you are reviewing whether the decomposition makes sense given how the code actually uses the children."

    def _build_user_prompt_for_parent_verify(self, node: Node, code: str) -> str:
        parent_inputs = ", ".join(f"{i.name}: {i.type} - {i.description}" for i in node.inputs)
        parent_outputs = ", ".join(f"{o.name}: {o.type} - {o.description}" for o in node.outputs)

        child_lines = []
        for child in (node.children or []):
            contract = node.children_contracts.get(child.name)
            purpose = contract.purpose if contract else child.purpose
            signature = contract.signature if contract else child.name
            child_lines.append(f"- {child.name}：{purpose}。签名：{signature}")
        children_text = "\n".join(child_lines)

        return f"""有一个名为 {node.name} 的节点，其作用是：{node.purpose}。

该节点接受输入：{parent_inputs}，产生输出：{parent_outputs}。

为了实现这个节点，我们计划将其分解为以下 {len(node.children)} 个子节点：

{children_text}

现在有一份实现代码，展示了 {node.name} 实际如何调用上述子节点：

```python
{code}
```

请根据这份代码实际调用了哪些子节点、如何调用，来判断上述分解是否合理。代码是判断分解的依据，而不是审查的对象。你需要从以下三个维度逐一审查分解：

**第一，功能覆盖：** 代码是否覆盖了 {node.name} 的全部职责？每个子节点在分解中承担的功能，是否在代码中有所体现？如果有子节点的功能被遗漏，分解就不能通过。

**第二，直接调用与树结构：** 这是一个树形分解，不是图。每个子节点必须由父节点直接调用——不能通过另一个子节点间接调用。如果代码中某个子节点没有被父节点直接调用（而是由它的兄弟节点调用），那说明分解结构有问题：要么该子节点应该成为调用它的那个子节点的下级，要么它根本不应该被分出来。

**第三，信息充分性：** 代码中不能凭空产生信息。每个函数调用的参数必须有明确来源：要么是父节点的输入，要么是之前子节点的输出，要么是常量。如果某个子节点被调用时使用了没有来源的变量，说明分解时缺少了提供该信息的子节点。

请逐项审查，给出判定结果。如果任意一项不通过，返回 cannot_compose 并说明原因和修复建议；如果全部通过，返回 ok。

返回合法 JSON，格式如下：
{{
  "status": "ok 或 cannot_compose",
  "checks": {{
    "function_coverage": {{"passed": true/false, "reason": "通过原因或失败原因"}},
    "direct_calls": {{"passed": true/false, "reason": "通过原因或失败原因"}},
    "information_sufficiency": {{"passed": true/false, "reason": "通过原因或失败原因"}}
  }},
  "failed_checks": ["未通过的检查项名称"],
  "suggested_fix": "针对分解的修复建议（不是修改代码，而是如何重新分解子节点；仅 cannot_compose 时需要）"
}}"""

    def generate_for_parent(self, node, previous_errors=None, previous_code=None):
        """Override to handle narrative prompt response format."""
        if not node.children:
            return "", ["Cannot generate parent code: no children defined"]

        # Step 1: REVIEW + IMPLEMENT (unchanged)
        messages = [
            {"role": "system", "content": self._build_system_prompt_for_parent()},
            {"role": "user", "content": self._build_user_prompt_for_parent(node, previous_errors, previous_code)}
        ]

        try:
            response = self.api_client.chat(messages, max_tokens=2048)
        except Exception as e:
            return "", [f"API call failed: {e}"]

        parsed = self._parse_response(response)
        status = parsed.get("status", "ok")
        self.last_composition_feedback = None

        if status == "cannot_compose":
            feedback_data = parsed.get("decomposition_feedback", {})
            feedback_data["status"] = "cannot_compose"
            self.last_composition_feedback = CompositionFeedback.from_dict(feedback_data)
            return "", [f"CANNOT_COMPOSE: {self.last_composition_feedback.reason}"]

        if "error" in parsed or not parsed.get("code"):
            return "", [f"Failed to parse code: {parsed.get('error', 'No code generated')}"]

        code = parsed.get("code", "")

        # Step 2: VERIFY with narrative prompt
        verify_messages = [
            {"role": "system", "content": self._build_system_prompt_for_parent_verify()},
            {"role": "user", "content": self._build_user_prompt_for_parent_verify(node, code)}
        ]

        try:
            verify_response = self.api_client.chat(verify_messages, max_tokens=1024)
        except Exception as e:
            print(f"Verification step failed, accepting step 1 code: {e}")
            return code, []

        verify_parsed = self._parse_response(verify_response)
        verify_status = verify_parsed.get("status", "ok")

        if verify_status == "cannot_compose":
            # Build CompositionFeedback from narrative format
            checks = verify_parsed.get("checks", {})
            failed_checks = verify_parsed.get("failed_checks", [])
            suggested_fix = verify_parsed.get("suggested_fix", "")

            # Build reason from failed checks
            reasons = []
            for check_name, check_data in checks.items():
                if not check_data.get("passed", True):
                    reasons.append(f"{check_name}: {check_data.get('reason', '')}")
            reason = "; ".join(reasons) if reasons else "Verification rejected code"

            feedback = CompositionFeedback(
                status="cannot_compose",
                reason=reason,
                failed_checks=failed_checks,
                suggested_fix=suggested_fix,
                checks=checks,
            )
            self.last_composition_feedback = feedback
            return "", [f"CANNOT_COMPOSE: {reason}"]

        return code, []


def save_tree_snapshot(node: Node, path: str):
    """Save a tree node's state for debugging."""
    snapshot = {
        "node_id": node.node_id,
        "name": node.name,
        "depth": node.depth,
        "stop_decompose": node.stop_decompose,
        "stop_reason": node.stop_reason,
        "children": [c.name for c in node.children],
        "children_contracts": {
            k: {"purpose": v.purpose, "signature": v.signature}
            for k, v in node.children_contracts.items()
        } if node.children_contracts else {},
        "needs_human_intervention": node.needs_human_intervention,
        "code_preview": node.code[:200] if node.code else "",
        "attempt_count": len(node.attempt_history),
    }
    if node.last_failure:
        snapshot["last_failure"] = {
            "stage": node.last_failure.stage,
            "errors": node.last_failure.errors,
            "repair_action": node.last_failure.repair_action,
        }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)


def run_test():
    print("=" * 70)
    print("  TEST: Single Node Decomposition Flow")
    print("  PRD: order_prd.md (medium)")
    print("  LLM log: " + LLM_LOG_DIR)
    print("=" * 70)

    # ---------------------------------------------------------------
    # Setup
    # ---------------------------------------------------------------
    if not os.path.exists(PRD_PATH):
        print(f"ERROR: PRD file not found at {PRD_PATH}")
        sys.exit(1)

    cfg = Config(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        temperature=0.2,
        max_depth=3,
        max_children=10,
        max_retries=3,
        max_decompose_retries=3,
        output_dir=OUTPUT_DIR,
        nodes_dir=os.path.join(OUTPUT_DIR, "nodes"),
    )

    if not cfg.api_key:
        print("ERROR: DEEPSEEK_API_KEY not set")
        sys.exit(1)

    api_client = LoggingAPIClient(cfg)

    # ---------------------------------------------------------------
    # Phase 0: PRD Conversion
    # ---------------------------------------------------------------
    print("\n" + "-" * 70)
    print("Phase 0: PRD Converter")
    print("-" * 70)

    with open(PRD_PATH, "r", encoding="utf-8") as f:
        prd_text = f.read()
    converter = PRDConverter(cfg, api_client)
    json_prd = converter.convert_and_save(prd_text, OUTPUT_DIR)
    if json_prd:
        print(f"  Converted: {len(json_prd.functional_requirements)} FRs, {len(json_prd.global_state_sources)} data sources")
    else:
        print("  WARNING: PRD conversion returned None, continuing with legacy mode")

    # ---------------------------------------------------------------
    # Phase 1: Root Node Creation
    # ---------------------------------------------------------------
    print("\n" + "-" * 70)
    print("Phase 1: Root Node Creation")
    print("-" * 70)

    from main import create_root_from_prd
    root = create_root_from_prd(PRD_PATH, name=None, json_prd=json_prd)
    print(f"  Root: {root.name}")
    print(f"  Purpose: {root.purpose[:60]}...")
    print(f"  Data sources: {len(root.data_sources)}")
    print(f"  Global vars: {len(root.global_vars)}")

    # ---------------------------------------------------------------
    # Phase 2: Interface Planning
    # ---------------------------------------------------------------
    print("\n" + "-" * 70)
    print("Phase 2: Interface Planner")
    print("-" * 70)

    interface_plan = None
    if json_prd:
        planner = InterfacePlanner(cfg, api_client)
        interface_plan = planner.plan(json_prd)
        if interface_plan and interface_plan.resources:
            print(f"  Resources: {len(interface_plan.resources)}")
            print(f"  Interfaces: {len(interface_plan.interfaces)}")
        else:
            print("  Interface plan is empty, skipping")

    # ---------------------------------------------------------------
    # Phase 3: Interface Code Generation
    # ---------------------------------------------------------------
    print("\n" + "-" * 70)
    print("Phase 3: Interface Code Generation")
    print("-" * 70)

    if interface_plan and interface_plan.resources:
        normalizer = InterfaceNormalizer()
        normalizer.normalize_plan(interface_plan)
        plan_errors = normalizer.validate_plan(interface_plan)
        if plan_errors:
            print(f"  Plan validation issues: {len(plan_errors)}")
            for err in plan_errors:
                print(f"    - {err}")
        else:
            print(f"  Interface Plan validation: PASSED")

        impl_gen = InterfaceImplementationGenerator(cfg, api_client)
        interface_code = impl_gen.generate(interface_plan)

        verifier = InterfaceVerifier(interface_plan)
        verify_errors = verifier.verify(interface_code)
        if verify_errors:
            print(f"  Verification FAILED: {len(verify_errors)} issues")
        else:
            print(f"  Interface code verification: PASSED")

        interface_dir = os.path.join(OUTPUT_DIR, "generated")
        os.makedirs(interface_dir, exist_ok=True)
        interface_path = os.path.join(interface_dir, "interfaces.py")
        with open(interface_path, "w", encoding="utf-8") as f:
            f.write(interface_code)
        print(f"  Generated: {interface_path}")
    else:
        print("  Skipping (no interface plan)")

    # ---------------------------------------------------------------
    # Phase 4: Root Node Decomposition Loop
    # ---------------------------------------------------------------
    print("\n" + "-" * 70)
    print("Phase 4: Root Node Decomposition Loop")
    print("-" * 70)

    builder = TreeBuilder(cfg, interface_plan=interface_plan, api_client=api_client)
    builder.code_generator = NarrativeCodeGenerator(cfg, api_client)
    if interface_plan:
        builder.code_generator.set_interface_plan(interface_plan)

    start = time.time()
    result_node, success = builder._process_node(root)
    elapsed = time.time() - start

    # Save final snapshot
    save_tree_snapshot(result_node, os.path.join(OUTPUT_DIR, "final_snapshot.json"))

    # ---------------------------------------------------------------
    # Results
    # ---------------------------------------------------------------
    print()
    print("=" * 70)
    print("  RESULTS")
    print("=" * 70)
    print(f"  Success: {success}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Attempts: {len(result_node.attempt_history)}")
    print(f"  Children: {len(result_node.children)}")
    print(f"  Needs human intervention: {result_node.needs_human_intervention}")
    print()

    print("  Attempt History:")
    for i, att in enumerate(result_node.attempt_history):
        print(f"    [{i}] stage={att.stage} attempt={att.attempt_number} decision={att.decision}")

    print()

    # Check CANNOT_COMPOSE rejections
    cannot_compose_count = sum(
        1 for att in result_node.attempt_history
        if "CANNOT_COMPOSE" in str(att.validation_errors)
    )
    if cannot_compose_count > 0:
        print(f"  CANNOT_COMPOSE rejections: {cannot_compose_count}")

    # Collect results for JSON
    results = {
        "prd": os.path.basename(PRD_PATH),
        "llm_log_dir": "llm_log/",
        "success": success,
        "elapsed": elapsed,
        "child_count": len(result_node.children),
        "needs_human_intervention": result_node.needs_human_intervention,
        "attempt_count": len(result_node.attempt_history),
        "cannot_compose_count": cannot_compose_count,
        "total_llm_calls": _call_counter,
        "attempts": [
            {
                "stage": att.stage,
                "attempt": att.attempt_number,
                "decision": att.decision,
                "errors": att.validation_errors,
            }
            for att in result_node.attempt_history
        ],
    }

    result_path = os.path.join(OUTPUT_DIR, "result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  Results: {result_path}")
    print()

    if success:
        print("  TEST PASSED: Root node decomposition succeeded within retry limit")
        print("=" * 70)
        return 0
    else:
        print("  TEST FAILED: Root node decomposition did not succeed within max retries")
        print("  See results above and LLM logs for details.")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(run_test())
