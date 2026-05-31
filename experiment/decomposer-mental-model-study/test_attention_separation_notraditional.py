"""
[VERIFIED 2026-05-28] Experiment 2: + No Traditional Patterns (Order domain)
Result: 0/5 routing = 0% — routing fully eliminated in Order domain.
Output: output/attention_separation_notraditional/deepseek-v4-flash/

Attention Separation — No Traditional Patterns condition.

Adds "Do Not Assume Traditional Methods" as a meta-rule in Phase 1.
Tests whether explicitly rejecting common software patterns (dispatcher, router,
command pattern, controller) reduces the routing rate.

Hypothesis: The routing pattern persists because it's a dominant training data
prior (command dispatcher pattern is ubiquitous in open-source code). By telling
the LLM to explicitly NOT use these patterns, we may bypass the prior.

Usage:
    python test_attention_separation_notraditional.py
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
MAX_TOKENS = int(os.getenv("CHRONOS_MAX_TOKENS", "8192"))
MAX_CONCURRENCY = int(os.getenv("CHRONOS_MAX_CONCURRENCY", "5"))

MIMO_MODELS = {"mimo-v2.5", "mimo-v2-flash", "mimo-v2.5-pro", "mimo-v2-pro", "mimo-v2-omni"}
MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"

OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "output", "attention_separation_notraditional"
)
NUM_TRIALS = 5


# -----------------------------------------------------------------------
# Phase 1 prompt — with "no traditional patterns" rule
# -----------------------------------------------------------------------
PHASE1_SYSTEM_PROMPT = """You are a software system decomposition agent. Your task is to decompose a function block into smaller child function blocks.

CRITICAL RULES:
1. EVERY CHILD MUST BE A FUNCTION, NOT A CLASS.
2. TREE STRUCTURE (not graph): The decomposition forms a tree. Children MUST NOT call each other (no cross-calls between siblings). The parent MUST explicitly and directly invoke all its children.
3. Do NOT add extra external inputs or outputs beyond what the parent has.
4. Children should be at the same abstraction level and minimally overlapping.

DO NOT ASSUME TRADITIONAL DEVELOPMENT PATTERNS:
- DO NOT create a "dispatcher", "router", "controller", "command_handler", or similar node that delegates work to other children.
- DO NOT use the Command Pattern, Strategy Pattern, or any design pattern where one child calls other children.
- DO NOT create a "coordinator" node whose primary purpose is to figure out which other child to call.
- Each child MUST be a self-contained function that does actual work. A child that only "routes" or "dispatches" to other children is NOT doing real work and is NOT allowed.
- The parent IS the router. If different inputs need different processing, the parent decides through conditional logic which child to call.

The purpose of decomposition is to divide work, not to recreate enterprise architecture patterns. Each child should directly perform a concrete task.

SEMANTIC STOP CONDITIONS — STOP DECOMPOSITION when:
1. PURE FUNCTION: Only mathematical transformations, no state/I/O/side effects.
2. ATOMIC OPERATION: Exactly one operation on exactly one data source.
3. MAXIMUM DEPTH REACHED.

DO NOT STOP if the node contains business logic, branching, or coordinates multiple operations.

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
# Phase 2 prompt (same as before)
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
# Build prompts
# -----------------------------------------------------------------------
def build_phase1_user_prompt(node_info):
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
    lines.append("Return ONLY the JSON response.")
    return "\n".join(lines)


def build_phase2_user_input(decomposition, node_info):
    children = decomposition.get("children", [])
    summary_lines = [
        "Derive interfaces for each child.",
        "",
        f"Parent: {node_info['name']}",
        f"Purpose: {node_info['purpose']}",
        "",
        "Parent inputs:",
        f"  - {node_info.get('input_desc', 'input: Any')}",
        "Parent outputs:",
        f"  - {node_info.get('output_desc', 'output: Any')}",
        "",
        "Available Data Stores:",
    ]
    if node_info.get("data_sources"):
        for ds in node_info["data_sources"]:
            summary_lines.append(f"  - {ds}")
    if node_info.get("data_interfaces"):
        summary_lines.append("")
        summary_lines.append("Available Data Interfaces:")
        for di in node_info["data_interfaces"]:
            summary_lines.append(f"  - {di}")
    summary_lines.append("")
    summary_lines.append("Children:")
    for c in children:
        summary_lines.append(
            f"  {c.get('name', '')}: {c.get('purpose', '')}"
        )
        summary_lines.append(f"    behavior: {c.get('behavior', '')[:200]}")
    return "\n".join(summary_lines)


# -----------------------------------------------------------------------
# LLM Logger
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
        max_tokens = max_tokens or MAX_TOKENS
        req = {"call_id": call_id, "timestamp": time.time(), "messages": messages, "max_tokens": max_tokens, "model": self.model}
        with open(os.path.join(self.log_dir, f"{call_id:04d}_request.json"), "w", encoding="utf-8") as f:
            json.dump(req, f, indent=2, ensure_ascii=False)
        client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=120)
        start = time.time()
        try:
            kwargs = dict(model=self.model, messages=messages, temperature=TEMPERATURE, max_tokens=max_tokens, extra_body={"thinking": {"type": "disabled"}})
            resp = client.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content
        except Exception as e:
            elapsed = time.time() - start
            with open(os.path.join(self.log_dir, f"{call_id:04d}_response.json"), "w", encoding="utf-8") as f:
                json.dump({"call_id": call_id, "elapsed": round(elapsed, 2), "error": str(e)}, f, indent=2, ensure_ascii=False)
            raise
        elapsed = time.time() - start
        with open(os.path.join(self.log_dir, f"{call_id:04d}_response.json"), "w", encoding="utf-8") as f:
            json.dump({"call_id": call_id, "elapsed": round(elapsed, 2), "response": text}, f, indent=2, ensure_ascii=False)
        return text


def parse_json(text):
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


ROUTING_PATTERNS = [
    re.compile(r'calls?\s+(?:the\s+)?(?:appropriate\s+)?(?:child\s+)?(?:handler\s+)?(\w+)', re.IGNORECASE),
    re.compile(r'invoke[s]?\s+(\w+)', re.IGNORECASE),
    re.compile(r'dispatch(?:es)?\s+(?:to\s+)?(\w+)', re.IGNORECASE),
    re.compile(r'route[s]?\s+(?:to\s+)?(\w+)', re.IGNORECASE),
]
ROUTER_NAME_PATTERNS = re.compile(r'(?:^router$|^dispatcher$|route|dispatch|parse.*input|parse.*command|process.*command)', re.IGNORECASE)
ROUTER_PURPOSE_PATTERNS = re.compile(r'(?:route[s]?\s+(?:the\s+)?(?:command|request|input)|dispatch(?:es)?\s+(?:to\s+)?(?:the\s+)?(?:appropriate|correct|corresponding))', re.IGNORECASE)


def detect_routing(children):
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
        is_router = bool(ROUTER_NAME_PATTERNS.search(name)) or bool(ROUTER_PURPOSE_PATTERNS.search(combined))
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


def run_trial(trial_idx, api_key, base_url, model):
    label = f"trial_{trial_idx:02d}"
    log_dir = os.path.join(OUTPUT_DIR, model, label)
    logger = LLMLogger(log_dir, api_key, base_url, model)
    t0 = time.time()

    # Phase 1
    phase1_user = build_phase1_user_prompt(ORDER_REAL_NODE)
    try:
        phase1_raw = logger.chat([
            {"role": "system", "content": PHASE1_SYSTEM_PROMPT},
            {"role": "user", "content": phase1_user},
        ])
    except Exception as e:
        return {"label": label, "error": f"Phase1: {e}", "elapsed": time.time() - t0}
    phase1 = parse_json(phase1_raw)
    if "error" in phase1 and not phase1.get("children"):
        return {"label": label, "error": f"Phase1 parse: {phase1.get('error')}", "elapsed": time.time() - t0}

    children_p1 = phase1.get("children", [])
    has_routing_p1, calls_p1 = detect_routing(children_p1)

    # Phase 2
    phase2_user = build_phase2_user_input(phase1, ORDER_REAL_NODE)
    try:
        phase2_raw = logger.chat([
            {"role": "system", "content": PHASE2_SYSTEM_PROMPT},
            {"role": "assistant", "content": json.dumps(phase1, indent=2, ensure_ascii=False)},
            {"role": "user", "content": phase2_user},
        ])
    except Exception as e:
        return {"label": label, "phase1": phase1, "has_routing_phase1": has_routing_p1, "error": f"Phase2: {e}", "elapsed": time.time() - t0}

    phase2 = parse_json(phase2_raw)
    children_p2 = phase2.get("children", children_p1)
    has_routing_p2, calls_p2 = detect_routing(children_p2)

    result = {
        "label": label, "trial": trial_idx,
        "n_children_phase1": len(children_p1), "n_children_phase2": len(children_p2),
        "child_names_phase1": [c.get("name", "") for c in children_p1],
        "child_names_phase2": [c.get("name", "") for c in children_p2],
        "has_routing_phase1": has_routing_p1, "has_routing_phase2": has_routing_p2,
        "sibling_calls_phase1": calls_p1, "sibling_calls_phase2": calls_p2,
        "elapsed": round(time.time() - t0, 1), "llm_calls": logger.call_counter,
    }
    with open(os.path.join(log_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--trials", type=int, default=NUM_TRIALS)
    parser.add_argument("--base_url", type=str, default=None)
    parser.add_argument("--api_key", type=str, default=None)
    args = parser.parse_args()

    model = args.model or _env("CHRONOS_MODEL", "deepseek-chat")
    if model in MIMO_MODELS:
        base_url = args.base_url or os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
        api_key = args.api_key or os.getenv("MIMO_API_KEY") or _env("CHRONOS_API_KEY")
    else:
        base_url = args.base_url or _env("CHRONOS_BASE_URL", "https://api.deepseek.com")
        api_key = args.api_key or _env("CHRONOS_API_KEY")

    if not api_key:
        print("ERROR: Set CHRONOS_API_KEY")
        return 1

    print(f"Model: {model}")
    print(f"Condition: Phase 1 with 'No Traditional Patterns' rule")
    print(f"Trials: {args.trials}")
    print()

    all_results = []
    os.makedirs(os.path.join(OUTPUT_DIR, model), exist_ok=True)

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = {pool.submit(run_trial, t, api_key, base_url, model): f"trial_{t:02d}" for t in range(args.trials)}
        for f in as_completed(futures):
            label = futures[f]
            try:
                r = f.result()
                all_results.append(r)
                names = ', '.join(r.get("child_names_phase1", []))[:80]
                r1 = "ROUTING" if r.get("has_routing_phase1") else "ok"
                r2 = "ROUTING" if r.get("has_routing_phase2") else "ok"
                print(f"  [{label}] P1:{r.get('n_children_phase1')} {r1} / P2:{r.get('n_children_phase2')} {r2} = {names}")
            except Exception as e:
                print(f"  [{label}] ERROR: {e}")

    results_path = os.path.join(OUTPUT_DIR, model, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved: {results_path}")

    r1 = sum(1 for r in all_results if r.get("has_routing_phase1", False))
    r2 = sum(1 for r in all_results if r.get("has_routing_phase2", False))
    total = len(all_results)
    print(f"\n{'='*60}")
    print(f"  Phase 1 routing: {r1}/{total} ({r1/total*100:.0f}%)")
    print(f"  Phase 2 routing: {r2}/{total} ({r2/total*100:.0f}%)")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
