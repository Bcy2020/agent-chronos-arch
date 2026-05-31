"""
Adapter to convert real Stage1 outputs into codegen-ready Node objects.

Parses 0001_response.json from Exp01, converts children/dataflow_sketch/
semantic_inputs/outputs into Node model with DataflowEdge, and records
every normalization in conversion_notes.json.

Do NOT use this in production. This is an experiment-only file.
"""
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "mvp", "mvp-0.4.4"))
from models import (
    Node, InputParam, OutputParam, Boundary, GlobalVar, DataSource,
    ChildContract, DataOperation, DataflowEdge,
)

# Domain parent I/O contracts for this subexperiment
DOMAIN_PARENT_IO = {
    "Order":       {"inputs": ["input"], "outputs": ["output"]},
    "Chat":        {"inputs": ["input"], "outputs": ["output"]},
    "BuildSystem": {"inputs": ["input"], "outputs": ["output"]},
}


def _is_valid_identifier(name: str) -> bool:
    """Check if name is a valid Python identifier."""
    return bool(re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name))


def _split_comma_fields(raw: str) -> List[str]:
    """Split comma-separated field names into individual names."""
    return [f.strip() for f in raw.split(",") if f.strip()]


class RealStage1Adapter:
    """Converts real Stage1 response into codegen-ready Node objects."""

    def __init__(self):
        self.conversion_notes: List[str] = []
        self.domain: str = ""

    def load_response(self, response_path: str) -> Dict[str, Any]:
        """Load and parse the 0001_response.json file."""
        with open(response_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        inner = raw.get("response", "")
        if isinstance(inner, str):
            return json.loads(inner)
        return inner

    def convert(self, response_path: str, case_name: str) -> Tuple[Node, Dict]:
        """
        Convert a Stage1 response into a codegen-ready Node.

        Returns (node, conversion_notes_dict).
        """
        self.conversion_notes = []
        self.domain = case_name.split("/")[0] if "/" in case_name else case_name
        data = self.load_response(response_path)

        children_data = data.get("children", [])
        dataflow_sketch = data.get("dataflow_sketch", [])
        rationale = data.get("decomposition_rationale", "")
        orchestration = data.get("orchestration_model", "")

        # Detect conditional dispatch pattern
        has_formatter = self._detect_formatter(children_data)
        is_conditional = orchestration == "conditional" or self._detect_conditional_dispatch(children_data, dataflow_sketch)
        if is_conditional:
            self.conversion_notes.append("  Detected conditional dispatch pattern")
        if has_formatter:
            self.conversion_notes.append(f"  Detected formatter/aggregator: {has_formatter}")

        # Build child nodes and contracts (excluding internal leaf access)
        child_nodes, contracts_map = self._build_children(children_data, has_formatter)

        # Convert dataflow_sketch to DataflowEdge (split comma fields, parent-local)
        edges = self._convert_dataflow_edges(dataflow_sketch)

        # Use domain contract for parent I/O
        parent_inputs, parent_outputs = self._build_domain_parent_io()

        # Build parent node
        node = Node(
            node_id=f"real_{case_name.replace('/', '_')}",
            name=self._infer_parent_name(),
            purpose=f"Real Stage1 decomposition for {case_name}",
            depth=0,
            inputs=parent_inputs,
            outputs=parent_outputs,
            children=child_nodes,
            children_contracts=contracts_map,
            dataflow_edges=edges,
            decomposition_rationale=rationale,
            global_vars=[],
            data_sources=self._infer_data_sources(children_data),
            boundary=Boundary(),
        )

        # Validate interface names
        validation_errors = self._validate_interface_names(node)

        notes = {
            "case_name": case_name,
            "source_path": response_path,
            "conversion_notes": self.conversion_notes,
            "original_child_count": len(children_data),
            "original_dataflow_edge_count": len(dataflow_sketch),
            "orchestration_model": orchestration,
            "is_conditional_dispatch": is_conditional,
            "formatter_child": has_formatter,
            "parent_inputs": [i.name for i in parent_inputs],
            "parent_outputs": [o.name for o in parent_outputs],
            "validation_errors": validation_errors,
        }

        return node, notes

    def _detect_formatter(self, children_data: List[Dict]) -> Optional[str]:
        """Detect if there's a formatter/aggregator child."""
        for c in children_data:
            role = c.get("composition_role", "").lower()
            if role in ("aggregate", "transform", "format"):
                return c["name"]
            # Also check by name pattern
            name = c["name"].lower()
            if "format" in name or "aggregate" in name:
                return c["name"]
        return None

    def _detect_conditional_dispatch(self, children_data: List[Dict], dataflow_sketch: List[Dict]) -> bool:
        """Detect if this is a conditional dispatch pattern."""
        # Check if multiple children have the same role (execute) and are conditionally called
        handlers = [c for c in children_data if c.get("composition_role", "").lower() == "execute"]
        if len(handlers) >= 2:
            return True
        # Check dataflow sketch for "if command is X" notes
        conditional_notes = [e for e in dataflow_sketch if "if command" in e.get("note", "").lower()]
        if len(conditional_notes) >= 2:
            return True
        return False

    def _build_children(self, children_data: List[Dict], formatter_name: Optional[str]) -> Tuple[List[Node], Dict[str, ChildContract]]:
        """Build child Node objects and ChildContract map from Stage1 children."""
        child_nodes = []
        contracts_map = {}

        for c in children_data:
            name = c["name"]
            purpose = c.get("purpose", "")
            behavior = c.get("behavior", "")

            # Convert semantic_inputs, excluding internal leaf access
            inputs = []
            for si in c.get("semantic_inputs", []):
                source = si.get("source", "")
                source_lower = source.lower().strip()

                # FIX 4: Exclude internal leaf access from child signature
                if source_lower == "internal leaf access":
                    self.conversion_notes.append(
                        f"  {name}: excluded '{si['name']}' (internal leaf access — child accesses internally)"
                    )
                    continue

                # Normalize source
                normalized_source = self._normalize_source(source, name)
                inputs.append(InputParam(
                    name=si["name"],
                    type="Any",
                    description=si.get("description", ""),
                    source=normalized_source,
                ))

            # Convert semantic_outputs
            outputs = []
            for so in c.get("semantic_outputs", []):
                consumer = so.get("consumer", "")
                normalized_consumer = self._normalize_consumer(consumer, name)
                outputs.append(OutputParam(
                    name=so["name"],
                    type="Any",
                    description=so.get("description", ""),
                    consumer=normalized_consumer,
                ))

            # Build signature from cleaned inputs/outputs
            sig_params = ", ".join([f"{i.name}: Any" for i in inputs])
            if len(outputs) == 0:
                sig_return = "None"
            elif len(outputs) == 1:
                sig_return = outputs[0].type
            else:
                sig_return = f"tuple[{', '.join(o.type for o in outputs)}]"
            signature = f"def {name}({sig_params}) -> {sig_return}"

            contract = ChildContract(
                purpose=purpose,
                inputs=inputs,
                outputs=outputs,
                behavior=behavior,
                signature=signature,
                data_operations=[],
            )
            contracts_map[name] = contract

            child_node = Node(
                node_id=f"child_{name}",
                name=name,
                depth=1,
                purpose=purpose,
            )
            child_nodes.append(child_node)

        return child_nodes, contracts_map

    def _normalize_source(self, source: str, child_name: str) -> str:
        """Normalize Stage1 source field to codegen-compatible format."""
        if not source:
            self.conversion_notes.append(f"  {child_name}: empty source -> 'unspecified'")
            return "unspecified"

        source_lower = source.lower().strip()

        if source_lower in ("parent input", "parent"):
            return "parent"
        if "|" in source:
            # Aggregate source — parent mediates
            return "parent"

        # Reference to another child — parent mediates the transfer
        self.conversion_notes.append(
            f"  {child_name}: source '{source}' -> 'parent (mediates from {source})'"
        )
        return "parent"

    def _normalize_consumer(self, consumer: str, child_name: str) -> str:
        """Normalize Stage1 consumer field to codegen-compatible format."""
        if not consumer:
            return "parent"

        consumer_lower = consumer.lower().strip()
        if consumer_lower == "parent":
            return "parent"

        # Consumer references another node — parent mediates
        self.conversion_notes.append(
            f"  {child_name}: consumer '{consumer}' -> 'parent (mediates to {consumer})'"
        )
        return "parent"

    def _convert_dataflow_edges(self, dataflow_sketch: List[Dict]) -> List[DataflowEdge]:
        """Convert Stage1 dataflow_sketch to DataflowEdge objects.

        FIX 6: Split comma-separated data fields into separate edges.
        FIX 2: Treat all child->parent data as parent-local (not external output).
        """
        edges = []
        for entry in dataflow_sketch:
            from_raw = entry.get("from", "")
            to_raw = entry.get("to", "")
            data = entry.get("data", "")
            note = entry.get("note", "")

            from_node = self._normalize_node_ref(from_raw)
            to_node = self._normalize_node_ref(to_raw)

            # Split comma-separated data fields
            fields = _split_comma_fields(data)
            if not fields:
                fields = [data]

            for field in fields:
                # FIX 6: skip fields that are not valid identifiers
                if not _is_valid_identifier(field):
                    self.conversion_notes.append(
                        f"  dataflow edge: skipped non-identifier field '{field}' (from={from_raw}, to={to_raw})"
                    )
                    continue

                edges.append(DataflowEdge(
                    from_node=from_node,
                    from_output=field,
                    to_node=to_node,
                    to_input=field,
                    note=note,
                ))

        return edges

    def _normalize_node_ref(self, ref: str) -> str:
        """Normalize a node reference in dataflow_sketch."""
        ref_lower = ref.lower().strip()
        if ref_lower in ("parent", "parent input"):
            return "parent"
        return ref

    def _build_domain_parent_io(self) -> Tuple[List[InputParam], List[OutputParam]]:
        """FIX 1: Use domain contract for parent I/O, not inferred from dataflow."""
        contract = DOMAIN_PARENT_IO.get(self.domain)
        if not contract:
            self.conversion_notes.append(f"  WARNING: No domain contract for '{self.domain}', using default")
            contract = {"inputs": ["input"], "outputs": ["output"]}

        parent_inputs = [InputParam(
            name=n, type="Any", description=f"Parent input: {n}", source="external"
        ) for n in contract["inputs"]]

        parent_outputs = [OutputParam(
            name=n, type="Any", description=f"Parent output: {n}", consumer="external"
        ) for n in contract["outputs"]]

        return parent_inputs, parent_outputs

    def _infer_parent_name(self) -> str:
        """Infer a parent function name from the domain."""
        name_map = {
            "Order": "ProcessOrder",
            "Chat": "ProcessChatCommand",
            "BuildSystem": "ProcessBuildAction",
            "PatientPortal": "ProcessPatientRequest",
            "DataPipeline": "ProcessPipelineTask",
        }
        return name_map.get(self.domain, f"Process{self.domain}")

    def _infer_data_sources(self, children_data: List[Dict]) -> List[DataSource]:
        """Infer data sources from children's 'internal leaf access' inputs."""
        sources = set()
        for c in children_data:
            for si in c.get("semantic_inputs", []):
                if si.get("source", "").lower() == "internal leaf access":
                    sources.add(si["name"])

        return [DataSource(
            name=name, category="data_store", access="read_write",
            description=f"Child-internal data source: {name}",
        ) for name in sorted(sources)]

    def _validate_interface_names(self, node: Node) -> List[str]:
        """FIX 5: Validate all interface names are valid Python identifiers."""
        errors = []

        for inp in node.inputs:
            if not _is_valid_identifier(inp.name):
                errors.append(f"parent input '{inp.name}' is not a valid Python identifier")

        for out in node.outputs:
            if not _is_valid_identifier(out.name):
                errors.append(f"parent output '{out.name}' is not a valid Python identifier")

        for child in (node.children or []):
            contract = node.children_contracts.get(child.name)
            if not contract:
                continue
            for ci in contract.inputs:
                if not _is_valid_identifier(ci.name):
                    errors.append(f"child {child.name} input '{ci.name}' is not a valid Python identifier")
            for co in contract.outputs:
                if not _is_valid_identifier(co.name):
                    errors.append(f"child {child.name} output '{co.name}' is not a valid Python identifier")

        if errors:
            self.conversion_notes.extend([f"  VALIDATION ERROR: {e}" for e in errors])

        return errors
