"""
Decomposer mental model test — interactive, parallel, two modes per case.

Test A (Post-decomposition Interview):
  1. Decompose the node
  2. Neutral follow-up questions (no leading, no right/wrong hints)
     - Why these children? How does the decomposition reason?
     - How does each rule get satisfied?
     - What is each child's responsibility boundary?

Test B (Pre-decomposition Alignment):
  1. Ask LLM to explain its understanding of each field (purpose, inputs,
     outputs, global_vars, constraints, acceptance_criteria)
  2. Then decompose

Each case is independent and runs in parallel.
Max concurrency: CHRONOS_MAX_CONCURRENCY env var (default 4).

Env vars (CHRONOS_xxx, fallback to DEEPSEEK_xxx):
  CHRONOS_API_KEY            - API key
  CHRONOS_BASE_URL           - API base URL
  CHRONOS_MODEL              - model name
  CHRONOS_MAX_CONCURRENCY    - max parallel cases (default 4)

Usage:
    python test_decomposer_mind.py
    python test_decomposer_mind.py --case 0
    python test_decomposer_mind.py --cases 0,1,2
    python test_decomposer_mind.py --mode A       # interview only
    python test_decomposer_mind.py --mode B       # alignment only
"""
import json
import os
import sys
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "test_data"))

from openai import OpenAI
from decomposer_cases import get_cases


# -----------------------------------------------------------------------
# Config from env
# -----------------------------------------------------------------------
def _env(key, default=""):
    return os.getenv(key) or os.getenv(f"DEEPSEEK_{key.removeprefix('CHRONOS_')}") or default


BASE_URL = _env("CHRONOS_BASE_URL", "https://api.deepseek.com")
API_KEY = _env("CHRONOS_API_KEY")
MODEL = _env("CHRONOS_MODEL", "deepseek-chat")
MAX_CONCURRENCY = int(os.getenv("CHRONOS_MAX_CONCURRENCY", "4"))
TEMPERATURE = float(os.getenv("CHRONOS_TEMPERATURE", "0.3"))
MAX_TOKENS = int(os.getenv("CHRONOS_MAX_TOKENS", "4096"))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "decomposer_mind", MODEL)


# -----------------------------------------------------------------------
# LLM caller with logging
# -----------------------------------------------------------------------
class LLMLogger:
    def __init__(self, log_dir):
        self.log_dir = log_dir
        self.call_counter = 0
        os.makedirs(log_dir, exist_ok=True)

    def chat(self, messages, max_tokens=None, system_label="", json_mode=False):
        self.call_counter += 1
        call_id = self.call_counter
        max_tokens = max_tokens or MAX_TOKENS

        req = {
            "call_id": call_id,
            "label": system_label,
            "timestamp": time.time(),
            "messages": messages,
            "max_tokens": max_tokens,
            "json_mode": json_mode,
        }
        with open(os.path.join(self.log_dir, f"{call_id:04d}_request.json"), "w", encoding="utf-8") as f:
            json.dump(req, f, indent=2, ensure_ascii=False)

        client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=120)
        start = time.time()
        try:
            kwargs = dict(
                model=MODEL,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=max_tokens,
            )
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            resp = client.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content
        except Exception as e:
            elapsed = time.time() - start
            err_resp = {"call_id": call_id, "elapsed": round(elapsed, 2), "error": str(e)}
            with open(os.path.join(self.log_dir, f"{call_id:04d}_response.json"), "w", encoding="utf-8") as f:
                json.dump(err_resp, f, indent=2, ensure_ascii=False)
            raise
        elapsed = time.time() - start

        resp_data = {"call_id": call_id, "elapsed": round(elapsed, 2), "response": text}
        with open(os.path.join(self.log_dir, f"{call_id:04d}_response.json"), "w", encoding="utf-8") as f:
            json.dump(resp_data, f, indent=2, ensure_ascii=False)

        return text


# -----------------------------------------------------------------------
# Prompt builders
# -----------------------------------------------------------------------
def build_decompose_system():
    """System prompt for decomposer — same as mvp-0.4.4 decomposer._build_system_prompt()."""
    return """You are a software system decomposition agent. Your task is to decompose a function block into smaller child function blocks.

YOU MUST DECOMPOSE. You are NOT allowed to return 0 children or refuse to decompose. Even if the node seems simple, you MUST break it into at least 2 child functions. Decomposition is mandatory — there are no exceptions.

CRITICAL RULES — ENFORCED BY TREE STRUCTURE:

1. PARENT IS SOLE COORDINATOR: The parent function is the ONLY function that calls child functions. Children do NOT call each other. Each child is independent and receives all its inputs from the parent.

2. CHILDREN ARE MUTUALLY INDEPENDENT: No child function may call, reference, or depend on any sibling child. If two children need to share data, the parent must pass the output of one as input to the other.

3. SIGNATURE LOCKING: When you declare a child function, you lock its signature (name, inputs, outputs). The code generator will implement exactly that signature. Do not change signatures after declaration.

4. DATA FLOW THROUGH PARENT: All data flows through the parent. The parent reads global state, passes it to children, collects results, and writes back. Children never directly access parent-level global state.

5. DECOMPOSITION CONTINUES RECURSIVELY: Each child may be further decomposed if it is complex enough. A child stops decomposition when it is simple enough to implement directly (leaf node).

6. COORDINATOR CHILD ALLOWED: A coordinator child node is ALLOWED, as long as it only coordinates work within its own subtree and never calls sibling nodes.

For each child, provide:
- name: function name (Python-valid identifier)
- purpose: one sentence describing what this child does
- inputs: list of {name, type, description}
- outputs: list of {name, type, description}
- signature: Python function signature
- behavior: brief description of internal logic
- data_operations: list of {source_name, operation_type, description} for any global state access

Return ONLY valid JSON with this structure:
{
  "children": [ ... ],
  "decomposition_rationale": "explanation of why this decomposition makes sense"
}"""


def build_decompose_user(node):
    """User prompt for decomposition."""
    inputs_desc = "\n".join(f"  - {i.name}: {i.type} - {i.description}" for i in node.inputs)
    outputs_desc = "\n".join(f"  - {o.name}: {o.type} - {o.description}" for o in node.outputs)
    globals_desc = "\n".join(f"  - {g.variable} ({g.op}): {g.description}" for g in node.global_vars)

    subprd_lines = []
    if node.subprd:
        if node.subprd.description:
            subprd_lines.append(f"\nTask Description:\n{node.subprd.description}")
        if node.subprd.constraints:
            subprd_lines.append(f"\nConstraints:")
            for c in node.subprd.constraints:
                subprd_lines.append(f"  - {c}")
        if node.subprd.acceptance_criteria:
            subprd_lines.append(f"\nAcceptance Criteria:")
            for ac in node.subprd.acceptance_criteria:
                subprd_lines.append(f"  - {ac.ac_id}: {ac.description}")

    subprd_text = "\n".join(subprd_lines)

    # Build input/output format examples
    input_format_lines = []
    for i in node.inputs:
        if i.type == "str" and "|" in i.description:
            # Extract enum values from description
            import re
            enum_match = re.search(r"'([^']+)'(?:\s*\|\s*'([^']+)')+", i.description)
            if enum_match:
                values = re.findall(r"'([^']+)'", i.description)
                input_format_lines.append(f"  {i.name}: string ({'|'.join(values)})")
            else:
                input_format_lines.append(f"  {i.name}: {i.type}")
        elif i.type == "dict":
            input_format_lines.append(f"  {i.name}: object")
        else:
            input_format_lines.append(f"  {i.name}: {i.type}")

    output_format_lines = []
    for o in node.outputs:
        output_format_lines.append(f"  {o.name}: {o.type}")

    # Build example calls based on command enum values
    example_lines = []
    for i in node.inputs:
        if i.type == "str" and "|" in i.description:
            import re
            values = re.findall(r"'([^']+)'", i.description)
            if values and len(values) > 1:
                # Generate example calls
                for v in values[:3]:  # Show up to 3 examples
                    other_args = ", ".join(f'{inp.name}=...' for inp in node.inputs if inp.name != i.name)
                    example_lines.append(f"  {node.name}('{v}', {other_args})")

    return f"""Decompose the following function block:

Node Name: {node.name}
Node Purpose: {node.purpose}

Inputs:
{inputs_desc}

Outputs:
{outputs_desc}

Global Variables:
{globals_desc}
{subprd_text}

INPUT FORMAT:
{chr(10).join(input_format_lines)}

OUTPUT FORMAT:
{chr(10).join(output_format_lines)}

EXAMPLE CALLS:
{chr(10).join(example_lines) if example_lines else '  (see task description above)'}

Decompose this node into child function blocks. Each child should have a clear, single responsibility."""


def build_interview_questions(node, child_names, rationale):
    """Neutral follow-up questions — no leading, no right/wrong hints."""
    return [
        {
            "role": "user",
            "content": (
                f"你将 {node.name} 分解为 {len(child_names)} 个子节点：{', '.join(child_names)}。\n\n"
                f"请说明你的分解思路：为什么选择这些子节点？每个子节点的职责边界是什么？"
            ),
        },
        {
            "role": "user",
            "content": (
                "树结构规则要求：父节点是唯一的协调者，子节点之间不能直接调用。\n"
                "请说明你的分解如何满足这一规则。每个子节点的输入来源是什么？"
            ),
        },
        {
            "role": "user",
            "content": (
                "请说明每个子节点的数据操作范围。"
                "哪些子节点需要读写全局状态？它们的操作是否存在重叠？"
            ),
        },
        {
            "role": "user",
            "content": (
                f"该节点有 {len(node.subprd.acceptance_criteria)} 条验收标准。"
                "请逐条说明你的分解如何覆盖每一条验收标准。"
            ),
        },
    ]


def build_alignment_prompts(node):
    """Ask LLM to explain its understanding of each field before decomposition."""
    prompts = []

    # Purpose
    prompts.append({
        "role": "user",
        "content": (
            f"有一个名为 {node.name} 的节点，其作用是：{node.purpose}\n\n"
            "请说明你对这个节点职责的理解。它应该做什么？不应该做什么？边界在哪里？"
        ),
    })

    # Inputs
    inputs_desc = "\n".join(f"  - {i.name}: {i.type} - {i.description}" for i in node.inputs)
    prompts.append({
        "role": "user",
        "content": (
            f"该节点的输入参数如下：\n{inputs_desc}\n\n"
            "请说明你对每个输入的理解。每个输入携带什么信息？在什么场景下会被使用？"
        ),
    })

    # Outputs
    outputs_desc = "\n".join(f"  - {o.name}: {o.type} - {o.description}" for o in node.outputs)
    prompts.append({
        "role": "user",
        "content": (
            f"该节点的输出参数如下：\n{outputs_desc}\n\n"
            "请说明你对每个输出的理解。输出的内容从哪里来？不同场景下输出有什么变化？"
        ),
    })

    # Global vars
    globals_desc = "\n".join(f"  - {g.variable} ({g.op}): {g.description}" for g in node.global_vars)
    prompts.append({
        "role": "user",
        "content": (
            f"该节点涉及的全局状态如下：\n{globals_desc}\n\n"
            "请说明你对每个全局变量的理解。它的数据结构是什么？读写操作分别在什么场景下发生？"
        ),
    })

    # Constraints
    if node.subprd and node.subprd.constraints:
        constraints_desc = "\n".join(f"  - {c}" for c in node.subprd.constraints)
        prompts.append({
            "role": "user",
            "content": (
                f"该节点有以下约束条件：\n{constraints_desc}\n\n"
                "请说明你对每条约束的理解。这条约束限制了什么？违反它会导致什么后果？"
            ),
        })

    # Acceptance criteria
    if node.subprd and node.subprd.acceptance_criteria:
        ac_desc = "\n".join(f"  - {ac.ac_id}: {ac.description}" for ac in node.subprd.acceptance_criteria)
        prompts.append({
            "role": "user",
            "content": (
                f"该节点有以下验收标准：\n{ac_desc}\n\n"
                "请说明你对每条验收标准的理解。它检验的是什么能力？要满足它需要做什么？"
            ),
        })

    return prompts


# -----------------------------------------------------------------------
# Test runners
# -----------------------------------------------------------------------
def run_test_a(case_index, case, label_prefix="A"):
    """Test A: Decompose then interview."""
    node = case["node"]
    label = f"{label_prefix}_{case_index:02d}_{node.name}"
    log_dir = os.path.join(OUTPUT_DIR, "llm_log", label)
    logger = LLMLogger(log_dir)

    print(f"  [{label}] Start (Test A: decompose + interview)")

    # Step 1: Decompose
    system = build_decompose_system()
    user = build_decompose_user(node)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    t0 = time.time()
    response = logger.chat(messages, system_label="decompose", json_mode=True)
    decompose_elapsed = time.time() - t0

    # Parse response
    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        import re
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if m:
            parsed = json.loads(m.group(1))
        else:
            parsed = {"error": "Failed to parse JSON", "raw": response[:500]}

    children_data = parsed.get("children", [])
    rationale = parsed.get("decomposition_rationale", "")
    child_names = [c.get("name", "?") for c in children_data]

    # Step 2: Interview (multi-turn)
    interview_messages = [
        {"role": "system", "content": (
            "你是一个软件架构师。你刚刚完成了一次函数分解。"
            "接下来会有人就你的分解提出问题。请如实回答，说明你的思路和判断依据。"
        )},
        {"role": "assistant", "content": (
            f"我将 {node.name} 分解为 {len(child_names)} 个子节点：\n"
            + "\n".join(f"{i+1}. {c.get('name', '?')}: {c.get('purpose', '')}" for i, c in enumerate(children_data))
            + f"\n\n分解理由：{rationale}"
        )},
    ]

    questions = build_interview_questions(node, child_names, rationale)
    interview_responses = []

    for q in questions:
        interview_messages.append(q)
        resp = logger.chat(interview_messages, system_label="interview")
        interview_messages.append({"role": "assistant", "content": resp})
        interview_responses.append({"question": q["content"], "answer": resp})

    total_elapsed = time.time() - t0

    # Build report
    report = {
        "test": "A",
        "case_index": case_index,
        "name": node.name,
        "elapsed": round(total_elapsed, 1),
        "llm_calls": logger.call_counter,
        "child_count": len(child_names),
        "children": child_names,
        "children_detail": [
            {"name": c.get("name"), "purpose": c.get("purpose", ""), "signature": c.get("signature", "")}
            for c in children_data
        ],
        "rationale": rationale,
        "interview": interview_responses,
        "expected_range": case["expected_children_range"],
        "tags": case["tags"],
    }

    # Detect routing pattern
    for c in children_data:
        behavior = (c.get("behavior", "") or "").lower()
        if "calls the" in behavior and "child handler" in behavior:
            report["has_routing_pattern"] = True
            report["routing_child"] = c.get("name")
            break

    # Save
    with open(os.path.join(log_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"  [{label}] Done ({total_elapsed:.1f}s, {logger.call_counter} calls, "
          f"{len(child_names)} children)")

    return report


def run_test_b(case_index, case, label_prefix="B"):
    """Test B: Field alignment then decompose."""
    node = case["node"]
    label = f"{label_prefix}_{case_index:02d}_{node.name}"
    log_dir = os.path.join(OUTPUT_DIR, "llm_log", label)
    logger = LLMLogger(log_dir)

    print(f"  [{label}] Start (Test B: alignment + decompose)")

    t0 = time.time()

    # Step 1: Alignment — ask about each field
    alignment_messages = [
        {"role": "system", "content": (
            "你是一个软件架构师。接下来会给你一个函数节点的描述，"
            "请你逐项说明你对每个字段的理解。不需要分解，只需要说明你对需求的理解。"
        )},
    ]

    alignment_prompts = build_alignment_prompts(node)
    alignment_responses = []

    for p in alignment_prompts:
        alignment_messages.append(p)
        resp = logger.chat(alignment_messages, system_label="alignment")
        alignment_messages.append({"role": "assistant", "content": resp})
        alignment_responses.append({"field": p["content"][:80], "understanding": resp})

    # Step 2: Decompose (with alignment context)
    decompose_system = build_decompose_system()
    decompose_user = build_decompose_user(node)

    # Build final messages: alignment history + decompose request
    decompose_messages = [
        {"role": "system", "content": decompose_system},
    ]
    # Add alignment Q&A as context
    for i in range(0, len(alignment_messages) - 1, 2):
        if alignment_messages[i]["role"] != "system":
            decompose_messages.append(alignment_messages[i])
            if i + 1 < len(alignment_messages):
                decompose_messages.append(alignment_messages[i + 1])

    decompose_messages.append({"role": "user", "content": decompose_user})

    response = logger.chat(decompose_messages, system_label="decompose", json_mode=True)
    decompose_elapsed = time.time() - t0

    # Parse
    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        import re
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if m:
            parsed = json.loads(m.group(1))
        else:
            parsed = {"error": "Failed to parse JSON", "raw": response[:500]}

    children_data = parsed.get("children", [])
    rationale = parsed.get("decomposition_rationale", "")
    child_names = [c.get("name", "?") for c in children_data]

    total_elapsed = time.time() - t0

    report = {
        "test": "B",
        "case_index": case_index,
        "name": node.name,
        "elapsed": round(total_elapsed, 1),
        "llm_calls": logger.call_counter,
        "child_count": len(child_names),
        "children": child_names,
        "children_detail": [
            {"name": c.get("name"), "purpose": c.get("purpose", ""), "signature": c.get("signature", "")}
            for c in children_data
        ],
        "rationale": rationale,
        "alignment": alignment_responses,
        "expected_range": case["expected_children_range"],
        "tags": case["tags"],
    }

    for c in children_data:
        behavior = (c.get("behavior", "") or "").lower()
        if "calls the" in behavior and "child handler" in behavior:
            report["has_routing_pattern"] = True
            report["routing_child"] = c.get("name")
            break

    with open(os.path.join(log_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"  [{label}] Done ({total_elapsed:.1f}s, {logger.call_counter} calls, "
          f"{len(child_names)} children)")

    return report


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Decomposer mental model test")
    parser.add_argument("--case", type=int, help="Run single case by index")
    parser.add_argument("--cases", type=str, help="Run selected cases (comma-separated)")
    parser.add_argument("--mode", type=str, choices=["A", "B", "AB"], default="AB",
                        help="A=interview, B=alignment, AB=both (default)")
    args = parser.parse_args()

    if not API_KEY:
        print("ERROR: Set CHRONOS_API_KEY (or DEEPSEEK_API_KEY)")
        return 1

    print(f"API: {BASE_URL}")
    print(f"Model: {MODEL}")
    print(f"Max concurrency: {MAX_CONCURRENCY}")

    all_cases = get_cases()
    if args.case is not None:
        indices = [args.case]
    elif args.cases:
        indices = [int(x) for x in args.cases.split(",")]
    else:
        indices = list(range(len(all_cases)))

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Build task list
    tasks = []
    for i in indices:
        case = all_cases[i]
        if args.mode in ("A", "AB"):
            tasks.append(("A", i, case))
        if args.mode in ("B", "AB"):
            tasks.append(("B", i, case))

    print(f"\nRunning {len(tasks)} tasks with concurrency {MAX_CONCURRENCY}...\n")

    # Execute in parallel
    results = []
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = {}
        for task_type, i, case in tasks:
            if task_type == "A":
                f = pool.submit(run_test_a, i, case)
            else:
                f = pool.submit(run_test_b, i, case)
            futures[f] = (task_type, i, case["node"].name)

        for f in as_completed(futures):
            task_type, i, name = futures[f]
            try:
                report = f.result()
                results.append(report)
            except Exception as e:
                print(f"  [ERROR] {task_type}_{i:02d}_{name}: {e}")
                results.append({"test": task_type, "case_index": i, "name": name, "error": str(e)})

    # Save combined results
    results_path = os.path.join(OUTPUT_DIR, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for r in sorted(results, key=lambda x: (x.get("test", ""), x.get("case_index", 0))):
        test = r.get("test", "?")
        name = r.get("name", "?")
        if "error" in r:
            print(f"  [{test}] {name}: ERROR — {r['error']}")
        else:
            routing = " [ROUTING]" if r.get("has_routing_pattern") else ""
            print(f"  [{test}] {name}: {r.get('child_count', '?')} children, "
                  f"{r.get('llm_calls', '?')} calls, {r.get('elapsed', '?')}s{routing}")

    print(f"\n  Results: {results_path}")
    print(f"  LLM logs: {OUTPUT_DIR}/llm_log/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
