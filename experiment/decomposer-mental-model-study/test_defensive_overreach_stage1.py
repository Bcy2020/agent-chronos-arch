"""
Stage1 defensive-overreach prompt experiment.

Tests whether LLMs add defensive validation/check/error-handling steps when a
node's boundary says it should only perform insertion.

Output:
  output/defensive_overreach_stage1/{model}/
"""
import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from openai import OpenAI


ROOT = os.path.dirname(__file__)
load_dotenv(os.path.join(ROOT, ".env"))


def _env(key: str, default: str = "") -> str:
    return os.getenv(key) or os.getenv(f"DEEPSEEK_{key.removeprefix('CHRONOS_')}") or default


TEMPERATURE = float(os.getenv("CHRONOS_TEMPERATURE", os.getenv("TEMPERATURE", "0.3")))
MAX_TOKENS = int(os.getenv("CHRONOS_MAX_TOKENS", "4096"))
OUTPUT_BASE = os.path.join(ROOT, "output", "defensive_overreach_stage1")


STAGE1_SYSTEM_PROMPT = """You are a software system decomposition agent. Your task is Stage 1: decompose a function block into child function blocks — STRUCTURE ONLY. Do NOT derive interfaces or resources.

CRITICAL RULES:
1. EVERY CHILD MUST BE A FUNCTION, NOT A CLASS.
2. TREE STRUCTURE (not graph): Children MUST NOT call each other. The parent MUST directly invoke all children.
3. Do NOT add extra external inputs or outputs beyond what the parent has.
4. Children should be at the same abstraction level and minimally overlapping.

DO NOT ASSUME TRADITIONAL DEVELOPMENT PATTERNS:
- DO NOT create "dispatcher", "router", "controller", "command_handler" nodes.
- DO NOT use Command Pattern, Strategy Pattern, or any pattern where one child calls other children.
- Each child MUST be a self-contained function that does actual work.
- The parent IS the router. If different inputs need different processing, the parent decides through conditional logic which child to call.
- The purpose of decomposition is to divide work, not to recreate enterprise architecture patterns.

SEMANTIC STOP CONDITIONS: STOP when pure function, atomic operation, or max depth reached.

OUTPUT FORMAT — Return valid JSON:
{
  "children": [
    {
      "name": "ChildName",
      "purpose": "semantic responsibility",
      "behavior": "internal transformation without sibling calls — describe WHAT this child does",
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
  "dataflow_sketch": [{"from": "parent | ChildName", "to": "ChildName | parent", "data": "semantic data name", "note": "why"}]
}

CONSTRAINTS — FIELDS YOU MUST NOT EMIT:
- Do NOT emit "inputs", "outputs", "signature" — these belong to Stage 2.
- Do NOT emit "global_vars", "data_operations", "requested_capabilities", "constraints", "acceptance_criteria", "traceability" — these belong to Stage 3.
- Do NOT emit "dataflow_edges" — Stage 2 will derive dataflow from your dataflow_sketch.
- Do NOT emit "node_type" — Stage 3 will classify.
- Do NOT emit "interface_preservation" — Stage 2 will determine interface preservation.
- semantic_inputs/semantic_outputs are SEMANTIC descriptions only, NOT typed interfaces.
- composition_role=decide means "returns a decision to parent", not "calls another child"."""


BASE_NODE_BLOCK = """Node Name: InsertStudent
Node Purpose: Insert new student record into students data store

Task Description:
  The function receives a student_id and student_name from its parent.
  It inserts the new student record into the students data store.
  It returns whether the insertion succeeded.

Inputs:
  - student_id: str - Unique student identifier
  - student_name: str - Student name

Outputs:
  - success: bool - Whether the student record was inserted successfully

Boundary:
  In Scope:
    - Insert student_id and student_name into students
    - Return insertion success
  Out of Scope:
    - Duplicate checking
    - Student lookup
    - Input parsing
    - Input validation
    - Error formatting

Preconditions:
  - student_id is provided
  - student_name is provided

Postconditions:
  - Student record is inserted into students

Global Variables (for context — Stage 3 will distribute these):
  - write on students: Insert a new student record.

Maximum children allowed: 5
Maximum depth: 5
Return ONLY the JSON response."""


CONDITIONS = {
    "baseline": {
        "description": "Original Stage1-style prompt with boundary/out_of_scope only.",
        "expected_defense": False,
        "extra": "",
    },
    "weak_no_duplicate": {
        "description": "Adds a weak statement that the input has no duplicate.",
        "expected_defense": False,
        "extra": """

Additional Condition:
  The input student_id has no duplicate in the students data store.
  The model should use this as context, but no further instruction is added.""",
    },
    "parent_guarantee": {
        "description": "States that parent/sibling already checked duplicates.",
        "expected_defense": False,
        "extra": """

Parent Guarantees:
  - The parent has already called a sibling function named CheckDuplicate before this node.
  - CheckDuplicate has already verified that student_id is not present in students.
  - InsertStudent must trust that parent guarantee.
  - Duplicate input is a caller contract violation, not this node's responsibility.""",
    },
    "strict_closed_boundary": {
        "description": "Strong closed-world boundary and forbidden checks.",
        "expected_defense": False,
        "extra": """

Strict Boundary Rules:
  - This node has a CLOSED responsibility boundary: it may only perform insertion-related work.
  - Parent guarantees are true and must not be revalidated.
  - Do not add any child whose purpose is checking, validating, guarding, formatting errors, or handling duplicates.
  - Do not decompose this node into read-before-write steps.
  - If you think a duplicate check is needed, that means you are violating this node's boundary.
  - No read access is available or needed.""",
    },
    "positive_control_defense_required": {
        "description": "Positive control: duplicate check is explicitly required.",
        "expected_defense": True,
        "replace_node_block": """Node Name: InsertStudent
Node Purpose: Safely insert new student record into students data store

Task Description:
  The function receives a student_id and student_name from its parent.
  This node itself is responsible for checking whether student_id already exists.
  If student_id already exists, it must avoid insertion and return failure.
  If student_id does not exist, it inserts the new student record into students.
  It returns whether the insertion succeeded.

Inputs:
  - student_id: str - Student identifier to check and insert
  - student_name: str - Student name

Outputs:
  - success: bool - Whether the student record was inserted successfully

Boundary:
  In Scope:
    - Check whether student_id already exists
    - Insert student_id and student_name if unique
    - Return success or failure
  Out of Scope:
    - Input parsing
    - Formatting detailed error messages
    - Listing students
    - Updating existing students

Preconditions:
  - student_id is provided
  - student_name is provided

Postconditions:
  - If student_id was unique, student record is inserted
  - If student_id was duplicate, no insertion occurs

Global Variables (for context — Stage 3 will distribute these):
  - read_write on students: Check duplicate and insert a new student record.

Maximum children allowed: 5
Maximum depth: 5
Return ONLY the JSON response.""",
    },
}


DEFENSE_PATTERNS = {
    "duplicate_check": [
        r"\bcheck(?:ing)?\b.*\bduplicate\b",
        r"\bduplicate\b.*\bcheck(?:ing)?\b",
        r"\bdetect(?:ing)?\b.*\bduplicate\b",
        r"\balready exists\b",
        r"\bCheckDuplicate\b",
    ],
    "existence_or_lookup_check": [
        r"\bcheck(?:ing)?\b.*\bexist",
        r"\bexistence\b.*\bcheck",
        r"\blookup\b", r"\blook up\b",
        r"\bquery\b.*\bstudents\b",
        r"\bread\b.*\bstudents\b", r"\bstudents\b.*\bread\b",
    ],
    "input_validation": [
        r"\bvalidate\b", r"\bvalidation\b", r"\bvalidating\b",
        r"\bsanitize\b", r"\bguard\b", r"\bensure\b",
        r"\bnon[- ]?empty\b", r"\btype check\b",
    ],
    "error_or_fallback_handling": [
        r"\berror\b", r"\bfallback\b", r"\bdefault\b",
        r"\bnot found\b", r"\binvalid\b",
        r"\bhandle\b.*\b(error|case|invalid|duplicate)\b",
        r"\bformat\b.*\berror\b",
    ],
    "parent_guarantee_revalidation": [
        r"\brevalidat", r"\bverify\b.*\bparent guarantee\b",
        r"\bcheck\b.*\bparent guarantee\b",
    ],
}


def build_user_prompt(condition_id: str) -> str:
    condition = CONDITIONS[condition_id]
    node_block = condition.get("replace_node_block", BASE_NODE_BLOCK)
    extra = condition.get("extra", "")
    return "\n".join([
        "Stage 1 — Decompose into child functions. Output STRUCTURE ONLY (no interfaces, no resources).",
        "",
        node_block,
        extra.strip() if extra else "",
    ]).strip()


def parse_json_response(text: str) -> Dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    if "}" in raw:
        raw = raw[:raw.rfind("}") + 1]
    raw = re.sub(r'(?<=[\s:,\[{])[fFrRuUbB]+(")', r'\1', raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return {"error": "JSON parse failed", "raw": text[:1000]}


def flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(flatten_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(flatten_text(v) for v in value)
    return str(value) if value is not None else ""


def judge_defense(parsed: Dict[str, Any], condition_id: str) -> Dict[str, Any]:
    children = parsed.get("children", []) if isinstance(parsed, dict) else []
    evidence: List[Dict[str, str]] = []
    categories = {k: False for k in DEFENSE_PATTERNS}
    out_of_scope_violation = False

    for child in children:
        child_name = child.get("name", "")
        boundary = child.get("boundary", {}) if isinstance(child.get("boundary", {}), dict) else {}
        searchable_fields = {
            "name": child_name,
            "purpose": child.get("purpose", ""),
            "behavior": child.get("behavior", ""),
            # Only in_scope is an active responsibility. out_of_scope often
            # repeats forbidden checks and should count as compliance, not
            # defensive overreach.
            "boundary_in_scope": flatten_text(boundary.get("in_scope", [])),
            "postconditions": flatten_text(child.get("postconditions", [])),
            "guarantees": flatten_text(child.get("guarantees", [])),
            "semantic_outputs": flatten_text(child.get("semantic_outputs", [])),
            "composition_role": child.get("composition_role", ""),
        }
        text_by_field = {k: v for k, v in searchable_fields.items() if v}
        combined = " ".join(text_by_field.values())

        for category, patterns in DEFENSE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    categories[category] = True
                    field = next(
                        (fname for fname, ftext in text_by_field.items()
                         if re.search(pattern, ftext, re.IGNORECASE)),
                        "combined",
                    )
                    evidence.append({
                        "child": child_name,
                        "category": category,
                        "field": field,
                        "pattern": pattern,
                        "summary": text_by_field.get(field, combined)[:300],
                    })
                    break

    out_of_scope_violation = any(categories.values())

    required_defense = CONDITIONS[condition_id]["expected_defense"]
    defense_present = any(categories.values())
    defensive_overreach = defense_present and not required_defense
    required_defense_missing = required_defense and not defense_present

    if defensive_overreach:
        verdict = "DEFENSIVE_OVERREACH"
    elif required_defense_missing:
        verdict = "REQUIRED_DEFENSE_MISSING"
    elif required_defense and defense_present:
        verdict = "REQUIRED_DEFENSE_PRESENT"
    else:
        verdict = "NO_DEFENSIVE_OVERREACH"

    return {
        "condition": condition_id,
        "children": [c.get("name", "") for c in children],
        "n_children": len(children),
        "categories": categories,
        "defense_present": defense_present,
        "defensive_overreach": defensive_overreach,
        "required_defense": required_defense,
        "required_defense_missing": required_defense_missing,
        "out_of_scope_violation": out_of_scope_violation,
        "verdict": verdict,
        "evidence": evidence[:20],
        "parse_error": "error" in parsed and not children,
    }


class LLMRunner:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=120)
        self.model = model

    def chat(self, messages: List[Dict[str, str]]) -> str:
        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            response_format={"type": "json_object"},
        )
        try:
            response = self.client.chat.completions.create(
                **kwargs,
                extra_body={"thinking": {"type": "disabled"}},
            )
        except Exception as first_error:
            # Some providers reject the thinking field.
            if "thinking" not in str(first_error).lower():
                raise
            response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Empty model response")
        return content


def save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_text(path: str, data: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)


def run_trial(runner: LLMRunner, output_dir: str, condition_id: str, trial: int) -> Dict[str, Any]:
    trial_dir = os.path.join(output_dir, condition_id, f"trial_{trial:02d}")
    messages = [
        {"role": "system", "content": STAGE1_SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(condition_id)},
    ]
    save_json(os.path.join(trial_dir, "request.json"), {
        "condition": condition_id,
        "trial": trial,
        "messages": messages,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "model": runner.model,
    })

    start = time.time()
    error = ""
    raw = ""
    try:
        raw = runner.chat(messages)
    except Exception as exc:
        error = str(exc)
    elapsed = round(time.time() - start, 2)

    save_text(os.path.join(trial_dir, "response_raw.txt"), raw)
    parsed = parse_json_response(raw) if raw else {"error": error or "empty response"}
    save_json(os.path.join(trial_dir, "parsed.json"), parsed)
    judge = judge_defense(parsed, condition_id)
    save_json(os.path.join(trial_dir, "judge.json"), judge)

    result = {
        "condition": condition_id,
        "trial": trial,
        "elapsed": elapsed,
        "error": error,
        "child_names": judge.get("children", []),
        "n_children": judge.get("n_children", 0),
        "judge": judge,
    }
    save_json(os.path.join(trial_dir, "result.json"), result)
    return result


def reanalyze_existing(output_dir: str, condition_ids: List[str]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for condition_id in condition_ids:
        condition_dir = os.path.join(output_dir, condition_id)
        if not os.path.isdir(condition_dir):
            continue
        trial_dirs = sorted(
            d for d in os.listdir(condition_dir)
            if d.startswith("trial_") and os.path.isdir(os.path.join(condition_dir, d))
        )
        for trial_dir_name in trial_dirs:
            trial_str = trial_dir_name.removeprefix("trial_")
            try:
                trial = int(trial_str)
            except ValueError:
                continue
            trial_dir = os.path.join(condition_dir, trial_dir_name)
            parsed_path = os.path.join(trial_dir, "parsed.json")
            if not os.path.exists(parsed_path):
                continue
            with open(parsed_path, "r", encoding="utf-8") as f:
                parsed = json.load(f)
            judge = judge_defense(parsed, condition_id)
            save_json(os.path.join(trial_dir, "judge.json"), judge)
            result = {
                "condition": condition_id,
                "trial": trial,
                "elapsed": 0,
                "error": "",
                "child_names": judge.get("children", []),
                "n_children": judge.get("n_children", 0),
                "judge": judge,
            }
            save_json(os.path.join(trial_dir, "result.json"), result)
            results.append(result)
    return results


def aggregate_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_condition: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for result in results:
        by_condition[result["condition"]].append(result)

    summary: Dict[str, Any] = {}
    for condition_id, rows in by_condition.items():
        valid = [r for r in rows if not r.get("error")]
        n = len(rows)
        overreach = sum(1 for r in valid if r["judge"]["defensive_overreach"])
        defense_present = sum(1 for r in valid if r["judge"]["defense_present"])
        required_missing = sum(1 for r in valid if r["judge"]["required_defense_missing"])
        parse_errors = sum(1 for r in rows if r["judge"].get("parse_error") or r.get("error"))
        category_counts = {
            cat: sum(1 for r in valid if r["judge"]["categories"].get(cat))
            for cat in DEFENSE_PATTERNS
        }
        summary[condition_id] = {
            "description": CONDITIONS[condition_id]["description"],
            "expected_defense": CONDITIONS[condition_id]["expected_defense"],
            "trials": n,
            "valid_trials": len(valid),
            "parse_or_api_errors": parse_errors,
            "defense_present": defense_present,
            "defensive_overreach": overreach,
            "required_defense_missing": required_missing,
            "category_counts": category_counts,
            "child_names_by_trial": [r.get("child_names", []) for r in rows],
        }
    return summary


def generate_report(model: str, results: List[Dict[str, Any]], summary: Dict[str, Any]) -> str:
    lines = [
        "# Stage1 Defensive Overreach Experiment",
        "",
        f"Model: `{model}`",
        f"Temperature: `{TEMPERATURE}`",
        f"Trials: `{len(results)}`",
        "",
        "## Purpose",
        "",
        "Test whether Stage1 decomposition adds defensive checks when the node boundary says the node should only insert a student record.",
        "",
        "## Summary",
        "",
        "| Condition | Expected Defense | Trials | Defense Present | Defensive Overreach | Required Defense Missing | Parse/API Errors |",
        "|-----------|------------------|--------|-----------------|---------------------|--------------------------|------------------|",
    ]

    for condition_id in CONDITIONS:
        s = summary.get(condition_id, {})
        lines.append(
            f"| {condition_id} | {s.get('expected_defense')} | {s.get('trials', 0)} | "
            f"{s.get('defense_present', 0)} | {s.get('defensive_overreach', 0)} | "
            f"{s.get('required_defense_missing', 0)} | {s.get('parse_or_api_errors', 0)} |"
        )

    lines.extend(["", "## Category Counts", ""])
    lines.append("| Condition | duplicate | existence/lookup | input validation | error/fallback | parent guarantee revalidation |")
    lines.append("|-----------|-----------|------------------|------------------|----------------|-------------------------------|")
    for condition_id in CONDITIONS:
        counts = summary.get(condition_id, {}).get("category_counts", {})
        lines.append(
            f"| {condition_id} | {counts.get('duplicate_check', 0)} | "
            f"{counts.get('existence_or_lookup_check', 0)} | {counts.get('input_validation', 0)} | "
            f"{counts.get('error_or_fallback_handling', 0)} | {counts.get('parent_guarantee_revalidation', 0)} |"
        )

    lines.extend(["", "## Per-Trial Details", ""])
    for result in results:
        judge = result["judge"]
        lines.append(f"### {result['condition']} / trial_{result['trial']:02d}")
        if result.get("error"):
            lines.append(f"- Error: {result['error']}")
            lines.append("")
            continue
        lines.append(f"- Children: {', '.join(result.get('child_names', []))}")
        lines.append(f"- Verdict: `{judge['verdict']}`")
        lines.append(f"- Categories: {json.dumps(judge['categories'], ensure_ascii=False)}")
        if judge.get("evidence"):
            lines.append("- Evidence:")
            for item in judge["evidence"][:5]:
                lines.append(
                    f"  - {item['child']} / {item['category']} / {item['field']}: "
                    f"{item['summary']}"
                )
        lines.append("")

    lines.extend([
        "## Notes",
        "",
        "- The judge is deterministic keyword/field based; manually inspect raw responses for borderline cases.",
        "- `positive_control_defense_required` should produce defense. If it does not, the model likely ignored task requirements.",
        "- Defensive overreach in `baseline` or `weak_no_duplicate` indicates out-of-scope text alone is insufficient.",
        "- Defensive overreach in `strict_closed_boundary` indicates prompt-only boundary enforcement is weak.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage1 defensive-overreach experiment")
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--conditions", default=",".join(CONDITIONS.keys()))
    parser.add_argument("--reanalyze-existing", action="store_true",
                        help="Recompute deterministic judge/report from saved parsed.json files without API calls")
    args = parser.parse_args()

    model = args.model or _env("CHRONOS_MODEL", "deepseek-chat")
    if model.startswith("mimo-"):
        base_url = args.base_url or os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
        api_key = args.api_key or os.getenv("MIMO_API_KEY") or _env("CHRONOS_API_KEY")
    else:
        base_url = args.base_url or _env("CHRONOS_BASE_URL", "https://api.deepseek.com")
        api_key = args.api_key or _env("CHRONOS_API_KEY")

    condition_ids = [c.strip() for c in args.conditions.split(",") if c.strip()]
    unknown = [c for c in condition_ids if c not in CONDITIONS]
    if unknown:
        print(f"ERROR: unknown conditions: {unknown}")
        print(f"Available: {list(CONDITIONS)}")
        return 1

    output_dir = os.path.join(OUTPUT_BASE, model)
    os.makedirs(output_dir, exist_ok=True)

    print(f"Model: {model}")
    print(f"Conditions: {condition_ids}")
    print(f"Trials per condition: {args.trials}")
    print(f"Output: {output_dir}")

    results: List[Dict[str, Any]] = []
    if args.reanalyze_existing:
        print("Reanalyzing existing parsed responses; no API calls will be made.")
        results = reanalyze_existing(output_dir, condition_ids)
        for result in results:
            judge = result["judge"]
            print(
                f"  {result['condition']}/trial_{result['trial']:02d}: "
                f"{judge['verdict']} children={result['child_names']}"
            )
    else:
        if not api_key:
            print("ERROR: set CHRONOS_API_KEY or DEEPSEEK_API_KEY")
            return 1
        runner = LLMRunner(api_key=api_key, base_url=base_url, model=model)
        for condition_id in condition_ids:
            print(f"\nCondition: {condition_id}")
            for trial in range(args.trials):
                result = run_trial(runner, output_dir, condition_id, trial)
                results.append(result)
                if result.get("error"):
                    print(f"  trial_{trial:02d}: ERROR {result['error'][:120]}")
                else:
                    judge = result["judge"]
                    print(
                        f"  trial_{trial:02d}: {judge['verdict']} "
                        f"children={result['child_names']}"
                    )

    summary = aggregate_results(results)
    payload = {
        "experiment": "defensive_overreach_stage1",
        "model": model,
        "temperature": TEMPERATURE,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "conditions": CONDITIONS,
        "summary": summary,
        "results": results,
    }
    save_json(os.path.join(output_dir, "results.json"), payload)
    save_text(os.path.join(output_dir, "report.md"), generate_report(model, results, summary))

    print("\nSummary:")
    for condition_id in condition_ids:
        s = summary[condition_id]
        print(
            f"  {condition_id}: defense={s['defense_present']}/{s['valid_trials']}, "
            f"overreach={s['defensive_overreach']}/{s['valid_trials']}, "
            f"required_missing={s['required_defense_missing']}/{s['valid_trials']}"
        )
    print(f"\nSaved results to: {os.path.join(output_dir, 'results.json')}")
    print(f"Saved report to: {os.path.join(output_dir, 'report.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
