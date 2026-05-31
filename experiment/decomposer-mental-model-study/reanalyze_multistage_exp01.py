"""
Rejudge Exp01 outputs using corrected criteria from guides/EXP01_EXP03_REJUDGE_GUIDE.md.

Primary evidence: dataflow_sketch
Secondary: behavior, purpose for control-call confirmation

Reads raw LLM responses from 0001_response.json, not old result.json.
"""

import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
INPUT_DIR = SCRIPT_DIR / "output" / "multistage_exp01_stage1_routing" / "deepseek-v4-flash"
OUTPUT_DIR = SCRIPT_DIR / "output" / "multistage_exp01_stage1_routing_rejudged" / "deepseek-v4-flash"

DOMAINS = ["Order", "Chat", "Patient", "BuildSystem", "DataPipeline"]

# --- Router-like name patterns (from guide 3.3) ---
ROUTER_NAME_PATTERNS = [
    r"^Route",
    r"Router$",
    r"^Dispatch",
    r"Dispatcher$",
    r"^Coordinator$",
    r"^CommandHandler$",
    r"^Controller$",
]
# NOT router-like by themselves
NOT_ROUTER_PATTERNS = [
    r"^Parse",
    r"^Validate",
    r"^ProcessCommand",
]

# --- Control-call semantics (hard routing evidence) ---
CONTROL_CALL_VERBS = [
    r"\bcalls?\b", r"\binvoke[sd]?\b", r"\bdispatch(?:es|ed|ing)?\b",
    r"\broute[sd]?\b", r"\bdelegat(?:es|ed|ing)?\b", r"\bselects?\b.*\bchild\b",
    r"\bwhich child to call\b", r"\broute to handler\b", r"\bdispatch to\b",
    r"\bselect which\b", r"\brouting\b.*\bcommand\b",
]

# --- Parent-orchestration keywords ---
PARENT_ORCHESTRATION_KEYWORDS = [
    r"\bparent orchestrates\b", r"\bparent selects\b", r"\bparent passes\b",
    r"\bparent decides\b", r"\bparent routes\b", r"\bparent invokes\b",
    r"\bparent calls\b", r"\bthe parent\b.*\bbased on\b",
]


def parse_response(filepath):
    """Parse 0001_response.json and extract the LLM output JSON."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    raw = data.get("response", "")
    # Try to parse the response string as JSON
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        m = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        return {"error": "parse_failed", "raw": raw[:500]}


def is_router_name(name):
    """Check if a child name matches router-like patterns."""
    for pat in ROUTER_NAME_PATTERNS:
        if re.search(pat, name, re.IGNORECASE):
            # But not if it matches NOT_ROUTER_PATTERNS
            for nrpat in NOT_ROUTER_PATTERNS:
                if re.search(nrpat, name, re.IGNORECASE):
                    return False
            return True
    return False


def has_control_call_text(text):
    """Check if text contains explicit control-call semantics."""
    if not text:
        return False
    for pat in CONTROL_CALL_VERBS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def has_parent_orchestration_text(text):
    """Check if text contains parent-orchestration keywords."""
    if not text:
        return False
    for pat in PARENT_ORCHESTRATION_KEYWORDS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def normalize_node_name(name):
    """Normalize a node name from dataflow edge."""
    name = name.strip()
    if name.lower() in ("parent", "parent input", "parent output"):
        return "parent"
    return name


def judge_trial(parsed):
    """Apply rejudge criteria to a single trial's parsed output."""
    evidence = []
    children = parsed.get("children", [])
    dataflow = parsed.get("dataflow_sketch", [])
    rationale = parsed.get("decomposition_rationale", "")
    child_names = {c.get("name", "") for c in children}

    # Build child lookup
    child_map = {}
    for c in children:
        child_map[c.get("name", "")] = c

    # --- Classify dataflow edges ---
    sibling_edges = []  # (from, to, edge) where both are non-parent children
    parent_mediated_edges = []  # edges involving parent
    for edge in dataflow:
        src = normalize_node_name(edge.get("from", ""))
        dst = normalize_node_name(edge.get("to", ""))
        if src == "parent" or dst == "parent":
            parent_mediated_edges.append(edge)
        elif src in child_names and dst in child_names:
            sibling_edges.append((src, dst, edge))

    # --- Check each child for router characteristics ---
    router_nodes = []
    for c in children:
        name = c.get("name", "")
        purpose = c.get("purpose", "")
        behavior = c.get("behavior", "")
        combined = f"{purpose} {behavior}"

        if is_router_name(name):
            if has_control_call_text(combined):
                router_nodes.append(name)
                evidence.append({
                    "category": "router_node",
                    "field": "child.purpose+behavior",
                    "child": name,
                    "target": "",
                    "snippet": f"Name matches router pattern; purpose/behavior: {combined[:200]}",
                    "reason": f"Router-like name '{name}' with control-call semantics in purpose/behavior"
                })

    # --- Check sibling edges for control-call semantics ---
    hard_routing_sibling_calls = []
    ambiguous_sibling_calls = []
    for src, dst, edge in sibling_edges:
        src_child = child_map.get(src, {})
        src_behavior = f"{src_child.get('purpose', '')} {src_child.get('behavior', '')}"
        note = edge.get("note", "")

        if has_control_call_text(src_behavior) or has_control_call_text(note):
            hard_routing_sibling_calls.append((src, dst, edge))
            evidence.append({
                "category": "hard_routing",
                "field": "dataflow_sketch",
                "child": src,
                "target": dst,
                "snippet": f"{src} -> {dst}: {note}",
                "reason": f"Sibling edge with control-call semantics in source child's behavior or edge note"
            })
        else:
            ambiguous_sibling_calls.append((src, dst, edge))
            evidence.append({
                "category": "ambiguous_direct_dataflow",
                "field": "dataflow_sketch",
                "child": src,
                "target": dst,
                "snippet": f"{src} -> {dst}: {note}",
                "reason": "Sibling-to-sibling edge without explicit control-call wording"
            })

    # --- Check for parent-mediated dataflow ---
    parent_mediated = False
    for edge in parent_mediated_edges:
        src = normalize_node_name(edge.get("from", ""))
        dst = normalize_node_name(edge.get("to", ""))
        if src in child_names and dst == "parent":
            child = child_map.get(src, {})
            consumers = []
            for so in child.get("semantic_outputs", []):
                consumers.append(so.get("consumer", ""))
            if "parent" in consumers:
                parent_mediated = True
                evidence.append({
                    "category": "parent_mediated_dataflow",
                    "field": "semantic_outputs",
                    "child": src,
                    "target": "parent",
                    "snippet": f"consumer=parent for {src}'s output",
                    "reason": "Child returns data to parent; parent orchestrates"
                })

    # Check rationale for parent orchestration
    if has_parent_orchestration_text(rationale):
        parent_mediated = True
        evidence.append({
            "category": "parent_mediated_dataflow",
            "field": "decomposition_rationale",
            "child": "",
            "target": "parent",
            "snippet": rationale[:300],
            "reason": "Rationale indicates parent orchestration"
        })

    # --- Check for traditional naming residue ---
    traditional_naming = False
    for c in children:
        name = c.get("name", "")
        purpose = c.get("purpose", "")
        behavior = c.get("behavior", "")
        if re.search(r"Handler$", name) and not has_control_call_text(f"{purpose} {behavior}"):
            traditional_naming = True
            evidence.append({
                "category": "traditional_naming_residue",
                "field": "child.name",
                "child": name,
                "target": "",
                "snippet": f"Name ends with 'Handler' but does real work",
                "reason": "Handler-style name with real business work, not a router"
            })

    # --- Check for abstraction-level mixing (weak signal) ---
    abstraction_mixing = False
    # Heuristic: if a high-level workflow child (e.g., PlaceOrder) exists alongside
    # its internal steps (e.g., ValidateItemsAndStock, ChargePayment)
    workflow_children = []
    step_children = []
    for c in children:
        name = c.get("name", "")
        purpose = c.get("purpose", "").lower()
        if any(w in purpose for w in ["workflow", "orchestrat", "execute the", "handle the entire"]):
            workflow_children.append(name)
    # Check if any step-like children are referenced by workflow children in dataflow
    for wf_name in workflow_children:
        for src, dst, edge in sibling_edges:
            if src == wf_name or dst == wf_name:
                step_name = dst if src == wf_name else src
                if step_name not in workflow_children:
                    abstraction_mixing = True
                    evidence.append({
                        "category": "abstraction_level_mixing_weak_signal",
                        "field": "dataflow_sketch",
                        "child": wf_name,
                        "target": step_name,
                        "snippet": f"{wf_name} <-> {step_name}",
                        "reason": "High-level workflow child coexists with its internal steps as siblings"
                    })

    # --- Compute verdicts ---
    hard_routing = len(hard_routing_sibling_calls) > 0 or len(router_nodes) > 0
    sibling_invocation = len(hard_routing_sibling_calls) > 0

    # Field completion
    total_fields = 0
    present_fields = 0
    required_fields = ["name", "purpose", "behavior", "boundary", "semantic_inputs",
                       "semantic_outputs", "preconditions", "postconditions", "guarantees",
                       "composition_role", "stop_decompose"]
    for c in children:
        for f in required_fields:
            total_fields += 1
            if c.get(f) is not None:
                present_fields += 1

    field_completion = present_fields / total_fields if total_fields > 0 else 0
    child_count = len(children)
    child_count_violation = child_count > 10 or child_count < 2

    return {
        "hard_routing": hard_routing,
        "sibling_invocation": sibling_invocation,
        "router_node": len(router_nodes) > 0,
        "parent_mediated_dataflow": parent_mediated,
        "ambiguous_direct_dataflow": len(ambiguous_sibling_calls) > 0,
        "traditional_naming_residue": traditional_naming,
        "abstraction_level_mixing_weak_signal": abstraction_mixing,
        "field_completion_rate": round(field_completion, 4),
        "child_count_violation": child_count_violation,
        "n_children": child_count,
        "child_names": [c.get("name", "") for c in children],
        "router_nodes": router_nodes,
        "hard_routing_sibling_calls": [
            {"from": s, "to": d, "note": e.get("note", "")} for s, d, e in hard_routing_sibling_calls
        ],
        "ambiguous_sibling_calls": [
            {"from": s, "to": d, "note": e.get("note", "")} for s, d, e in ambiguous_sibling_calls
        ],
    }


def get_old_judge(old_results, domain, trial_idx):
    """Find old judge result for a given domain and trial index."""
    for r in old_results:
        if r.get("domain") == domain and r.get("trial") == trial_idx:
            return r
    return None


def main():
    old_results_path = INPUT_DIR / "results.json"
    with open(old_results_path, "r", encoding="utf-8") as f:
        old_results = json.load(f)

    all_trials = []
    for domain in DOMAINS:
        domain_dir = INPUT_DIR / domain
        if not domain_dir.exists():
            continue
        for trial_dir in sorted(domain_dir.iterdir()):
            if not trial_dir.is_dir() or not trial_dir.name.startswith("trial_"):
                continue
            trial_idx = int(trial_dir.name.split("_")[1])
            response_file = trial_dir / "0001_response.json"
            if not response_file.exists():
                continue

            parsed = parse_response(response_file)
            if "error" in parsed and "children" not in parsed:
                all_trials.append({
                    "domain": domain,
                    "trial": trial_idx,
                    "label": f"{domain}_{trial_idx:02d}",
                    "parse_error": True,
                    "error": parsed.get("error"),
                })
                continue

            new_judge = judge_trial(parsed)
            old_judge = get_old_judge(old_results, domain, trial_idx)
            old_has_routing = old_judge.get("has_routing", None) if old_judge else None

            changed = old_has_routing != new_judge["hard_routing"]

            all_trials.append({
                "domain": domain,
                "trial": trial_idx,
                "label": f"{domain}_{trial_idx:02d}",
                "old_judge": {
                    "has_routing": old_has_routing,
                    "sibling_calls": old_judge.get("sibling_calls", []) if old_judge else [],
                    "has_toplevel_routing": old_judge.get("has_toplevel_routing", None) if old_judge else None,
                },
                "new_judge": new_judge,
                "changed": changed,
                "evidence": [e for e in _collect_evidence(parsed, new_judge)],
            })

    # Compute aggregate metrics
    valid_trials = [t for t in all_trials if not t.get("parse_error")]
    n = len(valid_trials)
    metrics = {
        "total_trials": n,
        "hard_routing_rate": sum(1 for t in valid_trials if t["new_judge"]["hard_routing"]) / n if n else 0,
        "sibling_invocation_rate": sum(1 for t in valid_trials if t["new_judge"]["sibling_invocation"]) / n if n else 0,
        "router_node_rate": sum(1 for t in valid_trials if t["new_judge"]["router_node"]) / n if n else 0,
        "parent_mediated_dataflow_rate": sum(1 for t in valid_trials if t["new_judge"]["parent_mediated_dataflow"]) / n if n else 0,
        "ambiguous_direct_dataflow_rate": sum(1 for t in valid_trials if t["new_judge"]["ambiguous_direct_dataflow"]) / n if n else 0,
        "traditional_naming_residue_rate": sum(1 for t in valid_trials if t["new_judge"]["traditional_naming_residue"]) / n if n else 0,
        "abstraction_level_mixing_weak_signal_rate": sum(1 for t in valid_trials if t["new_judge"]["abstraction_level_mixing_weak_signal"]) / n if n else 0,
        "field_completion_rate": sum(t["new_judge"]["field_completion_rate"] for t in valid_trials) / n if n else 0,
        "child_count_violation_rate": sum(1 for t in valid_trials if t["new_judge"]["child_count_violation"]) / n if n else 0,
    }

    # Old metrics for comparison
    old_routing_count = sum(1 for t in valid_trials if t.get("old_judge", {}).get("has_routing"))
    old_metrics = {
        "old_routing_rate": old_routing_count / n if n else 0,
        "old_routing_count": old_routing_count,
    }

    # Count changes
    downgraded = [t for t in valid_trials if t.get("changed") and not t["new_judge"]["hard_routing"]]
    remained_routing = [t for t in valid_trials if t["new_judge"]["hard_routing"]]

    # Write results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {
        "model": "deepseek-v4-flash",
        "metrics": metrics,
        "old_metrics": old_metrics,
        "downgraded_count": len(downgraded),
        "remained_routing_count": len(remained_routing),
        "trials": all_trials,
    }
    with open(OUTPUT_DIR / "results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    # Write report
    report = generate_report(results)
    with open(OUTPUT_DIR / "report.md", "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Rejudge complete. Output: {OUTPUT_DIR}")
    print(f"Hard routing: {metrics['hard_routing_rate']:.1%} ({sum(1 for t in valid_trials if t['new_judge']['hard_routing'])}/{n})")
    print(f"Old routing: {old_metrics['old_routing_rate']:.1%} ({old_metrics['old_routing_count']}/{n})")
    print(f"Downgraded: {len(downgraded)}")


def _collect_evidence(parsed, new_judge):
    """Collect evidence entries for a trial."""
    evidence = []
    children = parsed.get("children", [])
    dataflow = parsed.get("dataflow_sketch", [])
    rationale = parsed.get("decomposition_rationale", "")
    child_map = {c.get("name", ""): c for c in children}
    child_names = set(child_map.keys())

    # Router nodes
    for name in new_judge.get("router_nodes", []):
        c = child_map.get(name, {})
        evidence.append({
            "category": "router_node",
            "field": "child.purpose+behavior",
            "child": name,
            "target": "",
            "snippet": f"{c.get('purpose', '')} | {c.get('behavior', '')}"[:300],
            "reason": "Router-like name with control-call semantics"
        })

    # Hard routing sibling calls
    for call in new_judge.get("hard_routing_sibling_calls", []):
        src = call["from"]
        c = child_map.get(src, {})
        evidence.append({
            "category": "hard_routing",
            "field": "dataflow_sketch+behavior",
            "child": src,
            "target": call["to"],
            "snippet": f"Edge: {src} -> {call['to']}; note: {call.get('note', '')}",
            "reason": "Sibling edge with control-call semantics"
        })

    # Ambiguous sibling calls
    for call in new_judge.get("ambiguous_sibling_calls", []):
        evidence.append({
            "category": "ambiguous_direct_dataflow",
            "field": "dataflow_sketch",
            "child": call["from"],
            "target": call["to"],
            "snippet": f"{call['from']} -> {call['to']}: {call.get('note', '')}",
            "reason": "Sibling-to-sibling edge without explicit control-call wording"
        })

    # Parent-mediated
    if new_judge.get("parent_mediated_dataflow"):
        evidence.append({
            "category": "parent_mediated_dataflow",
            "field": "decomposition_rationale",
            "child": "",
            "target": "parent",
            "snippet": rationale[:300],
            "reason": "Rationale or semantic_outputs indicate parent orchestration"
        })

    # Traditional naming
    for c in children:
        name = c.get("name", "")
        if re.search(r"Handler$", name) and not has_control_call_text(f"{c.get('purpose', '')} {c.get('behavior', '')}"):
            evidence.append({
                "category": "traditional_naming_residue",
                "field": "child.name",
                "child": name,
                "target": "",
                "snippet": name,
                "reason": "Handler-style name but performs real work"
            })

    return evidence


def generate_report(results):
    """Generate report.md comparing old and new judgments."""
    metrics = results["metrics"]
    old_metrics = results["old_metrics"]
    trials = results["trials"]
    valid_trials = [t for t in trials if not t.get("parse_error")]

    lines = [
        "# Exp01 Rejudge Report",
        "",
        "Model: `deepseek-v4-flash`",
        f"Total trials: {len(valid_trials)}",
        "",
        "## Old vs New Metrics",
        "",
        "| Metric | Old Judge | New Judge |",
        "|--------|-----------|-----------|",
        f"| routing rate | {old_metrics['old_routing_rate']:.1%} ({old_metrics['old_routing_count']}/{len(valid_trials)}) | {metrics['hard_routing_rate']:.1%} ({sum(1 for t in valid_trials if t['new_judge']['hard_routing'])}/{len(valid_trials)}) |",
        f"| parent_mediated_dataflow | N/A | {metrics['parent_mediated_dataflow_rate']:.1%} |",
        f"| ambiguous_direct_dataflow | N/A | {metrics['ambiguous_direct_dataflow_rate']:.1%} |",
        f"| traditional_naming_residue | N/A | {metrics['traditional_naming_residue_rate']:.1%} |",
        f"| abstraction_level_mixing | N/A | {metrics['abstraction_level_mixing_weak_signal_rate']:.1%} |",
        f"| field_completion_rate | {metrics['field_completion_rate']:.1%} | same |",
        f"| child_count_violation | N/A | {metrics['child_count_violation_rate']:.1%} |",
        "",
        "## Verdict",
        "",
    ]

    hr = metrics["hard_routing_rate"]
    if hr <= 0.17:
        lines.append("- **PASS**: Hard routing rate is within the verified 0-17% range.")
    elif hr <= 0.30:
        lines.append("- **INCONCLUSIVE**: Hard routing rate is above target but not clearly systematic.")
    else:
        lines.append("- **FAIL**: Hard routing rate is clearly above target.")

    lines.append("")
    lines.append("## Downgraded Cases (old=routing -> new=not hard_routing)")
    lines.append("")

    downgraded = [t for t in valid_trials if t.get("changed") and not t["new_judge"]["hard_routing"]]
    if downgraded:
        for t in downgraded:
            d = t["domain"]
            ti = t["trial"]
            new = t["new_judge"]
            lines.append(f"### {d}/trial_{ti:02d}")
            lines.append("")
            lines.append(f"- Old: has_routing=True")
            lines.append(f"- New: hard_routing={new['hard_routing']}, parent_mediated={new['parent_mediated_dataflow']}, ambiguous={new['ambiguous_direct_dataflow']}")
            lines.append(f"- Children: {', '.join(new['child_names'])}")
            if new.get("ambiguous_sibling_calls"):
                lines.append(f"- Ambiguous edges: {new['ambiguous_sibling_calls']}")
            # Show key evidence
            key_ev = [e for e in t.get("evidence", []) if e["category"] in ("parent_mediated_dataflow", "ambiguous_direct_dataflow")]
            for e in key_ev[:3]:
                lines.append(f"  - [{e['category']}] {e['snippet'][:150]}")
            lines.append("")
    else:
        lines.append("No cases downgraded.")
        lines.append("")

    lines.append("## Remained Hard Routing")
    lines.append("")
    remained = [t for t in valid_trials if t["new_judge"]["hard_routing"]]
    if remained:
        for t in remained:
            d = t["domain"]
            ti = t["trial"]
            new = t["new_judge"]
            lines.append(f"### {d}/trial_{ti:02d}")
            lines.append("")
            lines.append(f"- Children: {', '.join(new['child_names'])}")
            lines.append(f"- Router nodes: {new.get('router_nodes', [])}")
            lines.append(f"- Hard routing calls: {new.get('hard_routing_sibling_calls', [])}")
            key_ev = [e for e in t.get("evidence", []) if e["category"] == "hard_routing"]
            for e in key_ev[:3]:
                lines.append(f"  - [{e['category']}] {e['snippet'][:200]}")
            lines.append("")
    else:
        lines.append("No trials remain as hard routing.")
        lines.append("")

    # Manual check section
    lines.append("## Manual Check Cases")
    lines.append("")
    manual_cases = [
        ("Order", 1), ("Chat", 2), ("BuildSystem", 0), ("Chat", 0), ("Order", 3)
    ]
    for d, ti in manual_cases:
        t = next((x for x in valid_trials if x["domain"] == d and x["trial"] == ti), None)
        if not t:
            lines.append(f"### {d}/trial_{ti:02d} — NOT FOUND")
            lines.append("")
            continue
        new = t["new_judge"]
        lines.append(f"### {d}/trial_{ti:02d}")
        lines.append("")
        lines.append(f"- **hard_routing**: {new['hard_routing']}")
        lines.append(f"- **parent_mediated_dataflow**: {new['parent_mediated_dataflow']}")
        lines.append(f"- **ambiguous_direct_dataflow**: {new['ambiguous_direct_dataflow']}")
        lines.append(f"- **router_node**: {new['router_node']}")
        lines.append(f"- **abstraction_level_mixing**: {new['abstraction_level_mixing_weak_signal']}")
        lines.append(f"- Children: {', '.join(new['child_names'])}")
        if new.get("router_nodes"):
            lines.append(f"- Router nodes: {new['router_nodes']}")
        if new.get("hard_routing_sibling_calls"):
            lines.append(f"- Hard routing calls: {new['hard_routing_sibling_calls']}")
        if new.get("ambiguous_sibling_calls"):
            lines.append(f"- Ambiguous calls: {new['ambiguous_sibling_calls']}")
        # Key evidence
        for e in t.get("evidence", [])[:5]:
            lines.append(f"  - [{e['category']}] {e.get('child', '')} -> {e.get('target', '')}: {e['snippet'][:150]}")
        lines.append("")

    # Per-domain breakdown
    lines.append("## Per-Domain Breakdown")
    lines.append("")
    lines.append("| Domain | Trials | hard_routing | parent_mediated | ambiguous | naming_residue |")
    lines.append("|--------|--------|-------------|-----------------|-----------|----------------|")
    for d in DOMAINS:
        dt = [t for t in valid_trials if t["domain"] == d]
        if not dt:
            continue
        n = len(dt)
        hr = sum(1 for t in dt if t["new_judge"]["hard_routing"])
        pm = sum(1 for t in dt if t["new_judge"]["parent_mediated_dataflow"])
        am = sum(1 for t in dt if t["new_judge"]["ambiguous_direct_dataflow"])
        nr = sum(1 for t in dt if t["new_judge"]["traditional_naming_residue"])
        lines.append(f"| {d} | {n} | {hr}/{n} | {pm}/{n} | {am}/{n} | {nr}/{n} |")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
