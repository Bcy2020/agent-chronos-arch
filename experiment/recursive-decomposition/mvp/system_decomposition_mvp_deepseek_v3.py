#!/usr/bin/env python3
"""
DeepSeek-compatible recursive system decomposition MVP with layered temperatures
and stricter interface-preservation prompting.
"""
import argparse
import json
import os
import re
from typing import Any, Dict, List, Optional
import requests


class AgentContext:
    def __init__(self, description: str, depth: int, parent: Optional["AgentContext"] = None, phase: str = "recursive") -> None:
        self.description = description
        self.depth = depth
        self.parent = parent
        self.phase = phase
        self.children: List["AgentContext"] = []

    def minimal_context(self) -> str:
        return self.description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "depth": self.depth,
            "phase": self.phase,
            "children": [child.to_dict() for child in self.children],
        }


class Decomposer:
    def __init__(
        self,
        provider: str,
        base_url: str,
        api_key: Optional[str],
        model: str,
        max_depth: int,
        max_children: int,
        timeout: int,
        root_temperature: float,
        recursive_temperature: float,
        proof_temperature: float,
    ) -> None:
        self.provider = provider.lower()
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.api_key = api_key
        self.model = model
        self.max_depth = max_depth
        self.max_children = max_children
        self.timeout = timeout
        self.root_temperature = root_temperature
        self.recursive_temperature = recursive_temperature
        self.proof_temperature = proof_temperature

    def _chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def _temperature_for(self, ctx: AgentContext) -> float:
        if ctx.depth == 0:
            return self.root_temperature
        # deeper layers are proof-heavy in this MVP
        if ctx.depth >= 1:
            return self.proof_temperature if ctx.depth >= 2 else self.recursive_temperature
        return self.recursive_temperature

    def _stub_children(self, ctx: AgentContext) -> List[str]:
        phrases = re.split(r"[\.;\n]", ctx.description)
        return [p.strip() for p in phrases if p.strip() and len(p.strip().split()) > 3][: self.max_children]

    def _build_messages(self, ctx: AgentContext) -> List[Dict[str, str]]:
        system = (
            "You are a software system decomposition agent. "
            "Decompose the given function block into a small set of child blocks. "
            "Use only the provided current block context. "
            "Every child must have explicit inputs, outputs, purpose, and boundaries. "
            "Preserve the parent external interface at the composition level. "
            "Do NOT introduce implied router, aggregator, orchestrator, or hidden components. "
            "If coordination is needed, create an explicit child node for it. "
            "Do NOT expose extra external inputs or outputs at the parent level. "
            "Intermediate artifacts must be listed only as internal interfaces. "
            "Return strict JSON with shape "
            '{"children":[{"name":"...","purpose":"...","inputs":["..."],"outputs":["..."],'
            '"boundary":{"in_scope":["..."],"out_of_scope":["..."]},'
            '"child_interaction_flow":["..."],"coverage_explanation":"...",'
            '"interface_preservation_proof":{"parent_inputs_covered_by":{},'
            '"parent_outputs_produced_by":{},"extra_external_inputs_required":[],'
            '"extra_external_outputs":[]},'
            '"internal_interfaces":["..."],'
            '"external_interface":{"inputs":["..."],"outputs":["..."]},'
            '"uncovered_responsibilities":[],"duplicate_conflict_notes":[],"stop_decompose":false,"stop_reason":""}]} '
            f"Limit children to at most {self.max_children}. "
            "Children should be cohesive, minimally overlapping, and at the same abstraction level."
        )
        user = (
            f"Current block depth: {ctx.depth}\n"
            f"Current block description:\n{ctx.minimal_context()}\n\n"
            "Return only JSON."
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def _parse_content(self, content: str) -> List[Dict[str, Any]]:
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[a-zA-Z0-9]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        data = json.loads(content)
        children = data.get("children", [])
        if not isinstance(children, list):
            return []
        return [c for c in children if isinstance(c, dict)]

    def _remote_decompose(self, ctx: AgentContext) -> List[Dict[str, Any]]:
        if not self.base_url or self.base_url == "stub":
            return [
                {
                    "name": f"Child{i+1}",
                    "purpose": desc,
                    "inputs": ["parent_input"],
                    "outputs": ["parent_output"],
                    "boundary": {"in_scope": [desc], "out_of_scope": []},
                    "child_interaction_flow": [],
                    "coverage_explanation": "",
                    "interface_preservation_proof": {
                        "parent_inputs_covered_by": {},
                        "parent_outputs_produced_by": {},
                        "extra_external_inputs_required": [],
                        "extra_external_outputs": [],
                    },
                    "internal_interfaces": [],
                    "external_interface": {"inputs": ["parent_input"], "outputs": ["parent_output"]},
                    "uncovered_responsibilities": [],
                    "duplicate_conflict_notes": [],
                    "stop_decompose": ctx.depth + 1 >= self.max_depth,
                    "stop_reason": "Reached configured max depth" if ctx.depth + 1 >= self.max_depth else "",
                }
                for i, desc in enumerate(self._stub_children(ctx))
            ]

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(ctx),
            "response_format": {"type": "json_object"},
            "temperature": self._temperature_for(ctx),
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        resp = requests.post(self._chat_completions_url(), json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return self._parse_content(content)

    def _validate_child(self, child: Dict[str, Any]) -> Dict[str, Any]:
        child.setdefault("inputs", [])
        child.setdefault("outputs", [])
        child.setdefault("boundary", {"in_scope": [], "out_of_scope": []})
        child.setdefault("child_interaction_flow", [])
        child.setdefault("coverage_explanation", "")
        child.setdefault("interface_preservation_proof", {
            "parent_inputs_covered_by": {},
            "parent_outputs_produced_by": {},
            "extra_external_inputs_required": [],
            "extra_external_outputs": [],
        })
        child.setdefault("internal_interfaces", [])
        child.setdefault("external_interface", {"inputs": child.get("inputs", []), "outputs": child.get("outputs", [])})
        child.setdefault("uncovered_responsibilities", [])
        child.setdefault("duplicate_conflict_notes", [])
        child.setdefault("stop_decompose", False)
        child.setdefault("stop_reason", "")
        return child

    def decompose(self, node: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
        if depth >= self.max_depth or node.get("stop_decompose"):
            node["stop_decompose"] = True
            node["stop_reason"] = node.get("stop_reason") or "Reached configured max depth"
            node.setdefault("children", [])
            return node

        ctx = AgentContext(description=node["purpose"], depth=depth)
        try:
            raw_children = self._remote_decompose(ctx)
        except Exception as e:
            node.setdefault("local_validation_notes", []).append(f"API error, used empty children: {e}")
            raw_children = []

        children: List[Dict[str, Any]] = []
        for child in raw_children[: self.max_children]:
            c = self._validate_child(child)
            c["depth"] = depth + 1
            c["parent_contract"] = node.get("name", "")
            c.setdefault("name", f"Node{depth+1}")
            c.setdefault("purpose", "")
            c = self.decompose(c, depth + 1)
            children.append(c)

        node["children"] = children
        return node


def extract_root_contract(prd_text: str) -> Dict[str, Any]:
        lines = [line.strip() for line in prd_text.splitlines() if line.strip()]
        desc = " ".join(lines[:8])
        return {
            "name": "RootSystem",
            "purpose": desc,
            "inputs": [],
            "outputs": [],
            "boundary": {"in_scope": [], "out_of_scope": []},
            "depth": 0,
            "parent_contract": "",
            "stop_decompose": False,
            "stop_reason": "",
            "duplicate_conflict_notes": [],
            "child_interaction_flow": [],
            "coverage_explanation": "",
            "interface_preservation_proof": {
                "parent_inputs_covered_by": {},
                "parent_outputs_produced_by": {},
                "extra_external_inputs_required": [],
                "extra_external_outputs": [],
            },
            "internal_interfaces": [],
            "external_interface": {"inputs": [], "outputs": []},
            "uncovered_responsibilities": [],
            "local_validation_notes": [],
            "children": [],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Recursive system decomposition MVP with DeepSeek compatibility")
    parser.add_argument("--input", required=True, help="Path to the PRD file")
    parser.add_argument("--provider", default="deepseek", help="Provider name, e.g. deepseek")
    parser.add_argument("--base-url", default="stub", help="API base URL or 'stub'")
    parser.add_argument("--api-key", default=None, help="API key")
    parser.add_argument("--model", default="deepseek-chat", help="Model name")
    parser.add_argument("--max-depth", type=int, default=2, help="Maximum recursion depth")
    parser.add_argument("--max-children", type=int, default=4, help="Maximum children per node")
    parser.add_argument("--timeout", type=int, default=120, help="HTTP timeout in seconds")
    parser.add_argument("--root-excerpt-chars", type=int, default=1600, help="Reserved arg for compatibility")
    parser.add_argument("--root-temperature", type=float, default=0.15, help="Temperature for root decomposition")
    parser.add_argument("--recursive-temperature", type=float, default=0.0, help="Temperature for recursive decomposition")
    parser.add_argument("--proof-temperature", type=float, default=0.0, help="Temperature for proof-heavy deeper decomposition")
    parser.add_argument("--output", help="Path to write JSON output")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        prd_text = f.read()

    root = extract_root_contract(prd_text)
    decomposer = Decomposer(
        provider=args.provider,
        base_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
        max_depth=args.max_depth,
        max_children=args.max_children,
        timeout=args.timeout,
        root_temperature=args.root_temperature,
        recursive_temperature=args.recursive_temperature,
        proof_temperature=args.proof_temperature,
    )
    tree = decomposer.decompose(root, 0)
    out = json.dumps(tree, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"Decomposition saved to {args.output}")
    else:
        print(out)


if __name__ == "__main__":
    main()
