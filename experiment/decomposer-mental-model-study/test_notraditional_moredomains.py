"""
[VERIFIED 2026-05-28] Experiment 3: Cross-Domain Validation (Chat + Patient)
Result: 1/6 routing = 17% — only Chat_00 triggered (name-based false positive).
Output: output/notraditional_moredomains/deepseek-v4-flash/

Test "No Traditional Patterns" rule on 2 more command-dispatch domains.
To verify the 0% routing result generalizes beyond Order Management.
"""
import json, os, sys, time, re, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from openai import OpenAI

def _env(key, default=""):
    return os.getenv(key) or os.getenv(f"DEEPSEEK_{key.removeprefix('CHRONOS_')}") or default

TEMPERATURE = float(os.getenv("CHRONOS_TEMPERATURE", "0.3"))
MAX_TOKENS = int(os.getenv("CHRONOS_MAX_TOKENS", "8192"))
MAX_CONCURRENCY = 5

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "notraditional_moredomains")
NUM_TRIALS = 3

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
# Domain definitions — two more command-dispatch PRDs
# -----------------------------------------------------------------------

CHAT_NODE = {
    "name": "ChatApp",
    "purpose": "Handle real-time messaging operations",
    "input_desc": "input: Any - JSON with command (send/history/create_channel/join) and message_data fields",
    "output_desc": "output: Any - JSON with success, data, and message fields",
    "description": """INPUT FORMAT:
  Format: json
  command: string - one of send, history, create_channel, join
  message_data: object with content, channel_id, user_id, channel_name fields

OUTPUT FORMAT:
  Format: json
  Output is a JSON object with success, data, and message fields.

Functional Requirements:
  [FR-001] Send Message: Validate user is a member of the target channel, store the message, update user's last_seen.
  [FR-002] Get History: Retrieve the last 100 messages from a channel, sorted by timestamp descending.
  [FR-003] Create Channel: Create a new channel, set the caller as creator and first member.
  [FR-004] Join Channel: Add the user to a channel's member list.""",
    "constraints": [
        "Storage: memory - Two data stores: messages, channels",
        "Concurrency: single-user, auth_required: False",
        "Language: Python",
    ],
    "data_sources": [
        "messages (memory, read_write): Stores messages keyed by message_id.",
        "channels (memory, read_write): Stores channel info keyed by channel_id.",
    ],
    "data_interfaces": [
        "messages.get: def get_message(message_id: int) -> dict",
        "messages.create: def create_message(message: dict) -> int",
        "messages.list_by_channel: def list_by_channel(channel_id: int, limit: int) -> list",
        "channels.get: def get_channel(channel_id: int) -> dict",
        "channels.create: def create_channel(channel: dict) -> int",
        "channels.add_member: def add_member(channel_id: int, user_id: int) -> None",
        "channels.is_member: def is_member(channel_id: int, user_id: int) -> bool",
    ],
}

PATIENT_NODE = {
    "name": "PatientPortal",
    "purpose": "Manage patient healthcare operations",
    "input_desc": "input: Any - JSON with command (register/book/records/update) and patient_data fields",
    "output_desc": "output: Any - JSON with success, data, and message fields",
    "description": """INPUT FORMAT:
  Format: json
  command: string - one of register, book, records, update
  patient_data: object with name, dob, contact, insurance, patient_id, doctor_id, appointment_time fields

OUTPUT FORMAT:
  Format: json
  Output is a JSON object with success, data, and message fields.

Functional Requirements:
  [FR-001] Register: Validate required fields, create patient record, generate unique patient_id.
  [FR-002] Book Appointment: Check patient exists, check doctor availability, create appointment, send confirmation.
  [FR-003] Get Records: Retrieve all medical records for a patient, sorted by date descending.
  [FR-004] Update Profile: Update patient profile fields. Validate insurance against external system.""",
    "constraints": [
        "Storage: memory - Two data stores: patients, appointments",
        "Concurrency: single-user, auth_required: False",
        "Language: Python",
    ],
    "data_sources": [
        "patients (memory, read_write): Stores patient records keyed by patient_id.",
        "appointments (memory, read_write): Stores appointment records keyed by appointment_id.",
    ],
    "data_interfaces": [
        "patients.get: def get_patient(patient_id: int) -> dict",
        "patients.create: def create_patient(patient: dict) -> int",
        "patients.update: def update_patient(patient_id: int, updates: dict) -> None",
        "appointments.get: def get_appointment(appointment_id: int) -> dict",
        "appointments.create: def create_appointment(appointment: dict) -> int",
        "appointments.list_by_patient: def list_by_patient(patient_id: int) -> list",
    ],
}


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
    lines.append(f"  - {node_info.get('input_desc', 'input: Any')}")
    lines.append("Outputs:")
    lines.append(f"  - {node_info.get('output_desc', 'output: Any')}")
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
        summary_lines.append(f"  {c.get('name', '')}: {c.get('purpose', '')}")
        summary_lines.append(f"    behavior: {c.get('behavior', '')[:200]}")
    return "\n".join(summary_lines)


class LLMLogger:
    def __init__(self, log_dir, api_key, base_url, model):
        self.log_dir = log_dir; self.api_key = api_key; self.base_url = base_url; self.model = model
        self.call_counter = 0
        os.makedirs(log_dir, exist_ok=True)
    def chat(self, messages, max_tokens=None):
        self.call_counter += 1; call_id = self.call_counter
        max_tokens = max_tokens or MAX_TOKENS
        req = {"call_id": call_id, "timestamp": time.time(), "messages": messages, "max_tokens": max_tokens, "model": self.model}
        with open(os.path.join(self.log_dir, f"{call_id:04d}_request.json"), "w", encoding="utf-8") as f:
            json.dump(req, f, indent=2, ensure_ascii=False)
        client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=120)
        start = time.time()
        try:
            resp = client.chat.completions.create(**dict(model=self.model, messages=messages, temperature=TEMPERATURE, max_tokens=max_tokens, extra_body={"thinking": {"type": "disabled"}}))
            text = resp.choices[0].message.content
        except Exception as e:
            with open(os.path.join(self.log_dir, f"{call_id:04d}_response.json"), "w", encoding="utf-8") as f:
                json.dump({"call_id": call_id, "elapsed": round(time.time()-start, 2), "error": str(e)}, f, indent=2)
            raise
        elapsed = time.time() - start
        with open(os.path.join(self.log_dir, f"{call_id:04d}_response.json"), "w", encoding="utf-8") as f:
            json.dump({"call_id": call_id, "elapsed": round(elapsed, 2), "response": text}, f, indent=2)
        return text


def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    if "}" in text:
        text = text[:text.rfind("}")+1]
    text = re.sub(r'(?<=[\s:,\[{])[fFrRuUbB]+(")', r'\1', text)
    try: return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try: return json.loads(m.group())
            except: pass
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
        for p in ROUTING_PATTERNS:
            for m in p.finditer(text):
                target = m.group(1)
                if target in child_names and target != cname:
                    sibling_calls.append({"from": cname, "to": target, "method": "text_pattern"})
    router_nodes = []
    for c in children:
        name = c.get("name", "")
        purpose = c.get("purpose", ""); behavior = c.get("behavior", "")
        combined = purpose + " " + behavior
        is_router = bool(ROUTER_NAME_PATTERNS.search(name)) or bool(ROUTER_PURPOSE_PATTERNS.search(combined))
        if is_router: router_nodes.append(name)
    if router_nodes and len(children) > len(router_nodes):
        for router in router_nodes:
            for c in children:
                if c.get("name", "") != router:
                    sibling_calls.append({"from": router, "to": c.get("name", ""), "method": "structural_router"})
    seen = set(); unique = []
    for sc in sibling_calls:
        k = (sc["from"], sc["to"], sc["method"])
        if k not in seen: seen.add(k); unique.append(sc)
    return len(unique) > 0, unique


def run_trial(trial_idx, node_info, domain_name, api_key, base_url, model):
    label = f"{domain_name}_{trial_idx:02d}"
    log_dir = os.path.join(OUTPUT_DIR, model, label)
    logger = LLMLogger(log_dir, api_key, base_url, model)
    t0 = time.time()

    phase1_raw = logger.chat([
        {"role": "system", "content": PHASE1_SYSTEM_PROMPT},
        {"role": "user", "content": build_phase1_user_prompt(node_info)},
    ])
    phase1 = parse_json(phase1_raw)
    if "error" in phase1 and not phase1.get("children"):
        return {"label": label, "error": f"Phase1 parse: {phase1.get('error')}", "elapsed": time.time()-t0}

    children_p1 = phase1.get("children", [])
    has_routing_p1, calls_p1 = detect_routing(children_p1)

    phase2_raw = logger.chat([
        {"role": "system", "content": PHASE2_SYSTEM_PROMPT},
        {"role": "assistant", "content": json.dumps(phase1, indent=2, ensure_ascii=False)},
        {"role": "user", "content": build_phase2_user_input(phase1, node_info)},
    ])
    phase2 = parse_json(phase2_raw)
    children_p2 = phase2.get("children", children_p1)
    has_routing_p2, calls_p2 = detect_routing(children_p2)

    result = {"label": label, "trial": trial_idx, "domain": domain_name,
        "n_children_phase1": len(children_p1), "n_children_phase2": len(children_p2),
        "child_names_phase1": [c.get("name","") for c in children_p1],
        "has_routing_phase1": has_routing_p1, "has_routing_phase2": has_routing_p2,
        "sibling_calls_phase1": calls_p1, "sibling_calls_phase2": calls_p2,
        "elapsed": round(time.time()-t0, 1), "llm_calls": logger.call_counter}
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
    if model in {"mimo-v2.5", "mimo-v2-flash", "mimo-v2.5-pro", "mimo-v2-pro", "mimo-v2-omni"}:
        base_url = args.base_url or os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
        api_key = args.api_key or os.getenv("MIMO_API_KEY") or _env("CHRONOS_API_KEY")
    else:
        base_url = args.base_url or _env("CHRONOS_BASE_URL", "https://api.deepseek.com")
        api_key = args.api_key or _env("CHRONOS_API_KEY")

    if not api_key:
        print("ERROR: Set CHRONOS_API_KEY"); return 1

    domains = [
        ("Chat", CHAT_NODE),
        ("Patient", PATIENT_NODE),
    ]

    all_results = []
    for dname, dnode in domains:
        print(f"\nDomain: {dname}")
        print(f"Trials: {args.trials}")
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
            futures = {pool.submit(run_trial, t, dnode, dname, api_key, base_url, model): f"{dname}_{t:02d}" for t in range(args.trials)}
            for f in as_completed(futures):
                r = f.result()
                all_results.append(r)
                names = ', '.join(r.get("child_names_phase1", []))[:80]
                r1 = "ROUTING" if r.get("has_routing_phase1") else "ok"
                r2 = "ROUTING" if r.get("has_routing_phase2") else "ok"
                print(f"  [{r['label']}] P1:{r.get('n_children_phase1')} {r1} / P2:{r.get('n_children_phase2')} {r2} = {names}")

    os.makedirs(os.path.join(OUTPUT_DIR, model), exist_ok=True)
    results_path = os.path.join(OUTPUT_DIR, model, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved: {results_path}")

    # Summary by domain
    from collections import defaultdict
    by_domain = defaultdict(list)
    for r in all_results:
        by_domain[r["domain"]].append(r)

    print(f"\n{'='*60}")
    print(f"  RESULTS BY DOMAIN")
    print(f"{'='*60}")
    for dname, results in sorted(by_domain.items()):
        r1 = sum(1 for r in results if r.get("has_routing_phase1", False))
        r2 = sum(1 for r in results if r.get("has_routing_phase2", False))
        total = len(results)
        print(f"\n  {dname}:")
        print(f"    Phase 1 routing: {r1}/{total}")
        print(f"    Phase 2 routing: {r2}/{total}")
        for r in results:
            names = ', '.join(r.get("child_names_phase1", []))[:80]
            r1m = "ROUTING" if r.get("has_routing_phase1") else "ok"
            print(f"      {r['label']}: P1={r1m} [{names}]")

    total_r1 = sum(1 for r in all_results if r.get("has_routing_phase1", False))
    total_r2 = sum(1 for r in all_results if r.get("has_routing_phase2", False))
    total_all = len(all_results)
    print(f"\n  TOTAL:")
    print(f"    Phase 1 routing: {total_r1}/{total_all} ({total_r1/total_all*100:.0f}%)")
    print(f"    Phase 2 routing: {total_r2}/{total_all} ({total_r2/total_all*100:.0f}%)")
    print(f"{'='*60}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
