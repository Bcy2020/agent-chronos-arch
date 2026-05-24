"""
Routing Ablation Experiment v2 — baseline exactly matches real pipeline.

Uses the real decomposer.py from mvp-0.4.4 for prompt construction.
Ablation conditions are targeted modifications to the real prompt.

Env vars (CHRONOS_xxx, fallback to DEEPSEEK_xxx):
  CHRONOS_API_KEY, CHRONOS_BASE_URL, CHRONOS_MODEL,
  CHRONOS_TEMPERATURE, CHRONOS_MAX_TOKENS, CHRONOS_MAX_CONCURRENCY

MiMo support:
  MIMO_API_KEY env var, --model mimo-v2.5 / mimo-v2-flash
  Auto-sets base_url to https://api.xiaomimimo.com/v1

Usage:
    python test_routing_ablation.py                    # run all (default model)
    python test_routing_ablation.py --model mimo-v2.5  # run with MiMo v2.5
    python test_routing_ablation.py --model mimo-v2-flash  # run with MiMo flash
    python test_routing_ablation.py --experiment 0     # run single experiment
    python test_routing_ablation.py --prd order        # run single PRD
    python test_routing_ablation.py --skip-interview   # skip follow-up questions
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

# Add mvp-0.4.4 to path for real pipeline modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mvp", "mvp-0.4.4"))
from models import (
    Node, InputParam, OutputParam, Boundary, GlobalVar,
    DataSource, SubPRD, Traceability, AcceptanceCriterion,
    JsonPRD, InterfacePlan, FunctionalRequirement
)
from decomposer import Decomposer
from config import Config as PipelineConfig


# -----------------------------------------------------------------------
# Config (resolved at runtime in main(), overridable via CLI)
# -----------------------------------------------------------------------
def _env(key, default=""):
    return os.getenv(key) or os.getenv(f"DEEPSEEK_{key.removeprefix('CHRONOS_')}") or default


TEMPERATURE = float(os.getenv("CHRONOS_TEMPERATURE", "0.3"))
MAX_TOKENS = int(os.getenv("CHRONOS_MAX_TOKENS", "16384"))
MAX_CONCURRENCY = int(os.getenv("CHRONOS_MAX_CONCURRENCY", "10"))

PREREQUISITES_DIR = os.path.join(os.path.dirname(__file__), "output", "routing_ablation", "prerequisites")

# MiMo model prefixes
MIMO_MODELS = {"mimo-v2.5", "mimo-v2-flash", "mimo-v2.5-pro", "mimo-v2-pro", "mimo-v2-omni"}
MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"


# -----------------------------------------------------------------------
# Real pipeline decomposer (for prompt generation only)
# -----------------------------------------------------------------------
_pipeline_config = PipelineConfig(api_key="dummy", max_children=10, max_depth=3)
_decomposer = Decomposer(_pipeline_config, None)


def build_interface_plan_summary(interface_plan_data):
    """Build interface plan summary string, same as TreeBuilder._build_interface_summary."""
    if not interface_plan_data:
        return ""
    plan = InterfacePlan.from_dict(interface_plan_data)
    lines = []
    for iface in plan.interfaces:
        lines.append(f"  - {iface.interface_id}: {iface.signature}")
        if iface.description:
            lines.append(f"    Description: {iface.description}")
    return "\n".join(lines)


def build_node_from_prerequisites(json_prd_data, interface_plan_data):
    """Build a Node object from prerequisites, same as create_root_from_prd."""
    json_prd = JsonPRD.from_dict(json_prd_data)

    purpose = json_prd.metadata.get("project_name", "System")
    safe_name = "".join(c if c.isalnum() else "_" for c in purpose)
    safe_name = safe_name[0].upper() + safe_name[1:] if safe_name else "System"

    # Data sources and global vars from global_state_sources
    data_sources = []
    global_vars = []
    for gss in json_prd.global_state_sources:
        ds = DataSource(
            name=gss.source_id, category="memory", access="read_write",
            data_type=gss.type, description=gss.description
        )
        data_sources.append(ds)
        gv = GlobalVar(variable=gss.source_id, op="read_write", description=gss.description)
        global_vars.append(gv)

    root = Node(
        node_id="root", name=safe_name, depth=0,
        purpose=purpose,
        inputs=[InputParam(name="input", type="Any", description="System input")],
        outputs=[OutputParam(name="output", type="Any", description="System output")],
        boundary=Boundary(
            in_scope=["All functionality described in the input"],
            out_of_scope=["Functionality not described in the input"]
        ),
        data_sources=data_sources,
        global_vars=global_vars
    )

    # Build SubPRD description with INPUT FORMAT + OUTPUT FORMAT + Functional Requirements
    fr_text = "\n".join(
        f"[{fr.fr_id}] {fr.title}: {fr.description}"
        for fr in json_prd.functional_requirements
    )

    def _build_spec_text(spec, label):
        lines = [f"{label}:"]
        fmt = spec.get("format", "")
        if fmt:
            lines.append(f"  Format: {fmt}")
        desc = spec.get("description", "")
        if desc:
            lines.append(f"  Description: {desc}")
        schema = spec.get("schema", {})
        if schema:
            lines.append(f"  Schema:")
            for k, v in schema.items():
                lines.append(f"    {k}: {v}")
        examples = spec.get("examples", [])
        if examples:
            lines.append(f"  Examples:")
            for ex in examples:
                ex_str = json.dumps(ex) if isinstance(ex, dict) else str(ex)
                lines.append(f"    {ex_str}")
        return "\n".join(lines)

    io_parts = []
    if json_prd.input_spec:
        io_parts.append(_build_spec_text(json_prd.input_spec, "INPUT FORMAT"))
    if json_prd.output_spec:
        io_parts.append(_build_spec_text(json_prd.output_spec, "OUTPUT FORMAT"))
    io_text = "\n\n".join(io_parts)
    description = f"{io_text}\n\nFunctional Requirements:\n{fr_text}" if io_text else f"Functional Requirements:\n{fr_text}"

    # Constraints from technical_constraints
    tc = json_prd.technical_constraints
    constraints = []
    if tc:
        if tc.storage:
            constraints.append({"constraint_id": "TC-STORAGE", "description": f"Storage: {tc.storage.get('type', 'memory')} - {tc.storage.get('details', '')}"})
        if tc.concurrency:
            constraints.append({"constraint_id": "TC-CONCURRENCY", "description": f"Concurrency: {tc.concurrency.get('model', 'single-user')}, auth_required: {tc.concurrency.get('auth_required', False)}"})
        if tc.ui:
            constraints.append({"constraint_id": "TC-UI", "description": f"UI: {tc.ui.get('type', 'cli')}"})
        if tc.language:
            constraints.append({"constraint_id": "TC-LANGUAGE", "description": f"Language: {tc.language}"})

    root.subprd = SubPRD(
        task_id="root", purpose=purpose, description=description,
        constraints=constraints,
        acceptance_criteria=[
            AcceptanceCriterion(ac_id=ac.ac_id, description=ac.description, verification_method=ac.verification_method)
            for ac in json_prd.acceptance_criteria
        ],
        traceability=Traceability(parent_requirement_ids=[fr.fr_id for fr in json_prd.functional_requirements])
    )
    return root


# -----------------------------------------------------------------------
# Ablation prompt modifiers (targeted removals from real prompt)
# -----------------------------------------------------------------------
def remove_section(prompt, start_marker, end_marker=None):
    """Remove a section from prompt delimited by markers."""
    idx = prompt.find(start_marker)
    if idx == -1:
        return prompt
    if end_marker:
        end_idx = prompt.find(end_marker, idx + len(start_marker))
        if end_idx != -1:
            return prompt[:idx] + prompt[end_idx + len(end_marker):]
    # Remove to next blank line
    nl = prompt.find("\n\n", idx)
    if nl != -1:
        return prompt[:idx] + prompt[nl:]
    return prompt[:idx]


def apply_ablation(system_prompt, user_prompt, ablation):
    """Apply targeted ablation to real prompts."""
    if ablation == "baseline":
        return system_prompt, user_prompt

    sp = system_prompt
    up = user_prompt

    if ablation == "no_coordinator":
        # Remove coordinator rule from TREE STRUCTURE rule
        sp = sp.replace(
            " A coordinator child node is ALLOWED, as long as it only coordinates work within its own subtree and never calls sibling nodes.",
            ""
        )

    elif ablation == "no_signature_locking":
        # Remove SIGNATURE LOCKING section
        sp = remove_section(sp,
            "SIGNATURE LOCKING - CHILD INTERFACES ARE BINDING CONTRACTS:\n",
            "- The verifier will reject code that does not match the declared signature exactly\n"
        )

    elif ablation == "no_stop_conditions":
        # Remove SEMANTIC STOP CONDITIONS section
        sp = remove_section(sp,
            "SEMANTIC STOP CONDITIONS - Use these instead of line-count estimation:\n",
            "- Contains conditional validation logic\n"
        )

    elif ablation == "no_dataflow_closure":
        # Remove DATAFLOW CLOSURE RULES section
        sp = remove_section(sp,
            "DATAFLOW CLOSURE RULES:\n",
            "5. Parent must not directly access global state or data interfaces — all data operations must go through child function calls.\n"
        )

    elif ablation == "no_boundary":
        # Remove Boundary section from user prompt
        up = remove_section(up, "Boundary:\n")

    elif ablation == "no_data_sources":
        # Remove Data Sources section from user prompt
        up = remove_section(up, "Data Sources (AVAILABLE DATA STORES):\n")

    elif ablation == "no_subprd":
        # Remove SubPRD Context section from user prompt
        up = remove_section(up, "SubPRD Context:\n")

    elif ablation == "specific_input":
        # Change input: Any to specific input types
        up = up.replace(
            "  - input: Any - System input\n  - output: Any - System output",
            "  - command: str - Command to execute\n  - order_data: dict - Data for the command\n  - result: dict - JSON with success, message, data"
        )

    return sp, up


# -----------------------------------------------------------------------
# Experiment conditions
# -----------------------------------------------------------------------
EXPERIMENTS = [
    {"name": "baseline",          "ablation": "baseline"},
    {"name": "no_coordinator",    "ablation": "no_coordinator"},
    {"name": "no_signature_lock", "ablation": "no_signature_locking"},
    {"name": "no_stop_conditions","ablation": "no_stop_conditions"},
    {"name": "no_dataflow_closure","ablation": "no_dataflow_closure"},
    {"name": "no_boundary",       "ablation": "no_boundary"},
    {"name": "no_data_sources",   "ablation": "no_data_sources"},
    {"name": "no_subprd",         "ablation": "no_subprd"},
    {"name": "specific_input",    "ablation": "specific_input"},
]

TRIALS_PER_CONDITION = 5


# -----------------------------------------------------------------------
# LLM caller with logging
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
    r'(?:route[s]?\s+(?:the\s+)?(?:command|request|input)|dispatch(?:es)?\s+(?:to\s+)?(?:the\s+)?(?:appropriate|correct|corresponding)|parse[s]?\s+(?:the\s+)?input\s+(?:and|to)\s+(?:route|dispatch|extract))',
    re.IGNORECASE
)


def detect_routing(children):
    """Detect if any child calls a sibling (routing violation)."""
    child_names = {c.get("name", "") for c in children}
    sibling_calls = []

    # Method 1: Text-based detection
    for c in children:
        cname = c.get("name", "")
        text = c.get("purpose", "") + " " + c.get("behavior", "")
        for pattern in ROUTING_PATTERNS:
            for match in pattern.finditer(text):
                target = match.group(1)
                if target in child_names and target != cname:
                    sibling_calls.append({"from": cname, "to": target, "method": "text_pattern"})

    # Method 2: Structural detection
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

    # Deduplicate
    seen = set()
    unique = []
    for sc in sibling_calls:
        key = (sc["from"], sc["to"], sc["method"])
        if key not in seen:
            seen.add(key)
            unique.append(sc)

    return len(unique) > 0, unique


# -----------------------------------------------------------------------
# Interview questions (neutral, no leading)
# -----------------------------------------------------------------------
def build_interview_questions(routing_node_name):
    return [
        "请解释你对这个节点输入格式的理解。command 参数的含义是什么？",
        "你为什么选择这样的子节点划分方式？每个子节点的职责边界是什么？",
        f"你提到 {routing_node_name} 会调用其他子节点，请解释这个设计的意图。",
        "如果要求所有子节点只能被父节点直接调用，你会如何调整分解？",
    ]


# -----------------------------------------------------------------------
# Trial runner
# -----------------------------------------------------------------------
def run_trial(prd_name, node, interface_plan_summary, experiment, trial_idx, api_key, base_url, model, output_dir, skip_interview=False):
    """Run a single trial: decompose + optional interview."""
    exp_name = experiment["name"]
    ablation = experiment["ablation"]
    label = f"{exp_name}/{prd_name}/trial_{trial_idx:02d}"
    log_dir = os.path.join(output_dir, f"experiment_{exp_name}", prd_name)
    logger = LLMLogger(log_dir, api_key, base_url, model)

    t0 = time.time()

    # Build real pipeline prompts
    system_prompt = _decomposer._build_system_prompt()
    user_prompt = _decomposer._build_user_prompt(node, interface_plan_summary=interface_plan_summary)

    # Apply ablation
    system_prompt, user_prompt = apply_ablation(system_prompt, user_prompt, ablation)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response_text = logger.chat(messages)
    except Exception as e:
        return {
            "label": label, "exp_name": exp_name, "prd_name": prd_name,
            "trial": trial_idx, "error": str(e), "elapsed": time.time() - t0,
        }

    # Parse response (same logic as real decomposer)
    content = response_text.strip()
    if content.startswith("```"):
        content = re.sub(r"^```[a-zA-Z0-9]*\n?", "", content)
        content = re.sub(r"\n?```$", "", content)
    if "}" in content:
        last_brace = content.rfind("}")
        content = content[:last_brace + 1]
    content = re.sub(r'(?<=[\s:,\[{])[fFrRuUbB]+(")', r'\1', content)

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', content, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group())
            except:
                parsed = {"error": "JSON parse failed", "raw": content[:500]}
        else:
            parsed = {"error": "No JSON found", "raw": content[:500]}

    children = parsed.get("children", [])

    # Detect routing
    has_routing, sibling_calls = detect_routing(children)

    result = {
        "label": label, "exp_name": exp_name, "prd_name": prd_name,
        "trial": trial_idx, "n_children": len(children),
        "child_names": [c.get("name", "") for c in children],
        "has_routing": has_routing, "sibling_calls": sibling_calls,
        "decomposition_rationale": parsed.get("decomposition_rationale", ""),
        "elapsed": round(time.time() - t0, 1), "llm_calls": logger.call_counter,
    }

    # Save full response
    trial_path = os.path.join(log_dir, f"trial_{trial_idx:02d}.json")
    with open(trial_path, "w", encoding="utf-8") as f:
        json.dump({
            "experiment": experiment,
            "ablation": ablation,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "response": parsed,
            "routing": {"has_routing": has_routing, "sibling_calls": sibling_calls},
        }, f, indent=2, ensure_ascii=False)

    # Interview if routing detected
    if has_routing and not skip_interview:
        routing_node = sibling_calls[0]["from"] if sibling_calls else "Unknown"
        questions = build_interview_questions(routing_node)
        interview_responses = []

        interview_messages = [
            {"role": "system", "content": (
                "你是一个代码架构师。你刚刚完成了一次系统分解。"
                "接下来会有人就你的设计决策提出问题。请如实回答。"
            )},
            {"role": "assistant", "content": (
                f"我将 {prd_name} 分解为 {len(children)} 个子节点：\n"
                + "\n".join(f"- {c.get('name', '')}: {c.get('purpose', '')}" for c in children)
                + f"\n\n分解理由：{parsed.get('decomposition_rationale', '')}"
            )},
        ]

        for q in questions:
            interview_messages.append({"role": "user", "content": q})
            try:
                resp = logger.chat(interview_messages)
                interview_messages.append({"role": "assistant", "content": resp})
                interview_responses.append({"question": q, "answer": resp})
            except Exception as e:
                interview_responses.append({"question": q, "error": str(e)})

        result["interview"] = interview_responses

        interview_path = os.path.join(log_dir, f"trial_{trial_idx:02d}_interview.json")
        with open(interview_path, "w", encoding="utf-8") as f:
            json.dump(interview_responses, f, indent=2, ensure_ascii=False)

    return result


# -----------------------------------------------------------------------
# Load prerequisites
# -----------------------------------------------------------------------
def load_prerequisites(prd_name):
    """Load JSON PRD and Interface Plan for a PRD."""
    prd_dir = os.path.join(PREREQUISITES_DIR, prd_name)

    prd_path = os.path.join(prd_dir, ".chronos", "prd.json")
    if not os.path.exists(prd_path):
        raise FileNotFoundError(f"JSON PRD not found: {prd_path}")
    with open(prd_path, "r", encoding="utf-8") as f:
        json_prd = json.load(f)

    plan_path = os.path.join(prd_dir, "interface_plan.json")
    interface_plan = None
    if os.path.exists(plan_path):
        with open(plan_path, "r", encoding="utf-8") as f:
            interface_plan = json.load(f)

    return json_prd, interface_plan


# -----------------------------------------------------------------------
# Report generation
# -----------------------------------------------------------------------
def generate_report(all_results, model):
    """Generate markdown report from all results."""
    prd_names = sorted(set(r["prd_name"] for r in all_results))
    exp_names = [e["name"] for e in EXPERIMENTS]

    lines = [
        "# Routing Ablation Experiment Report (v2)",
        "",
        f"- Model: {model}",
        f"- Temperature: {TEMPERATURE}",
        f"- Trials per condition: {TRIALS_PER_CONDITION}",
        f"- PRDs: {', '.join(prd_names)}",
        f"- Total trials: {len(all_results)}",
        "",
        "---",
        "",
        "## Results Matrix",
        "",
    ]

    header = "| Experiment |"
    separator = "|------------|"
    for prd in prd_names:
        header += f" {prd} |"
        separator += "--------|"
    header += " Total |"
    separator += "-------|"
    lines.append(header)
    lines.append(separator)

    exp_routing_counts = {}
    for exp in exp_names:
        row = f"| **{exp}** |"
        total_routing = 0
        total_trials = 0
        for prd in prd_names:
            trials = [r for r in all_results if r["exp_name"] == exp and r["prd_name"] == prd]
            routing_count = sum(1 for r in trials if r.get("has_routing", False))
            total = len(trials)
            total_routing += routing_count
            total_trials += total
            row += f" {routing_count}/{total} |"
        row += f" **{total_routing}/{total_trials}** |"
        lines.append(row)
        exp_routing_counts[exp] = (total_routing, total_trials)

    lines.append("")

    # Delta analysis
    lines.append("## Variable Impact Analysis")
    lines.append("")
    lines.append("| Ablation | What's Removed | Rate | Delta vs Baseline |")
    lines.append("|----------|----------------|------|-------------------|")

    baseline = exp_routing_counts.get("baseline", (0, 1))
    baseline_rate = baseline[0] / baseline[1] if baseline[1] > 0 else 0

    ablation_descriptions = {
        "no_coordinator": "Coordinator rule from TREE STRUCTURE",
        "no_signature_lock": "SIGNATURE LOCKING section",
        "no_stop_conditions": "SEMANTIC STOP CONDITIONS section",
        "no_dataflow_closure": "DATAFLOW CLOSURE RULES section",
        "no_boundary": "Boundary section from user prompt",
        "no_data_sources": "Data Sources section from user prompt",
        "no_subprd": "SubPRD Context section from user prompt",
        "specific_input": "input: Any -> command: str, order_data: dict",
    }

    for exp in EXPERIMENTS:
        if exp["name"] == "baseline":
            lines.append(f"| **baseline** | (exact real pipeline) | {baseline_rate:.0%} | — |")
            continue
        counts = exp_routing_counts.get(exp["name"], (0, 1))
        rate = counts[0] / counts[1] if counts[1] > 0 else 0
        delta = rate - baseline_rate
        desc = ablation_descriptions.get(exp["ablation"], "")
        lines.append(f"| {exp['name']} | {desc} | {rate:.0%} | {delta:+.0%} |")

    lines.append("")

    # Routing details
    routing_results = [r for r in all_results if r.get("has_routing", False)]
    if routing_results:
        lines.append("## Routing Cases Detail")
        lines.append("")
        for r in routing_results:
            lines.append(f"### {r['label']}")
            lines.append(f"- Children: {', '.join(r.get('child_names', []))}")
            lines.append(f"- Sibling calls: {json.dumps(r.get('sibling_calls', []), ensure_ascii=False)}")
            rationale = r.get('decomposition_rationale', '')
            if rationale:
                lines.append(f"- Rationale: {rationale[:300]}")
            if r.get("interview"):
                lines.append("- Interview:")
                for qa in r["interview"]:
                    lines.append(f"  - Q: {qa['question']}")
                    answer = qa.get("answer", qa.get("error", ""))
                    lines.append(f"    A: {answer[:200]}")
            lines.append("")

    lines.append("## Key Findings")
    lines.append("")
    lines.append("(To be filled after analysis)")
    lines.append("")

    return "\n".join(lines)


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Routing ablation experiment v2")
    parser.add_argument("--experiment", type=int, help="Run single experiment by index")
    parser.add_argument("--prd", type=str, help="Run single PRD (order/grade/project)")
    parser.add_argument("--skip-interview", action="store_true", help="Skip follow-up questions")
    parser.add_argument("--trials", type=int, default=TRIALS_PER_CONDITION, help="Trials per condition")
    parser.add_argument("--model", type=str, default=None, help="Model name (e.g. mimo-v2.5, mimo-v2-flash)")
    parser.add_argument("--base-url", type=str, default=None, help="API base URL")
    parser.add_argument("--api-key", type=str, default=None, help="API key")
    args = parser.parse_args()

    # Resolve model config
    model = args.model or _env("CHRONOS_MODEL", "deepseek-chat")
    if model in MIMO_MODELS:
        base_url = args.base_url or os.getenv("MIMO_BASE_URL", MIMO_BASE_URL)
        api_key = args.api_key or os.getenv("MIMO_API_KEY") or _env("CHRONOS_API_KEY")
    else:
        base_url = args.base_url or _env("CHRONOS_BASE_URL", "https://api.deepseek.com")
        api_key = args.api_key or _env("CHRONOS_API_KEY")

    output_dir = os.path.join(os.path.dirname(__file__), "output", "routing_ablation", model)

    if not api_key:
        print("ERROR: Set CHRONOS_API_KEY (or DEEPSEEK_API_KEY or MIMO_API_KEY)")
        return 1

    print(f"API: {base_url}")
    print(f"Model: {model}")
    print(f"Max concurrency: {MAX_CONCURRENCY}")

    # Load prerequisites and build Nodes
    prd_names = ["order_real", "grade_real", "project_real"]
    if args.prd:
        prd_names = [args.prd]

    prds = {}
    for name in prd_names:
        try:
            json_prd_data, iface_data = load_prerequisites(name)
            node = build_node_from_prerequisites(json_prd_data, iface_data)
            iface_summary = build_interface_plan_summary(iface_data)
            prds[name] = (node, iface_summary)

            # Verify prompt matches real pipeline
            sp = _decomposer._build_system_prompt()
            up = _decomposer._build_user_prompt(node, interface_plan_summary=iface_summary)
            print(f"Loaded: {name} (node={node.name}, FRs={len(node.subprd.traceability.parent_requirement_ids) if node.subprd else 0})")
            print(f"  System prompt: {len(sp)} chars, User prompt: {len(up)} chars")
        except Exception as e:
            print(f"ERROR loading {name}: {e}")
            import traceback; traceback.print_exc()
            return 1

    # Select experiments
    experiments = EXPERIMENTS
    if args.experiment is not None:
        experiments = [EXPERIMENTS[args.experiment]]

    os.makedirs(output_dir, exist_ok=True)

    # Build task list
    tasks = []
    for exp in experiments:
        for prd_name, (node, iface_summary) in prds.items():
            for trial in range(args.trials):
                tasks.append((prd_name, node, iface_summary, exp, trial))

    print(f"\nRunning {len(tasks)} trials with concurrency {MAX_CONCURRENCY}...\n")

    # Execute in parallel
    all_results = []
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = {}
        for prd_name, node, iface_summary, exp, trial in tasks:
            f = pool.submit(run_trial, prd_name, node, iface_summary, exp, trial,
                            api_key, base_url, model, output_dir, args.skip_interview)
            futures[f] = f"{exp['name']}/{prd_name}/trial_{trial:02d}"

        for f in as_completed(futures):
            label = futures[f]
            try:
                result = f.result()
                all_results.append(result)
                routing_str = "ROUTING" if result.get("has_routing") else "ok"
                n_children = result.get("n_children", 0)
                elapsed = result.get("elapsed", 0)
                print(f"  [{label}] {n_children} children, {routing_str}, {elapsed:.1f}s")
            except Exception as e:
                print(f"  [{label}] ERROR: {e}")
                all_results.append({"label": label, "error": str(e)})

    # Save results
    results_path = os.path.join(output_dir, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nResults saved: {results_path}")

    # Generate report
    report = generate_report(all_results, model)
    report_path = os.path.join(output_dir, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved: {report_path}")

    # Summary
    routing_count = sum(1 for r in all_results if r.get("has_routing", False))
    total = len(all_results)
    print(f"\n{'='*60}")
    print(f"  SUMMARY: {routing_count}/{total} trials produced routing")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
