"""
Data models for decomposition tree nodes.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json


@dataclass
class InputParam:
    name: str
    type: str
    description: str = ""
    source: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"name": self.name, "type": self.type, "description": self.description}
        if self.source:
            result["source"] = self.source
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InputParam":
        return cls(
            name=data.get("name", ""),
            type=data.get("type", "Any"),
            description=data.get("description", ""),
            source=data.get("source", "")
        )


@dataclass
class OutputParam:
    name: str
    type: str
    description: str = ""
    consumer: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"name": self.name, "type": self.type, "description": self.description}
        if self.consumer:
            result["consumer"] = self.consumer
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OutputParam":
        return cls(
            name=data.get("name", ""),
            type=data.get("type", "Any"),
            description=data.get("description", ""),
            consumer=data.get("consumer", "")
        )


@dataclass
class DataSource:
    name: str
    category: str
    access: str
    data_type: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "access": self.access,
            "data_type": self.data_type,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataSource":
        return cls(
            name=data.get("name", ""),
            category=data.get("category", "memory"),
            access=data.get("access", "read"),
            data_type=data.get("data_type", "Any"),
            description=data.get("description", "")
        )


@dataclass
class DataOperation:
    source_name: str
    operation_type: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "operation_type": self.operation_type,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataOperation":
        return cls(
            source_name=data.get("source_name", ""),
            operation_type=data.get("operation_type", "read"),
            description=data.get("description", "")
        )


@dataclass
class GlobalVar:
    variable: str
    op: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variable": self.variable,
            "op": self.op,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlobalVar":
        return cls(
            variable=data.get("variable", data.get("name", "")),
            op=data.get("op", data.get("access", "read")),
            description=data.get("description", "")
        )


@dataclass
class Boundary:
    in_scope: List[str] = field(default_factory=list)
    out_of_scope: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {"in_scope": self.in_scope, "out_of_scope": self.out_of_scope}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Boundary":
        return cls(
            in_scope=data.get("in_scope", []),
            out_of_scope=data.get("out_of_scope", [])
        )


# === New Schema Types (改进.md: JsonPRD & SubPRD) ===

@dataclass
class FunctionalRequirement:
    fr_id: str
    title: str
    description: str
    priority: str = "medium"
    related_nfr_ids: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fr_id": self.fr_id, "title": self.title, "description": self.description,
            "priority": self.priority, "related_nfr_ids": self.related_nfr_ids,
            "depends_on": self.depends_on
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FunctionalRequirement":
        return cls(
            fr_id=data.get("fr_id", ""), title=data.get("title", ""),
            description=data.get("description", ""), priority=data.get("priority", "medium"),
            related_nfr_ids=data.get("related_nfr_ids", []),
            depends_on=data.get("depends_on", [])
        )


@dataclass
class NonFunctionalRequirement:
    nfr_id: str
    category: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {"nfr_id": self.nfr_id, "category": self.category, "description": self.description}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NonFunctionalRequirement":
        return cls(
            nfr_id=data.get("nfr_id", ""), category=data.get("category", ""),
            description=data.get("description", "")
        )


@dataclass
class AcceptanceCriterion:
    ac_id: str
    description: str
    verification_method: str = ""
    related_fr_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ac_id": self.ac_id, "description": self.description,
            "verification_method": self.verification_method,
            "related_fr_ids": self.related_fr_ids
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AcceptanceCriterion":
        return cls(
            ac_id=data.get("ac_id", ""), description=data.get("description", ""),
            verification_method=data.get("verification_method", ""),
            related_fr_ids=data.get("related_fr_ids", [])
        )


@dataclass
class TechnicalConstraints:
    storage: Dict[str, Any] = field(default_factory=dict)
    concurrency: Dict[str, Any] = field(default_factory=dict)
    ui: Dict[str, Any] = field(default_factory=dict)
    language: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"storage": self.storage, "concurrency": self.concurrency, "ui": self.ui, "language": self.language}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TechnicalConstraints":
        return cls(
            storage=data.get("storage", {}), concurrency=data.get("concurrency", {}),
            ui=data.get("ui", {}), language=data.get("language", "")
        )


@dataclass
class GlobalStateSource:
    source_id: str
    type: str
    description: str = ""
    initial_state: Any = None
    item_schema: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id, "type": self.type,
            "description": self.description, "initial_state": self.initial_state,
            "item_schema": self.item_schema
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlobalStateSource":
        return cls(
            source_id=data.get("source_id", ""), type=data.get("type", "list"),
            description=data.get("description", ""),
            initial_state=data.get("initial_state"),
            item_schema=data.get("item_schema", {})
        )


@dataclass
class JsonPRD:
    metadata: Dict[str, Any]
    functional_requirements: List[FunctionalRequirement] = field(default_factory=list)
    non_functional_requirements: List[NonFunctionalRequirement] = field(default_factory=list)
    acceptance_criteria: List[AcceptanceCriterion] = field(default_factory=list)
    technical_constraints: TechnicalConstraints = field(default_factory=TechnicalConstraints)
    glossary: Dict[str, str] = field(default_factory=dict)
    global_state_sources: List[GlobalStateSource] = field(default_factory=list)
    input_spec: Dict[str, Any] = field(default_factory=dict)
    output_spec: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata,
            "functional_requirements": [fr.to_dict() for fr in self.functional_requirements],
            "non_functional_requirements": [nfr.to_dict() for nfr in self.non_functional_requirements],
            "acceptance_criteria": [ac.to_dict() for ac in self.acceptance_criteria],
            "technical_constraints": self.technical_constraints.to_dict(),
            "glossary": self.glossary,
            "global_state_sources": [gss.to_dict() for gss in self.global_state_sources],
            "input_spec": self.input_spec,
            "output_spec": self.output_spec
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JsonPRD":
        return cls(
            metadata=data.get("metadata", {}),
            functional_requirements=[FunctionalRequirement.from_dict(fr) for fr in data.get("functional_requirements", [])],
            non_functional_requirements=[NonFunctionalRequirement.from_dict(nfr) for nfr in data.get("non_functional_requirements", [])],
            acceptance_criteria=[AcceptanceCriterion.from_dict(ac) for ac in data.get("acceptance_criteria", [])],
            technical_constraints=TechnicalConstraints.from_dict(data.get("technical_constraints", {})),
            glossary=data.get("glossary", {}),
            global_state_sources=[GlobalStateSource.from_dict(gss) for gss in data.get("global_state_sources", [])],
            input_spec=data.get("input_spec", {}),
            output_spec=data.get("output_spec", {})
        )


# === SubPRD Supporting Types ===

@dataclass
class Traceability:
    parent_requirement_ids: List[str] = field(default_factory=list)
    derived_from: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"parent_requirement_ids": self.parent_requirement_ids, "derived_from": self.derived_from}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Traceability":
        return cls(
            parent_requirement_ids=data.get("parent_requirement_ids", []),
            derived_from=data.get("derived_from", "")
        )


@dataclass
class StateOperation:
    op_id: str
    source_id: str
    op_type: str
    target: Dict[str, Any] = field(default_factory=dict)
    payload: Dict[str, Any] = field(default_factory=dict)
    constraint: str = ""
    depends_on: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op_id": self.op_id, "source_id": self.source_id, "op_type": self.op_type,
            "target": self.target, "payload": self.payload,
            "constraint": self.constraint, "depends_on": self.depends_on
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateOperation":
        return cls(
            op_id=data.get("op_id", ""), source_id=data.get("source_id", ""),
            op_type=data.get("op_type", "read"), target=data.get("target", {}),
            payload=data.get("payload", {}), constraint=data.get("constraint", ""),
            depends_on=data.get("depends_on", "")
        )


@dataclass
class SubPRD:
    task_id: str = ""
    purpose: str = ""
    description: str = ""
    inputs: List[InputParam] = field(default_factory=list)
    outputs: List[OutputParam] = field(default_factory=list)
    boundary: Boundary = field(default_factory=Boundary)
    constraints: List[Dict[str, str]] = field(default_factory=list)
    acceptance_criteria: List[AcceptanceCriterion] = field(default_factory=list)
    traceability: Traceability = field(default_factory=Traceability)
    global_state_operations: List[StateOperation] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id, "purpose": self.purpose, "description": self.description,
            "inputs": [i.to_dict() for i in self.inputs],
            "outputs": [o.to_dict() for o in self.outputs],
            "boundary": self.boundary.to_dict(),
            "constraints": self.constraints,
            "acceptance_criteria": [ac.to_dict() for ac in self.acceptance_criteria],
            "traceability": self.traceability.to_dict(),
            "global_state_operations": [op.to_dict() for op in self.global_state_operations],
            "dependencies": self.dependencies
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubPRD":
        return cls(
            task_id=data.get("task_id", ""), purpose=data.get("purpose", ""),
            description=data.get("description", ""),
            inputs=[InputParam.from_dict(i) for i in data.get("inputs", [])],
            outputs=[OutputParam.from_dict(o) for o in data.get("outputs", [])],
            boundary=Boundary.from_dict(data.get("boundary", {})),
            constraints=data.get("constraints", []),
            acceptance_criteria=[AcceptanceCriterion.from_dict(ac) for ac in data.get("acceptance_criteria", [])],
            traceability=Traceability.from_dict(data.get("traceability", {})),
            global_state_operations=[StateOperation.from_dict(op) for op in data.get("global_state_operations", [])],
            dependencies=data.get("dependencies", [])
        )


@dataclass
class ChildContract:
    purpose: str
    inputs: List[InputParam]
    outputs: List[OutputParam]
    behavior: str = ""
    signature: str = ""
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    data_operations: List[DataOperation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "purpose": self.purpose,
            "inputs": [i.to_dict() for i in self.inputs],
            "outputs": [o.to_dict() for o in self.outputs],
            "behavior": self.behavior,
            "signature": self.signature,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "data_operations": [op.to_dict() for op in self.data_operations]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChildContract":
        return cls(
            purpose=data.get("purpose", ""),
            inputs=[InputParam.from_dict(i) for i in data.get("inputs", [])],
            outputs=[OutputParam.from_dict(o) for o in data.get("outputs", [])],
            behavior=data.get("behavior", ""),
            signature=data.get("signature", ""),
            preconditions=data.get("preconditions", []),
            postconditions=data.get("postconditions", []),
            data_operations=[DataOperation.from_dict(op) for op in data.get("data_operations", [])]
        )


@dataclass
class ValidationResult:
    passed: bool = False
    errors: List[str] = field(default_factory=list)
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {"passed": self.passed, "errors": self.errors, "retry_count": self.retry_count}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationResult":
        return cls(
            passed=data.get("passed", False),
            errors=data.get("errors", []),
            retry_count=data.get("retry_count", 0)
        )


@dataclass
class Node:
    node_id: str
    name: str
    depth: int
    parent_id: Optional[str] = None

    purpose: str = ""
    inputs: List[InputParam] = field(default_factory=list)
    outputs: List[OutputParam] = field(default_factory=list)
    boundary: Boundary = field(default_factory=Boundary)

    global_vars: List[GlobalVar] = field(default_factory=list)
    data_sources: List[DataSource] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    error_handling: Dict[str, str] = field(default_factory=dict)

    children: List["Node"] = field(default_factory=list)
    children_contracts: Dict[str, ChildContract] = field(default_factory=dict)

    decomposition_rationale: str = ""

    subprd: Optional[SubPRD] = None

    stop_decompose: bool = False
    stop_reason: str = ""
    estimated_lines: int = 0

    code: str = ""
    code_file: str = ""

    validation: ValidationResult = field(default_factory=ValidationResult)
    needs_human_intervention: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "depth": self.depth,
            "parent_id": self.parent_id,
            "purpose": self.purpose,
            "inputs": [i.to_dict() for i in self.inputs],
            "outputs": [o.to_dict() for o in self.outputs],
            "boundary": self.boundary.to_dict(),
            "global_vars": [g.to_dict() for g in self.global_vars],
            "data_sources": [ds.to_dict() for ds in self.data_sources],
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "error_handling": self.error_handling,
            "children": [c.to_dict() for c in self.children],
            "children_contracts": {k: v.to_dict() for k, v in self.children_contracts.items()},
            "decomposition_rationale": self.decomposition_rationale,
            "subprd": self.subprd.to_dict() if self.subprd else None,
            "stop_decompose": self.stop_decompose,
            "stop_reason": self.stop_reason,
            "estimated_lines": self.estimated_lines,
            "code": self.code,
            "code_file": self.code_file,
            "validation": self.validation.to_dict(),
            "needs_human_intervention": self.needs_human_intervention
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        node = cls(
            node_id=data.get("node_id", ""),
            name=data.get("name", ""),
            depth=data.get("depth", 0),
            parent_id=data.get("parent_id"),
            purpose=data.get("purpose", ""),
            inputs=[InputParam.from_dict(i) for i in data.get("inputs", [])],
            outputs=[OutputParam.from_dict(o) for o in data.get("outputs", [])],
            boundary=Boundary.from_dict(data.get("boundary", {})),
            global_vars=[GlobalVar.from_dict(g) for g in data.get("global_vars", [])],
            data_sources=[DataSource.from_dict(ds) for ds in data.get("data_sources", [])],
            preconditions=data.get("preconditions", []),
            postconditions=data.get("postconditions", []),
            error_handling=data.get("error_handling", {}),
            children=[Node.from_dict(c) for c in data.get("children", [])],
            children_contracts={
                k: ChildContract.from_dict(v) for k, v in data.get("children_contracts", {}).items()
            },
            decomposition_rationale=data.get("decomposition_rationale", ""),
            subprd=SubPRD.from_dict(data["subprd"]) if data.get("subprd") else None,
            stop_decompose=data.get("stop_decompose", False),
            stop_reason=data.get("stop_reason", ""),
            estimated_lines=data.get("estimated_lines", 0),
            code=data.get("code", ""),
            code_file=data.get("code_file", ""),
            validation=ValidationResult.from_dict(data.get("validation", {})),
            needs_human_intervention=data.get("needs_human_intervention", False)
        )
        return node
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> "Node":
        return cls.from_dict(json.loads(json_str))
    
    def get_context_for_child(self, child_name: str) -> Dict[str, Any]:
        """
        Get the context that should be passed to a child node.
        This follows the black-box principle: child only receives what parent specifies.
        If SubPRD is available, includes structured context.
        """
        contract = self.children_contracts.get(child_name)
        if contract:
            context = {
                "name": child_name,
                "purpose": contract.purpose,
                "inputs": [i.to_dict() for i in contract.inputs],
                "outputs": [o.to_dict() for o in contract.outputs],
                "behavior": contract.behavior,
                "preconditions": contract.preconditions,
                "postconditions": contract.postconditions,
                "parent_name": self.name,
                "parent_purpose": self.purpose
            }
            child = next((c for c in self.children if c.name == child_name), None)
            if child and child.subprd:
                context["subprd"] = child.subprd.to_dict()
            return context
        return {}
    
    def get_interface_signature(self) -> str:
        """Get the function signature for this node."""
        inputs_str = ", ".join([f"{i.name}: {i.type}" for i in self.inputs])
        outputs_str = ", ".join([o.type for o in self.outputs]) if self.outputs else "None"
        if len(self.outputs) > 1:
            outputs_str = f"Tuple[{outputs_str}]"
        elif len(self.outputs) == 1:
            outputs_str = self.outputs[0].type
        return f"def {self.name}({inputs_str}) -> {outputs_str}:"
