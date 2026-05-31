"""
Experiment 3: Shallow Pipeline Regression

Compares three decomposition conditions on real pipeline errors:
  - single_stage_baseline: current mvp-0.4.4 decomposer prompt
  - single_stage_notraditional: + no-traditional-pattern principle
  - three_stage: Stage 1 + Stage 2 + Stage 3 merged

Only root-level decomposition/composition, not full recursive tree building.

Output: output/multistage_exp03_pipeline_regression/{model}/
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

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "multistage_exp03_pipeline_regression_conservation_prompt")

# Import pipeline models and decomposer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mvp", "mvp-0.4.4"))
from models import (
    Node, InputParam, OutputParam, Boundary, GlobalVar, DataSource,
    SubPRD, AcceptanceCriterion, ChildContract, DataOperation,
)
from decomposer import Decomposer
from config import Config as PipelineConfig

# Import decomposer_cases for case definitions
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "test_data"))
from decomposer_cases import get_cases, ALL_CASES

# ========================================================================
# Condition prompts
# ========================================================================

NOTRADITIONAL_ADDITION = """

DO NOT ASSUME TRADITIONAL DEVELOPMENT PATTERNS:
- DO NOT create a "dispatcher", "router", "controller", "command_handler", or similar node that delegates work to other children.
- DO NOT use the Command Pattern, Strategy Pattern, or any design pattern where one child calls other children.
- DO NOT create a "coordinator" node whose primary purpose is to figure out which other child to call.
- Each child MUST be a self-contained function that does actual work.
- The parent IS the router. If different inputs need different processing, the parent decides through conditional logic which child to call.
- The purpose of decomposition is to divide work, not to recreate enterprise architecture patterns."""


STAGE1_SYSTEM_PROMPT = """You are a software system decomposition agent. Your task is to decompose a function block into smaller child function blocks.

CRITICAL RULES:
1. EVERY CHILD MUST BE A FUNCTION, NOT A CLASS.
2. TREE STRUCTURE (not graph): Children MUST NOT call each other. The parent MUST directly invoke all children.
3. Do NOT add extra external inputs or outputs beyond what the parent has.
4. Children should be at the same abstraction level and minimally overlapping.

DO NOT ASSUME TRADITIONAL DEVELOPMENT PATTERNS:
- DO NOT create "dispatcher", "router", "controller", "command_handler" nodes.
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
3. Do not use handler/router/dispatcher/controller patterns.
4. Do NOT emit inputs, outputs, signature, global_vars, data_operations, requested_capabilities."""


STAGE2_SYSTEM_PROMPT = """You are an interface derivation agent. Given a frozen Stage 1 decomposition, derive precise typed interfaces for each child.

RULES:
1. Do NOT add, delete, rename, or reorder children.
2. Do NOT change any Stage 1 field (purpose, behavior, boundary, preconditions, postconditions, guarantees, composition_role).
3. Derive ONLY: inputs, outputs, signature for each child.
4. Use precise Python types.
5. Every child input must have an explicit source.

OUTPUT FORMAT — Return valid JSON:
{
  "children": [
    {
      "name": "ChildName (UNCHANGED)",
      "purpose": "(UNCHANGED)",
      "behavior": "(UNCHANGED)",
      "boundary": {"in_scope": ["(UNCHANGED)"], "out_of_scope": ["(UNCHANGED)"]},
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
  "interface_preservation": {"parent_inputs_covered_by": {}, "parent_outputs_produced_by": {}},
  "dataflow_edges": [{"from_node": "parent|ChildName", "from_output": "", "to_node": "ChildName|parent", "to_input": "", "note": ""}]
}"""


STAGE3_SYSTEM_PROMPT = """You are a governance and resource derivation agent. Given frozen Stage 1 + Stage 2, derive resource allocation and governance fields.

RULES:
1. Do NOT change Stage 1 semantics or Stage 2 signatures.
2. Do NOT add, delete, rename, or reorder children.
3. Derive ONLY: global_vars, data_operations, requested_capabilities, constraints, acceptance_criteria, traceability, node_type.
4. Each child's global_vars MUST be a subset of the parent's global_vars.

GLOBAL STATE CONSERVATION — HARD REQUIREMENT:
The parent's global_vars are an architectural contract. You MUST distribute them to children.
For every parent global var, the union of all child global_vars MUST cover the parent's required operation.
If parent requires read_write on X, children must collectively cover both read and write on X.
It is valid to assign read and write to different children, but neither side may disappear.
Do not only infer local child needs; first satisfy the parent conservation ledger, then assign operations to responsible children.
A child global_vars variable must come from parent global_vars — do not invent new variables.
data_operations should be consistent with global_vars.
requested_capabilities should reflect the same resource operation needs.
Do not silently drop any parent operation.

SELF-CHECK before returning JSON:
- List every parent global var and its required op.
- For each, confirm which child (or children) covers it.
- If any parent op is unassigned, fix it before responding.

OUTPUT FORMAT — Return valid JSON:
{
  "children": [
    {
      "name": "ChildName (UNCHANGED)",
      "purpose": "(UNCHANGED from Stage 1)",
      "behavior": "(UNCHANGED from Stage 1)",
      "inputs": ["(UNCHANGED from Stage 2)"],
      "outputs": ["(UNCHANGED from Stage 2)"],
      "signature": "(UNCHANGED from Stage 2)",
      "global_vars": [{"variable": "var_name", "op": "read|write|read_write", "description": ""}],
      "data_operations": [{"source_name": "source", "operation_type": "read|write|read_write", "description": ""}],
      "requested_capabilities": ["resource.operation"],
      "constraints": [{"constraint_id": "C-001", "description": ""}],
      "acceptance_criteria": [{"ac_id": "AC-001", "description": ""}],
      "traceability": {"parent_requirement_ids": ["FR-001"]},
      "node_type": "pure_function|atomic_operation",
      "stop_decompose": false,
      "stop_reason": ""
    }
  ],
  "governance_notes": ""
}"""

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


# Routing detection
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
        combined = c.get("purpose", "") + " " + c.get("behavior", "")
        if bool(ROUTER_NAME_PATTERNS.search(name)) or bool(ROUTER_PURPOSE_PATTERNS.search(combined)):
            router_nodes.append(name)
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


# ========================================================================
# Deterministic checks
# ========================================================================

def check_child_count(children, expected_range=(2, 10)):
    n = len(children)
    return n < expected_range[0] or n > expected_range[1]


def check_missing_required_fields(children, condition):
    """Check for required fields based on condition."""
    missing = []
    if condition == "three_stage":
        # Full schema required
        required_per_child = ["name", "purpose", "behavior", "inputs", "outputs", "signature",
                              "global_vars", "data_operations", "constraints", "acceptance_criteria",
                              "traceability", "node_type"]
    else:
        # Single-stage: full pipeline schema
        required_per_child = ["name", "purpose", "inputs", "outputs", "boundary",
                              "preconditions", "postconditions", "behavior", "signature",
                              "data_operations", "constraints", "acceptance_criteria",
                              "global_vars", "traceability", "requested_capabilities"]
    for c in children:
        cname = c.get("name", "?")
        for f in required_per_child:
            if f not in c or c[f] is None:
                missing.append(f"{cname}:{f}")
    return missing


def check_dangling_inputs(children, parent_node):
    """Check if child input sources can be traced."""
    parent_input_names = {i.name for i in parent_node.inputs}
    earlier_outputs = set()
    dangling = []
    for c in children:
        cname = c.get("name", "")
        for inp in c.get("inputs", []):
            source = inp.get("source", "")
            param_name = inp.get("name", "")
            # Valid sources: parent input, earlier child output, constant, leaf capability
            if not source:
                dangling.append(f"{cname}.{param_name}: no source declared")
                continue
            source_lower = source.lower()
            is_valid = False
            # Check parent inputs
            for pname in parent_input_names:
                if pname.lower() in source_lower:
                    is_valid = True; break
            # Check earlier child outputs
            if not is_valid:
                for prev_out in earlier_outputs:
                    if prev_out.lower() in source_lower:
                        is_valid = True; break
            # Check constants/config
            if not is_valid:
                if any(kw in source_lower for kw in ["constant", "config", "default", "internal", "leaf"]):
                    is_valid = True
            if not is_valid:
                dangling.append(f"{cname}.{param_name}: source '{source}' not traceable")
        # Track this child's outputs for later children
        for out in c.get("outputs", []):
            earlier_outputs.add(out.get("name", ""))
    return dangling


def check_global_var_subset(children, parent_globals):
    """Check if each child's global_vars is a subset of parent's."""
    parent_vars = {(g.variable if hasattr(g, 'variable') else g.get("variable", "")) for g in parent_globals}
    violations = []
    for c in children:
        cname = c.get("name", "")
        for gv in c.get("global_vars", []):
            var = gv.get("variable", "") if isinstance(gv, dict) else gv.variable
            if var and var not in parent_vars:
                violations.append(f"{cname}:{var}")
    return violations


def check_global_var_union_gap(children, parent_globals):
    """Check if parent's global var operations are covered by children's union."""
    parent_ops = {}
    for g in parent_globals:
        var = g.variable if hasattr(g, 'variable') else g.get("variable", "")
        op = g.op if hasattr(g, 'op') else g.get("op", "")
        if var:
            parent_ops[var] = op

    child_ops = defaultdict(set)
    for c in children:
        for gv in c.get("global_vars", []):
            var = gv.get("variable", "") if isinstance(gv, dict) else gv.variable
            op = gv.get("op", "") if isinstance(gv, dict) else gv.op
            if var:
                child_ops[var].add(op)

    gaps = []
    for var, needed_op in parent_ops.items():
        if var not in child_ops:
            gaps.append(f"{var}: no child covers {needed_op}")
        # For read_write, both read and write must be covered
        elif needed_op == "read_write":
            has_read = "read" in child_ops[var] or "read_write" in child_ops[var]
            has_write = "write" in child_ops[var] or "read_write" in child_ops[var]
            if not has_read:
                gaps.append(f"{var}: read not covered")
            if not has_write:
                gaps.append(f"{var}: write not covered")
    return gaps


# ========================================================================
# Composition check (simplified - uses LLM)
# ========================================================================

COMPOSE_SYSTEM_PROMPT = """You are a decomposition verifier. Check if a parent function CAN be correctly implemented by composing its child functions.

TREE STRUCTURE RULES:
1. Each child is independent. A child must NOT call, reference, or depend on any sibling.
2. Sibling invisibility: children have no knowledge of each other.
3. Parent is the ONLY node that directly calls its children.
4. Data flow goes through parent — parent takes one child's output and passes it to another.

If any tree structure check fails, return cannot_compose with reason "tree_structure_violation".

Return ONLY valid JSON:
{
  "status": "ok | cannot_compose",
  "decomposition_feedback": {
    "reason": "tree_structure_violation | missing_child_input_source | cannot_satisfy_parent_output | other",
    "offending_child": "ChildName or empty",
    "violations": [{"from_node": "", "to_node": "", "rule": "", "details": ""}],
    "suggested_fix": "",
    "requires_redecomposition": true
  }
}"""


def check_cannot_compose(node, children_data, logger):
    """Use LLM to check if decomposition can be composed."""
    children_desc = []
    for c in children_data:
        sig = c.get("signature", "def {}({}) -> {}".format(
            c.get("name", ""),
            ", ".join(f"{i.get('name', '')}: {i.get('type', 'Any')}" for i in c.get("inputs", [])),
            c.get("outputs", [{}])[0].get("type", "Any") if c.get("outputs") else "Any"
        ))
        children_desc.append(f"  [{c.get('name', '')}] {c.get('purpose', '')}\n    Signature: {sig}\n    Behavior: {c.get('behavior', '')[:200]}")

    user_prompt = f"""Check if this parent can be implemented by composing its children.

Parent: {node.name}
Purpose: {node.purpose}
Inputs: {', '.join(f'{i.name}: {i.type}' for i in node.inputs)}
Outputs: {', '.join(f'{o.name}: {o.type}' for o in node.outputs)}

Children:
{chr(10).join(children_desc)}

Return ONLY the JSON response."""

    try:
        raw = logger.chat([
            {"role": "system", "content": COMPOSE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ], max_tokens=1024)
        parsed = parse_json(raw)
        return parsed
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ========================================================================
# Three-stage decomposition
# ========================================================================

def build_stage1_user_prompt(node):
    """Build user prompt for Stage 1 from a Node object."""
    lines = [
        "Decompose the following function block:", "",
        f"Node Name: {node.name}",
        f"Node Purpose: {node.purpose}", "",
    ]
    if node.subprd and node.subprd.description:
        lines.append(node.subprd.description)
        lines.append("")
    lines.append("Inputs:")
    for inp in node.inputs:
        lines.append(f"  - {inp.name}: {inp.type} - {inp.description}")
    lines.append("Outputs:")
    for out in node.outputs:
        lines.append(f"  - {out.name}: {out.type} - {out.description}")
    lines.append("")
    if node.subprd and node.subprd.constraints:
        lines.append("Constraints:")
        for c in node.subprd.constraints:
            if isinstance(c, dict):
                lines.append(f"  - {c.get('description', c)}")
            else:
                lines.append(f"  - {c}")
        lines.append("")
    if node.data_sources:
        lines.append("Available Data Stores:")
        for ds in node.data_sources:
            lines.append(f"  - {ds.name} ({ds.category}, {ds.access}): {ds.description}")
        lines.append("")
    if node.global_vars:
        lines.append("Global Variables:")
        for gv in node.global_vars:
            lines.append(f"  - {gv.op} on {gv.variable}: {gv.description}")
        lines.append("")
    lines.append("Maximum children allowed: 10")
    lines.append("Maximum depth: 3")
    lines.append("")
    lines.append("Return ONLY the JSON response.")
    return "\n".join(lines)


def build_stage2_user_prompt(stage1_data, node):
    children = stage1_data.get("children", [])
    lines = [
        "Derive interfaces for each child.", "",
        f"Parent: {node.name}",
        f"Purpose: {node.purpose}", "",
        "Inputs:",
    ]
    for inp in node.inputs:
        lines.append(f"  - {inp.name}: {inp.type} - {inp.description}")
    lines.append("Outputs:")
    for out in node.outputs:
        lines.append(f"  - {out.name}: {out.type} - {out.description}")
    lines.append("")
    if node.data_sources:
        lines.append("Available Data Stores:")
        for ds in node.data_sources:
            lines.append(f"  - {ds.name} ({ds.category}, {ds.access})")
        lines.append("")
    lines.append("Children (frozen from Stage 1):")
    for c in children:
        lines.append(f"  {c.get('name', '')}: {c.get('purpose', '')}")
        lines.append(f"    behavior: {c.get('behavior', '')[:200]}")
        lines.append(f"    role: {c.get('composition_role', '')}")
    lines.append("")
    lines.append("Return ONLY the JSON response.")
    return "\n".join(lines)


def build_stage3_user_prompt(stage1_data, stage2_data, node):
    children = stage2_data.get("children", stage1_data.get("children", []))
    lines = [
        "Derive governance and resource fields for each child.", "",
        f"Parent: {node.name}",
        f"Purpose: {node.purpose}", "",
    ]
    if node.data_sources:
        lines.append("Available Data Stores:")
        for ds in node.data_sources:
            lines.append(f"  - {ds.name} ({ds.category}, {ds.access})")
        lines.append("")
    if node.global_vars:
        lines.append("=== PARENT GLOBAL STATE CONSERVATION LEDGER ===")
        lines.append("Every row below MUST be covered by the union of child global_vars.")
        lines.append("Do not drop any row. If a row requires read_write, both read and write must appear.")
        lines.append("")
        lines.append("| Variable | Required Op | Description |")
        lines.append("|----------|-------------|-------------|")
        for gv in node.global_vars:
            lines.append(f"| {gv.variable} | {gv.op} | {gv.description} |")
        lines.append("")
        lines.append("After assigning child global_vars, verify every row above is covered.")
        lines.append("")
    lines.append("Children (frozen from Stage 1 + Stage 2):")
    for c in children:
        lines.append(f"  {c.get('name', '')}: {c.get('purpose', '')}")
        sig = c.get("signature", "")
        if sig:
            lines.append(f"    signature: {sig}")
    lines.append("")
    lines.append("Return ONLY the JSON response.")
    return "\n".join(lines)


def merge_stages(stage1, stage2, stage3):
    """Merge three stages into a single children list compatible with pipeline checks."""
    s1_children = {c.get("name", ""): c for c in stage1.get("children", [])}
    s2_children = {c.get("name", ""): c for c in stage2.get("children", [])}
    s3_children = {c.get("name", ""): c for c in stage3.get("children", [])}

    merged = []
    for name in s1_children:
        m = {}
        # Stage 1 fields
        m.update(s1_children[name])
        # Stage 2 fields (override/add)
        if name in s2_children:
            s2 = s2_children[name]
            for key in ("inputs", "outputs", "signature"):
                if key in s2:
                    m[key] = s2[key]
        # Stage 3 fields (override/add)
        if name in s3_children:
            s3 = s3_children[name]
            for key in ("global_vars", "data_operations", "requested_capabilities",
                        "constraints", "acceptance_criteria", "traceability", "node_type"):
                if key in s3:
                    m[key] = s3[key]
        merged.append(m)
    return merged


# ========================================================================
# Trial runner
# ========================================================================

def _fix_constraints(node):
    """Convert string constraints to dict format expected by real pipeline decomposer."""
    import copy
    node = copy.deepcopy(node)
    if node.subprd and node.subprd.constraints:
        fixed = []
        for c in node.subprd.constraints:
            if isinstance(c, str):
                fixed.append({"description": c})
            elif isinstance(c, dict):
                fixed.append(c)
            else:
                fixed.append({"description": str(c)})
        node.subprd.constraints = fixed
    return node


def run_trial_baseline(case, trial_idx, api_key, base_url, model):
    """Run single-stage baseline decomposition."""
    node = _fix_constraints(case["node"])
    case_name = node.name
    label = f"single_stage_baseline/{case_name}/trial_{trial_idx:02d}"
    log_dir = os.path.join(OUTPUT_DIR, model, "single_stage_baseline", case_name, f"trial_{trial_idx:02d}")
    logger = LLMLogger(log_dir, api_key, base_url, model)
    t0 = time.time()

    # Use real pipeline decomposer prompt
    config = PipelineConfig(api_key="dummy", max_children=10, max_depth=3)
    decomposer = Decomposer(config, None)
    system_prompt = decomposer._build_system_prompt()
    user_prompt = decomposer._build_user_prompt(node)

    try:
        raw = logger.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
    except Exception as e:
        return {"label": label, "condition": "single_stage_baseline", "case": case_name,
                "trial": trial_idx, "error": f"API failed: {e}", "elapsed": time.time()-t0, "llm_calls": 1}

    parsed = parse_json(raw)
    elapsed = round(time.time()-t0, 1)

    children = parsed.get("children", [])
    has_routing, sibling_calls = detect_routing(children)

    # Deterministic checks
    child_count_viol = check_child_count(children, case.get("expected_children_range", (2, 10)))
    missing_fields = check_missing_required_fields(children, "single_stage_baseline")
    dangling = check_dangling_inputs(children, node)
    gv_subset = check_global_var_subset(children, node.global_vars)
    gv_gap = check_global_var_union_gap(children, node.global_vars)

    # Composition check
    comp_result = check_cannot_compose(node, children, logger)
    cannot_compose = comp_result.get("status") == "cannot_compose"

    result = {
        "label": label, "condition": "single_stage_baseline", "case": case_name,
        "trial": trial_idx, "n_children": len(children),
        "child_names": [c.get("name", "") for c in children],
        "has_routing": has_routing, "sibling_calls": sibling_calls,
        "child_count_violation": child_count_viol,
        "missing_required_fields": missing_fields[:10],
        "dangling_inputs": dangling[:10],
        "global_var_subset_violations": gv_subset[:10],
        "global_var_union_gap": gv_gap[:10],
        "cannot_compose": cannot_compose,
        "composition_feedback": comp_result.get("decomposition_feedback", {}),
        "parse_error": "error" in parsed and not parsed.get("children"),
        "elapsed": elapsed, "llm_calls": logger.call_counter,
    }

    with open(os.path.join(log_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    return result


def run_trial_notraditional(case, trial_idx, api_key, base_url, model):
    """Run single-stage with notraditional addition."""
    node = _fix_constraints(case["node"])
    case_name = node.name
    label = f"single_stage_notraditional/{case_name}/trial_{trial_idx:02d}"
    log_dir = os.path.join(OUTPUT_DIR, model, "single_stage_notraditional", case_name, f"trial_{trial_idx:02d}")
    logger = LLMLogger(log_dir, api_key, base_url, model)
    t0 = time.time()

    config = PipelineConfig(api_key="dummy", max_children=10, max_depth=3)
    decomposer = Decomposer(config, None)
    system_prompt = decomposer._build_system_prompt() + NOTRADITIONAL_ADDITION
    user_prompt = decomposer._build_user_prompt(node)

    try:
        raw = logger.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
    except Exception as e:
        return {"label": label, "condition": "single_stage_notraditional", "case": case_name,
                "trial": trial_idx, "error": f"API failed: {e}", "elapsed": time.time()-t0, "llm_calls": 1}

    parsed = parse_json(raw)
    elapsed = round(time.time()-t0, 1)

    children = parsed.get("children", [])
    has_routing, sibling_calls = detect_routing(children)

    child_count_viol = check_child_count(children, case.get("expected_children_range", (2, 10)))
    missing_fields = check_missing_required_fields(children, "single_stage_notraditional")
    dangling = check_dangling_inputs(children, node)
    gv_subset = check_global_var_subset(children, node.global_vars)
    gv_gap = check_global_var_union_gap(children, node.global_vars)

    comp_result = check_cannot_compose(node, children, logger)
    cannot_compose = comp_result.get("status") == "cannot_compose"

    result = {
        "label": label, "condition": "single_stage_notraditional", "case": case_name,
        "trial": trial_idx, "n_children": len(children),
        "child_names": [c.get("name", "") for c in children],
        "has_routing": has_routing, "sibling_calls": sibling_calls,
        "child_count_violation": child_count_viol,
        "missing_required_fields": missing_fields[:10],
        "dangling_inputs": dangling[:10],
        "global_var_subset_violations": gv_subset[:10],
        "global_var_union_gap": gv_gap[:10],
        "cannot_compose": cannot_compose,
        "composition_feedback": comp_result.get("decomposition_feedback", {}),
        "parse_error": "error" in parsed and not parsed.get("children"),
        "elapsed": elapsed, "llm_calls": logger.call_counter,
    }

    with open(os.path.join(log_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    return result


def run_trial_threestage(case, trial_idx, api_key, base_url, model):
    """Run three-stage decomposition."""
    node = _fix_constraints(case["node"])
    case_name = node.name
    label = f"three_stage/{case_name}/trial_{trial_idx:02d}"
    log_dir = os.path.join(OUTPUT_DIR, model, "three_stage", case_name, f"trial_{trial_idx:02d}")
    logger = LLMLogger(log_dir, api_key, base_url, model)
    t0 = time.time()
    total_llm = 0

    # Stage 1
    try:
        s1_raw = logger.chat([
            {"role": "system", "content": STAGE1_SYSTEM_PROMPT},
            {"role": "user", "content": build_stage1_user_prompt(node)},
        ])
    except Exception as e:
        return {"label": label, "condition": "three_stage", "case": case_name,
                "trial": trial_idx, "error": f"Stage1 API failed: {e}", "elapsed": time.time()-t0, "llm_calls": 1}

    stage1 = parse_json(s1_raw)
    total_llm = logger.call_counter

    if "error" in stage1 and not stage1.get("children"):
        return {"label": label, "condition": "three_stage", "case": case_name,
                "trial": trial_idx, "error": f"Stage1 parse: {stage1.get('error')}",
                "elapsed": round(time.time()-t0, 1), "llm_calls": total_llm}

    with open(os.path.join(log_dir, "stage1.json"), "w", encoding="utf-8") as f:
        json.dump(stage1, f, indent=2, ensure_ascii=False)

    # Stage 2
    try:
        s2_raw = logger.chat([
            {"role": "system", "content": STAGE2_SYSTEM_PROMPT},
            {"role": "assistant", "content": json.dumps(stage1, indent=2, ensure_ascii=False)},
            {"role": "user", "content": build_stage2_user_prompt(stage1, node)},
        ])
    except Exception as e:
        return {"label": label, "condition": "three_stage", "case": case_name,
                "trial": trial_idx, "error": f"Stage2 API failed: {e}",
                "elapsed": round(time.time()-t0, 1), "llm_calls": total_llm}

    stage2 = parse_json(s2_raw)
    total_llm = logger.call_counter

    with open(os.path.join(log_dir, "stage2.json"), "w", encoding="utf-8") as f:
        json.dump(stage2, f, indent=2, ensure_ascii=False)

    # Stage 3
    try:
        s3_raw = logger.chat([
            {"role": "system", "content": STAGE3_SYSTEM_PROMPT},
            {"role": "assistant", "content": json.dumps(stage2, indent=2, ensure_ascii=False)},
            {"role": "user", "content": build_stage3_user_prompt(stage1, stage2, node)},
        ])
    except Exception as e:
        return {"label": label, "condition": "three_stage", "case": case_name,
                "trial": trial_idx, "error": f"Stage3 API failed: {e}",
                "elapsed": round(time.time()-t0, 1), "llm_calls": total_llm}

    stage3 = parse_json(s3_raw)
    total_llm = logger.call_counter

    with open(os.path.join(log_dir, "stage3.json"), "w", encoding="utf-8") as f:
        json.dump(stage3, f, indent=2, ensure_ascii=False)

    # Merge stages
    merged = merge_stages(stage1, stage2, stage3)
    with open(os.path.join(log_dir, "merged_node.json"), "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    elapsed = round(time.time()-t0, 1)

    # Run checks on merged result
    has_routing, sibling_calls = detect_routing(merged)
    child_count_viol = check_child_count(merged, case.get("expected_children_range", (2, 10)))
    missing_fields = check_missing_required_fields(merged, "three_stage")
    dangling = check_dangling_inputs(merged, node)
    gv_subset = check_global_var_subset(merged, node.global_vars)
    gv_gap = check_global_var_union_gap(merged, node.global_vars)

    # Check stage drift
    s1_names = [c.get("name", "") for c in stage1.get("children", [])]
    merged_names = [c.get("name", "") for c in merged]
    stage_drift = s1_names != merged_names

    # Composition check
    comp_result = check_cannot_compose(node, merged, logger)
    cannot_compose = comp_result.get("status") == "cannot_compose"
    total_llm = logger.call_counter

    result = {
        "label": label, "condition": "three_stage", "case": case_name,
        "trial": trial_idx, "n_children": len(merged),
        "child_names": merged_names,
        "has_routing": has_routing, "sibling_calls": sibling_calls,
        "child_count_violation": child_count_viol,
        "missing_required_fields": missing_fields[:10],
        "dangling_inputs": dangling[:10],
        "global_var_subset_violations": gv_subset[:10],
        "global_var_union_gap": gv_gap[:10],
        "stage_drift": stage_drift,
        "cannot_compose": cannot_compose,
        "composition_feedback": comp_result.get("decomposition_feedback", {}),
        "parse_error": False,
        "elapsed": elapsed, "llm_calls": total_llm,
    }

    with open(os.path.join(log_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    return result


# ========================================================================
# Report generation
# ========================================================================

def generate_report(all_results, model, cases, n_trials):
    lines = [
        "# Exp03: Shallow Pipeline Regression Report",
        "",
        f"Model: `{model}`",
        f"Cases: {', '.join(c['node'].name for c in cases)}",
        f"Trials per condition per case: {n_trials}",
        f"Conditions: single_stage_baseline, single_stage_notraditional, three_stage",
        f"",
    ]

    conditions = ["single_stage_baseline", "single_stage_notraditional", "three_stage"]
    metrics = ["routing_rate", "child_count_violation_rate", "missing_field_rate",
               "dangling_input_rate", "global_var_subset_violation_rate",
               "global_var_union_gap_rate", "cannot_compose_rate", "parse_error_rate"]

    # Results matrix
    lines.append("## Results Matrix (Condition x Metric)\n")
    header = "| Condition | Trials | " + " | ".join(m.replace("_rate", "") for m in metrics) + " |"
    sep = "|-----------|--------|" + "|".join(["---"] * len(metrics)) + "|"
    lines.append(header)
    lines.append(sep)

    for cond in conditions:
        results = [r for r in all_results if r.get("condition") == cond]
        n = len(results)
        if n == 0:
            continue
        vals = []
        vals.append(f"{sum(1 for r in results if r.get('has_routing', False))}/{n}")
        vals.append(f"{sum(1 for r in results if r.get('child_count_violation', False))}/{n}")
        vals.append(f"{sum(1 for r in results if r.get('missing_required_fields'))}/{n}")
        vals.append(f"{sum(1 for r in results if r.get('dangling_inputs'))}/{n}")
        vals.append(f"{sum(1 for r in results if r.get('global_var_subset_violations'))}/{n}")
        vals.append(f"{sum(1 for r in results if r.get('global_var_union_gap'))}/{n}")
        vals.append(f"{sum(1 for r in results if r.get('cannot_compose', False))}/{n}")
        vals.append(f"{sum(1 for r in results if r.get('parse_error', False) or r.get('error'))}/{n}")
        lines.append(f"| {cond} | {n} | " + " | ".join(vals) + " |")

    lines.append("")

    # Per-case breakdown
    lines.append("## Per-Case Breakdown\n")
    case_names = sorted(set(r.get("case", "") for r in all_results))
    for case_name in case_names:
        lines.append(f"### {case_name}\n")
        lines.append("| Condition | Routing | CC Viol | Missing | Dangling | GV Subset | GV Gap | Compose |")
        lines.append("|-----------|---------|---------|---------|----------|-----------|--------|---------|")
        for cond in conditions:
            results = [r for r in all_results if r.get("condition") == cond and r.get("case") == case_name]
            n = len(results)
            if n == 0:
                continue
            routing = sum(1 for r in results if r.get("has_routing", False))
            cc = sum(1 for r in results if r.get("child_count_violation", False))
            miss = sum(1 for r in results if r.get("missing_required_fields"))
            dang = sum(1 for r in results if r.get("dangling_inputs"))
            gv_sub = sum(1 for r in results if r.get("global_var_subset_violations"))
            gv_gap = sum(1 for r in results if r.get("global_var_union_gap"))
            comp = sum(1 for r in results if r.get("cannot_compose", False))
            lines.append(f"| {cond} | {routing}/{n} | {cc}/{n} | {miss}/{n} | {dang}/{n} | {gv_sub}/{n} | {gv_gap}/{n} | {comp}/{n} |")
        lines.append("")

    # Top failures
    lines.append("## Top Failure Reasons\n")
    failure_counter = defaultdict(int)
    for r in all_results:
        if r.get("has_routing"):
            failure_counter["routing"] += 1
        if r.get("child_count_violation"):
            failure_counter["child_count_violation"] += 1
        if r.get("missing_required_fields"):
            failure_counter["missing_required_fields"] += 1
        if r.get("dangling_inputs"):
            failure_counter["dangling_inputs"] += 1
        if r.get("global_var_subset_violations"):
            failure_counter["global_var_subset_violations"] += 1
        if r.get("global_var_union_gap"):
            failure_counter["global_var_union_gap"] += 1
        if r.get("cannot_compose"):
            failure_counter["cannot_compose"] += 1
        if r.get("parse_error") or r.get("error"):
            failure_counter["parse_error"] += 1
    for reason, count in sorted(failure_counter.items(), key=lambda x: -x[1]):
        lines.append(f"- {reason}: {count} occurrences")
    lines.append("")

    # Representative failures
    lines.append("## Representative Failures\n")
    failure_cases = [r for r in all_results if any([
        r.get("has_routing"), r.get("cannot_compose"), r.get("global_var_union_gap"),
        r.get("dangling_inputs"),
    ])]
    for r in failure_cases[:5]:
        lines.append(f"- **{r['label']}**: routing={r.get('has_routing')}, compose={r.get('cannot_compose')}, "
                      f"gv_gap={len(r.get('global_var_union_gap', []))}, dangling={len(r.get('dangling_inputs', []))}")
    lines.append("")

    # Verdict
    lines.append("## Verdict\n")
    baseline_routing = sum(1 for r in all_results if r.get("condition") == "single_stage_baseline" and r.get("has_routing"))
    notrad_routing = sum(1 for r in all_results if r.get("condition") == "single_stage_notraditional" and r.get("has_routing"))
    three_routing = sum(1 for r in all_results if r.get("condition") == "three_stage" and r.get("has_routing"))
    baseline_n = sum(1 for r in all_results if r.get("condition") == "single_stage_baseline")
    notrad_n = sum(1 for r in all_results if r.get("condition") == "single_stage_notraditional")
    three_n = sum(1 for r in all_results if r.get("condition") == "three_stage")

    lines.append(f"- Baseline routing: {baseline_routing}/{baseline_n}")
    lines.append(f"- Notraditional routing: {notrad_routing}/{notrad_n}")
    lines.append(f"- Three-stage routing: {three_routing}/{three_n}")
    lines.append("")

    # Check if three_stage improves on notraditional
    three_gap = sum(len(r.get("global_var_union_gap", [])) for r in all_results if r.get("condition") == "three_stage")
    three_dang = sum(len(r.get("dangling_inputs", [])) for r in all_results if r.get("condition") == "three_stage")
    three_comp = sum(1 for r in all_results if r.get("condition") == "three_stage" and r.get("cannot_compose"))
    notrad_gap = sum(len(r.get("global_var_union_gap", [])) for r in all_results if r.get("condition") == "single_stage_notraditional")
    notrad_dang = sum(len(r.get("dangling_inputs", [])) for r in all_results if r.get("condition") == "single_stage_notraditional")
    notrad_comp = sum(1 for r in all_results if r.get("condition") == "single_stage_notraditional" and r.get("cannot_compose"))

    lines.append(f"- GV union gap: notraditional={notrad_gap}, three_stage={three_gap}")
    lines.append(f"- Dangling inputs: notraditional={notrad_dang}, three_stage={three_dang}")
    lines.append(f"- Cannot compose: notraditional={notrad_comp}, three_stage={three_comp}")
    lines.append("")

    if three_routing <= notrad_routing and (three_gap < notrad_gap or three_dang < notrad_dang or three_comp < notrad_comp):
        verdict = "PASS"
    elif three_routing > notrad_routing:
        verdict = "FAIL (routing regression)"
    else:
        verdict = "INCONCLUSIVE"
    lines.append(f"- **Verdict: {verdict}**")
    lines.append("")
    return "\n".join(lines)


# ========================================================================
# Main
# ========================================================================

def main():
    parser = argparse.ArgumentParser(description="Exp03: Shallow Pipeline Regression")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--cases", type=str, default="OrderSystem,ChatApp,PatientPortal,BuildSystem,DataPipeline",
                        help="Comma-separated case names")
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

    # Select cases
    case_name_map = {c["node"].name: c for c in ALL_CASES}
    requested = [c.strip() for c in args.cases.split(",")]
    cases = [case_name_map[c] for c in requested if c in case_name_map]
    if not cases:
        print(f"ERROR: No valid cases. Available: {list(case_name_map.keys())}"); return 1

    print(f"Model: {model}")
    print(f"Cases: {[c['node'].name for c in cases]}")
    print(f"Trials per condition per case: {args.trials}")
    print(f"Conditions: single_stage_baseline, single_stage_notraditional, three_stage")
    print(f"Output: {OUTPUT_DIR}/{model}/")
    print()

    # Build task list
    tasks = []
    for case in cases:
        for t in range(args.trials):
            tasks.append(("single_stage_baseline", case, t))
            tasks.append(("single_stage_notraditional", case, t))
            tasks.append(("three_stage", case, t))

    all_results = []
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = {}
        for cond, case, t in tasks:
            case_name = case["node"].name
            if cond == "single_stage_baseline":
                f = pool.submit(run_trial_baseline, case, t, api_key, base_url, model)
            elif cond == "single_stage_notraditional":
                f = pool.submit(run_trial_notraditional, case, t, api_key, base_url, model)
            else:
                f = pool.submit(run_trial_threestage, case, t, api_key, base_url, model)
            futures[f] = f"{cond}/{case_name}_{t:02d}"

        for f in as_completed(futures):
            r = f.result()
            all_results.append(r)
            err = r.get("error", "")
            if err:
                print(f"  [{r['label']}] ERROR: {err[:80]}")
            else:
                rt = "RT" if r.get("has_routing") else "ok"
                cc = "CC!" if r.get("child_count_violation") else ""
                comp = "COMP!" if r.get("cannot_compose") else ""
                print(f"  [{r['label']}] {r.get('n_children',0)}ch {rt} {cc} {comp} {r.get('elapsed',0)}s")

    # Sort results
    all_results.sort(key=lambda r: (r.get("condition", ""), r.get("case", ""), r.get("trial", 0)))

    # Save results
    out_dir = os.path.join(OUTPUT_DIR, model)
    os.makedirs(out_dir, exist_ok=True)
    results_path = os.path.join(out_dir, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved: {results_path}")

    # Generate report
    report = generate_report(all_results, model, cases, args.trials)
    report_path = os.path.join(out_dir, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Saved: {report_path}")

    # Summary
    total = len(all_results)
    total_routing = sum(1 for r in all_results if r.get("has_routing", False))
    total_comp = sum(1 for r in all_results if r.get("cannot_compose", False))
    total_err = sum(1 for r in all_results if r.get("error") or r.get("parse_error", False))
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Total trials: {total}")
    print(f"  Routing: {total_routing}/{total}")
    print(f"  Cannot compose: {total_comp}/{total}")
    print(f"  Errors: {total_err}/{total}")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
