"""
Experiment 2b: Shared Conversation Memory vs Independent Context

Compare two conditions for multi-stage decomposition:
  A) independent_context: separate API calls per stage (current Exp02 construction)
  B) shared_conversation: single continuous message history across all stages

Hypothesis: shared conversation memory may reduce identity drift, parse failures,
internal leaf resource leakage into call signatures, invalid dataflow endpoints,
and Stage3 resource-field inconsistency.

Output: output/multistage_exp02_shared_conversation/{model}/
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
MAX_TOKENS = int(os.getenv("CHRONOS_MAX_TOKENS", "8192"))
MAX_CONCURRENCY = 5

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "multistage_exp02_shared_conversation")

# ========================================================================
# Prompts
# ========================================================================

# --- Shared global system prompt (for shared_conversation condition) ---

SHARED_GLOBAL_SYSTEM_PROMPT = """You are Agent Chronos' multi-stage decomposition agent.

You will complete one decomposition through three stages in a single conversation:

Stage 1: structural decomposition only.
Stage 2: interface derivation only.
Stage 3: governance and resource derivation only.

You must preserve all prior-stage names, responsibilities, boundaries,
preconditions, postconditions, guarantees, and composition roles unless the user
explicitly asks for a new experiment.

The decomposition is tree-centered:
- parent is the sole orchestrator
- children do not call siblings
- dataflow between children is mediated by the parent
- leaf nodes may access their own declared resources internally

Return only valid JSON for every stage."""

# --- Stage 1 system prompt (for independent_context condition) ---

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

# --- Stage 2 system prompt (for independent_context condition) ---

STAGE2_SYSTEM_PROMPT = """You are an interface derivation agent. Given a frozen Stage 1 decomposition, your task is to derive precise typed interfaces for each child.

RULES:
1. You MUST NOT add, delete, rename, or reorder children. The child list from Stage 1 is LOCKED.
2. You MUST NOT change any Stage 1 field (purpose, behavior, boundary, preconditions, postconditions, guarantees, composition_role).
3. Derive ONLY interface fields.
4. Separate parent-call parameters from internal leaf resource access.

REQUIRED INTERFACE CATEGORIES:
- call_inputs: Parameters the parent must pass when calling this child. Only these may appear in the Python signature.
- internal_leaf_accesses: Resources/data stores this child accesses inside its own implementation. These must NOT appear in the Python signature.
- outputs: Values returned by the child to the parent.
- signature: Python function signature built only from call_inputs.

DATAFLOW RULES:
- from_node and to_node must be either "parent" or an exact child name.
- Resource/store names such as raw_data, processed_data, channels, messages, orders, inventory, or payments must NOT appear as from_node/to_node.

OUTPUT FORMAT — Return valid JSON:
{
  "children": [
    {
      "name": "UNCHANGED from Stage 1",
      "purpose": "UNCHANGED",
      "behavior": "UNCHANGED",
      "boundary": {"in_scope": ["UNCHANGED"], "out_of_scope": ["UNCHANGED"]},
      "semantic_inputs": ["UNCHANGED"],
      "semantic_outputs": ["UNCHANGED"],
      "preconditions": ["UNCHANGED"],
      "postconditions": ["UNCHANGED"],
      "guarantees": ["UNCHANGED"],
      "composition_role": "UNCHANGED",
      "stop_decompose": false,
      "stop_reason": "",
      "call_inputs": [
        {"name": "param", "type": "dict", "description": "what parent passes", "source": "parent input | previous child output | constant"}
      ],
      "internal_leaf_accesses": [
        {"resource": "resource_name", "op": "read|write|read_write", "reason": "why this child needs the resource internally"}
      ],
      "outputs": [
        {"name": "result", "type": "dict", "description": "what child returns", "consumer": "parent"}
      ],
      "signature": "def ChildName(param: type) -> return_type"
    }
  ],
  "interface_preservation": {
    "parent_inputs_covered_by": {"input_name": "child_name"},
    "parent_outputs_produced_by": {"output_name": "child_name"}
  },
  "dataflow_edges": [
    {"from_node": "parent | ChildName", "from_output": "output_name", "to_node": "ChildName | parent", "to_input": "input_name", "note": "why"}
  ],
  "interface_audit": {
    "identity_preservation_detail": "explain whether child names/order are preserved",
    "semantic_preservation_detail": "explain whether Stage1 semantics are unchanged",
    "call_signature_detail": "explain why signature contains only call_inputs",
    "internal_leaf_separation_detail": "explain why resources are not call params",
    "dataflow_schema_detail": "explain endpoint legality",
    "final_status": "ok | needs_attention"
  }
}"""

# --- Stage 3 system prompt (for independent_context condition) ---

STAGE3_SYSTEM_PROMPT = """You are a governance and resource derivation agent. Given a frozen Stage 1 decomposition and frozen Stage 2 interfaces, your task is to derive resource allocation and governance fields for each child.

RULES:
1. You MUST NOT change Stage 1 semantics (purpose, behavior, boundary, preconditions, postconditions, guarantees, composition_role) or Stage 2 interfaces (call_inputs, internal_leaf_accesses, outputs, signature).
2. You MUST NOT add, delete, rename, or reorder children.
3. Derive ONLY governance/resource fields.
4. Use Stage2 internal_leaf_accesses as the primary source for resource fields.
5. global_vars and data_operations must be synchronized.
6. If a child has data_operations over a resource, global_vars must contain the same resource/op, unless governance_notes explains a deliberate exception.

OUTPUT FORMAT — Return valid JSON:
{
  "children": [
    {
      "name": "UNCHANGED",
      "purpose": "UNCHANGED from Stage 1",
      "behavior": "UNCHANGED from Stage 1",
      "boundary": {"in_scope": ["UNCHANGED"], "out_of_scope": ["UNCHANGED"]},
      "preconditions": ["UNCHANGED"],
      "postconditions": ["UNCHANGED"],
      "guarantees": ["UNCHANGED"],
      "composition_role": "UNCHANGED",
      "call_inputs": ["UNCHANGED from Stage 2"],
      "internal_leaf_accesses": ["UNCHANGED from Stage 2"],
      "outputs": ["UNCHANGED from Stage 2"],
      "signature": "UNCHANGED from Stage 2",
      "global_vars": [
        {"variable": "resource", "op": "read|write|read_write", "description": "what operation"}
      ],
      "data_operations": [
        {"source_name": "resource", "operation_type": "read|write|read_write", "description": "what operation"}
      ],
      "requested_capabilities": ["resource.operation"],
      "constraints": [{"constraint_id": "C-001", "description": "constraint"}],
      "acceptance_criteria": [{"ac_id": "AC-001", "description": "criterion"}],
      "traceability": {"parent_requirement_ids": ["FR-001"]},
      "node_type": "pure_function|atomic_operation",
      "stop_decompose": false,
      "stop_reason": ""
    }
  ],
  "governance_notes": "notes for validator/codegen",
  "resource_audit": {
    "signature_preservation_detail": "explain no signature changed",
    "internal_leaf_mapping_detail": "explain how internal_leaf_accesses map to resources",
    "global_vars_data_operations_sync_detail": "explain synchronization",
    "coverage_detail": "explain resource coverage",
    "final_status": "ok | needs_attention"
  }
}"""


# ========================================================================
# Domain definitions (same as old Exp02)
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
            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
            )
            text = resp.choices[0].message.content
        except Exception as e:
            with open(os.path.join(self.log_dir, f"{call_id:04d}_response.json"), "w", encoding="utf-8") as f:
                json.dump({"call_id": call_id, "elapsed": round(time.time() - start, 2), "error": str(e)}, f, indent=2)
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
        text = text[:text.rfind("}") + 1]
    text = re.sub(r'(?<=[\s:,\[{])[fFrRuUbB]+(")', r'\1', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return {"error": "JSON parse failed", "raw": text[:500]}


# ========================================================================
# Prompt builders
# ========================================================================

def build_stage1_user_prompt(node_info):
    lines = [
        "Decompose the following function block:", "",
        f"Node Name: {node_info['name']}",
        f"Node Purpose: {node_info['purpose']}", "",
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


def build_stage2_user_prompt(stage1_data, node_info):
    """Stage 2 user prompt for independent_context condition."""
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
    """Stage 3 user prompt for independent_context condition."""
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
        ci = c.get("call_inputs", [])
        if ci:
            lines.append(f"    call_inputs: {json.dumps(ci, ensure_ascii=False)[:200]}")
        ila = c.get("internal_leaf_accesses", [])
        if ila:
            lines.append(f"    internal_leaf_accesses: {json.dumps(ila, ensure_ascii=False)[:200]}")
        out = c.get("outputs", [])
        if out:
            lines.append(f"    outputs: {json.dumps(out, ensure_ascii=False)[:200]}")
    lines.append("")
    lines.append("Return ONLY the JSON response.")
    return "\n".join(lines)


def build_stage2_shared_user_prompt(stage1_data, node_info):
    """Stage 2 user prompt for shared_conversation condition."""
    children = stage1_data.get("children", [])
    lines = [
        "Now derive interfaces for each child from the Stage 1 decomposition above.", "",
        f"Parent: {node_info['name']}",
        f"Purpose: {node_info['purpose']}", "",
        f"Parent inputs: {node_info.get('input_desc', 'input: Any')}",
        f"Parent outputs: {node_info.get('output_desc', 'output: Any')}", "",
        "Available Data Stores:",
    ]
    for ds in node_info.get("data_sources", []):
        lines.append(f"  - {ds}")
    lines.append("")
    lines.append("You are continuing the same conversation. Use the Stage 1 JSON above as the frozen source of truth.")
    lines.append("Do not add, delete, rename, or reorder children.")
    lines.append("Do not change Stage 1 semantic fields.")
    lines.append("Derive only interface fields.")
    lines.append("Separate parent-call parameters from internal leaf resource access.")
    lines.append("")
    lines.append("REQUIRED INTERFACE CATEGORIES:")
    lines.append("- call_inputs: Parameters the parent must pass when calling this child. Only these may appear in the Python signature.")
    lines.append("- internal_leaf_accesses: Resources/data stores this child accesses inside its own implementation. These must NOT appear in the Python signature.")
    lines.append("- outputs: Values returned by the child to the parent.")
    lines.append("- signature: Python function signature built only from call_inputs.")
    lines.append("")
    lines.append("DATAFLOW RULES:")
    lines.append("- from_node and to_node must be either \"parent\" or an exact child name.")
    lines.append("- Resource/store names such as raw_data, processed_data, channels, messages, orders, inventory, or payments must NOT appear as from_node/to_node.")
    lines.append("")
    lines.append("OUTPUT FORMAT — Return valid JSON with exactly this structure:")
    lines.append("{")
    lines.append('  "children": [')
    lines.append("    {")
    lines.append('      "name": "UNCHANGED from Stage 1",')
    lines.append('      "purpose": "UNCHANGED",')
    lines.append('      "behavior": "UNCHANGED",')
    lines.append('      "boundary": {"in_scope": ["UNCHANGED"], "out_of_scope": ["UNCHANGED"]},')
    lines.append('      "semantic_inputs": ["UNCHANGED"],')
    lines.append('      "semantic_outputs": ["UNCHANGED"],')
    lines.append('      "preconditions": ["UNCHANGED"],')
    lines.append('      "postconditions": ["UNCHANGED"],')
    lines.append('      "guarantees": ["UNCHANGED"],')
    lines.append('      "composition_role": "UNCHANGED",')
    lines.append('      "stop_decompose": false,')
    lines.append('      "stop_reason": "",')
    lines.append('      "call_inputs": [')
    lines.append('        {"name": "param", "type": "dict", "description": "what parent passes", "source": "parent input | previous child output | constant"}')
    lines.append("      ],")
    lines.append('      "internal_leaf_accesses": [')
    lines.append('        {"resource": "resource_name", "op": "read|write|read_write", "reason": "why this child needs the resource internally"}')
    lines.append("      ],")
    lines.append('      "outputs": [')
    lines.append('        {"name": "result", "type": "dict", "description": "what child returns", "consumer": "parent"}')
    lines.append("      ],")
    lines.append('      "signature": "def ChildName(param: type) -> return_type"')
    lines.append("    }")
    lines.append("  ],")
    lines.append('  "interface_preservation": {')
    lines.append('    "parent_inputs_covered_by": {"input_name": "child_name"},')
    lines.append('    "parent_outputs_produced_by": {"output_name": "child_name"}')
    lines.append("  },")
    lines.append('  "dataflow_edges": [')
    lines.append('    {"from_node": "parent | ChildName", "from_output": "output_name", "to_node": "ChildName | parent", "to_input": "input_name", "note": "why"}')
    lines.append("  ],")
    lines.append('  "interface_audit": {')
    lines.append('    "identity_preservation_detail": "explain whether child names/order are preserved",')
    lines.append('    "semantic_preservation_detail": "explain whether Stage1 semantics are unchanged",')
    lines.append('    "call_signature_detail": "explain why signature contains only call_inputs",')
    lines.append('    "internal_leaf_separation_detail": "explain why resources are not call params",')
    lines.append('    "dataflow_schema_detail": "explain endpoint legality",')
    lines.append('    "final_status": "ok | needs_attention"')
    lines.append("  }")
    lines.append("}")
    lines.append("")
    lines.append("IMPORTANT: The top-level JSON MUST have the key \"children\" (not \"interfaces\" or \"children_interfaces\").")
    lines.append("Return ONLY the JSON response.")
    return "\n".join(lines)


def build_stage3_shared_user_prompt(stage1_data, stage2_data, node_info):
    """Stage 3 user prompt for shared_conversation condition."""
    children = stage2_data.get("children", stage1_data.get("children", []))
    lines = [
        "Now derive governance and resource fields for each child from Stage 1 + Stage 2 above.", "",
        f"Parent: {node_info['name']}",
        f"Purpose: {node_info['purpose']}", "",
        f"Parent inputs: {node_info.get('input_desc', 'input: Any')}",
        f"Parent outputs: {node_info.get('output_desc', 'output: Any')}", "",
        "Available Data Stores:",
    ]
    for ds in node_info.get("data_sources", []):
        lines.append(f"  - {ds}")
    lines.append("")
    lines.append("You are continuing the same conversation. Stage1 and Stage2 are frozen.")
    lines.append("Do not change child names, order, semantics, call_inputs, outputs, or signature.")
    lines.append("Derive only governance/resource fields.")
    lines.append("Use Stage2 internal_leaf_accesses as the primary source for resource fields.")
    lines.append("global_vars and data_operations must be synchronized.")
    lines.append("If a child has data_operations over a resource, global_vars must contain the same resource/op, unless governance_notes explains a deliberate exception.")
    lines.append("")
    lines.append("OUTPUT FORMAT — Return valid JSON with exactly this structure:")
    lines.append("{")
    lines.append('  "children": [')
    lines.append("    {")
    lines.append('      "name": "UNCHANGED",')
    lines.append('      "purpose": "UNCHANGED from Stage 1",')
    lines.append('      "behavior": "UNCHANGED from Stage 1",')
    lines.append('      "boundary": {"in_scope": ["UNCHANGED"], "out_of_scope": ["UNCHANGED"]},')
    lines.append('      "preconditions": ["UNCHANGED"],')
    lines.append('      "postconditions": ["UNCHANGED"],')
    lines.append('      "guarantees": ["UNCHANGED"],')
    lines.append('      "composition_role": "UNCHANGED",')
    lines.append('      "call_inputs": ["UNCHANGED from Stage2"],')
    lines.append('      "internal_leaf_accesses": ["UNCHANGED from Stage2"],')
    lines.append('      "outputs": ["UNCHANGED from Stage2"],')
    lines.append('      "signature": "UNCHANGED from Stage2",')
    lines.append('      "global_vars": [')
    lines.append('        {"variable": "resource", "op": "read|write|read_write", "description": "what operation"}')
    lines.append("      ],")
    lines.append('      "data_operations": [')
    lines.append('        {"source_name": "resource", "operation_type": "read|write|read_write", "description": "what operation"}')
    lines.append("      ],")
    lines.append('      "requested_capabilities": ["resource.operation"],')
    lines.append('      "constraints": [{"constraint_id": "C-001", "description": "constraint"}],')
    lines.append('      "acceptance_criteria": [{"ac_id": "AC-001", "description": "criterion"}],')
    lines.append('      "traceability": {"parent_requirement_ids": ["FR-001"]},')
    lines.append('      "node_type": "pure_function|atomic_operation",')
    lines.append('      "stop_decompose": false,')
    lines.append('      "stop_reason": ""')
    lines.append("    }")
    lines.append("  ],")
    lines.append('  "governance_notes": "notes for validator/codegen",')
    lines.append('  "resource_audit": {')
    lines.append('    "signature_preservation_detail": "explain no signature changed",')
    lines.append('    "internal_leaf_mapping_detail": "explain how internal_leaf_accesses map to resources",')
    lines.append('    "global_vars_data_operations_sync_detail": "explain synchronization",')
    lines.append('    "coverage_detail": "explain resource coverage",')
    lines.append('    "final_status": "ok | needs_attention"')
    lines.append("  }")
    lines.append("}")
    lines.append("")
    lines.append("IMPORTANT: The top-level JSON MUST have the key \"children\" (not \"interfaces\" or \"children_interfaces\").")
    lines.append("Return ONLY the JSON response.")
    return "\n".join(lines)


# ========================================================================
# Audit / Judge functions
# ========================================================================

SEMANTIC_FIELDS = ("purpose", "behavior", "preconditions", "postconditions", "guarantees", "composition_role")


def audit_parse_success(parsed):
    """Return True if parse succeeded and has 'children' key.

    Counts as failure:
    - parse_json() returned {"error": ...} with no children
    - Parsed JSON lacks "children" key (schema deviation, e.g. "interfaces" or "children_interfaces")
    - "children" is not a list
    """
    if not isinstance(parsed, dict):
        return False
    if "error" in parsed and not parsed.get("children"):
        return False
    if "children" not in parsed:
        return False
    if not isinstance(parsed.get("children"), list):
        return False
    return True


def audit_child_identity(stage1_children, derived_children):
    """Check if child identity drifted."""
    s1_names = [c.get("name", "") for c in stage1_children]
    d_names = [c.get("name", "") for c in derived_children]
    if s1_names != d_names:
        return {
            "drifted": True,
            "stage1_names": s1_names,
            "derived_names": d_names,
            "added": list(set(d_names) - set(s1_names)),
            "removed": list(set(s1_names) - set(d_names)),
        }
    return {"drifted": False}


def audit_semantic_preservation(stage1_children, derived_children):
    """Check that semantic fields are unchanged. Returns list of changes."""
    changes = []
    s1_map = {c.get("name", ""): c for c in stage1_children}
    d_map = {c.get("name", ""): c for c in derived_children}
    for name in s1_map:
        if name not in d_map:
            changes.append({"child": name, "field": "MISSING_IN_DERIVED"})
            continue
        s1 = s1_map[name]
        d = d_map[name]
        for field in SEMANTIC_FIELDS:
            s1v = s1.get(field)
            dv = d.get(field)
            if field in ("preconditions", "postconditions", "guarantees"):
                s1v = json.dumps(s1v, sort_keys=True) if s1v else "[]"
                dv = json.dumps(dv, sort_keys=True) if dv else "[]"
            if s1v != dv:
                changes.append({"child": name, "field": field, "stage1": str(s1.get(field))[:100], "derived": str(d.get(field))[:100]})
        # boundary
        s1b = json.dumps(s1.get("boundary", {}), sort_keys=True)
        db = json.dumps(d.get("boundary", {}), sort_keys=True)
        if s1b != db:
            changes.append({"child": name, "field": "boundary"})
    return changes


def _extract_names(items):
    """Extract names from a list that may contain dicts or strings."""
    names = set()
    for item in items:
        if isinstance(item, dict):
            names.add(item.get("name", item.get("resource", "")))
        elif isinstance(item, str):
            names.add(item)
    return names


def _extract_leaf_resources(items):
    """Extract resource names from internal_leaf_accesses list."""
    resources = set()
    for item in items:
        if isinstance(item, dict):
            resources.add(item.get("resource", ""))
        elif isinstance(item, str):
            resources.add(item)
    return resources


def audit_signature_resource_leak(children):
    """Check for internal leaf access resources leaking into signatures."""
    leaks = []
    for c in children:
        name = c.get("name", "")
        sig = c.get("signature", "")
        call_input_names = _extract_names(c.get("call_inputs", []))
        leaf_resources = _extract_leaf_resources(c.get("internal_leaf_accesses", []))

        # Extract param names from signature
        sig_params = set()
        m = re.search(r'\(([^)]*)\)', sig)
        if m:
            for param in m.group(1).split(","):
                param = param.strip()
                if ":" in param:
                    param = param.split(":")[0].strip()
                if param:
                    sig_params.add(param)

        # Check: signature contains internal_leaf_access resource name
        for resource in leaf_resources:
            if resource in sig_params:
                leaks.append({
                    "child": name,
                    "type": "leaf_resource_in_signature",
                    "resource": resource,
                    "signature": sig,
                })

        # Check: signature param not in call_inputs
        for sp in sig_params:
            if sp not in call_input_names and sp != "self":
                leaks.append({
                    "child": name,
                    "type": "param_not_in_call_inputs",
                    "param": sp,
                    "signature": sig,
                })

        # Check: call_inputs source is "internal leaf access"
        for ci in c.get("call_inputs", []):
            if isinstance(ci, dict):
                source = ci.get("source", "")
                if "internal" in source.lower() and "leaf" in source.lower():
                    leaks.append({
                        "child": name,
                        "type": "call_input_source_is_leaf",
                        "call_input": ci.get("name", ""),
                        "source": source,
                    })

    return leaks


def audit_dataflow_schema(data, child_names):
    """Check that dataflow edges only use parent/child names as endpoints."""
    violations = []
    valid_endpoints = {"parent"} | set(child_names)
    for edge in data.get("dataflow_edges", []):
        fn = edge.get("from_node", "")
        tn = edge.get("to_node", "")
        if fn not in valid_endpoints:
            violations.append({
                "from_node": fn,
                "to_node": tn,
                "reason": f"from_node '{fn}' is not a valid endpoint",
            })
        if tn not in valid_endpoints:
            violations.append({
                "from_node": fn,
                "to_node": tn,
                "reason": f"to_node '{tn}' is not a valid endpoint",
            })
    return violations


def audit_stage3_signature_drift(stage2_children, stage3_children):
    """Check that Stage3 did not change Stage2 call_inputs, outputs, or signature."""
    drifts = []
    s2_map = {c.get("name", ""): c for c in stage2_children}
    s3_map = {c.get("name", ""): c for c in stage3_children}
    for name in s2_map:
        if name not in s3_map:
            continue
        s2 = s2_map[name]
        s3 = s3_map[name]
        for field in ("call_inputs", "outputs", "signature"):
            s2f = s2.get(field)
            s3f = s3.get(field)
            # Normalize: both as JSON string for comparison
            if isinstance(s2f, str):
                s2v = s2f
            elif s2f is None:
                s2v = ""
            else:
                s2v = json.dumps(s2f, sort_keys=True)
            if isinstance(s3f, str):
                s3v = s3f
            elif s3f is None:
                s3v = ""
            else:
                s3v = json.dumps(s3f, sort_keys=True)
            if s2v != s3v:
                drifts.append({"child": name, "field": field, "stage2": str(s2v)[:100], "stage3": str(s3v)[:100]})
    return drifts


def normalize_op(op):
    """Normalize operation for comparison: read_write covers read and write."""
    if op == "read_write":
        return {"read", "write"}
    return {op}


def audit_gv_do_sync(children):
    """Check global_vars / data_operations synchronization per child."""
    gaps = []
    for c in children:
        name = c.get("name", "")
        gv_set = {}
        for g in c.get("global_vars", []):
            var = g.get("variable", "")
            op = g.get("op", "")
            gv_set.setdefault(var, set()).update(normalize_op(op))
        do_set = {}
        for d in c.get("data_operations", []):
            src = d.get("source_name", "")
            op = d.get("operation_type", "")
            do_set.setdefault(src, set()).update(normalize_op(op))

        # Check gv has do
        for var, ops in gv_set.items():
            if var not in do_set:
                gaps.append({"child": name, "type": "gv_missing_data_operation", "variable": var})
            elif ops != do_set[var]:
                gaps.append({"child": name, "type": "op_mismatch", "variable": var, "gv_ops": list(ops), "do_ops": list(do_set[var])})

        # Check do has gv
        for src, ops in do_set.items():
            if src not in gv_set:
                gaps.append({"child": name, "type": "data_operation_missing_gv", "variable": src})

    return gaps


def audit_internal_leaf_mapping(stage2_children, stage3_children):
    """Check that Stage3 resources are derived from Stage2 internal_leaf_accesses."""
    s2_map = {c.get("name", ""): c for c in stage2_children}
    s3_map = {c.get("name", ""): c for c in stage3_children}
    coverage = {}
    for name in s2_map:
        s2 = s2_map[name]
        s3 = s3_map.get(name, {})
        leaf_resources = {ila.get("resource", "") for ila in s2.get("internal_leaf_accesses", [])}
        gv_resources = {g.get("variable", "") for g in s3.get("global_vars", [])}
        do_resources = {d.get("source_name", "") for d in s3.get("data_operations", [])}
        all_s3_resources = gv_resources | do_resources
        covered = leaf_resources & all_s3_resources
        uncovered = leaf_resources - all_s3_resources
        coverage[name] = {
            "leaf_resources": list(leaf_resources),
            "stage3_resources": list(all_s3_resources),
            "covered": list(covered),
            "uncovered": list(uncovered),
            "coverage_rate": len(covered) / len(leaf_resources) if leaf_resources else 1.0,
        }
    return coverage


# ========================================================================
# Old-style metrics (kept as diagnostics only)
# ========================================================================

def normalize_signatures(children):
    result = {}
    for c in children:
        name = c.get("name", "")
        sig = c.get("signature", "")
        # Use call_inputs if available, else fall back to inputs
        inputs = c.get("call_inputs", c.get("inputs", []))
        outputs = c.get("outputs", [])
        # Handle inputs that may be dicts or strings
        if inputs and isinstance(inputs[0], dict):
            param_names = tuple(sorted(i.get("name", "") for i in inputs))
            param_types = tuple(sorted(i.get("type", "") for i in inputs))
        else:
            param_names = tuple(sorted(str(i) for i in inputs)) if inputs else ()
            param_types = ()
        if outputs and isinstance(outputs[0], dict):
            ret_types = tuple(sorted(o.get("type", "") for o in outputs))
        else:
            ret_types = ()
        result[name] = (sig, param_names, param_types, ret_types)
    return result


def normalize_dataflow(data):
    edges = data.get("dataflow_edges", [])
    return set((e.get("from_node", ""), e.get("to_node", ""), e.get("to_input", "")) for e in edges)


def normalize_resources(children):
    result = {}
    for c in children:
        name = c.get("name", "")
        gv = tuple(sorted((g.get("variable", ""), g.get("op", "")) for g in c.get("global_vars", [])))
        do = tuple(sorted((d.get("source_name", ""), d.get("operation_type", "")) for d in c.get("data_operations", [])))
        rc = tuple(sorted(c.get("requested_capabilities", [])))
        result[name] = (gv, do, rc)
    return result


# ========================================================================
# Chain runner
# ========================================================================

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def save_raw(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def run_chain_independent(stage1_data, node_info, chain_idx, api_key, base_url, model, chain_dir):
    """Run one chain under independent_context condition."""
    llm = LLMLogger(chain_dir, api_key, base_url, model)
    llm_calls = 0

    # Stage 2
    s2_msgs = [
        {"role": "system", "content": STAGE2_SYSTEM_PROMPT},
        {"role": "assistant", "content": json.dumps(stage1_data, indent=2, ensure_ascii=False)},
        {"role": "user", "content": build_stage2_user_prompt(stage1_data, node_info)},
    ]
    save_json(os.path.join(chain_dir, "stage2_messages.json"), s2_msgs)
    try:
        s2_raw = llm.chat(s2_msgs)
    except Exception as e:
        return {"error": f"Stage2 API failed: {e}", "llm_calls": llm.call_counter}
    llm_calls += llm.call_counter
    save_raw(os.path.join(chain_dir, "stage2_response_raw.txt"), s2_raw)
    s2_parsed = parse_json(s2_raw)
    save_json(os.path.join(chain_dir, "stage2.json"), s2_parsed)

    if not audit_parse_success(s2_parsed):
        return {
            "stage2_parse_failed": True,
            "stage3_parse_failed": True,
            "error": "Stage2 parse failed",
            "llm_calls": llm_calls,
        }

    # Stage 3
    s3_msgs = [
        {"role": "system", "content": STAGE3_SYSTEM_PROMPT},
        {"role": "assistant", "content": json.dumps(s2_parsed, indent=2, ensure_ascii=False)},
        {"role": "user", "content": build_stage3_user_prompt(stage1_data, s2_parsed, node_info)},
    ]
    save_json(os.path.join(chain_dir, "stage3_messages.json"), s3_msgs)
    try:
        s3_raw = llm.chat(s3_msgs)
    except Exception as e:
        return {"error": f"Stage3 API failed: {e}", "stage2_parsed": s2_parsed, "llm_calls": llm_calls}
    llm_calls += llm.call_counter
    save_raw(os.path.join(chain_dir, "stage3_response_raw.txt"), s3_raw)
    s3_parsed = parse_json(s3_raw)
    save_json(os.path.join(chain_dir, "stage3.json"), s3_parsed)

    return {
        "stage2_parsed": s2_parsed,
        "stage3_parsed": s3_parsed,
        "stage2_parse_failed": False,
        "stage3_parse_failed": not audit_parse_success(s3_parsed),
        "llm_calls": llm_calls,
    }


def run_chain_shared(stage1_data, stage1_raw, node_info, chain_idx, api_key, base_url, model, chain_dir):
    """Run one chain under shared_conversation condition."""
    llm = LLMLogger(chain_dir, api_key, base_url, model)
    llm_calls = 0

    # Build initial messages: system + user Stage1 + assistant Stage1 response
    messages = [
        {"role": "system", "content": SHARED_GLOBAL_SYSTEM_PROMPT},
        {"role": "user", "content": build_stage1_user_prompt(node_info)},
        {"role": "assistant", "content": stage1_raw},
    ]

    # Save Stage1 messages
    save_json(os.path.join(chain_dir, "stage1_messages.json"), messages)
    save_raw(os.path.join(chain_dir, "stage1_response_raw.txt"), stage1_raw)
    save_json(os.path.join(chain_dir, "stage1.json"), stage1_data)

    # Stage 2: append user prompt, call API
    s2_user = build_stage2_shared_user_prompt(stage1_data, node_info)
    messages.append({"role": "user", "content": s2_user})
    save_json(os.path.join(chain_dir, "stage2_messages.json"), list(messages))
    try:
        s2_raw = llm.chat(list(messages))
    except Exception as e:
        return {"error": f"Stage2 API failed: {e}", "llm_calls": llm.call_counter}
    llm_calls += llm.call_counter
    save_raw(os.path.join(chain_dir, "stage2_response_raw.txt"), s2_raw)
    s2_parsed = parse_json(s2_raw)
    save_json(os.path.join(chain_dir, "stage2.json"), s2_parsed)

    if not audit_parse_success(s2_parsed):
        return {
            "stage2_parse_failed": True,
            "stage3_parse_failed": True,
            "error": "Stage2 parse failed",
            "llm_calls": llm_calls,
        }

    # Append Stage2 response
    messages.append({"role": "assistant", "content": s2_raw})

    # Stage 3: append user prompt, call API
    s3_user = build_stage3_shared_user_prompt(stage1_data, s2_parsed, node_info)
    messages.append({"role": "user", "content": s3_user})
    save_json(os.path.join(chain_dir, "stage3_messages.json"), list(messages))
    try:
        s3_raw = llm.chat(list(messages))
    except Exception as e:
        return {"error": f"Stage3 API failed: {e}", "stage2_parsed": s2_parsed, "llm_calls": llm_calls}
    llm_calls += llm.call_counter
    save_raw(os.path.join(chain_dir, "stage3_response_raw.txt"), s3_raw)
    s3_parsed = parse_json(s3_raw)
    save_json(os.path.join(chain_dir, "stage3.json"), s3_parsed)

    return {
        "stage2_parsed": s2_parsed,
        "stage3_parsed": s3_parsed,
        "stage2_parse_failed": False,
        "stage3_parse_failed": not audit_parse_success(s3_parsed),
        "llm_calls": llm_calls,
    }


def audit_chain(stage1_children, chain_result, condition):
    """Run all audit checks on a single chain result."""
    s2 = chain_result.get("stage2_parsed")
    s3 = chain_result.get("stage3_parsed")
    s2_pf = chain_result.get("stage2_parse_failed", True)
    s3_pf = chain_result.get("stage3_parse_failed", True)

    audit = {"condition": condition}

    # Parse success
    audit["stage2_parse_success"] = not s2_pf
    audit["stage3_parse_success"] = not s3_pf

    if s2_pf:
        audit["child_identity_drift_stage2"] = "parse_failure"
        audit["semantic_drift_stage2"] = "parse_failure"
        audit["signature_resource_leaks"] = "parse_failure"
        audit["dataflow_schema_violations"] = "parse_failure"
    else:
        s2_children = s2.get("children", [])
        # Child identity
        id_drift = audit_child_identity(stage1_children, s2_children)
        audit["child_identity_drift_stage2"] = id_drift
        # Semantic preservation
        sem_changes = audit_semantic_preservation(stage1_children, s2_children)
        audit["semantic_drift_stage2"] = len(sem_changes)
        audit["semantic_changes_detail_s2"] = sem_changes[:10]
        # Signature resource leak
        leaks = audit_signature_resource_leak(s2_children)
        audit["signature_resource_leaks"] = len(leaks)
        audit["signature_resource_leaks_detail"] = leaks[:10]
        # Dataflow schema
        child_names = [c.get("name", "") for c in stage1_children]
        df_violations = audit_dataflow_schema(s2, child_names)
        audit["dataflow_schema_violations"] = len(df_violations)
        audit["dataflow_schema_violations_detail"] = df_violations[:10]

    if s3_pf:
        audit["child_identity_drift_stage3"] = "parse_failure"
        audit["semantic_drift_stage3"] = "parse_failure"
        audit["stage3_signature_drift"] = "parse_failure"
        audit["gv_do_sync_gaps"] = "parse_failure"
    else:
        s3_children = s3.get("children", [])
        # Child identity
        id_drift3 = audit_child_identity(stage1_children, s3_children)
        audit["child_identity_drift_stage3"] = id_drift3
        # Semantic preservation
        sem_changes3 = audit_semantic_preservation(stage1_children, s3_children)
        audit["semantic_drift_stage3"] = len(sem_changes3)
        audit["semantic_changes_detail_s3"] = sem_changes3[:10]
        # Stage3 signature drift (vs Stage2)
        if not s2_pf and s2:
            drifts = audit_stage3_signature_drift(s2.get("children", []), s3_children)
            audit["stage3_signature_drift"] = len(drifts)
            audit["stage3_signature_drift_detail"] = drifts[:10]
            # Internal leaf mapping
            leaf_cov = audit_internal_leaf_mapping(s2.get("children", []), s3_children)
            audit["internal_leaf_mapping_coverage"] = leaf_cov
        else:
            audit["stage3_signature_drift"] = "no_stage2_reference"
        # GV/DO sync
        gv_gaps = audit_gv_do_sync(s3_children)
        audit["gv_do_sync_gaps"] = len(gv_gaps)
        audit["gv_do_sync_gaps_detail"] = gv_gaps[:10]

    # Old-style diagnostic metrics
    if not s2_pf and s2:
        s2_children = s2.get("children", [])
        sigs = normalize_signatures(s2_children)
        audit["diagnostic_signatures"] = {k: v[0] for k, v in sigs.items()}
    if not s3_pf and s3:
        s3_children = s3.get("children", [])
        res = normalize_resources(s3_children)
        audit["diagnostic_resources"] = {k: {"gv": list(v[0]), "do": list(v[1])} for k, v in res.items()}

    return audit


# ========================================================================
# Sample runner
# ========================================================================

def generate_stage1(node_info, api_key, base_url, model, sample_idx, log_dir):
    """Generate a single Stage 1 decomposition."""
    llm = LLMLogger(log_dir, api_key, base_url, model)
    msgs = [
        {"role": "system", "content": STAGE1_SYSTEM_PROMPT},
        {"role": "user", "content": build_stage1_user_prompt(node_info)},
    ]
    try:
        raw = llm.chat(msgs)
    except Exception as e:
        return None, None, f"Stage1 API failed: {e}", llm.call_counter

    parsed = parse_json(raw)
    if not audit_parse_success(parsed):
        return None, None, f"Stage1 parse failed: {parsed.get('error')}", llm.call_counter

    with open(os.path.join(log_dir, "stage1.json"), "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False, default=str)
    with open(os.path.join(log_dir, "stage1_response_raw.txt"), "w", encoding="utf-8") as f:
        f.write(raw)

    return parsed, raw, None, llm.call_counter


def run_sample(domain_name, node_info, sample_idx, n_reps, api_key, base_url, model):
    """Run one sample: Stage1 + n_reps chains x 2 conditions."""
    label = f"{domain_name}/sample_{sample_idx:02d}"
    base_dir = os.path.join(OUTPUT_DIR, model, domain_name, f"sample_{sample_idx:02d}")
    os.makedirs(base_dir, exist_ok=True)
    t0 = time.time()
    total_llm = 0

    # Generate Stage 1 (shared between conditions)
    stage1_data, stage1_raw, err, calls = generate_stage1(
        node_info, api_key, base_url, model, sample_idx, base_dir
    )
    total_llm += calls
    if err:
        return {
            "label": label, "domain": domain_name, "sample": sample_idx,
            "error": err, "elapsed": round(time.time() - t0, 1), "llm_calls": total_llm,
        }

    stage1_children = stage1_data.get("children", [])
    if len(stage1_children) < 2:
        return {
            "label": label, "domain": domain_name, "sample": sample_idx,
            "error": f"Stage1 returned {len(stage1_children)} children, need >= 2",
            "elapsed": round(time.time() - t0, 1), "llm_calls": total_llm,
        }

    # Run chains for both conditions
    results_a = []  # independent_context
    results_b = []  # shared_conversation

    for chain_idx in range(n_reps):
        chain_label = f"chain_{chain_idx:02d}"

        # Condition A: independent_context
        chain_dir_a = os.path.join(base_dir, "independent_context", chain_label)
        os.makedirs(chain_dir_a, exist_ok=True)
        result_a = run_chain_independent(
            stage1_data, node_info, chain_idx, api_key, base_url, model, chain_dir_a
        )
        total_llm += result_a.get("llm_calls", 0)
        audit_a = audit_chain(stage1_children, result_a, "independent_context")
        save_json(os.path.join(chain_dir_a, "audit.json"), audit_a)
        results_a.append({"chain": chain_idx, "result": result_a, "audit": audit_a})

        # Condition B: shared_conversation
        chain_dir_b = os.path.join(base_dir, "shared_conversation", chain_label)
        os.makedirs(chain_dir_b, exist_ok=True)
        result_b = run_chain_shared(
            stage1_data, stage1_raw, node_info, chain_idx, api_key, base_url, model, chain_dir_b
        )
        total_llm += result_b.get("llm_calls", 0)
        audit_b = audit_chain(stage1_children, result_b, "shared_conversation")
        save_json(os.path.join(chain_dir_b, "audit.json"), audit_b)
        results_b.append({"chain": chain_idx, "result": result_b, "audit": audit_b})

    elapsed = round(time.time() - t0, 1)

    # Aggregate per-sample metrics
    def aggregate_metrics(chains, condition):
        metrics = {
            "condition": condition,
            "n_chains": len(chains),
            "stage2_parse_failures": sum(1 for c in chains if c["result"].get("stage2_parse_failed", True)),
            "stage3_parse_failures": sum(1 for c in chains if c["result"].get("stage3_parse_failed", True)),
            "child_identity_drift_stage2": 0,
            "child_identity_drift_stage3": 0,
            "semantic_drift_stage2": 0,
            "semantic_drift_stage3": 0,
            "signature_resource_leak_total": 0,
            "dataflow_schema_violation_total": 0,
            "stage3_signature_drift_total": 0,
            "gv_do_sync_gap_total": 0,
        }
        for c in chains:
            a = c["audit"]
            # Identity drift
            id2 = a.get("child_identity_drift_stage2", {})
            if isinstance(id2, dict) and id2.get("drifted"):
                metrics["child_identity_drift_stage2"] += 1
            id3 = a.get("child_identity_drift_stage3", {})
            if isinstance(id3, dict) and id3.get("drifted"):
                metrics["child_identity_drift_stage3"] += 1
            # Semantic drift
            sd2 = a.get("semantic_drift_stage2", 0)
            if isinstance(sd2, int):
                metrics["semantic_drift_stage2"] += sd2
            sd3 = a.get("semantic_drift_stage3", 0)
            if isinstance(sd3, int):
                metrics["semantic_drift_stage3"] += sd3
            # Signature resource leaks
            srl = a.get("signature_resource_leaks", 0)
            if isinstance(srl, int):
                metrics["signature_resource_leak_total"] += srl
            # Dataflow schema violations
            dsv = a.get("dataflow_schema_violations", 0)
            if isinstance(dsv, int):
                metrics["dataflow_schema_violation_total"] += dsv
            # Stage3 signature drift
            s3d = a.get("stage3_signature_drift", 0)
            if isinstance(s3d, int):
                metrics["stage3_signature_drift_total"] += s3d
            # GV/DO sync gaps
            gvg = a.get("gv_do_sync_gaps", 0)
            if isinstance(gvg, int):
                metrics["gv_do_sync_gap_total"] += gvg
        return metrics

    metrics_a = aggregate_metrics(results_a, "independent_context")
    metrics_b = aggregate_metrics(results_b, "shared_conversation")

    # Old-style diagnostic stability metrics (for comparison)
    def compute_stability(chains):
        valid_s2 = [c["result"]["stage2_parsed"] for c in chains if c["result"].get("stage2_parsed") and not c["result"].get("stage2_parse_failed")]
        valid_s3 = [c["result"]["stage3_parsed"] for c in chains if c["result"].get("stage3_parsed") and not c["result"].get("stage3_parse_failed")]

        sig_stab = 1.0
        if len(valid_s2) >= 2:
            sigs_list = [normalize_signatures(s.get("children", [])) for s in valid_s2]
            ref = sigs_list[0]
            matches = 0
            comps = 0
            for name in ref:
                for other in sigs_list[1:]:
                    comps += 1
                    if name in other and ref[name] == other[name]:
                        matches += 1
            sig_stab = matches / comps if comps else 1.0

        df_stab = 1.0
        if len(valid_s2) >= 2:
            dfs = [normalize_dataflow(s) for s in valid_s2]
            ref_df = dfs[0]
            m = sum(1 for df in dfs[1:] if df == ref_df)
            df_stab = m / (len(dfs) - 1) if len(dfs) > 1 else 1.0

        res_stab = 1.0
        if len(valid_s3) >= 2:
            ress = [normalize_resources(s.get("children", [])) for s in valid_s3]
            ref_r = ress[0]
            m = sum(1 for r in ress[1:] if r == ref_r)
            res_stab = m / (len(ress) - 1) if len(ress) > 1 else 1.0

        return round(sig_stab, 4), round(df_stab, 4), round(res_stab, 4)

    sig_a, df_a, res_a = compute_stability(results_a)
    sig_b, df_b, res_b = compute_stability(results_b)

    metrics_a["diagnostic_signature_stability"] = sig_a
    metrics_a["diagnostic_dataflow_stability"] = df_a
    metrics_a["diagnostic_resource_stability"] = res_a
    metrics_b["diagnostic_signature_stability"] = sig_b
    metrics_b["diagnostic_dataflow_stability"] = df_b
    metrics_b["diagnostic_resource_stability"] = res_b

    sample_result = {
        "label": label,
        "domain": domain_name,
        "sample": sample_idx,
        "n_stage1_children": len(stage1_children),
        "stage1_child_names": [c.get("name", "") for c in stage1_children],
        "independent_context": metrics_a,
        "shared_conversation": metrics_b,
        "elapsed": elapsed,
        "llm_calls": total_llm,
    }

    save_json(os.path.join(base_dir, "result.json"), sample_result)
    return sample_result


# ========================================================================
# Report generation
# ========================================================================

def generate_report(all_results, model, n_samples, n_reps):
    lines = [
        "# Exp02b: Shared Conversation Memory vs Independent Context",
        "",
        f"Model: `{model}`",
        f"Samples per domain: {n_samples}",
        f"Repetitions per sample (chains): {n_reps}",
        f"Total samples: {len(all_results)}",
        "",
        "## Purpose",
        "",
        "Test whether keeping Stage 1, Stage 2, and Stage 3 inside the same message",
        "history (shared_conversation) improves stage identity continuity and",
        "interface-category discipline compared to separate API calls (independent_context).",
        "",
        "## Hypothesis",
        "",
        "Shared conversation memory may reduce identity drift, parse failures,",
        "internal leaf resource leakage into call signatures, invalid dataflow",
        "endpoints, and Stage3 resource-field inconsistency.",
        "",
        "## Prompt Delta",
        "",
        "- **independent_context**: Uses separate system prompts per stage (STAGE2_SYSTEM_PROMPT, STAGE3_SYSTEM_PROMPT).",
        "  Stage1 JSON injected as assistant message before Stage2 user prompt.",
        "  Stage2 JSON injected as assistant message before Stage3 user prompt.",
        "- **shared_conversation**: Uses one SHARED_GLOBAL_SYSTEM_PROMPT for the entire conversation.",
        "  Stage1 user prompt + assistant response + Stage2 user prompt + assistant response + Stage3 user prompt.",
        "  No multiple system prompts in the same history.",
        "",
        "- **Stage 2 prompt changes**: Separates `call_inputs` (parent-call parameters) from",
        "  `internal_leaf_accesses` (child-internal resource access). Adds `interface_audit`",
        "  with detail-first schema (audit reasoning before `final_status`).",
        "- **Stage 3 prompt changes**: Uses `internal_leaf_accesses` as primary source for",
        "  `global_vars`/`data_operations`. Adds `resource_audit` with detail-first schema.",
        "",
    ]

    # Aggregate by domain
    by_domain = defaultdict(list)
    for r in all_results:
        by_domain[r["domain"]].append(r)

    domain_order = ["Order", "Chat", "Patient", "BuildSystem", "DataPipeline"]

    # --- Primary metrics comparison table ---
    lines.append("## Primary Metrics Comparison\n")
    lines.append("| Metric | independent_context | shared_conversation | Delta |")
    lines.append("|--------|:-------------------:|:-------------------:|:-----:|")

    def sum_metric(results, condition, key):
        return sum(r.get(condition, {}).get(key, 0) for r in results)

    total = len(all_results)
    total_chains_a = sum(r.get("independent_context", {}).get("n_chains", 0) for r in all_results)
    total_chains_b = sum(r.get("shared_conversation", {}).get("n_chains", 0) for r in all_results)

    metrics_to_compare = [
        ("Stage2 parse failures", "stage2_parse_failures"),
        ("Stage3 parse failures", "stage3_parse_failures"),
        ("Child identity drift (S2)", "child_identity_drift_stage2"),
        ("Child identity drift (S3)", "child_identity_drift_stage3"),
        ("Semantic drift (S2)", "semantic_drift_stage2"),
        ("Semantic drift (S3)", "semantic_drift_stage3"),
        ("Signature resource leaks", "signature_resource_leak_total"),
        ("Dataflow schema violations", "dataflow_schema_violation_total"),
        ("Stage3 signature drift", "stage3_signature_drift_total"),
        ("GV/DO sync gaps", "gv_do_sync_gap_total"),
    ]

    for label, key in metrics_to_compare:
        va = sum_metric(all_results, "independent_context", key)
        vb = sum_metric(all_results, "shared_conversation", key)
        delta = vb - va
        sign = "+" if delta > 0 else ""
        lines.append(f"| {label} | {va} | {vb} | {sign}{delta} |")

    # Diagnostic stability
    lines.append("")
    lines.append("## Diagnostic Stability (old-style, cross-chain comparison)\n")
    lines.append("| Domain | Sig Stability (A) | Sig Stability (B) | DF Stability (A) | DF Stability (B) | Res Stability (A) | Res Stability (B) |")
    lines.append("|--------|:-----------------:|:-----------------:|:----------------:|:----------------:|:-----------------:|:-----------------:|")

    for dname in domain_order:
        results = by_domain.get(dname, [])
        if not results:
            continue
        n = len(results)
        avg = lambda cond, key: sum(r.get(cond, {}).get(key, 0) for r in results) / n
        sa = avg("independent_context", "diagnostic_signature_stability")
        sb = avg("shared_conversation", "diagnostic_signature_stability")
        da = avg("independent_context", "diagnostic_dataflow_stability")
        db = avg("shared_conversation", "diagnostic_dataflow_stability")
        ra = avg("independent_context", "diagnostic_resource_stability")
        rb = avg("shared_conversation", "diagnostic_resource_stability")
        lines.append(f"| {dname} | {sa*100:.1f}% | {sb*100:.1f}% | {da*100:.1f}% | {db*100:.1f}% | {ra*100:.1f}% | {rb*100:.1f}% |")

    # Totals
    n = len(all_results)
    avg_all = lambda cond, key: sum(r.get(cond, {}).get(key, 0) for r in all_results) / n if n else 0
    t_sa = avg_all("independent_context", "diagnostic_signature_stability")
    t_sb = avg_all("shared_conversation", "diagnostic_signature_stability")
    t_da = avg_all("independent_context", "diagnostic_dataflow_stability")
    t_db = avg_all("shared_conversation", "diagnostic_dataflow_stability")
    t_ra = avg_all("independent_context", "diagnostic_resource_stability")
    t_rb = avg_all("shared_conversation", "diagnostic_resource_stability")
    lines.append(f"| **TOTAL** | **{t_sa*100:.1f}%** | **{t_sb*100:.1f}%** | **{t_da*100:.1f}%** | **{t_db*100:.1f}%** | **{t_ra*100:.1f}%** | **{t_rb*100:.1f}%** |")
    lines.append("")

    # --- Per-domain primary metrics ---
    lines.append("## Per-Domain Primary Metrics\n")
    lines.append("| Domain | Samples | S2 Parse Fail (A/B) | S3 Parse Fail (A/B) | Identity Drift S2 (A/B) | Sig Leak (A/B) | DF Violation (A/B) | S3 Sig Drift (A/B) | GV/DO Gap (A/B) |")
    lines.append("|--------|:-------:|:-------------------:|:-------------------:|:-----------------------:|:--------------:|:------------------:|:------------------:|:---------------:|")

    for dname in domain_order:
        results = by_domain.get(dname, [])
        if not results:
            continue
        n_d = len(results)
        s2f_a = sum(r["independent_context"]["stage2_parse_failures"] for r in results)
        s2f_b = sum(r["shared_conversation"]["stage2_parse_failures"] for r in results)
        s3f_a = sum(r["independent_context"]["stage3_parse_failures"] for r in results)
        s3f_b = sum(r["shared_conversation"]["stage3_parse_failures"] for r in results)
        id_a = sum(r["independent_context"]["child_identity_drift_stage2"] for r in results)
        id_b = sum(r["shared_conversation"]["child_identity_drift_stage2"] for r in results)
        sl_a = sum(r["independent_context"]["signature_resource_leak_total"] for r in results)
        sl_b = sum(r["shared_conversation"]["signature_resource_leak_total"] for r in results)
        dv_a = sum(r["independent_context"]["dataflow_schema_violation_total"] for r in results)
        dv_b = sum(r["shared_conversation"]["dataflow_schema_violation_total"] for r in results)
        sd_a = sum(r["independent_context"]["stage3_signature_drift_total"] for r in results)
        sd_b = sum(r["shared_conversation"]["stage3_signature_drift_total"] for r in results)
        gv_a = sum(r["independent_context"]["gv_do_sync_gap_total"] for r in results)
        gv_b = sum(r["shared_conversation"]["gv_do_sync_gap_total"] for r in results)
        lines.append(f"| {dname} | {n_d} | {s2f_a}/{s2f_b} | {s3f_a}/{s3f_b} | {id_a}/{id_b} | {sl_a}/{sl_b} | {dv_a}/{dv_b} | {sd_a}/{sd_b} | {gv_a}/{gv_b} |")

    lines.append("")

    # --- Cases where shared conversation improved ---
    lines.append("## Cases Where Shared Conversation Improved\n")
    improved = []
    for r in all_results:
        a = r.get("independent_context", {})
        b = r.get("shared_conversation", {})
        improvements = []
        # Check each metric
        for key in ("stage2_parse_failures", "stage3_parse_failures", "child_identity_drift_stage2",
                     "child_identity_drift_stage3", "semantic_drift_stage2", "semantic_drift_stage3",
                     "signature_resource_leak_total", "dataflow_schema_violation_total",
                     "stage3_signature_drift_total", "gv_do_sync_gap_total"):
            va = a.get(key, 0)
            vb = b.get(key, 0)
            if vb < va:
                improvements.append(f"{key}: {va} -> {vb}")
        if improvements:
            improved.append((r["label"], improvements))

    if improved:
        for label, imps in improved:
            lines.append(f"### {label}")
            for imp in imps:
                lines.append(f"- {imp}")
            lines.append("")
    else:
        lines.append("No cases where shared conversation strictly improved primary metrics.\n")

    # --- Cases where shared conversation regressed ---
    lines.append("## Cases Where Shared Conversation Regressed\n")
    regressed = []
    for r in all_results:
        a = r.get("independent_context", {})
        b = r.get("shared_conversation", {})
        regressions = []
        for key in ("stage2_parse_failures", "stage3_parse_failures", "child_identity_drift_stage2",
                     "child_identity_drift_stage3", "semantic_drift_stage2", "semantic_drift_stage3",
                     "signature_resource_leak_total", "dataflow_schema_violation_total",
                     "stage3_signature_drift_total", "gv_do_sync_gap_total"):
            va = a.get(key, 0)
            vb = b.get(key, 0)
            if vb > va:
                regressions.append(f"{key}: {va} -> {vb}")
        if regressions:
            regressed.append((r["label"], regressions))

    if regressed:
        for label, regs in regressed:
            lines.append(f"### {label}")
            for reg in regs:
                lines.append(f"- {reg}")
            lines.append("")
    else:
        lines.append("No cases where shared conversation regressed on primary metrics.\n")

    # --- Manual audit notes ---
    lines.append("## Manual Audit Notes\n")
    lines.append("### Order")
    lines.append("")
    order_results = by_domain.get("Order", [])
    if order_results:
        r0 = order_results[0]
        for cond in ("independent_context", "shared_conversation"):
            m = r0.get(cond, {})
            lines.append(f"**{cond}**: S2 parse fail={m.get('stage2_parse_failures',0)}, "
                         f"sig_leak={m.get('signature_resource_leak_total',0)}, "
                         f"df_violation={m.get('dataflow_schema_violation_total',0)}, "
                         f"s3_drift={m.get('stage3_signature_drift_total',0)}")
        lines.append("")
    else:
        lines.append("No Order samples.\n")

    lines.append("### Chat")
    lines.append("")
    chat_results = by_domain.get("Chat", [])
    if chat_results:
        r0 = chat_results[0]
        for cond in ("independent_context", "shared_conversation"):
            m = r0.get(cond, {})
            lines.append(f"**{cond}**: S2 parse fail={m.get('stage2_parse_failures',0)}, "
                         f"sig_leak={m.get('signature_resource_leak_total',0)}, "
                         f"df_violation={m.get('dataflow_schema_violation_total',0)}, "
                         f"s3_drift={m.get('stage3_signature_drift_total',0)}")
        lines.append("")
    else:
        lines.append("No Chat samples.\n")

    lines.append("### DataPipeline")
    lines.append("")
    dp_results = by_domain.get("DataPipeline", [])
    if dp_results:
        r0 = dp_results[0]
        for cond in ("independent_context", "shared_conversation"):
            m = r0.get(cond, {})
            lines.append(f"**{cond}**: S2 parse fail={m.get('stage2_parse_failures',0)}, "
                         f"sig_leak={m.get('signature_resource_leak_total',0)}, "
                         f"df_violation={m.get('dataflow_schema_violation_total',0)}, "
                         f"s3_drift={m.get('stage3_signature_drift_total',0)}")
        lines.append("")
    else:
        lines.append("No DataPipeline samples.\n")

    lines.append("### Patient/sample_01 parse behavior")
    lines.append("")
    pat_results = by_domain.get("Patient", [])
    if len(pat_results) >= 2:
        r1 = pat_results[1]
        for cond in ("independent_context", "shared_conversation"):
            m = r1.get(cond, {})
            lines.append(f"**{cond}**: S2 parse fail={m.get('stage2_parse_failures',0)}, "
                         f"S3 parse fail={m.get('stage3_parse_failures',0)}, "
                         f"identity_drift_s2={m.get('child_identity_drift_stage2',0)}")
        lines.append("")
    else:
        lines.append("No Patient/sample_01.\n")

    # --- Verdict ---
    lines.append("## Verdict\n")
    total_s2f_a = sum_metric(all_results, "independent_context", "stage2_parse_failures")
    total_s2f_b = sum_metric(all_results, "shared_conversation", "stage2_parse_failures")
    total_s3f_a = sum_metric(all_results, "independent_context", "stage3_parse_failures")
    total_s3f_b = sum_metric(all_results, "shared_conversation", "stage3_parse_failures")
    total_id_a = sum_metric(all_results, "independent_context", "child_identity_drift_stage2") + sum_metric(all_results, "independent_context", "child_identity_drift_stage3")
    total_id_b = sum_metric(all_results, "shared_conversation", "child_identity_drift_stage2") + sum_metric(all_results, "shared_conversation", "child_identity_drift_stage3")
    total_sl_a = sum_metric(all_results, "independent_context", "signature_resource_leak_total")
    total_sl_b = sum_metric(all_results, "shared_conversation", "signature_resource_leak_total")
    total_dv_a = sum_metric(all_results, "independent_context", "dataflow_schema_violation_total")
    total_dv_b = sum_metric(all_results, "shared_conversation", "dataflow_schema_violation_total")
    total_sd_a = sum_metric(all_results, "independent_context", "stage3_signature_drift_total")
    total_sd_b = sum_metric(all_results, "shared_conversation", "stage3_signature_drift_total")
    total_gv_a = sum_metric(all_results, "independent_context", "gv_do_sync_gap_total")
    total_gv_b = sum_metric(all_results, "shared_conversation", "gv_do_sync_gap_total")

    lines.append(f"| Metric | independent_context | shared_conversation |")
    lines.append(f"|--------|:-------------------:|:-------------------:|")
    lines.append(f"| Stage2 parse failures | {total_s2f_a} | {total_s2f_b} |")
    lines.append(f"| Stage3 parse failures | {total_s3f_a} | {total_s3f_b} |")
    lines.append(f"| Child identity drift (total) | {total_id_a} | {total_id_b} |")
    lines.append(f"| Signature resource leaks | {total_sl_a} | {total_sl_b} |")
    lines.append(f"| Dataflow schema violations | {total_dv_a} | {total_dv_b} |")
    lines.append(f"| Stage3 signature drift | {total_sd_a} | {total_sd_b} |")
    lines.append(f"| GV/DO sync gaps | {total_gv_a} | {total_gv_b} |")
    lines.append("")

    # Determine verdict
    # Check if shared conversation improves on key metrics without regression
    key_metrics = ("stage2_parse_failures", "stage3_parse_failures", "child_identity_drift_stage2",
                   "child_identity_drift_stage3", "signature_resource_leak_total",
                   "dataflow_schema_violation_total", "stage3_signature_drift_total")

    improved_count = 0
    regressed_count = 0
    for key in key_metrics:
        va = sum_metric(all_results, "independent_context", key)
        vb = sum_metric(all_results, "shared_conversation", key)
        if vb < va:
            improved_count += 1
        elif vb > va:
            regressed_count += 1

    if total_s2f_b > total_s2f_a or total_s3f_b > total_s3f_a:
        verdict = "SHARED_CONTEXT_REGRESSION"
    elif improved_count > 0 and regressed_count == 0:
        verdict = "SHARED_CONTEXT_IMPROVES_INTERFACE_DISCIPLINE"
    elif improved_count == 0 and regressed_count == 0:
        verdict = "NO_CLEAR_IMPROVEMENT"
    elif regressed_count > 0 and improved_count > 0:
        verdict = "NO_CLEAR_IMPROVEMENT"
    else:
        verdict = "INCONCLUSIVE_PARSE_OR_INFRA_FAILURE"

    lines.append(f"**Verdict: {verdict}**")
    lines.append("")
    lines.append("### Verdict Boundary")
    lines.append("")
    lines.append("This experiment can only support or reject the narrower hypothesis:")
    lines.append("> shared conversation memory improves Stage2/3 continuity and interface-category discipline")
    lines.append("")
    lines.append("It does NOT establish migration readiness. Migration requires additional validation")
    lines.append("including real codegen integration and production-domain testing.")
    lines.append("")

    return "\n".join(lines)


# ========================================================================
# Main
# ========================================================================

def main():
    parser = argparse.ArgumentParser(description="Exp02b: Shared Conversation Memory vs Independent Context")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--samples", type=int, default=2, help="Samples per domain")
    parser.add_argument("--repetitions", type=int, default=5, help="Chains per sample (both conditions)")
    parser.add_argument("--domains", type=str, default="Order,Chat,Patient,BuildSystem,DataPipeline")
    parser.add_argument("--base_url", type=str, default=None)
    parser.add_argument("--api_key", type=str, default=None)
    parser.add_argument("--skip_existing", action="store_true", help="Skip samples that already have result.json")
    args = parser.parse_args()

    model = args.model or _env("CHRONOS_MODEL", "deepseek-v4-flash")
    if model in {"mimo-v2.5", "mimo-v2-flash", "mimo-v2.5-pro", "mimo-v2-pro", "mimo-v2-omni"}:
        base_url = args.base_url or os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
        api_key = args.api_key or os.getenv("MIMO_API_KEY") or _env("CHRONOS_API_KEY")
    else:
        base_url = args.base_url or _env("CHRONOS_BASE_URL", "https://api.deepseek.com")
        api_key = args.api_key or _env("CHRONOS_API_KEY")

    if not api_key:
        print("ERROR: Set CHRONOS_API_KEY")
        return 1

    requested = [d.strip() for d in args.domains.split(",")]
    domains = [(d, DOMAINS[d]) for d in requested if d in DOMAINS]
    if not domains:
        print(f"ERROR: No valid domains. Available: {list(DOMAINS.keys())}")
        return 1

    print(f"Model: {model}")
    print(f"Domains: {[d[0] for d in domains]}")
    print(f"Samples per domain: {args.samples}")
    print(f"Chains per sample: {args.repetitions}")
    print(f"Conditions: independent_context, shared_conversation")
    print(f"Output: {OUTPUT_DIR}/{model}/")
    print()

    # Build task list, optionally skipping existing
    tasks = []
    all_results = []
    for dname, dnode in domains:
        for s in range(args.samples):
            if args.skip_existing:
                result_path = os.path.join(OUTPUT_DIR, model, dname, f"sample_{s:02d}", "result.json")
                if os.path.exists(result_path):
                    with open(result_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                    all_results.append(existing)
                    print(f"  [{dname}/sample_{s:02d}] SKIP (result.json exists)")
                    continue
            tasks.append((dname, dnode, s, args.repetitions, api_key, base_url, model))

    if not tasks:
        print("All samples already completed. Regenerating report from existing results.")
    else:
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
                    a = r.get("independent_context", {})
                    b = r.get("shared_conversation", {})
                    print(f"  [{r['label']}] children={r.get('n_stage1_children',0)}, "
                          f"sig_leak A={a.get('signature_resource_leak_total',0)} B={b.get('signature_resource_leak_total',0)}, "
                          f"df_viol A={a.get('dataflow_schema_violation_total',0)} B={b.get('dataflow_schema_violation_total',0)}, "
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
    total_sl_a = sum(r.get("independent_context", {}).get("signature_resource_leak_total", 0) for r in all_results)
    total_sl_b = sum(r.get("shared_conversation", {}).get("signature_resource_leak_total", 0) for r in all_results)
    total_dv_a = sum(r.get("independent_context", {}).get("dataflow_schema_violation_total", 0) for r in all_results)
    total_dv_b = sum(r.get("shared_conversation", {}).get("dataflow_schema_violation_total", 0) for r in all_results)
    total_calls = sum(r.get("llm_calls", 0) for r in all_results)
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Total samples: {n}")
    print(f"  Sig resource leaks: A={total_sl_a} B={total_sl_b}")
    print(f"  DF schema violations: A={total_dv_a} B={total_dv_b}")
    print(f"  Total LLM calls: {total_calls}")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
