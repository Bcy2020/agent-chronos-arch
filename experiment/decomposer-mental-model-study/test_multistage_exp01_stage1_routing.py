"""
Experiment 1: Expanded Stage 1 Routing Robustness

Tests whether the expanded Stage 1 schema (adding boundary, semantic IO,
preconditions, postconditions, guarantees, composition_role, etc.)
still suppresses routing, or reintroduces routing and child-count errors.

Output: output/multistage_exp01_stage1_routing/{model}/
"""
import json, os, sys, time, re, argparse, hashlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from openai import OpenAI

def _env(key, default=""):
    return os.getenv(key) or os.getenv(f"DEEPSEEK_{key.removeprefix('CHRONOS_')}") or default

TEMPERATURE = float(os.getenv("CHRONOS_TEMPERATURE", "0.3"))
MAX_TOKENS = int(os.getenv("CHRONOS_MAX_TOKENS", "8192"))
MAX_CONCURRENCY = 5

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "multistage_exp01_stage1_routing")
NUM_TRIALS = 5

# ========================================================================
# Expanded Stage 1 System Prompt (from guides/MULTI_STAGE_EXPERIMENT_GUIDE.md)
# ========================================================================

EXPANDED_STAGE1_SYSTEM_PROMPT = """You are a software system decomposition agent. Your task is to decompose a function block into smaller child function blocks.

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

SEMANTIC STOP CONDITIONS:
STOP DECOMPOSITION when:
1. PURE FUNCTION: Only mathematical transformations, no state/I/O/side effects.
2. ATOMIC OPERATION: Exactly one operation on exactly one data source.
3. MAXIMUM DEPTH REACHED.
DO NOT STOP if the node contains business logic, branching, or coordinates multiple operations.

OUTPUT FORMAT — Return valid JSON:
{
  "children": [
    {
      "name": "ChildName",
      "purpose": "semantic responsibility",
      "behavior": "internal transformation without sibling calls",
      "boundary": {
        "in_scope": ["what this child handles"],
        "out_of_scope": ["what this child explicitly does NOT handle"]
      },
      "semantic_inputs": [
        {"name": "conceptual_input", "description": "what information is needed", "source": "parent input | previous child output | constant | internal leaf access"}
      ],
      "semantic_outputs": [
        {"name": "conceptual_output", "description": "what guarantee/result is produced", "consumer": "parent | ChildName"}
      ],
      "preconditions": ["conditions that must hold before execution"],
      "postconditions": ["conditions guaranteed after execution"],
      "guarantees": ["invariants this child maintains"],
      "composition_role": "transform | validate | decide | execute | aggregate | query | mutate",
      "stop_decompose": false,
      "stop_reason": ""
    }
  ],
  "decomposition_rationale": "how children jointly cover parent responsibility",
  "orchestration_model": "sequence | conditional | aggregate | pipeline | mixed",
  "dataflow_sketch": [
    {"from": "parent | ChildName", "to": "ChildName | parent", "data": "semantic data", "note": "why"}
  ]
}

STAGE 1 CONSTRAINTS — You MUST follow these:
1. Child must not call, invoke, dispatch to, route to, or reference siblings.
2. Parent is the only router/orchestrator at the current depth.
3. composition_role=decide means "returns a decision to parent", not "calls another child".
4. Do not use handler/router/dispatcher/controller patterns as decomposition units.
5. Do NOT emit inputs, outputs, signature, global_vars, data_operations, requested_capabilities, traceability, or acceptance_criteria. Those will be derived in a separate step."""

# ========================================================================
# Domain definitions (5 domains: 3 command-dispatch, 2 sequential)
# ========================================================================

ORDER_NODE = {
    "name": "OrderSystem",
    "purpose": "Process e-commerce orders via a single entry point.",
    "input_desc": "input: Any - JSON with command (place/cancel/track) and order_data fields",
    "output_desc": "output: Any - JSON with success, order_id, status, message fields",
    "description": """INPUT FORMAT:
  command: string - one of place, cancel, track
  order_data: object with items, payment_method, shipping_address, order_id fields

OUTPUT FORMAT:
  JSON with success, order_id, status, message fields.

Functional Requirements:
  [FR-001] Place Order: Validate items and stock, charge payment, reserve inventory, create order.
  [FR-002] Cancel Order: Verify order not shipped, refund payment, restore inventory.
  [FR-003] Track Order: Return current order status and estimated delivery.""",
    "constraints": [
        "All operations must be atomic",
        "Inventory must be reserved until order confirmed",
        "Cannot cancel a shipped order",
    ],
    "data_sources": [
        "orders (memory, read_write): Order records keyed by order_id.",
        "inventory (memory, read_write): Product stock data.",
        "payments (memory, read_write): Payment records.",
    ],
}

CHAT_NODE = {
    "name": "ChatApp",
    "purpose": "Handle real-time messaging operations",
    "input_desc": "input: Any - JSON with command (send/history/create_channel/join) and message_data fields",
    "output_desc": "output: Any - JSON with success, data, and message fields",
    "description": """INPUT FORMAT:
  command: string - one of send, history, create_channel, join
  message_data: object with content, channel_id, user_id, channel_name fields

OUTPUT FORMAT:
  JSON with success, data, message fields.

Functional Requirements:
  [FR-001] Send Message: Validate user is member of target channel, store message, update last_seen.
  [FR-002] Get History: Retrieve last 100 messages from a channel, sorted by timestamp desc.
  [FR-003] Create Channel: Create new channel, set caller as creator and first member.
  [FR-004] Join Channel: Add user to channel's member list.""",
    "constraints": [
        "Users can only send messages to joined channels",
        "History limited to 100 messages per channel",
        "Channel names must be unique",
    ],
    "data_sources": [
        "messages (memory, read_write): Message store keyed by message_id.",
        "channels (memory, read_write): Channel data keyed by channel_id.",
    ],
}

PATIENT_NODE = {
    "name": "PatientPortal",
    "purpose": "Manage patient healthcare operations",
    "input_desc": "input: Any - JSON with command (register/book/records/update) and patient_data fields",
    "output_desc": "output: Any - JSON with success, data, and message fields",
    "description": """INPUT FORMAT:
  command: string - one of register, book, records, update
  patient_data: object with name, dob, contact, insurance, patient_id, doctor_id, appointment_time fields

OUTPUT FORMAT:
  JSON with success, data, message fields.

Functional Requirements:
  [FR-001] Register: Validate required fields, create patient record, generate unique patient_id.
  [FR-002] Book Appointment: Check patient exists, check doctor availability, create appointment.
  [FR-003] Get Records: Retrieve all medical records for a patient, sorted by date desc.
  [FR-004] Update Profile: Update patient profile fields. Validate insurance against external system.""",
    "constraints": [
        "Patient must be registered before booking",
        "Cannot book appointments in the past",
        "Medical records are append-only",
    ],
    "data_sources": [
        "patients (memory, read_write): Patient records keyed by patient_id.",
        "appointments (memory, read_write): Appointment records keyed by appointment_id.",
    ],
}

BUILD_NODE = {
    "name": "BuildSystem",
    "purpose": "Manage CI/CD builds: trigger, status, list, cancel.",
    "input_desc": "input: Any - JSON with action (trigger/status/list/cancel), repo, branch, config fields",
    "output_desc": "output: Any - JSON with success, build_id, status, logs fields",
    "description": """INPUT FORMAT:
  build_request: JSON object with action, repo, branch, config, build_id fields.

OUTPUT FORMAT:
  JSON with success, build_id, status, logs fields.

Functional Requirements:
  [FR-001] Trigger: Create build record, run compile, run test, package artifacts.
  [FR-002] Status: Return current build status and logs.
  [FR-003] List: Return all builds filtered by repo/branch/status.
  [FR-004] Cancel: Stop a running build, update status to cancelled.""",
    "constraints": [
        "Only one build per repo+branch at a time",
        "Build logs stored incrementally",
        "Cancelling completed build is a no-op",
    ],
    "data_sources": [
        "builds (memory, read_write): Build records keyed by build_id.",
        "artifacts (memory, read_write): Build artifacts keyed by artifact_id.",
    ],
}

PIPELINE_NODE = {
    "name": "DataPipeline",
    "purpose": "ETL data processing: ingest, transform, validate, export.",
    "input_desc": "input: Any - JSON with action (ingest/transform/validate/export), source, transform_config fields",
    "output_desc": "output: Any - JSON with success, records_processed, errors, data fields",
    "description": """INPUT FORMAT:
  pipeline_request: JSON object with action, source, transform_config, export_format fields.

OUTPUT FORMAT:
  JSON with success, records_processed, errors, data fields.

Functional Requirements:
  [FR-001] Ingest: Read from source, parse records, store in raw_data, log ingestion.
  [FR-002] Transform: Apply transformation rules to raw_data, store in processed_data.
  [FR-003] Validate: Check processed_data against quality rules, mark invalid records.
  [FR-004] Export: Format processed_data as output, log export.""",
    "constraints": [
        "Each step must log with counts",
        "Transform must skip malformed records rather than failing",
        "Export includes only records that passed validation",
    ],
    "data_sources": [
        "raw_data (memory, read_write): Raw ingested data.",
        "processed_data (memory, read_write): Transformed and validated data.",
    ],
}


def build_stage1_user_prompt(node_info):
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


# ========================================================================
# LLM, JSON parsing, routing detection
# ========================================================================

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


# Routing patterns (extended to scan expanded fields)
ROUTING_PATTERNS = [
    re.compile(r'calls?\s+(?:the\s+)?(?:appropriate\s+)?(?:child\s+)?(?:handler\s+)?(\w+)', re.IGNORECASE),
    re.compile(r'invoke[s]?\s+(\w+)', re.IGNORECASE),
    re.compile(r'dispatch(?:es)?\s+(?:to\s+)?(\w+)', re.IGNORECASE),
    re.compile(r'route[s]?\s+(?:to\s+)?(\w+)', re.IGNORECASE),
]
ROUTER_NAME_PATTERNS = re.compile(r'(?:^router$|^dispatcher$|route|dispatch|parse.*input|parse.*command|process.*command)', re.IGNORECASE)
ROUTER_PURPOSE_PATTERNS = re.compile(r'(?:route[s]?\s+(?:the\s+)?(?:command|request|input)|dispatch(?:es)?\s+(?:to\s+)?(?:the\s+)?(?:appropriate|correct|corresponding))', re.IGNORECASE)


def _collect_text_fields(child):
    """Collect all text fields from an expanded Stage 1 child for routing scan."""
    texts = []
    for key in ("name", "purpose", "behavior"):
        texts.append(child.get(key, ""))
    boundary = child.get("boundary", {})
    for key in ("in_scope", "out_of_scope"):
        val = boundary.get(key, [])
        if isinstance(val, list):
            texts.extend(val)
        elif isinstance(val, str):
            texts.append(val)
    for key in ("preconditions", "postconditions", "guarantees"):
        val = child.get(key, [])
        if isinstance(val, list):
            texts.extend(val)
        elif isinstance(val, str):
            texts.append(val)
    for si in child.get("semantic_inputs", []):
        texts.append(si.get("source", ""))
        texts.append(si.get("description", ""))
    for so in child.get("semantic_outputs", []):
        texts.append(so.get("consumer", ""))
        texts.append(so.get("description", ""))
    texts.append(child.get("composition_role", ""))
    return " ".join(texts)


def detect_routing_extended(children):
    """Extended routing detection scanning all expanded Stage 1 fields."""
    child_names = {c.get("name", "") for c in children}
    sibling_calls = []

    # Method 1: Text pattern matching across all fields
    for c in children:
        cname = c.get("name", "")
        text = _collect_text_fields(c)
        for p in ROUTING_PATTERNS:
            for m in p.finditer(text):
                target = m.group(1)
                if target in child_names and target != cname:
                    sibling_calls.append({"from": cname, "to": target, "method": "text_pattern"})

    # Method 2: Structural router detection
    router_nodes = []
    for c in children:
        name = c.get("name", "")
        purpose = c.get("purpose", ""); behavior = c.get("behavior", "")
        combined = purpose + " " + behavior
        is_router = bool(ROUTER_NAME_PATTERNS.search(name)) or bool(ROUTER_PURPOSE_PATTERNS.search(combined))
        if is_router:
            router_nodes.append(name)
    if router_nodes and len(children) > len(router_nodes):
        for router in router_nodes:
            for c in children:
                if c.get("name", "") != router:
                    sibling_calls.append({"from": router, "to": c.get("name", ""), "method": "structural_router"})

    # Method 3: Scan dataflow_sketch and decomposition_rationale
    # (top-level fields, not per-child — handled separately)

    seen = set(); unique = []
    for sc in sibling_calls:
        k = (sc["from"], sc["to"], sc["method"])
        if k not in seen:
            seen.add(k); unique.append(sc)
    return len(unique) > 0, unique


def detect_routing_in_toplevel(data):
    """Scan top-level dataflow_sketch and decomposition_rationale for sibling references."""
    children = data.get("children", [])
    child_names = {c.get("name", "") for c in children}
    violations = []

    # Check dataflow_sketch
    for edge in data.get("dataflow_sketch", []):
        src = edge.get("from", ""); dst = edge.get("to", "")
        if src in child_names and dst in child_names and src != dst:
            violations.append({"from": src, "to": dst, "method": "dataflow_sketch_sibling_ref"})

    # Check decomposition_rationale for sibling references
    rationale = data.get("decomposition_rationale", "")
    for p in ROUTING_PATTERNS:
        for m in p.finditer(rationale):
            target = m.group(1)
            if target in child_names:
                violations.append({"from": "rationale", "to": target, "method": "rationale_sibling_ref"})

    return len(violations) > 0, violations


# ========================================================================
# Stage 1 required fields
# ========================================================================

STAGE1_REQUIRED_CHILD_FIELDS = [
    "name", "purpose", "behavior", "boundary", "semantic_inputs",
    "semantic_outputs", "preconditions", "postconditions", "guarantees",
    "composition_role", "stop_decompose",
]

STAGE1_REQUIRED_TOP_FIELDS = [
    "children", "decomposition_rationale", "orchestration_model", "dataflow_sketch",
]

VALID_COMPOSITION_ROLES = {"transform", "validate", "decide", "execute", "aggregate", "query", "mutate"}


def check_field_completeness(data):
    """Check Stage 1 field completeness. Returns (total_fields, present_fields, missing_list)."""
    missing = []
    total = 0
    present = 0

    # Top-level fields
    for f in STAGE1_REQUIRED_TOP_FIELDS:
        total += 1
        if f in data and data[f] is not None:
            present += 1
        else:
            missing.append(f"top:{f}")

    # Per-child fields
    children = data.get("children", [])
    for i, child in enumerate(children):
        cname = child.get("name", f"child_{i}")
        for f in STAGE1_REQUIRED_CHILD_FIELDS:
            total += 1
            if f in child and child[f] is not None:
                present += 1
                # Check composition_role validity
                if f == "composition_role" and child[f] not in VALID_COMPOSITION_ROLES:
                    missing.append(f"{cname}:composition_role={child[f]} (invalid)")
            else:
                missing.append(f"{cname}:{f}")

        # Check boundary structure
        boundary = child.get("boundary", {})
        if isinstance(boundary, dict):
            for sub in ("in_scope", "out_of_scope"):
                total += 1
                if sub in boundary:
                    present += 1
                else:
                    missing.append(f"{cname}:boundary.{sub}")

        # Check semantic_inputs structure
        for si in child.get("semantic_inputs", []):
            for field_name in ("name", "description", "source"):
                total += 1
                if field_name in si:
                    present += 1
                else:
                    missing.append(f"{cname}:semantic_inputs[].{field_name}")

        # Check semantic_outputs structure
        for so in child.get("semantic_outputs", []):
            for field_name in ("name", "description", "consumer"):
                total += 1
                if field_name in so:
                    present += 1
                else:
                    missing.append(f"{cname}:semantic_outputs[].{field_name}")

    return total, present, missing


def check_child_count(children, valid_range=(2, 10)):
    n = len(children)
    return n < valid_range[0] or n > valid_range[1]


# ========================================================================
# Trial runner
# ========================================================================

def run_trial(trial_idx, node_info, domain_name, api_key, base_url, model):
    label = f"{domain_name}_{trial_idx:02d}"
    log_dir = os.path.join(OUTPUT_DIR, model, domain_name, f"trial_{trial_idx:02d}")
    logger = LLMLogger(log_dir, api_key, base_url, model)
    t0 = time.time()

    try:
        stage1_raw = logger.chat([
            {"role": "system", "content": EXPANDED_STAGE1_SYSTEM_PROMPT},
            {"role": "user", "content": build_stage1_user_prompt(node_info)},
        ])
    except Exception as e:
        return {"label": label, "domain": domain_name, "trial": trial_idx,
                "error": f"API call failed: {e}", "elapsed": round(time.time()-t0, 1)}

    stage1 = parse_json(stage1_raw)
    elapsed = round(time.time()-t0, 1)

    # Save raw result
    with open(os.path.join(log_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(stage1, f, indent=2, ensure_ascii=False, default=str)

    if "error" in stage1 and not stage1.get("children"):
        return {"label": label, "domain": domain_name, "trial": trial_idx,
                "error": f"Parse failed: {stage1.get('error')}", "elapsed": elapsed,
                "llm_calls": logger.call_counter, "raw_preview": stage1.get("raw", "")[:200]}

    children = stage1.get("children", [])

    # Routing detection
    has_routing, sibling_calls = detect_routing_extended(children)
    has_toplevel_routing, toplevel_violations = detect_routing_in_toplevel(stage1)

    # Field completeness
    total_fields, present_fields, missing_fields = check_field_completeness(stage1)
    completion_rate = present_fields / total_fields if total_fields > 0 else 0

    # Child count check
    child_count_violation = check_child_count(children)

    result = {
        "label": label,
        "domain": domain_name,
        "trial": trial_idx,
        "n_children": len(children),
        "child_names": [c.get("name", "") for c in children],
        "composition_roles": [c.get("composition_role", "") for c in children],
        "orchestration_model": stage1.get("orchestration_model", ""),
        "has_routing": has_routing,
        "sibling_calls": sibling_calls,
        "has_toplevel_routing": has_toplevel_routing,
        "toplevel_violations": toplevel_violations,
        "child_count_violation": child_count_violation,
        "field_completion_rate": round(completion_rate, 4),
        "total_fields": total_fields,
        "present_fields": present_fields,
        "missing_fields": missing_fields[:20],  # cap for readability
        "parse_error": False,
        "elapsed": elapsed,
        "llm_calls": logger.call_counter,
    }

    # Update result.json with full analysis
    with open(os.path.join(log_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    return result


# ========================================================================
# Report generation
# ========================================================================

def generate_report(all_results, model, domains):
    lines = [
        f"# Exp01: Expanded Stage 1 Routing Robustness Report",
        f"",
        f"Model: `{model}`",
        f"Domains: {', '.join(d[0] for d in domains)}",
        f"Trials per domain: {NUM_TRIALS}",
        f"Total trials: {len(all_results)}",
        f"",
    ]

    # Summary by domain
    lines.append("## Results by Domain\n")
    lines.append("| Domain | Trials | Routing | Top-Level Routing | Child Count Violations | Parse Errors | Avg Field Completion |")
    lines.append("|--------|--------|---------|-------------------|----------------------|--------------|---------------------|")

    by_domain = defaultdict(list)
    for r in all_results:
        by_domain[r["domain"]].append(r)

    for dname in [d[0] for d in domains]:
        results = by_domain.get(dname, [])
        total = len(results)
        routing = sum(1 for r in results if r.get("has_routing", False))
        top_routing = sum(1 for r in results if r.get("has_toplevel_routing", False))
        cc_viol = sum(1 for r in results if r.get("child_count_violation", False))
        parse_err = sum(1 for r in results if r.get("error") or r.get("parse_error", False))
        avg_fc = sum(r.get("field_completion_rate", 0) for r in results) / total if total > 0 else 0
        lines.append(f"| {dname} | {total} | {routing}/{total} | {top_routing}/{total} | {cc_viol}/{total} | {parse_err}/{total} | {avg_fc*100:.1f}% |")

    # Overall totals
    total = len(all_results)
    total_routing = sum(1 for r in all_results if r.get("has_routing", False))
    total_top = sum(1 for r in all_results if r.get("has_toplevel_routing", False))
    total_cc = sum(1 for r in all_results if r.get("child_count_violation", False))
    total_parse = sum(1 for r in all_results if r.get("error") or r.get("parse_error", False))
    total_avg_fc = sum(r.get("field_completion_rate", 0) for r in all_results) / total if total > 0 else 0
    lines.append(f"| **TOTAL** | **{total}** | **{total_routing}/{total} ({total_routing/total*100:.0f}%)** | **{total_top}/{total}** | **{total_cc}/{total}** | **{total_parse}/{total}** | **{total_avg_fc*100:.1f}%** |")
    lines.append("")

    # Routing cases detail
    routing_cases = [r for r in all_results if r.get("has_routing") or r.get("has_toplevel_routing")]
    if routing_cases:
        lines.append("## Routing Cases Detail\n")
        for r in routing_cases:
            lines.append(f"### {r['label']}")
            lines.append(f"- Children: {r.get('child_names', [])}")
            lines.append(f"- Composition roles: {r.get('composition_roles', [])}")
            lines.append(f"- Orchestration model: {r.get('orchestration_model', '')}")
            if r.get("sibling_calls"):
                lines.append(f"- Sibling calls (extended):")
                for sc in r["sibling_calls"]:
                    lines.append(f"  - {sc['from']} -> {sc['to']} ({sc['method']})")
            if r.get("toplevel_violations"):
                lines.append(f"- Top-level violations:")
                for tv in r["toplevel_violations"]:
                    lines.append(f"  - {tv['from']} -> {tv['to']} ({tv['method']})")
            lines.append("")
    else:
        lines.append("## Routing Cases Detail\n")
        lines.append("No routing violations detected.\n")

    # Missing fields analysis
    all_missing = []
    for r in all_results:
        all_missing.extend(r.get("missing_fields", []))
    if all_missing:
        missing_counter = defaultdict(int)
        for m in all_missing:
            # Normalize: strip child name prefix for grouping
            parts = m.split(":", 1)
            field = parts[1] if len(parts) > 1 else m
            missing_counter[field] += 1
        lines.append("## Most Common Missing Fields\n")
        lines.append("| Field | Count |")
        lines.append("|-------|-------|")
        for field, count in sorted(missing_counter.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"| {field} | {count} |")
        lines.append("")

    # Verdict
    lines.append("## Verdict\n")
    routing_rate = total_routing / total if total > 0 else 0
    if routing_rate <= 0.17:
        verdict = "PASS"
    elif routing_rate <= 0.30:
        verdict = "INCONCLUSIVE"
    else:
        verdict = "FAIL"
    lines.append(f"- Routing rate: {routing_rate*100:.1f}% (target: 0-17%)")
    lines.append(f"- Child count violations: {total_cc}/{total}")
    lines.append(f"- Field completion: {total_avg_fc*100:.1f}%")
    lines.append(f"- **Verdict: {verdict}**")
    lines.append("")
    return "\n".join(lines)


# ========================================================================
# Main
# ========================================================================

def main():
    parser = argparse.ArgumentParser(description="Exp01: Expanded Stage 1 Routing Robustness")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--trials", type=int, default=NUM_TRIALS)
    parser.add_argument("--domains", type=str, default="Order,Chat,Patient,BuildSystem,DataPipeline",
                        help="Comma-separated domain names")
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

    ALL_DOMAINS = {
        "Order": ORDER_NODE,
        "Chat": CHAT_NODE,
        "Patient": PATIENT_NODE,
        "BuildSystem": BUILD_NODE,
        "DataPipeline": PIPELINE_NODE,
    }

    requested = [d.strip() for d in args.domains.split(",")]
    domains = [(d, ALL_DOMAINS[d]) for d in requested if d in ALL_DOMAINS]
    if not domains:
        print(f"ERROR: No valid domains found. Available: {list(ALL_DOMAINS.keys())}"); return 1

    print(f"Model: {model}")
    print(f"Domains: {[d[0] for d in domains]}")
    print(f"Trials per domain: {args.trials}")
    print(f"Output: {OUTPUT_DIR}/{model}/")
    print()

    all_results = []
    for dname, dnode in domains:
        print(f"Domain: {dname}")
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
            futures = {
                pool.submit(run_trial, t, dnode, dname, api_key, base_url, model): f"{dname}_{t:02d}"
                for t in range(args.trials)
            }
            for f in as_completed(futures):
                r = f.result()
                all_results.append(r)
                names = ', '.join(r.get("child_names", []))[:80]
                status = "ROUTING" if r.get("has_routing") else "ok"
                err = r.get("error", "")
                fc = r.get("field_completion_rate", 0) * 100
                if err:
                    print(f"  [{r['label']}] ERROR: {err[:80]}")
                else:
                    print(f"  [{r['label']}] {r.get('n_children',0)} children, {status}, fields={fc:.0f}% = {names}")

    # Save results
    out_dir = os.path.join(OUTPUT_DIR, model)
    os.makedirs(out_dir, exist_ok=True)
    results_path = os.path.join(out_dir, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved: {results_path}")

    # Generate report
    report = generate_report(all_results, model, domains)
    report_path = os.path.join(out_dir, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Saved: {report_path}")

    # Print summary
    total = len(all_results)
    total_routing = sum(1 for r in all_results if r.get("has_routing", False))
    total_parse_err = sum(1 for r in all_results if r.get("error"))
    total_avg_fc = sum(r.get("field_completion_rate", 0) for r in all_results) / total if total > 0 else 0
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Total trials: {total}")
    print(f"  Routing: {total_routing}/{total} ({total_routing/total*100:.0f}%)")
    print(f"  Parse errors: {total_parse_err}/{total}")
    print(f"  Avg field completion: {total_avg_fc*100:.1f}%")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
