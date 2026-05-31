"""
[VERIFIED 2026-05-28] Experiment 1: Baseline (Two-Phase Separation)
Result: 5/5 routing = 100% — separation alone does NOT reduce routing.
Output: output/attention_separation/deepseek-v4-flash/

Attention Separation Experiment.

Hypothesis: The decomposer prompt overloads attention by asking for ~20 rules
simultaneously (tree structure, interfaces, global vars, data operations, etc.).
By separating decomposition (Phase 1) from interface derivation (Phase 2), each
phase gets focused attention on fewer dimensions, reducing reliance on training
data priors (routing pattern).

Method:
  Phase 1 (decompose): Given parent PRD, produce children with ONLY name, purpose,
    behavior, and stop_decompose. NO inputs, outputs, global_vars, data_operations,
    traceability, constraints, acceptance_criteria, requested_capabilities.

  Phase 2 (interfaces): Given Phase 1 output, derive inputs/outputs with types,
    sources, consumers for each child, plus dataflow_edges.

Comparison: Routing rate vs baseline (single-pass, from existing trials).

Usage:
    python test_attention_separation.py
"""
import json
import os
import sys
import time
import re
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from openai import OpenAI


# -----------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------
def _env(key, default=""):
    return os.getenv(key) or os.getenv(f"DEEPSEEK_{key.removeprefix('CHRONOS_')}") or default

TEMPERATURE = float(os.getenv("CHRONOS_TEMPERATURE", "0.3"))
MAX_TOKENS_PHASE1 = int(os.getenv("CHRONOS_MAX_TOKENS", "8192"))
MAX_TOKENS_PHASE2 = int(os.getenv("CHRONOS_MAX_TOKENS", "8192"))
MAX_CONCURRENCY = int(os.getenv("CHRONOS_MAX_CONCURRENCY", "5"))

MIMO_MODELS = {"mimo-v2.5", "mimo-v2-flash", "mimo-v2.5-pro", "mimo-v2-pro", "mimo-v2-omni"}
MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"

PREREQUISITES_DIR = os.path.join(
    os.path.dirname(__file__), "output", "routing_ablation", "prerequisites"
)

OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "output", "attention_separation"
)

NUM_TRIALS = 5


# -----------------------------------------------------------------------
# Phase 1 prompt — ONLY structure, NO interfaces
# -----------------------------------------------------------------------
PHASE1_SYSTEM_PROMPT = """You are a software system decomposition agent. Your task is to decompose a function block into smaller child function blocks.

CRITICAL RULES:
1. EVERY CHILD MUST BE A FUNCTION, NOT A CLASS.
2. TREE STRUCTURE (not graph): The decomposition forms a tree. Children MUST NOT call each other (no cross-calls between siblings). The parent MUST explicitly and directly invoke all its children.
3. Do NOT add extra external inputs or outputs beyond what the parent has.
4. Children should be at the same abstraction level and minimally overlapping.

SEMANTIC STOP CONDITIONS — STOP DECOMPOSITION when:
1. PURE FUNCTION: Only mathematical transformations, no state/I/O/side effects.
2. ATOMIC OPERATION: Exactly one operation on exactly one data source.
3. MAXIMUM DEPTH REACHED.

DO NOT STOP if the node contains business logic, branching, loops, or coordinates multiple operations.

OUTPUT FORMAT — Return valid JSON:
{
  "children": [
    {
      "name": "ChildName",
      "purpose": "What this child function does",
      "behavior": "How this function transforms inputs to outputs",
      "stop_decompose": false,
      "stop_reason": ""
    }
  ],
  "decomposition_rationale": "Explain how these children work together",
  "dataflow_edges": [
    {
      "from_node": "parent | ChildName",
      "from_output": "output_name",
      "to_node": "ChildName | parent",
      "to_input": "input_name",
      "note": "why this dataflow exists"
    }
  ]
}

IMPORTANT: Output ONLY name, purpose, behavior, and stop_decompose per child.
Do NOT include inputs, outputs, global_vars, data_operations, or any other fields.
Those will be derived in a separate step."""


# -----------------------------------------------------------------------
# Phase 2 prompt — derive interfaces from decomposition
# -----------------------------------------------------------------------
PHASE2_SYSTEM_PROMPT = """You are an interface derivation agent. Given a decomposition tree with children (names, purposes, behavior), your task is to derive precise interfaces — inputs, outputs, types, sources, and consumers — for each child.

RULES:
1. SIGNATURE LOCKING: Each child's inputs/outputs become a LOCKED signature. Use precise Python types: str, int, float, bool, dict, list, Optional[dict], etc.

2. DATAFLOW CLOSURE: Every child input must have an explicit source:
   - a parent input,
   - an output of an earlier sibling child,
   - a local constant/config value.

3. Every child output that is consumed by another child must have that child named as consumer.

4. Parent inputs are consumed by children; parent outputs are produced by children.

5. Do NOT invent unnecessary parameters.

OUTPUT FORMAT — Return valid JSON with updated children plus dataflow_edges:
{
  "children": [
    {
      "name": "ChildName",
      "purpose": "(unchanged)",
      "behavior": "(unchanged)",
      "inputs": [{"name": "param", "type": "str", "description": "desc", "source": "where data comes from"}],
      "outputs": [{"name": "result", "type": "dict", "description": "desc", "consumer": "who uses this"}],
      "signature": "def ChildName(param1: type1) -> return_type",
      "stop_decompose": false,
      "stop_reason": ""
    }
  ],
  "interface_preservation": {
    "parent_inputs_covered_by": {"input_name": "child_name"},
    "parent_outputs_produced_by": {"output_name": "child_name"}
  },
  "dataflow_edges": [
    {
      "from_node": "parent | ChildName",
      "from_output": "output_name",
      "to_node": "ChildName | parent",
      "to_input": "input_name",
      "note": "why"
    }
  ]
}"""


# -----------------------------------------------------------------------
# Build Phase 1 user prompt (simplified, like the existing decomposer but stripped)
# -----------------------------------------------------------------------
def build_phase1_user_prompt(node_info):
    """Build Phase 1 user prompt with only structural requirements."""
    lines = [
        "Decompose the following function block:",
        "",
        f"Node Name: {node_info['name']}",
        f"Node Purpose: {node_info['purpose']}",
        "",
    ]

    if node_info.get("description"):
        lines.append(node_info["description"])
        lines.append("")

    lines.append("Inputs:")
    lines.append(f"  - {node_info.get('input_desc', 'input: Any - System input')}")
    lines.append("Outputs:")
    lines.append(f"  - {node_info.get('output_desc', 'output: Any - System output')}")
    lines.append("")

    if node_info.get("constraints"):
        lines.append("Constraints:")
        for c in node_info["constraints"]:
            lines.append(f"  - {c}")
        lines.append("")

    if node_info.get("data_sources"):
        lines.append("Available Data Stores:")
        for ds in node_info["data_sources"]:
            lines.append(f"  - {ds}")
        lines.append("")

    lines.append("Maximum children allowed: 10")
    lines.append("Maximum depth: 3")
    lines.append("")
    lines.append("Return ONLY the JSON response with name, purpose, behavior per child.")
    lines.append("Do NOT include inputs, outputs, global_vars, or data_operations.")

    return "\n".join(lines)


def build_phase2_user_input(decomposition, node_info):
    """Build Phase 2 user prompt: the decomposition + request to derive interfaces."""
    children = decomposition.get("children", [])
    summary_lines = [
        "Here is the decomposition from Phase 1. Derive interfaces (inputs, outputs, types, sources, consumers) for each child.",
        "",
        f"Parent name: {node_info['name']}",
        f"Parent purpose: {node_info['purpose']}",
        "",
        "Parent inputs:",
        f"  - {node_info.get('input_desc', 'input: Any - System input')}",
        "Parent outputs:",
        f"  - {node_info.get('output_desc', 'output: Any - System output')}",
        "",
        "Available Data Stores:",
    ]
    if node_info.get("data_sources"):
        for ds in node_info["data_sources"]:
            summary_lines.append(f"  - {ds}")
    else:
        summary_lines.append("  - (none)")

    summary_lines.append("")
    summary_lines.append("Available Data Interfaces:")
    if node_info.get("data_interfaces"):
        for di in node_info["data_interfaces"]:
            summary_lines.append(f"  - {di}")
    else:
        summary_lines.append("  - (none)")

    summary_lines.append("")
    summary_lines.append("\n".join(
        f"Child {c.get('name', '')}: purpose='{c.get('purpose', '')}', behavior='{c.get('behavior', '')}'"
        for c in children
    ))

    summary_lines.append("")
    summary_lines.append("""For each child, determine:
1. What inputs does it need? What TYPE each input is? Where does it COME FROM (which child or parent input)?
2. What outputs does it produce? What TYPE each output is? Who CONSUMES it (which child or parent output)?""")

    return "\n".join(summary_lines)


# -----------------------------------------------------------------------
# LLM Logger (same pattern as test_routing_ablation.py)
# -----------------------------------------------------------------------
class LLMLogger:
    def __init__(self, log_dir, api_key, base_url, model):
        self.log_dir = log_dir
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.call_counter = 0
        os.makedirs(log_dir, exist_ok=True)

    def chat(self, messages, max_tokens=None):
        self.call_counter += 1
        call_id = self.call_counter
        max_tokens = max_tokens or MAX_TOKENS_PHASE1

        req = {
            "call_id": call_id,
            "timestamp": time.time(),
            "messages": messages,
            "max_tokens": max_tokens,
            "model": self.model,
        }
        with open(os.path.join(self.log_dir, f"{call_id:04d}_request.json"), "w", encoding="utf-8") as f:
            json.dump(req, f, indent=2, ensure_ascii=False)

        client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=120)
        start = time.time()
        try:
            kwargs = dict(
                model=self.model,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=max_tokens,
                extra_body={"thinking": {"type": "disabled"}},
            )
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


def parse_json(text):
    """Parse JSON from LLM response, handling markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    if "}" in text:
        last_brace = text.rfind("}")
        text = text[:last_brace + 1]
    text = re.sub(r'(?<=[\s:,\[{])[fFrRuUbB]+(")', r'\1', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except:
                pass
    return {"error": "JSON parse failed", "raw": text[:500]}


# -----------------------------------------------------------------------
# Routing detection
# -----------------------------------------------------------------------
ROUTING_PATTERNS = [
    re.compile(r'calls?\s+(?:the\s+)?(?:appropriate\s+)?(?:child\s+)?(?:handler\s+)?(\w+)', re.IGNORECASE),
    re.compile(r'invoke[s]?\s+(\w+)', re.IGNORECASE),
    re.compile(r'dispatch(?:es)?\s+(?:to\s+)?(\w+)', re.IGNORECASE),
    re.compile(r'route[s]?\s+(?:to\s+)?(\w+)', re.IGNORECASE),
]

ROUTER_NAME_PATTERNS = re.compile(
    r'(?:^router$|^dispatcher$|route|dispatch|parse.*input|parse.*command|process.*command)',
    re.IGNORECASE
)

ROUTER_PURPOSE_PATTERNS = re.compile(
    r'(?:route[s]?\s+(?:the\s+)?(?:command|request|input)|dispatch(?:es)?\s+(?:to\s+)?(?:the\s+)?(?:appropriate|correct|corresponding))',
    re.IGNORECASE
)


def detect_routing(children):
    """Detect if any child calls a sibling (routing violation)."""
    child_names = {c.get("name", "") for c in children}
    sibling_calls = []

    for c in children:
        cname = c.get("name", "")
        text = c.get("purpose", "") + " " + c.get("behavior", "")
        for pattern in ROUTING_PATTERNS:
            for match in pattern.finditer(text):
                target = match.group(1)
                if target in child_names and target != cname:
                    sibling_calls.append({"from": cname, "to": target, "method": "text_pattern"})

    router_nodes = []
    for c in children:
        name = c.get("name", "")
        purpose = c.get("purpose", "")
        behavior = c.get("behavior", "")
        combined = purpose + " " + behavior
        is_router = False
        if ROUTER_NAME_PATTERNS.search(name):
            is_router = True
        if ROUTER_PURPOSE_PATTERNS.search(combined):
            is_router = True
        if is_router:
            router_nodes.append(name)

    if router_nodes and len(children) > len(router_nodes):
        for router in router_nodes:
            for c in children:
                other_name = c.get("name", "")
                if other_name != router:
                    sibling_calls.append({"from": router, "to": other_name, "method": "structural_router"})

    seen = set()
    unique = []
    for sc in sibling_calls:
        key = (sc["from"], sc["to"], sc["method"])
        if key not in seen:
            seen.add(key)
            unique.append(sc)

    return len(unique) > 0, unique


# -----------------------------------------------------------------------
# PRD-specific: order_real
# -----------------------------------------------------------------------
ORDER_REAL_NODE = {
    "name": "Order_Management_System",
    "purpose": "Order Management System",
    "input_desc": "input: Any - System input (JSON with command and order_data fields)",
    "output_desc": "output: Any - System output (JSON with success, message, and data)",
    "description": """INPUT FORMAT:
  Format: json
  Input is a JSON object with command and order_data fields.
  command: string - one of create_order, pay_order, ship_order, complete_order, cancel_order, list_orders, get_user_orders, list_products
  order_data: object - contains fields depending on command

OUTPUT FORMAT:
  Format: json
  Output is a JSON object with success, message, and data fields.

Functional Requirements:
  [FR-001] Create Order: Check user existence, product stock, calculate total price, deduct stock, create order record.
  [FR-002] Pay Order: Check order exists and status is pending, check user balance, deduct balance, update order status.
  [FR-003] Ship Order: Check order exists and status is paid, update status to shipped.
  [FR-004] Complete Order: Check order exists and status is shipped, update status to completed.
  [FR-005] Cancel Order: Check order exists and status is pending or paid, restore stock, refund if paid, update status.
  [FR-006] List Orders: List orders with optional filters by user and status.
  [FR-007] Get User Orders: Get all orders for a user, calculate total spent and status distribution.
  [FR-008] List Products: List products with stock, optionally filter low stock.""",
    "constraints": [
        "Storage: memory - Three data stores: users, products, orders",
        "Concurrency: single-user, auth_required: False",
        "Language: Python",
    ],
    "data_sources": [
        "users (memory, read_write): Stores user information keyed by user_id.",
        "products (memory, read_write): Stores product information keyed by product_id.",
        "orders (memory, read_write): Stores order records keyed by order_id.",
    ],
    "data_interfaces": [
        "users.get: def get_user(user_id: int) -> dict",
        "users.update: def update_user(user_id: int, updates: dict) -> None",
        "users.exists: def user_exists(user_id: int) -> bool",
        "products.get: def get_product(product_id: int) -> dict",
        "products.update: def update_product(product_id: int, updates: dict) -> None",
        "products.list: def list_products(low_stock_threshold: Optional[int] = None) -> list",
        "orders.get: def get_order(order_id: int) -> dict",
        "orders.create: def create_order(order: dict) -> int",
        "orders.update: def update_order(order_id: int, updates: dict) -> None",
        "orders.list: def list_orders(user_id: Optional[int] = None, status: Optional[str] = None) -> list",
        "orders.exists: def order_exists(order_id: int) -> bool",
    ],
}


# -----------------------------------------------------------------------
# Trial runner
# -----------------------------------------------------------------------
def run_trial(trial_idx, api_key, base_url, model):
    """Run a single two-phase decomposition trial."""
    label = f"trial_{trial_idx:02d}"
    log_dir = os.path.join(OUTPUT_DIR, model, label)
    logger = LLMLogger(log_dir, api_key, base_url, model)

    t0 = time.time()

    # ---- Phase 1: Structural decomposition only ----
    phase1_user = build_phase1_user_prompt(ORDER_REAL_NODE)
    phase1_messages = [
        {"role": "system", "content": PHASE1_SYSTEM_PROMPT},
        {"role": "user", "content": phase1_user},
    ]

    try:
        phase1_raw = logger.chat(phase1_messages, max_tokens=MAX_TOKENS_PHASE1)
    except Exception as e:
        return {"label": label, "error": f"Phase 1: {e}", "elapsed": time.time() - t0}

    phase1 = parse_json(phase1_raw)
    if "error" in phase1 and not phase1.get("children"):
        return {"label": label, "error": f"Phase 1 parse failed: {phase1.get('error')}", "raw": phase1_raw[:500], "elapsed": time.time() - t0}

    children_phase1 = phase1.get("children", [])
    n_children_phase1 = len(children_phase1)

    # ---- Phase 2: Interface derivation ----
    phase2_user = build_phase2_user_input(phase1, ORDER_REAL_NODE)
    # Give the LLM its own Phase 1 output as context
    phase2_messages = [
        {"role": "system", "content": PHASE2_SYSTEM_PROMPT},
        {"role": "assistant", "content": json.dumps(phase1, indent=2, ensure_ascii=False)},
        {"role": "user", "content": phase2_user},
    ]

    try:
        phase2_raw = logger.chat(phase2_messages, max_tokens=MAX_TOKENS_PHASE2)
    except Exception as e:
        return {
            "label": label, "phase1": phase1,
            "error": f"Phase 2: {e}", "elapsed": time.time() - t0,
        }

    phase2 = parse_json(phase2_raw)
    children_phase2 = phase2.get("children", children_phase1)
    n_children_phase2 = len(children_phase2)

    # Detect routing in Phase 1
    has_routing_p1, sibling_calls_p1 = detect_routing(children_phase1)
    # Detect routing in Phase 2
    has_routing_p2, sibling_calls_p2 = detect_routing(children_phase2)

    # Check if routing increased/decreased from Phase 1 to Phase 2
    routing_change = "same"
    if has_routing_p1 and not has_routing_p2:
        routing_change = "removed_in_phase2"
    elif not has_routing_p1 and has_routing_p2:
        routing_change = "added_in_phase2"

    # Save full result
    result = {
        "label": label,
        "trial": trial_idx,
        "n_children_phase1": n_children_phase1,
        "n_children_phase2": n_children_phase2,
        "child_names_phase1": [c.get("name", "") for c in children_phase1],
        "child_names_phase2": [c.get("name", "") for c in children_phase2],
        "has_routing_phase1": has_routing_p1,
        "has_routing_phase2": has_routing_p2,
        "sibling_calls_phase1": sibling_calls_p1,
        "sibling_calls_phase2": sibling_calls_p2,
        "routing_change": routing_change,
        "phase1_raw": phase1_raw,
        "phase2_raw": phase2_raw,
        "phase1_parsed": phase1,
        "phase2_parsed": phase2,
        "elapsed": round(time.time() - t0, 1),
        "llm_calls": logger.call_counter,
    }

    result_path = os.path.join(log_dir, "result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    return result


# -----------------------------------------------------------------------
# Report
# -----------------------------------------------------------------------
def generate_report(all_results, model):
    lines = [
        "# Attention Separation Experiment Report",
        "",
        f"- **Model:** {model}",
        f"- **Temperature:** {TEMPERATURE}",
        f"- **Trials:** {len(all_results)}",
        f"- **Date:** 2026-05-25",
        "",
        "---",
        "",
        "## Methodology",
        "",
        "Two-phase decomposition:",
        "- **Phase 1**: Structural decomposition only — children with name, purpose, behavior. NO interfaces.",
        "- **Phase 2**: Given Phase 1 output, derive inputs/outputs with types, sources, consumers.",
        "",
        "This tests whether separating interface concerns from structural decomposition reduces",
        "the routing pattern rate by allowing focused attention on tree structure rules in Phase 1.",
        "",
        "---",
        "",
        "## Results",
        "",
        "| # | Trial | Phase1 Children | Phase2 Children | Phase1 Routing | Phase2 Routing | Change |",
        "|---|-------|----------------|----------------|---------------|---------------|--------|",
    ]

    routing_p1 = 0
    routing_p2 = 0
    for i, r in enumerate(all_results):
        n1 = r.get("n_children_phase1", 0)
        n2 = r.get("n_children_phase2", 0)
        r1 = "ROUTING" if r.get("has_routing_phase1") else "ok"
        r2 = "ROUTING" if r.get("has_routing_phase2") else "ok"
        change = r.get("routing_change", "same")
        if r.get("has_routing_phase1"):
            routing_p1 += 1
        if r.get("has_routing_phase2"):
            routing_p2 += 1
        lines.append(f"| {i} | trial_{r['trial']:02d} | {n1} | {n2} | {r1} | {r2} | {change} |")

    lines.extend([
        "",
        "## Summary",
        "",
        f"Phase 1 routing rate: {routing_p1}/{len(all_results)} ({routing_p1/len(all_results)*100:.0f}%)",
        f"Phase 2 routing rate: {routing_p2}/{len(all_results)} ({routing_p2/len(all_results)*100:.0f}%)",
        "",
        "### Comparison with Baseline",
        "",
        "Baseline (single-pass, from routing ablation experiment): 5/5 = 100% routing for order_real. 10 nodes per decomposition.",
        "",
        "---",
        "",
        "## Phase 1 Decompositions Detail",
        "",
    ])

    for r in all_results:
        lines.append(f"### Trial {r['trial']:02d}")
        lines.append(f"- Phase 1 children: {', '.join(r.get('child_names_phase1', []))}")
        lines.append(f"- Routing: {r.get('has_routing_phase1', False)}")
        if r.get("sibling_calls_phase1"):
            lines.append(f"- Sibling calls: {json.dumps(r['sibling_calls_phase1'], ensure_ascii=False)}")
        lines.append(f"- Phase 2 children: {', '.join(r.get('child_names_phase2', []))}")
        lines.append(f"- Routing: {r.get('has_routing_phase2', False)}")
        if r.get("sibling_calls_phase2"):
            lines.append(f"- Sibling calls: {json.dumps(r['sibling_calls_phase2'], ensure_ascii=False)}")
        if r.get("error"):
            lines.append(f"- ERROR: {r['error']}")
        lines.append("")

    return "\n".join(lines)


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Attention separation experiment")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--base-url", type=str, default=None)
    parser.add_argument("--api-key", type=str, default=None)
    parser.add_argument("--trials", type=int, default=NUM_TRIALS)
    args = parser.parse_args()

    model = args.model or _env("CHRONOS_MODEL", "deepseek-chat")
    if model in MIMO_MODELS:
        base_url = args.base_url or os.getenv("MIMO_BASE_URL", MIMO_BASE_URL)
        api_key = args.api_key or os.getenv("MIMO_API_KEY") or _env("CHRONOS_API_KEY")
    else:
        base_url = args.base_url or _env("CHRONOS_BASE_URL", "https://api.deepseek.com")
        api_key = args.api_key or _env("CHRONOS_API_KEY")

    if not api_key:
        print("ERROR: Set CHRONOS_API_KEY")
        return 1

    print(f"Model: {model}")
    print(f"API: {base_url}")
    print(f"Trials: {args.trials}")
    print()

    all_results = []
    os.makedirs(os.path.join(OUTPUT_DIR, model), exist_ok=True)

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = {}
        for t in range(args.trials):
            f = pool.submit(run_trial, t, api_key, base_url, model)
            futures[f] = f"trial_{t:02d}"

        for f in as_completed(futures):
            label = futures[f]
            try:
                r = f.result()
                all_results.append(r)
                n1 = r.get("n_children_phase1", 0)
                n2 = r.get("n_children_phase2", 0)
                r1 = "ROUTING" if r.get("has_routing_phase1") else "ok"
                r2 = "ROUTING" if r.get("has_routing_phase2") else "ok"
                s1 = ', '.join(r.get('child_names_phase1', []))[:80]
                print(f"  [{label}] P1:{n1} {r1} / P2:{n2} {r2} = {s1}")
            except Exception as e:
                print(f"  [{label}] ERROR: {e}")
                all_results.append({"label": label, "error": str(e)})

    # Save results
    results_path = os.path.join(OUTPUT_DIR, model, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nResults saved: {results_path}")

    # Report
    report = generate_report(all_results, model)
    report_path = os.path.join(OUTPUT_DIR, model, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved: {report_path}")

    # Summary
    routing_p1 = sum(1 for r in all_results if r.get("has_routing_phase1", False))
    routing_p2 = sum(1 for r in all_results if r.get("has_routing_phase2", False))
    total = len(all_results)
    print(f"\n{'='*60}")
    print(f"  Phase 1 routing: {routing_p1}/{total} ({routing_p1/total*100:.0f}%)")
    print(f"  Phase 2 routing: {routing_p2}/{total} ({routing_p2/total*100:.0f}%)")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
