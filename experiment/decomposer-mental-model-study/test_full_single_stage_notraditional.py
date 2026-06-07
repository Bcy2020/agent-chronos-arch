"""
Experiment: Full Single-Stage Decomposer Schema + No-Traditional Rule

Tests whether the no-traditional rule still suppresses hard routing when the
model must emit the full original single-stage schema in a single call.

Output: output/full_single_stage_notraditional/{model}/
"""
import json, os, sys, time, re, argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from openai import OpenAI

def _env(key, default=""):
    return os.getenv(key) or os.getenv(f"DEEPSEEK_{key.removeprefix('CHRONOS_')}") or default

TEMPERATURE = float(os.getenv("CHRONOS_TEMPERATURE", "0.3"))
MAX_TOKENS = int(os.getenv("CHRONOS_MAX_TOKENS", "16384"))
MAX_CONCURRENCY = 5

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "full_single_stage_notraditional")
NUM_TRIALS = 5

# ========================================================================
# Full Single-Stage System Prompt (from mvp-0.4.4/decomposer.py + no-traditional)
# ========================================================================

FULL_SINGLE_STAGE_SYSTEM_PROMPT = """You are a software system decomposition agent. Your task is to decompose a function block into smaller child function blocks.

CRITICAL RULES - ENFORCED:
1. EVERY CHILD MUST BE A FUNCTION, NOT A CLASS. Never generate class definitions for child blocks.
2. Each child must have explicit: name, purpose, inputs, outputs, and boundary
3. Preserve the parent's external interface - children's composition must match parent's inputs/outputs
4. TREE STRUCTURE (not graph): The decomposition forms a tree, not a graph. Children MUST NOT call each other (no cross-calls between siblings). The parent MUST explicitly and directly invoke all its children. A coordinator child node is ALLOWED, as long as it only coordinates work within its own subtree and never calls sibling nodes.
5. Do NOT add extra external inputs or outputs beyond what the parent has
6. Children should be at the same abstraction level and minimally overlapping

DO NOT ASSUME TRADITIONAL DEVELOPMENT PATTERNS:
- DO NOT create a "dispatcher", "router", "controller", "command_handler", or similar node that delegates work to other children.
- DO NOT use the Command Pattern, Strategy Pattern, or any design pattern where one child calls other children.
- DO NOT create a "coordinator" node whose primary purpose is to figure out which other child to call.
- Each child MUST be a self-contained function that does actual work. A child that only "routes" or "dispatches" to other children is NOT doing real work and is NOT allowed.
- The parent IS the router. If different inputs need different processing, the parent decides through conditional logic which child to call.

SIGNATURE LOCKING - CHILD INTERFACES ARE BINDING CONTRACTS:
- Each child's declared inputs/outputs become a LOCKED signature that code generators MUST follow exactly
- Use precise Python types: str, int, float, bool, dict, list, Optional[dict], List[str], Dict[int, str], Tuple[str, int], Any, None
- Do NOT invent unnecessary parameters - a child should only receive what it needs to do its job
- Do NOT use generic "Any" when a specific type is known - precision enables signature validation
- Example CORRECT: inputs=[{"name": "task_id", "type": "int", "description": "ID of the task to validate"}]
- Example WRONG:   inputs=[{"name": "task_id", "type": "Any", "description": "the task id"}]
- The verifier will reject code that does not match the declared signature exactly

SEMANTIC STOP CONDITIONS - Use these instead of line-count estimation:
STOP DECOMPOSITION when the node is ONE of the following types:

1. PURE FUNCTION: The node performs only mathematical transformations with no:
   - Global/state variable dependencies (except parameters)
   - I/O operations (file, network, database)
   - Side effects or state modifications
   Example: calculate_totals(prices, tax_rate) -> total

2. ATOMIC OPERATION: The node performs exactly one operation on exactly one data source:
   - Read from a single data source (database, cache, file)
   - Write to a single data source
   - Read-modify-write on a single data source
   Example: reserve_inventory(product_id, quantity) -> bool

3. MAXIMUM DEPTH REACHED: Tree has reached the configured maximum depth

DO NOT STOP if the node:
- Contains business logic, branching, or loops
- Coordinates multiple child operations
- Transforms data between multiple sources
- Contains conditional validation logic

DATAFLOW CLOSURE RULES:
1. Every child input must have an explicit source.
2. A child input source must be one of:
   - a parent input,
   - an output of an earlier sibling child,
   - a local constant/config value explicitly described,
   - data obtained inside that same leaf through requested_capabilities.
3. If a child needs data that no previous child outputs and no parent input provides, add a child before it to produce that data, or move the data access inside that child as a leaf capability.
4. Do not create child signatures with dangling parameters such as products_data unless a previous child outputs products_data.
5. Parent must not directly access global state or data interfaces — all data operations must go through child function calls.

OUTPUT FORMAT - You MUST return valid JSON with this exact structure:
{
  "children": [
    {
      "name": "ChildName",
      "purpose": "Clear description of what this child function does",
      "inputs": [{"name": "param", "type": "str", "description": "desc", "source": "where data comes from"}],
      "outputs": [{"name": "result", "type": "int", "description": "desc", "consumer": "who uses this output"}],
      "boundary": {"in_scope": ["..."], "out_of_scope": ["..."]},
      "preconditions": ["..."],
      "postconditions": ["..."],
      "behavior": "Detailed description of expected behavior - how this function transforms inputs to outputs",
      "signature": "def ChildName(param1: type1, param2: type2) -> return_type",
      "stop_decompose": false,
      "stop_reason": "",
      "node_type": "pure_function|atomic_operation",
      "data_operations": [
        {"source_name": "data_source_name", "operation_type": "read|write|read_write", "description": "what operation is performed"}
      ],
      "constraints": [{"constraint_id": "C-001", "description": "constraint description"}],
      "acceptance_criteria": [{"ac_id": "AC-001", "description": "criterion description", "verification_method": "automated_test"}],
      "global_vars": [
        {"variable": "data_store_name", "op": "read|write|read_write", "description": "what operation is needed"}
      ],
      "traceability": {"parent_requirement_ids": ["FR-001"], "derived_from": "root"},
      "requested_capabilities": ["resource.operation", "resource.operation"]
    }
  ],
  "data_sources": [
    {"name": "source_name", "category": "database|file|cache|external|memory", "access": "read|write|read_write", "data_type": "dict|list|object", "description": "description"}
  ],
  "decomposition_rationale": "CRITICAL: Explain HOW these children work together to implement the parent. Describe the interaction flow, data transformation, and how they collectively cover ALL parent responsibilities. This is required for the code generator to understand how to compose these functions.",
  "interface_preservation": {
    "parent_inputs_covered_by": {"input_name": "child_name"},
    "parent_outputs_produced_by": {"output_name": "child_name"}
  },
  "dataflow_edges": [
    {
      "from_node": "parent | ChildName",
      "from_output": "parent_input_or_child_output_name",
      "to_node": "ChildName | parent",
      "to_input": "child_input_or_parent_output_name",
      "note": "why this dataflow exists"
    }
  ]
}

CRITICAL GLOBAL VARIABLES DISTRIBUTION RULE:
The parent's "global_vars" declares which data variables the subtree operates on and what operations are needed (read/write/read_write).
You MUST distribute these global_vars among children based on their responsibilities:
- A child that performs read/write on a variable declares the corresponding "global_vars"
- Each child's global_vars MUST be a subset of the parent's global_vars
- The union of all children's global_vars MUST cover all of the parent's declared operations on each variable"""

# ========================================================================
# Domain definitions (same 5 domains as Exp01)
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


def build_user_prompt(node_info):
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
# LLM, JSON parsing
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
            resp = client.chat.completions.create(
                **dict(model=self.model, messages=messages, temperature=TEMPERATURE,
                       max_tokens=max_tokens, response_format={"type": "json_object"},
                       extra_body={"thinking": {"type": "disabled"}})
            )
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


# ========================================================================
# Deterministic Judging (from reanalyze_multistage_exp01.py)
# ========================================================================

ROUTER_NAME_PATTERNS = [
    r"^Route", r"Router$", r"^Dispatch", r"Dispatcher$",
    r"^Coordinator$", r"^CommandHandler$", r"^Controller$",
]
NOT_ROUTER_PATTERNS = [
    r"^Parse", r"^Validate", r"^ProcessCommand",
]
CONTROL_CALL_VERBS = [
    r"\bcalls?\b", r"\binvoke[sd]?\b", r"\bdispatch(?:es|ed|ing)?\b",
    r"\broute[sd]?\b", r"\bdelegat(?:es|ed|ing)?\b", r"\bselects?\b.*\bchild\b",
    r"\bwhich child to call\b", r"\broute to handler\b", r"\bdispatch to\b",
    r"\bselect which\b", r"\brouting\b.*\bcommand\b",
]
PARENT_ORCHESTRATION_KEYWORDS = [
    r"\bparent orchestrates\b", r"\bparent selects\b", r"\bparent passes\b",
    r"\bparent decides\b", r"\bparent routes\b", r"\bparent invokes\b",
    r"\bparent calls\b", r"\bthe parent\b.*\bbased on\b",
]


def is_router_name(name):
    for pat in ROUTER_NAME_PATTERNS:
        if re.search(pat, name, re.IGNORECASE):
            for nrpat in NOT_ROUTER_PATTERNS:
                if re.search(nrpat, name, re.IGNORECASE):
                    return False
            return True
    return False


def has_control_call_text(text):
    if not text:
        return False
    for pat in CONTROL_CALL_VERBS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def has_parent_orchestration_text(text):
    if not text:
        return False
    for pat in PARENT_ORCHESTRATION_KEYWORDS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def normalize_node_name(name):
    name = name.strip()
    if name.lower() in ("parent", "parent input", "parent output"):
        return "parent"
    return name


def collect_dataflow_edges(data):
    """Collect dataflow edges from either dataflow_edges or dataflow_sketch."""
    edges = data.get("dataflow_edges", [])
    if not edges:
        edges = data.get("dataflow_sketch", [])
    return edges


def judge_trial(parsed):
    """Deterministic hard-routing / parent-mediated judging."""
    evidence = []
    children = parsed.get("children", [])
    dataflow_edges_raw = collect_dataflow_edges(parsed)
    rationale = parsed.get("decomposition_rationale", "")
    child_names = {c.get("name", "") for c in children}
    child_map = {c.get("name", ""): c for c in children}

    # Classify dataflow edges
    sibling_edges = []
    parent_mediated_edges = []
    for edge in dataflow_edges_raw:
        src = normalize_node_name(edge.get("from_node", edge.get("from", "")))
        dst = normalize_node_name(edge.get("to_node", edge.get("to", "")))
        if src == "parent" or dst == "parent":
            parent_mediated_edges.append(edge)
        elif src in child_names and dst in child_names:
            sibling_edges.append((src, dst, edge))

    # Check each child for router characteristics
    router_nodes = []
    for c in children:
        name = c.get("name", "")
        purpose = c.get("purpose", "")
        behavior = c.get("behavior", "")
        combined = f"{purpose} {behavior}"

        if is_router_name(name) and has_control_call_text(combined):
            router_nodes.append(name)
            evidence.append({
                "category": "router_node", "field": "child.purpose+behavior",
                "child": name, "target": "",
                "snippet": f"Name matches router pattern; purpose/behavior: {combined[:200]}",
                "reason": f"Router-like name '{name}' with control-call semantics in purpose/behavior"
            })

    # Check sibling edges for control-call semantics
    hard_routing_sibling_calls = []
    ambiguous_sibling_calls = []
    for src, dst, edge in sibling_edges:
        src_child = child_map.get(src, {})
        src_behavior = f"{src_child.get('purpose', '')} {src_child.get('behavior', '')}"
        note = edge.get("note", "")

        if has_control_call_text(src_behavior) or has_control_call_text(note):
            hard_routing_sibling_calls.append((src, dst, edge))
            evidence.append({
                "category": "hard_routing", "field": "dataflow_edge",
                "child": src, "target": dst,
                "snippet": f"{src} -> {dst}: {note}",
                "reason": "Sibling edge with control-call semantics"
            })
        else:
            ambiguous_sibling_calls.append((src, dst, edge))
            evidence.append({
                "category": "ambiguous_direct_dataflow", "field": "dataflow_edge",
                "child": src, "target": dst,
                "snippet": f"{src} -> {dst}: {note}",
                "reason": "Sibling-to-sibling edge without explicit control-call wording"
            })

    # Check parent-mediated dataflow
    parent_mediated = False
    for edge in parent_mediated_edges:
        src = normalize_node_name(edge.get("from_node", edge.get("from", "")))
        if src in child_names:
            child = child_map.get(src, {})
            consumers = []
            for so in child.get("outputs", []):
                consumers.append(so.get("consumer", ""))
            if "parent" in consumers:
                parent_mediated = True
                evidence.append({
                    "category": "parent_mediated_dataflow", "field": "outputs[].consumer",
                    "child": src, "target": "parent",
                    "snippet": f"consumer=parent for {src}'s output",
                    "reason": "Child returns data to parent; parent orchestrates"
                })

    if has_parent_orchestration_text(rationale):
        parent_mediated = True
        evidence.append({
            "category": "parent_mediated_dataflow", "field": "decomposition_rationale",
            "child": "", "target": "parent",
            "snippet": rationale[:300],
            "reason": "Rationale indicates parent orchestration"
        })

    # Traditional naming residue
    traditional_naming = False
    for c in children:
        name = c.get("name", "")
        purpose = c.get("purpose", "")
        behavior = c.get("behavior", "")
        if re.search(r"Handler$", name) and not has_control_call_text(f"{purpose} {behavior}"):
            traditional_naming = True
            evidence.append({
                "category": "traditional_naming_residue", "field": "child.name",
                "child": name, "target": "",
                "snippet": f"Name ends with 'Handler' but does real work",
                "reason": "Handler-style name with real business work, not a router"
            })

    # Verdicts
    hard_routing = len(hard_routing_sibling_calls) > 0 or len(router_nodes) > 0

    return {
        "hard_routing": hard_routing,
        "sibling_invocation": len(hard_routing_sibling_calls) > 0,
        "router_node": len(router_nodes) > 0,
        "parent_mediated_dataflow": parent_mediated,
        "ambiguous_direct_dataflow": len(ambiguous_sibling_calls) > 0,
        "traditional_naming_residue": traditional_naming,
        "router_nodes": router_nodes,
        "hard_routing_sibling_calls": [
            {"from": s, "to": d, "note": e.get("note", "")} for s, d, e in hard_routing_sibling_calls
        ],
        "ambiguous_sibling_calls": [
            {"from": s, "to": d, "note": e.get("note", "")} for s, d, e in ambiguous_sibling_calls
        ],
    }


# ========================================================================
# Field completeness for full single-stage schema
# ========================================================================

FULL_REQUIRED_TOP_FIELDS = [
    "children", "data_sources", "decomposition_rationale",
    "interface_preservation", "dataflow_edges",
]

FULL_REQUIRED_CHILD_FIELDS = [
    "name", "purpose", "inputs", "outputs", "boundary",
    "preconditions", "postconditions", "behavior", "signature",
    "stop_decompose", "stop_reason", "node_type",
    "data_operations", "constraints", "acceptance_criteria",
    "global_vars", "traceability", "requested_capabilities",
]

VALID_NODE_TYPES = {"pure_function", "atomic_operation"}


def check_field_completeness(data):
    missing = []
    total = 0
    present = 0

    for f in FULL_REQUIRED_TOP_FIELDS:
        total += 1
        if f in data and data[f] is not None:
            present += 1
        else:
            missing.append(f"top:{f}")

    children = data.get("children", [])
    for i, child in enumerate(children):
        cname = child.get("name", f"child_{i}")
        for f in FULL_REQUIRED_CHILD_FIELDS:
            total += 1
            if f in child and child[f] is not None:
                present += 1
                if f == "node_type" and child[f] not in VALID_NODE_TYPES:
                    missing.append(f"{cname}:node_type={child[f]} (invalid)")
            else:
                missing.append(f"{cname}:{f}")

        # boundary sub-fields
        boundary = child.get("boundary", {})
        if isinstance(boundary, dict):
            for sub in ("in_scope", "out_of_scope"):
                total += 1
                if sub in boundary:
                    present += 1
                else:
                    missing.append(f"{cname}:boundary.{sub}")

        # inputs sub-fields
        for inp in child.get("inputs", []):
            for field_name in ("name", "type", "description", "source"):
                total += 1
                if field_name in inp:
                    present += 1
                else:
                    missing.append(f"{cname}:inputs[].{field_name}")

        # outputs sub-fields
        for out in child.get("outputs", []):
            for field_name in ("name", "type", "description", "consumer"):
                total += 1
                if field_name in out:
                    present += 1
                else:
                    missing.append(f"{cname}:outputs[].{field_name}")

        # data_operations sub-fields
        for dop in child.get("data_operations", []):
            for field_name in ("source_name", "operation_type", "description"):
                total += 1
                if field_name in dop:
                    present += 1
                else:
                    missing.append(f"{cname}:data_operations[].{field_name}")

        # global_vars sub-fields
        for gv in child.get("global_vars", []):
            for field_name in ("variable", "op", "description"):
                total += 1
                if field_name in gv:
                    present += 1
                else:
                    missing.append(f"{cname}:global_vars[].{field_name}")

        # constraints sub-fields
        for con in child.get("constraints", []):
            for field_name in ("constraint_id", "description"):
                total += 1
                if field_name in con:
                    present += 1
                else:
                    missing.append(f"{cname}:constraints[].{field_name}")

        # acceptance_criteria sub-fields
        for ac in child.get("acceptance_criteria", []):
            for field_name in ("ac_id", "description", "verification_method"):
                total += 1
                if field_name in ac:
                    present += 1
                else:
                    missing.append(f"{cname}:acceptance_criteria[].{field_name}")

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
        raw = logger.chat([
            {"role": "system", "content": FULL_SINGLE_STAGE_SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(node_info)},
        ])
    except Exception as e:
        return {"label": label, "domain": domain_name, "trial": trial_idx,
                "error": f"API call failed: {e}", "elapsed": round(time.time()-t0, 1)}

    parsed = parse_json(raw)
    elapsed = round(time.time()-t0, 1)

    if "error" in parsed and not parsed.get("children"):
        result = {"label": label, "domain": domain_name, "trial": trial_idx,
                  "error": f"Parse failed: {parsed.get('error')}", "elapsed": elapsed,
                  "llm_calls": logger.call_counter, "raw_preview": parsed.get("raw", "")[:200]}
        with open(os.path.join(log_dir, "result.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        return result

    children = parsed.get("children", [])

    # Deterministic judging
    judge = judge_trial(parsed)

    # Field completeness
    total_fields, present_fields, missing_fields = check_field_completeness(parsed)
    completion_rate = present_fields / total_fields if total_fields > 0 else 0

    # Top-level dataflow check
    toplevel_sibling_refs = []
    dataflow_edges_raw = collect_dataflow_edges(parsed)
    child_names = {c.get("name", "") for c in children}
    for edge in dataflow_edges_raw:
        src = normalize_node_name(edge.get("from_node", edge.get("from", "")))
        dst = normalize_node_name(edge.get("to_node", edge.get("to", "")))
        if src in child_names and dst in child_names and src != dst:
            toplevel_sibling_refs.append({"from": src, "to": dst, "note": edge.get("note", "")})

    child_count_violation = check_child_count(children)

    result = {
        "label": label,
        "domain": domain_name,
        "trial": trial_idx,
        "n_children": len(children),
        "child_names": [c.get("name", "") for c in children],
        "node_types": [c.get("node_type", "") for c in children],
        "orchestration_model": parsed.get("orchestration_model", ""),
        "toplevel_sibling_refs": toplevel_sibling_refs,
        "child_count_violation": child_count_violation,
        "field_completion_rate": round(completion_rate, 4),
        "total_fields": total_fields,
        "present_fields": present_fields,
        "missing_fields": missing_fields[:30],
        "parse_error": False,
        "elapsed": elapsed,
        "llm_calls": logger.call_counter,
        "judge": judge,
    }

    with open(os.path.join(log_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    return result


# ========================================================================
# Report generation
# ========================================================================

def generate_report(all_results, model, domains):
    lines = [
        f"# Full Single-Stage + No-Traditional: Missing Cell Experiment Report",
        f"",
        f"Model: `{model}`",
        f"Domains: {', '.join(d[0] for d in domains)}",
        f"Trials per domain: {NUM_TRIALS}",
        f"Total trials: {len(all_results)}",
        f"",
        f"## Purpose",
        f"",
        f"Test the missing experimental cell: full single-stage decomposer schema + no-traditional rule.",
        f"",
        f"> Does the no-traditional rule still suppress hard routing when the decomposer",
        f"> is asked to produce the full original single-stage schema?",
        f"",
        f"## Prompt Condition",
        f"",
        f"System prompt: full original single-stage schema from `mvp-0.4.4/decomposer.py`",
        f"plus the DO NOT ASSUME TRADITIONAL DEVELOPMENT PATTERNS block.",
        f"",
        f"No stage separation — all fields (inputs, outputs, signature, data_operations,",
        f"global_vars, traceability, dataflow_edges, etc.) in a single LLM call.",
        f"",
    ]

    # Summary by domain
    lines.append("## Results by Domain\n")
    lines.append("| Domain | Trials | Hard Routing | Ambiguous Dataflow | Parent-Mediated | Child Count Violations | Parse Errors | Avg Field Completion |")
    lines.append("|--------|--------|-------------|-------------------|-----------------|----------------------|--------------|---------------------|")

    by_domain = defaultdict(list)
    for r in all_results:
        by_domain[r["domain"]].append(r)

    for dname in [d[0] for d in domains]:
        results = by_domain.get(dname, [])
        total = len(results)
        hr = sum(1 for r in results if r.get("judge", {}).get("hard_routing", False))
        amb = sum(1 for r in results if r.get("judge", {}).get("ambiguous_direct_dataflow", False))
        pm = sum(1 for r in results if r.get("judge", {}).get("parent_mediated_dataflow", False))
        cc_viol = sum(1 for r in results if r.get("child_count_violation", False))
        parse_err = sum(1 for r in results if r.get("error") or r.get("parse_error", False))
        avg_fc = sum(r.get("field_completion_rate", 0) for r in results) / total if total > 0 else 0
        lines.append(f"| {dname} | {total} | {hr}/{total} | {amb}/{total} | {pm}/{total} | {cc_viol}/{total} | {parse_err}/{total} | {avg_fc*100:.1f}% |")

    # Overall totals
    total = len(all_results)
    total_hr = sum(1 for r in all_results if r.get("judge", {}).get("hard_routing", False))
    total_amb = sum(1 for r in all_results if r.get("judge", {}).get("ambiguous_direct_dataflow", False))
    total_pm = sum(1 for r in all_results if r.get("judge", {}).get("parent_mediated_dataflow", False))
    total_cc = sum(1 for r in all_results if r.get("child_count_violation", False))
    total_parse = sum(1 for r in all_results if r.get("error") or r.get("parse_error", False))
    total_avg_fc = sum(r.get("field_completion_rate", 0) for r in all_results) / total if total > 0 else 0
    lines.append(f"| **TOTAL** | **{total}** | **{total_hr}/{total} ({total_hr/total*100:.0f}%)** | **{total_amb}/{total}** | **{total_pm}/{total}** | **{total_cc}/{total}** | **{total_parse}/{total}** | **{total_avg_fc*100:.1f}%** |")
    lines.append("")

    # Verdict
    lines.append("## Verdict\n")
    if total_hr <= 0.17:
        verdict = "PASS"
        verdict_note = "Hard routing rate is within the verified 0-17% range."
    elif total_hr <= 0.30:
        verdict = "INCONCLUSIVE"
        verdict_note = "Hard routing rate is above target but not clearly systematic."
    else:
        verdict = "FAIL"
        verdict_note = "Hard routing rate is clearly above the target range."
    lines.append(f"- **Hard routing rate**: {total_hr}/{total} ({total_hr/total*100:.0f}%)")
    lines.append(f"- **Child count violations**: {total_cc}/{total}")
    lines.append(f"- **Field completion**: {total_avg_fc*100:.1f}%")
    lines.append(f"- **Verdict: {verdict}** — {verdict_note}")
    lines.append("")

    # Comparison
    lines.append("## Comparison with Staged No-Traditional\n")
    lines.append("| Condition | Hard Routing | Notes |")
    lines.append("|-----------|-------------|-------|")
    base_hr = 0.17  # Exp01 rejudged: 8%, 0-17% range
    staged_hr = 0.17  # staged no-traditional
    lines.append(f"| Staged Phase 1 + no-traditional (Exp01 rejudged) | 8% (2/25) | Lean output, no inputs/outputs/signature |")
    lines.append(f"| Staged baseline (no no-traditional) | 100% (5/5) | Two-phase, Order domain only |")
    lines.append(f"| Cross-domain staged + no-traditional | 17% (1/6) | 3 additional domains |")
    lines.append(f"| **Full single-stage + no-traditional (this experiment)** | **{total_hr/total*100:.0f}% ({total_hr}/{total})** | Full original schema in one call |")
    lines.append("")

    # Hard routing cases detail
    hr_cases = [r for r in all_results if r.get("judge", {}).get("hard_routing", False)]
    if hr_cases:
        lines.append("## Hard Routing Cases Detail\n")
        for r in hr_cases:
            lines.append(f"### {r['label']}")
            lines.append(f"- Children: {', '.join(r.get('child_names', []))}")
            lines.append(f"- Node types: {r.get('node_types', [])}")
            j = r.get("judge", {})
            if j.get("router_nodes"):
                lines.append(f"- Router nodes: {j['router_nodes']}")
            if j.get("hard_routing_sibling_calls"):
                lines.append(f"- Hard routing sibling calls:")
                for sc in j["hard_routing_sibling_calls"]:
                    lines.append(f"  - {sc['from']} -> {sc['to']}: {sc.get('note', '')}")
            lines.append("")
    else:
        lines.append("## Hard Routing Cases\n")
        lines.append("No hard routing violations detected.\n")

    # Ambiguous dataflow cases
    amb_cases = [r for r in all_results if r.get("judge", {}).get("ambiguous_direct_dataflow", False) and not r.get("judge", {}).get("hard_routing", False)]
    if amb_cases:
        lines.append("## Ambiguous Direct Dataflow Cases\n")
        for r in amb_cases:
            lines.append(f"### {r['label']}")
            j = r.get("judge", {})
            lines.append(f"- Children: {', '.join(r.get('child_names', []))}")
            if j.get("ambiguous_sibling_calls"):
                for sc in j["ambiguous_sibling_calls"]:
                    lines.append(f"  - {sc['from']} -> {sc['to']}: {sc.get('note', '')}")
            lines.append("")

    # Parent-mediated evidence
    pm_cases = [r for r in all_results if r.get("judge", {}).get("parent_mediated_dataflow", False)]
    if pm_cases:
        lines.append("## Parent-Mediated Dataflow (not counted as hard routing)\n")
        for r in pm_cases[:5]:  # cap
            lines.append(f"- {r['label']}: {', '.join(r.get('child_names', []))}")
        lines.append("")

    # Missing fields analysis
    all_missing = []
    for r in all_results:
        all_missing.extend(r.get("missing_fields", []))
    if all_missing:
        missing_counter = defaultdict(int)
        for m in all_missing:
            parts = m.split(":", 1)
            field = parts[1] if len(parts) > 1 else m
            missing_counter[field] += 1
        lines.append("## Most Common Missing Fields\n")
        lines.append("| Field | Count |")
        lines.append("|-------|-------|")
        for field, count in sorted(missing_counter.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"| {field} | {count} |")
        lines.append("")

    # Interpretation
    lines.append("## Interpretation\n")
    lines.append(f"### Does full single-stage + no-traditional suppress hard routing?")
    if total_hr <= 0.17:
        lines.append(f"Yes. Hard routing rate {total_hr}/{total} ({total_hr/total*100:.0f}%) is within the")
        lines.append("0-17% range established by staged no-traditional experiments.")
    elif total_hr <= 0.30:
        lines.append("Inconclusive. Hard routing rate is elevated but not clearly systematic.")
    else:
        lines.append(f"No. Hard routing rate {total_hr}/{total} ({total_hr/total*100:.0f}%) is significantly")
        lines.append("above the staged no-traditional baseline.")
    lines.append("")

    lines.append("### Is the result comparable to lean staged no-traditional?")
    if total_hr <= 0.17:
        lines.append(f"Yes. The full single-stage schema does not degrade no-traditional's effectiveness.")
    elif total_hr <= 0.30:
        lines.append("Partially. The full schema load may slightly reduce no-traditional's effectiveness.")
    else:
        lines.append(f"No. The full schema load substantially reduces no-traditional's effectiveness.")
    lines.append("")

    lines.append("### What remains inconclusive?")
    lines.append("- Field completion: full schema requires ~20 fields per child plus top-level fields;")
    lines.append("  LLM may omit sub-fields even if no-traditional routing suppression works.")
    lines.append("- The no-traditional block was not separately ablated — we cannot distinguish")
    lines.append("  full-schema effects from no-traditional effects without a full-schema baseline.")
    lines.append("- Single model (deepseek-v4-flash) only; generalizability to other models unknown.")
    lines.append("- The stop rule was followed: no prompt tuning, no judge patching, no fixture changes.")
    lines.append("")

    # Stop rule
    lines.append("## Stop Rule Compliance\n")
    lines.append("This experiment was implemented as a single pass with no follow-up modifications.")
    lines.append("After producing results, no prompt tuning, judge patching, fixture changes,")
    lines.append("MVP modifications, or hot.md updates were made.")
    lines.append("")

    return "\n".join(lines)


# ========================================================================
# Main
# ========================================================================

def main():
    parser = argparse.ArgumentParser(description="Full Single-Stage + No-Traditional Experiment")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--trials", type=int, default=NUM_TRIALS)
    parser.add_argument("--domains", type=str, default="Order,Chat,Patient,BuildSystem,DataPipeline")
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
                j = r.get("judge", {})
                status = "HARD_ROUTING" if j.get("hard_routing") else "ok"
                amb = " AMB" if j.get("ambiguous_direct_dataflow") else ""
                err = r.get("error", "")
                fc = r.get("field_completion_rate", 0) * 100
                if err:
                    print(f"  [{r['label']}] ERROR: {err[:80]}")
                else:
                    print(f"  [{r['label']}] {r.get('n_children',0)} children, {status}{amb}, fields={fc:.0f}% = {names}")

    # Save results
    out_dir = os.path.join(OUTPUT_DIR, model)
    os.makedirs(out_dir, exist_ok=True)

    # Aggregate metrics
    valid = [r for r in all_results if not r.get("error") and not r.get("parse_error")]
    n = len(valid)
    metrics = {
        "model": model,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "experiment": "full_single_stage_notraditional",
        "prompt_condition": "Full original single-stage schema + DO NOT ASSUME TRADITIONAL DEVELOPMENT PATTERNS block",
        "total_trials": len(all_results),
        "valid_trials": len(valid),
        "parse_errors": sum(1 for r in all_results if r.get("error") or r.get("parse_error", False)),
        "hard_routing_rate": sum(1 for r in valid if r.get("judge", {}).get("hard_routing", False)) / n if n else 0,
        "ambiguous_direct_dataflow_rate": sum(1 for r in valid if r.get("judge", {}).get("ambiguous_direct_dataflow", False)) / n if n else 0,
        "parent_mediated_dataflow_rate": sum(1 for r in valid if r.get("judge", {}).get("parent_mediated_dataflow", False)) / n if n else 0,
        "child_count_violation_rate": sum(1 for r in valid if r.get("child_count_violation", False)) / n if n else 0,
        "field_completion_rate": sum(r.get("field_completion_rate", 0) for r in valid) / n if n else 0,
        "per_domain": {},
    }

    by_domain = defaultdict(list)
    for r in valid:
        by_domain[r["domain"]].append(r)
    for dname in [d[0] for d in domains]:
        dt = by_domain.get(dname, [])
        metrics["per_domain"][dname] = {
            "trials": len(dt),
            "hard_routing": sum(1 for r in dt if r.get("judge", {}).get("hard_routing", False)),
            "ambiguous_direct_dataflow": sum(1 for r in dt if r.get("judge", {}).get("ambiguous_direct_dataflow", False)),
            "parent_mediated_dataflow": sum(1 for r in dt if r.get("judge", {}).get("parent_mediated_dataflow", False)),
        }

    results_payload = {
        "metrics": metrics,
        "trials": all_results,
    }

    results_path = os.path.join(out_dir, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved: {results_path}")

    # Generate report
    report = generate_report(all_results, model, domains)
    report_path = os.path.join(out_dir, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Saved: {report_path}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Total trials: {len(all_results)}")
    print(f"  Parse errors: {metrics['parse_errors']}/{len(all_results)}")
    print(f"  Hard routing: {metrics['hard_routing_rate']*100:.0f}%")
    print(f"  Ambiguous dataflow: {metrics['ambiguous_direct_dataflow_rate']*100:.0f}%")
    print(f"  Parent-mediated: {metrics['parent_mediated_dataflow_rate']*100:.0f}%")
    print(f"  Field completion: {metrics['field_completion_rate']*100:.1f}%")
    print(f"  Child count violations: {metrics['child_count_violation_rate']*100:.0f}%")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
