"""
Experiment 2: Stage 1 → Stage 2/3 Derivation Stability

Given a fixed Stage 1 decomposition, run Stage 2 and Stage 3 repeatedly
to measure drift and stability of derived interfaces and resources.

Consumes valid Stage 1 results from Exp01 output or generates fresh ones.

Output: output/multistage_exp02_derivation_stability/{model}/
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

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "multistage_exp02_derivation_stability")

# ========================================================================
# Stage 1 System Prompt (same as Exp01)
# ========================================================================

STAGE1_SYSTEM_PROMPT = """You are a software system decomposition agent. Your task is to decompose a function block into smaller child function blocks.

CRITICAL RULES:
1. EVERY CHILD MUST BE A FUNCTION, NOT A CLASS.
2. TREE STRUCTURE (not graph): Children MUST NOT call each other. The parent MUST directly invoke all children.
3. Do NOT add extra external inputs or outputs beyond what the parent has.
4. Children should be at the same abstraction level and minimally overlapping.

DO NOT ASSUME TRADITIONAL DEVELOPMENT PATTERNS:
- DO NOT create "dispatcher", "router", "controller", "command_handler" nodes.
- DO NOT use Command Pattern, Strategy Pattern, or any pattern where one child calls other children.
- Each child MUST be a self-contained function that does actual work.
- The parent IS the router.

SEMANTIC STOP CONDITIONS: STOP when pure function, atomic operation, or max depth reached.

OUTPUT FORMAT — Return valid JSON:
{
  "children": [
    {
      "name": "ChildName",
      "purpose": "semantic responsibility",
      "behavior": "internal transformation without sibling calls",
      "boundary": {"in_scope": ["..."], "out_of_scope": ["..."]},
      "semantic_inputs": [{"name": "...", "description": "...", "source": "parent input | previous child output | constant | internal leaf access"}],
      "semantic_outputs": [{"name": "...", "description": "...", "consumer": "parent | ChildName"}],
      "preconditions": ["..."],
      "postconditions": ["..."],
      "guarantees": ["..."],
      "composition_role": "transform | validate | decide | execute | aggregate | query | mutate",
      "stop_decompose": false,
      "stop_reason": ""
    }
  ],
  "decomposition_rationale": "how children jointly cover parent responsibility",
  "orchestration_model": "sequence | conditional | aggregate | pipeline | mixed",
  "dataflow_sketch": [{"from": "parent | ChildName", "to": "ChildName | parent", "data": "semantic data", "note": "why"}]
}

CONSTRAINTS:
1. Child must not call, invoke, dispatch to, route to, or reference siblings.
2. Parent is the only router/orchestrator.
3. composition_role=decide means "returns a decision to parent", not "calls another child".
4. Do not use handler/router/dispatcher/controller patterns.
5. Do NOT emit inputs, outputs, signature, global_vars, data_operations, requested_capabilities."""


# ========================================================================
# Stage 2 System Prompt
# ========================================================================

STAGE2_SYSTEM_PROMPT = """You are an interface derivation agent. Given a frozen Stage 1 decomposition, your task is to derive precise typed interfaces for each child.

RULES:
1. You MUST NOT add, delete, rename, or reorder children. The child list from Stage 1 is LOCKED.
2. You MUST NOT change any Stage 1 field (purpose, behavior, boundary, preconditions, postconditions, guarantees, composition_role).
3. Derive ONLY: inputs, outputs, signature for each child.
4. SIGNATURE LOCKING: Use precise Python types: str, int, float, bool, dict, list, Optional[dict], List[str], Dict[int, str], etc.
5. DATAFLOW CLOSURE: Every child input must have an explicit source (parent input, earlier child output, constant, or internal leaf access).
6. Parent inputs are consumed by children; parent outputs are produced by children.

OUTPUT FORMAT — Return valid JSON:
{
  "children": [
    {
      "name": "ChildName (UNCHANGED from Stage 1)",
      "purpose": "(UNCHANGED)",
      "behavior": "(UNCHANGED)",
      "boundary": {"in_scope": ["(UNCHANGED)"], "out_of_scope": ["(UNCHANGED)"]},
      "semantic_inputs": ["(UNCHANGED)"],
      "semantic_outputs": ["(UNCHANGED)"],
      "preconditions": ["(UNCHANGED)"],
      "postconditions": ["(UNCHANGED)"],
      "guarantees": ["(UNCHANGED)"],
      "composition_role": "(UNCHANGED)",
      "stop_decompose": false,
      "stop_reason": "",
      "inputs": [{"name": "param", "type": "str", "description": "desc", "source": "where data comes from"}],
      "outputs": [{"name": "result", "type": "dict", "description": "desc", "consumer": "who uses this"}],
      "signature": "def ChildName(param1: type1) -> return_type"
    }
  ],
  "interface_preservation": {
    "parent_inputs_covered_by": {"input_name": "child_name"},
    "parent_outputs_produced_by": {"output_name": "child_name"}
  },
  "dataflow_edges": [
    {"from_node": "parent | ChildName", "from_output": "output_name", "to_node": "ChildName | parent", "to_input": "input_name", "note": "why"}
  ]
}"""


# ========================================================================
# Stage 3 System Prompt
# ========================================================================

STAGE3_SYSTEM_PROMPT = """You are a governance and resource derivation agent. Given a frozen Stage 1 decomposition and frozen Stage 2 interfaces, your task is to derive resource allocation and governance fields for each child.

RULES:
1. You MUST NOT change Stage 1 semantics (purpose, behavior, boundary, preconditions, postconditions, guarantees, composition_role) or Stage 2 signatures (inputs, outputs, signature).
2. You MUST NOT add, delete, rename, or reorder children.
3. Derive ONLY: global_vars, data_operations, requested_capabilities, constraints, acceptance_criteria, traceability, node_type.
4. Each child's global_vars MUST be a subset of the parent's global_vars.
5. The union of all children's data_operations must cover the parent's data needs.

OUTPUT FORMAT — Return valid JSON:
{
  "children": [
    {
      "name": "ChildName (UNCHANGED)",
      "purpose": "(UNCHANGED from Stage 1)",
      "behavior": "(UNCHANGED from Stage 1)",
      "boundary": {"in_scope": ["(UNCHANGED)"], "out_of_scope": ["(UNCHANGED)"]},
      "preconditions": ["(UNCHANGED)"],
      "postconditions": ["(UNCHANGED)"],
      "guarantees": ["(UNCHANGED)"],
      "composition_role": "(UNCHANGED)",
      "inputs": ["(UNCHANGED from Stage 2)"],
      "outputs": ["(UNCHANGED from Stage 2)"],
      "signature": "(UNCHANGED from Stage 2)",
      "global_vars": [{"variable": "var_name", "op": "read|write|read_write", "description": "what operation"}],
      "data_operations": [{"source_name": "source", "operation_type": "read|write|read_write", "description": "what operation"}],
      "requested_capabilities": ["resource.operation"],
      "constraints": [{"constraint_id": "C-001", "description": "constraint description"}],
      "acceptance_criteria": [{"ac_id": "AC-001", "description": "criterion"}],
      "traceability": {"parent_requirement_ids": ["FR-001"]},
      "node_type": "pure_function|atomic_operation",
      "stop_decompose": false,
      "stop_reason": ""
    }
  ],
  "governance_notes": "any notes for validator/codegen"
}"""


# ========================================================================
# Domain definitions (same as Exp01, minimal set for Stage 1 generation)
# ========================================================================

DOMAINS = {
    "Order": {
        "name": "OrderSystem",
        "purpose": "Process e-commerce orders via a single entry point.",
        "input_desc": "input: Any - JSON with command (place/cancel/track) and order_data",
        "output_desc": "output: Any - JSON with success, order_id, status, message",
        "description": "Functional Requirements:\n  [FR-001] Place Order\n  [FR-002] Cancel Order\n  [FR-003] Track Order",
        "constraints": ["All operations must be atomic", "Cannot cancel a shipped order"],
        "data_sources": ["orders (memory, read_write)", "inventory (memory, read_write)", "payments (memory, read_write)"],
    },
    "Chat": {
        "name": "ChatApp",
        "purpose": "Handle real-time messaging operations",
        "input_desc": "input: Any - JSON with command (send/history/create_channel/join)",
        "output_desc": "output: Any - JSON with success, data, message",
        "description": "Functional Requirements:\n  [FR-001] Send Message\n  [FR-002] Get History\n  [FR-003] Create Channel\n  [FR-004] Join Channel",
        "constraints": ["Users can only send to joined channels", "History limited to 100 messages"],
        "data_sources": ["messages (memory, read_write)", "channels (memory, read_write)"],
    },
    "Patient": {
        "name": "PatientPortal",
        "purpose": "Manage patient healthcare operations",
        "input_desc": "input: Any - JSON with command (register/book/records/update)",
        "output_desc": "output: Any - JSON with success, data, message",
        "description": "Functional Requirements:\n  [FR-001] Register\n  [FR-002] Book Appointment\n  [FR-003] Get Records\n  [FR-004] Update Profile",
        "constraints": ["Patient must be registered before booking", "Records are append-only"],
        "data_sources": ["patients (memory, read_write)", "appointments (memory, read_write)"],
    },
    "BuildSystem": {
        "name": "BuildSystem",
        "purpose": "Manage CI/CD builds: trigger, status, list, cancel.",
        "input_desc": "input: Any - JSON with action (trigger/status/list/cancel), repo, branch",
        "output_desc": "output: Any - JSON with success, build_id, status, logs",
        "description": "Functional Requirements:\n  [FR-001] Trigger build\n  [FR-002] Check status\n  [FR-003] List builds\n  [FR-004] Cancel build",
        "constraints": ["Only one build per repo+branch", "Build logs stored incrementally"],
        "data_sources": ["builds (memory, read_write)", "artifacts (memory, read_write)"],
    },
    "DataPipeline": {
        "name": "DataPipeline",
        "purpose": "ETL data processing: ingest, transform, validate, export.",
        "input_desc": "input: Any - JSON with action (ingest/transform/validate/export), source",
        "output_desc": "output: Any - JSON with success, records_processed, errors, data",
        "description": "Functional Requirements:\n  [FR-001] Ingest data\n  [FR-002] Transform data\n  [FR-003] Validate quality\n  [FR-004] Export results",
        "constraints": ["Each step must log", "Export includes only valid records"],
        "data_sources": ["raw_data (memory, read_write)", "processed_data (memory, read_write)"],
    },
}


# ========================================================================
# Shared utilities
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


def build_user_prompt(node_info):
    lines = [
        "Decompose the following function block:", "",
        f"Node Name: {node_info['name']}",
        f"Node Purpose: {node_info['purpose']}", "",
    ]
    if node_info.get("description"):
        lines.append(node_info["description"]); lines.append("")
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


def build_stage2_user_prompt(stage1_data, node_info):
    children = stage1_data.get("children", [])
    lines = [
        "Derive interfaces for each child.", "",
        f"Parent: {node_info['name']}",
        f"Purpose: {node_info['purpose']}", "",
        f"Parent inputs: {node_info.get('input_desc', 'input: Any')}",
        f"Parent outputs: {node_info.get('output_desc', 'output: Any')}", "",
        "Available Data Stores:",
    ]
    for ds in node_info.get("data_sources", []):
        lines.append(f"  - {ds}")
    lines.append("")
    lines.append("Children (frozen from Stage 1):")
    for c in children:
        lines.append(f"  {c.get('name', '')}: {c.get('purpose', '')}")
        lines.append(f"    behavior: {c.get('behavior', '')[:200]}")
        lines.append(f"    role: {c.get('composition_role', '')}")
    lines.append("")
    lines.append("Return ONLY the JSON response.")
    return "\n".join(lines)


def build_stage3_user_prompt(stage1_data, stage2_data, node_info):
    children = stage2_data.get("children", stage1_data.get("children", []))
    lines = [
        "Derive governance and resource fields for each child.", "",
        f"Parent: {node_info['name']}",
        f"Purpose: {node_info['purpose']}", "",
        f"Parent inputs: {node_info.get('input_desc', 'input: Any')}",
        f"Parent outputs: {node_info.get('output_desc', 'output: Any')}", "",
        "Available Data Stores:",
    ]
    for ds in node_info.get("data_sources", []):
        lines.append(f"  - {ds}")
    lines.append("")
    lines.append("Children (frozen from Stage 1 + Stage 2):")
    for c in children:
        lines.append(f"  {c.get('name', '')}: {c.get('purpose', '')}")
        sig = c.get("signature", "")
        if sig:
            lines.append(f"    signature: {sig}")
        inp = c.get("inputs", [])
        if inp:
            lines.append(f"    inputs: {json.dumps(inp, ensure_ascii=False)[:200]}")
        out = c.get("outputs", [])
        if out:
            lines.append(f"    outputs: {json.dumps(out, ensure_ascii=False)[:200]}")
    lines.append("")
    lines.append("Return ONLY the JSON response.")
    return "\n".join(lines)


# ========================================================================
# Stability comparison utilities
# ========================================================================

def normalize_child_list(children):
    """Extract normalized child identity list for comparison."""
    return [(c.get("name", ""), c.get("purpose", ""), c.get("composition_role", "")) for c in children]


def normalize_signatures(children):
    """Extract normalized signatures for comparison."""
    result = {}
    for c in children:
        name = c.get("name", "")
        sig = c.get("signature", "")
        inputs = c.get("inputs", [])
        outputs = c.get("outputs", [])
        # Normalize: sort params, extract types
        param_names = tuple(sorted(i.get("name", "") for i in inputs))
        param_types = tuple(sorted(i.get("type", "") for i in inputs))
        ret_types = tuple(sorted(o.get("type", "") for o in outputs))
        result[name] = (sig, param_names, param_types, ret_types)
    return result


def normalize_dataflow(data):
    """Extract normalized dataflow topology."""
    edges = data.get("dataflow_edges", [])
    return set((e.get("from_node", ""), e.get("to_node", ""), e.get("to_input", "")) for e in edges)


def normalize_resources(children):
    """Extract normalized resource allocation."""
    result = {}
    for c in children:
        name = c.get("name", "")
        gv = tuple(sorted((g.get("variable", ""), g.get("op", "")) for g in c.get("global_vars", [])))
        do = tuple(sorted((d.get("source_name", ""), d.get("operation_type", "")) for d in c.get("data_operations", [])))
        rc = tuple(sorted(c.get("requested_capabilities", [])))
        result[name] = (gv, do, rc)
    return result


def compare_child_identity(stage1_children, derived_children):
    """Check if child identity drifted (added, removed, renamed, reordered)."""
    s1_names = [c.get("name", "") for c in stage1_children]
    d_names = [c.get("name", "") for c in derived_children]
    if s1_names != d_names:
        return {"drifted": True, "stage1_names": s1_names, "derived_names": d_names,
                "added": set(d_names) - set(s1_names), "removed": set(s1_names) - set(d_names)}
    return {"drifted": False}


def compare_semantics(stage1_children, derived_children):
    """Check if Stage 2/3 changed Stage 1 semantic fields."""
    changes = []
    s1_map = {c.get("name", ""): c for c in stage1_children}
    d_map = {c.get("name", ""): c for c in derived_children}
    for name in s1_map:
        if name not in d_map:
            continue
        s1 = s1_map[name]; d = d_map[name]
        for field in ("purpose", "behavior", "composition_role"):
            if s1.get(field) != d.get(field):
                changes.append({"child": name, "field": field, "stage1": s1.get(field), "derived": d.get(field)})
        # Compare boundary
        s1_boundary = json.dumps(s1.get("boundary", {}), sort_keys=True)
        d_boundary = json.dumps(d.get("boundary", {}), sort_keys=True)
        if s1_boundary != d_boundary:
            changes.append({"child": name, "field": "boundary", "stage1": s1.get("boundary"), "derived": d.get("boundary")})
        # Compare preconditions/postconditions/guarantees
        for field in ("preconditions", "postconditions", "guarantees"):
            if json.dumps(s1.get(field, []), sort_keys=True) != json.dumps(d.get(field, []), sort_keys=True):
                changes.append({"child": name, "field": field})
    return changes


# ========================================================================
# Trial runner
# ========================================================================

def generate_stage1(node_info, domain_name, api_key, base_url, model, sample_idx, log_dir):
    """Generate a single Stage 1 decomposition."""
    logger = LLMLogger(log_dir, api_key, base_url, model)
    t0 = time.time()
    try:
        raw = logger.chat([
            {"role": "system", "content": STAGE1_SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(node_info)},
        ])
    except Exception as e:
        return None, f"Stage1 API failed: {e}", logger.call_counter

    parsed = parse_json(raw)
    elapsed = round(time.time()-t0, 1)

    if "error" in parsed and not parsed.get("children"):
        return None, f"Stage1 parse failed: {parsed.get('error')}", logger.call_counter

    with open(os.path.join(log_dir, "stage1.json"), "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False, default=str)

    return parsed, None, logger.call_counter


def derive_stage2(stage1_data, node_info, rep_idx, api_key, base_url, model, log_dir):
    """Run Stage 2 derivation once on frozen Stage 1."""
    logger = LLMLogger(log_dir, api_key, base_url, model)
    t0 = time.time()
    try:
        raw = logger.chat([
            {"role": "system", "content": STAGE2_SYSTEM_PROMPT},
            {"role": "assistant", "content": json.dumps(stage1_data, indent=2, ensure_ascii=False)},
            {"role": "user", "content": build_stage2_user_prompt(stage1_data, node_info)},
        ])
    except Exception as e:
        return None, f"Stage2 API failed: {e}", logger.call_counter

    parsed = parse_json(raw)
    elapsed = round(time.time()-t0, 1)

    with open(os.path.join(log_dir, f"stage2_rep_{rep_idx:02d}.json"), "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False, default=str)

    return parsed, None, logger.call_counter


def derive_stage3(stage1_data, stage2_data, node_info, rep_idx, api_key, base_url, model, log_dir):
    """Run Stage 3 derivation once on frozen Stage 1 + Stage 2."""
    logger = LLMLogger(log_dir, api_key, base_url, model)
    t0 = time.time()
    try:
        raw = logger.chat([
            {"role": "system", "content": STAGE3_SYSTEM_PROMPT},
            {"role": "assistant", "content": json.dumps(stage2_data, indent=2, ensure_ascii=False)},
            {"role": "user", "content": build_stage3_user_prompt(stage1_data, stage2_data, node_info)},
        ])
    except Exception as e:
        return None, f"Stage3 API failed: {e}", logger.call_counter

    parsed = parse_json(raw)
    elapsed = round(time.time()-t0, 1)

    with open(os.path.join(log_dir, f"stage3_rep_{rep_idx:02d}.json"), "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False, default=str)

    return parsed, None, logger.call_counter


def run_sample(domain_name, node_info, sample_idx, n_reps, api_key, base_url, model):
    """Run one sample: Stage 1 + n_reps x Stage 2 + n_reps x Stage 3."""
    label = f"{domain_name}/sample_{sample_idx:02d}"
    log_dir = os.path.join(OUTPUT_DIR, model, domain_name, f"sample_{sample_idx:02d}")
    os.makedirs(log_dir, exist_ok=True)
    t0 = time.time()

    # Generate Stage 1
    stage1_data, err, llm_calls = generate_stage1(node_info, domain_name, api_key, base_url, model, sample_idx, log_dir)
    if err:
        return {"label": label, "domain": domain_name, "sample": sample_idx,
                "error": err, "elapsed": round(time.time()-t0, 1), "llm_calls": llm_calls}

    stage1_children = stage1_data.get("children", [])
    if len(stage1_children) < 2:
        return {"label": label, "domain": domain_name, "sample": sample_idx,
                "error": f"Stage1 returned {len(stage1_children)} children, need >= 2",
                "elapsed": round(time.time()-t0, 1), "llm_calls": llm_calls}

    # Run Stage 2 repeatedly
    stage2_results = []
    stage2_parse_errors = 0
    for rep in range(n_reps):
        s2_data, err, calls = derive_stage2(stage1_data, node_info, rep, api_key, base_url, model, log_dir)
        llm_calls += calls
        if err:
            stage2_parse_errors += 1
            stage2_results.append(None)
        else:
            stage2_results.append(s2_data)

    # Run Stage 3 repeatedly (using first valid Stage 2 as base)
    stage3_results = []
    stage3_parse_errors = 0
    base_s2 = next((s for s in stage2_results if s is not None), None)
    if base_s2:
        for rep in range(n_reps):
            s3_data, err, calls = derive_stage3(stage1_data, base_s2, node_info, rep, api_key, base_url, model, log_dir)
            llm_calls += calls
            if err:
                stage3_parse_errors += 1
                stage3_results.append(None)
            else:
                stage3_results.append(s3_data)

    # Compute stability metrics
    valid_s2 = [s for s in stage2_results if s is not None]
    valid_s3 = [s for s in stage3_results if s is not None]

    # Child identity drift
    s2_identity_drifts = []
    for s2 in valid_s2:
        drift = compare_child_identity(stage1_children, s2.get("children", []))
        if drift["drifted"]:
            s2_identity_drifts.append(drift)

    s3_identity_drifts = []
    for s3 in valid_s3:
        drift = compare_child_identity(stage1_children, s3.get("children", []))
        if drift["drifted"]:
            s3_identity_drifts.append(drift)

    # Semantic drift (purpose, behavior, boundary)
    s2_semantic_changes = []
    for s2 in valid_s2:
        changes = compare_semantics(stage1_children, s2.get("children", []))
        s2_semantic_changes.extend(changes)

    s3_semantic_changes = []
    for s3 in valid_s3:
        changes = compare_semantics(stage1_children, s3.get("children", []))
        s3_semantic_changes.extend(changes)

    # Signature stability (compare across Stage 2 repetitions)
    sig_stability = 1.0
    if len(valid_s2) >= 2:
        sigs = [normalize_signatures(s.get("children", [])) for s in valid_s2]
        ref = sigs[0]
        matches = 0
        comparisons = 0
        for name in ref:
            for other_sigs in sigs[1:]:
                comparisons += 1
                if name in other_sigs and ref[name] == other_sigs[name]:
                    matches += 1
        sig_stability = matches / comparisons if comparisons > 0 else 1.0

    # Dataflow topology stability
    df_stability = 1.0
    if len(valid_s2) >= 2:
        dfs = [normalize_dataflow(s) for s in valid_s2]
        ref = dfs[0]
        matches = sum(1 for df in dfs[1:] if df == ref)
        df_stability = matches / (len(dfs) - 1) if len(dfs) > 1 else 1.0

    # Resource allocation stability (Stage 3)
    res_stability = 1.0
    if len(valid_s3) >= 2:
        ress = [normalize_resources(s.get("children", [])) for s in valid_s3]
        ref = ress[0]
        matches = sum(1 for res in ress[1:] if res == ref)
        res_stability = matches / (len(ress) - 1) if len(ress) > 1 else 1.0

    elapsed = round(time.time()-t0, 1)

    result = {
        "label": label,
        "domain": domain_name,
        "sample": sample_idx,
        "n_stage1_children": len(stage1_children),
        "stage1_child_names": [c.get("name", "") for c in stage1_children],
        "n_stage2_valid": len(valid_s2),
        "n_stage2_parse_errors": stage2_parse_errors,
        "n_stage3_valid": len(valid_s3),
        "n_stage3_parse_errors": stage3_parse_errors,
        "child_identity_drift_stage2": len(s2_identity_drifts),
        "child_identity_drift_stage3": len(s3_identity_drifts),
        "semantic_drift_stage2": len(s2_semantic_changes),
        "semantic_drift_stage3": len(s3_semantic_changes),
        "signature_stability": round(sig_stability, 4),
        "dataflow_topology_stability": round(df_stability, 4),
        "resource_allocation_stability": round(res_stability, 4),
        "semantic_changes_detail": (s2_semantic_changes + s3_semantic_changes)[:10],
        "identity_drift_detail": (s2_identity_drifts + s3_identity_drifts)[:5],
        "elapsed": elapsed,
        "llm_calls": llm_calls,
    }

    with open(os.path.join(log_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    return result


# ========================================================================
# Report generation
# ========================================================================

def generate_report(all_results, model, n_samples, n_reps):
    lines = [
        "# Exp02: Stage 1 → Stage 2/3 Derivation Stability Report",
        "",
        f"Model: `{model}`",
        f"Samples per domain: {n_samples}",
        f"Repetitions per stage: {n_reps}",
        f"Total samples: {len(all_results)}",
        "",
    ]

    # Summary by domain
    lines.append("## Results by Domain\n")
    lines.append("| Domain | Samples | Identity Drift (S2) | Identity Drift (S3) | Semantic Drift (S2) | Semantic Drift (S3) | Sig Stability | DF Stability | Res Stability | S2 Parse Err | S3 Parse Err |")
    lines.append("|--------|---------|--------------------|--------------------|--------------------|--------------------|--------------|-------------|--------------|-------------|-------------|")

    by_domain = defaultdict(list)
    for r in all_results:
        by_domain[r["domain"]].append(r)

    domain_order = ["Order", "Chat", "Patient", "BuildSystem", "DataPipeline"]
    for dname in domain_order:
        results = by_domain.get(dname, [])
        if not results:
            continue
        n = len(results)
        id_s2 = sum(r.get("child_identity_drift_stage2", 0) for r in results)
        id_s3 = sum(r.get("child_identity_drift_stage3", 0) for r in results)
        sem_s2 = sum(r.get("semantic_drift_stage2", 0) for r in results)
        sem_s3 = sum(r.get("semantic_drift_stage3", 0) for r in results)
        avg_sig = sum(r.get("signature_stability", 0) for r in results) / n
        avg_df = sum(r.get("dataflow_topology_stability", 0) for r in results) / n
        avg_res = sum(r.get("resource_allocation_stability", 0) for r in results) / n
        s2_err = sum(r.get("n_stage2_parse_errors", 0) for r in results)
        s3_err = sum(r.get("n_stage3_parse_errors", 0) for r in results)
        lines.append(f"| {dname} | {n} | {id_s2} | {id_s3} | {sem_s2} | {sem_s3} | {avg_sig*100:.1f}% | {avg_df*100:.1f}% | {avg_res*100:.1f}% | {s2_err} | {s3_err} |")

    # Totals
    n = len(all_results)
    total_id_s2 = sum(r.get("child_identity_drift_stage2", 0) for r in all_results)
    total_id_s3 = sum(r.get("child_identity_drift_stage3", 0) for r in all_results)
    total_sem_s2 = sum(r.get("semantic_drift_stage2", 0) for r in all_results)
    total_sem_s3 = sum(r.get("semantic_drift_stage3", 0) for r in all_results)
    total_sig = sum(r.get("signature_stability", 0) for r in all_results) / n if n else 0
    total_df = sum(r.get("dataflow_topology_stability", 0) for r in all_results) / n if n else 0
    total_res = sum(r.get("resource_allocation_stability", 0) for r in all_results) / n if n else 0
    total_s2_err = sum(r.get("n_stage2_parse_errors", 0) for r in all_results)
    total_s3_err = sum(r.get("n_stage3_parse_errors", 0) for r in all_results)
    lines.append(f"| **TOTAL** | **{n}** | **{total_id_s2}** | **{total_id_s3}** | **{total_sem_s2}** | **{total_sem_s3}** | **{total_sig*100:.1f}%** | **{total_df*100:.1f}%** | **{total_res*100:.1f}%** | **{total_s2_err}** | **{total_s3_err}** |")
    lines.append("")

    # Drift cases detail
    drift_cases = [r for r in all_results if r.get("child_identity_drift_stage2", 0) > 0 or r.get("child_identity_drift_stage3", 0) > 0]
    if drift_cases:
        lines.append("## Identity Drift Cases\n")
        for r in drift_cases:
            lines.append(f"### {r['label']}")
            for d in r.get("identity_drift_detail", []):
                lines.append(f"- Added: {d.get('added', set())}, Removed: {d.get('removed', set())}")
                lines.append(f"  Stage1: {d.get('stage1_names', [])}")
                lines.append(f"  Derived: {d.get('derived_names', [])}")
            lines.append("")
    else:
        lines.append("## Identity Drift Cases\n")
        lines.append("No child identity drift detected.\n")

    # Semantic drift detail
    sem_cases = [r for r in all_results if r.get("semantic_drift_stage2", 0) > 0 or r.get("semantic_drift_stage3", 0) > 0]
    if sem_cases:
        lines.append("## Semantic Drift Cases\n")
        field_counter = defaultdict(int)
        for r in all_results:
            for c in r.get("semantic_changes_detail", []):
                field_counter[c.get("field", "unknown")] += 1
        lines.append("| Field | Drift Count |")
        lines.append("|-------|-------------|")
        for field, count in sorted(field_counter.items(), key=lambda x: -x[1]):
            lines.append(f"| {field} | {count} |")
        lines.append("")
    else:
        lines.append("## Semantic Drift Cases\n")
        lines.append("No semantic drift detected.\n")

    # Verdict
    lines.append("## Verdict\n")
    lines.append(f"- Child identity drift (Stage 2): {total_id_s2} occurrences")
    lines.append(f"- Child identity drift (Stage 3): {total_id_s3} occurrences")
    lines.append(f"- Semantic drift (Stage 2): {total_sem_s2} field changes")
    lines.append(f"- Semantic drift (Stage 3): {total_sem_s3} field changes")
    lines.append(f"- Signature stability: {total_sig*100:.1f}%")
    lines.append(f"- Dataflow topology stability: {total_df*100:.1f}%")
    lines.append(f"- Resource allocation stability: {total_res*100:.1f}%")

    if total_id_s2 == 0 and total_id_s3 == 0 and total_sig >= 0.80:
        verdict = "PASS"
    elif total_id_s2 > 0 or total_id_s3 > 0:
        verdict = "FAIL"
    else:
        verdict = "INCONCLUSIVE"
    lines.append(f"- **Verdict: {verdict}**")
    lines.append("")
    return "\n".join(lines)


# ========================================================================
# Main
# ========================================================================

def main():
    parser = argparse.ArgumentParser(description="Exp02: Stage 1 → Stage 2/3 Derivation Stability")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--samples", type=int, default=2, help="Samples per domain")
    parser.add_argument("--repetitions", type=int, default=5, help="Repetitions for Stage 2 and Stage 3")
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

    requested = [d.strip() for d in args.domains.split(",")]
    domains = [(d, DOMAINS[d]) for d in requested if d in DOMAINS]
    if not domains:
        print(f"ERROR: No valid domains. Available: {list(DOMAINS.keys())}"); return 1

    print(f"Model: {model}")
    print(f"Domains: {[d[0] for d in domains]}")
    print(f"Samples per domain: {args.samples}")
    print(f"Repetitions: {args.repetitions}")
    print(f"Output: {OUTPUT_DIR}/{model}/")
    print()

    # Build task list
    tasks = []
    for dname, dnode in domains:
        for s in range(args.samples):
            tasks.append((dname, dnode, s, args.repetitions, api_key, base_url, model))

    all_results = []
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = {
            pool.submit(run_sample, dname, dnode, s, n_reps, api_key, base_url, model): f"{dname}_s{s}"
            for dname, dnode, s, n_reps, api_key, base_url, model in tasks
        }
        for f in as_completed(futures):
            r = f.result()
            all_results.append(r)
            err = r.get("error", "")
            if err:
                print(f"  [{r['label']}] ERROR: {err[:80]}")
            else:
                print(f"  [{r['label']}] children={r.get('n_stage1_children',0)}, "
                      f"sig_stab={r.get('signature_stability',0)*100:.0f}%, "
                      f"id_drift_s2={r.get('child_identity_drift_stage2',0)}, "
                      f"calls={r.get('llm_calls',0)}")

    # Sort by domain then sample
    all_results.sort(key=lambda r: (r.get("domain", ""), r.get("sample", 0)))

    # Save results
    out_dir = os.path.join(OUTPUT_DIR, model)
    os.makedirs(out_dir, exist_ok=True)
    results_path = os.path.join(out_dir, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved: {results_path}")

    # Generate report
    report = generate_report(all_results, model, args.samples, args.repetitions)
    report_path = os.path.join(out_dir, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Saved: {report_path}")

    # Summary
    n = len(all_results)
    total_id = sum(r.get("child_identity_drift_stage2", 0) + r.get("child_identity_drift_stage3", 0) for r in all_results)
    total_sem = sum(r.get("semantic_drift_stage2", 0) + r.get("semantic_drift_stage3", 0) for r in all_results)
    avg_sig = sum(r.get("signature_stability", 0) for r in all_results) / n if n else 0
    total_calls = sum(r.get("llm_calls", 0) for r in all_results)
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Total samples: {n}")
    print(f"  Identity drift: {total_id}")
    print(f"  Semantic drift: {total_sem}")
    print(f"  Avg signature stability: {avg_sig*100:.1f}%")
    print(f"  Total LLM calls: {total_calls}")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
