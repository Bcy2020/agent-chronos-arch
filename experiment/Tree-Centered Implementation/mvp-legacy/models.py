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
    
    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "type": self.type, "description": self.description}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InputParam":
        return cls(
            name=data.get("name", ""),
            type=data.get("type", "Any"),
            description=data.get("description", "")
        )


@dataclass
class OutputParam:
    name: str
    type: str
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "type": self.type, "description": self.description}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OutputParam":
        return cls(
            name=data.get("name", ""),
            type=data.get("type", "Any"),
            description=data.get("description", "")
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
    name: str
    type: str
    access: str
    description: str = ""
    data_source: Optional[str] = None
    data_type: str = "Any"
    operations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "access": self.access,
            "description": self.description,
            "data_source": self.data_source,
            "data_type": self.data_type,
            "operations": self.operations
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlobalVar":
        return cls(
            name=data.get("name", ""),
            type=data.get("type", "Any"),
            access=data.get("access", "read"),
            description=data.get("description", ""),
            data_source=data.get("data_source"),
            data_type=data.get("data_type", "Any"),
            operations=data.get("operations", [])
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

    stop_decompose: bool = False
    stop_reason: str = ""
    estimated_lines: int = 0

    code: str = ""
    code_file: str = ""

    validation: ValidationResult = field(default_factory=ValidationResult)

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
            "stop_decompose": self.stop_decompose,
            "stop_reason": self.stop_reason,
            "estimated_lines": self.estimated_lines,
            "code": self.code,
            "code_file": self.code_file,
            "validation": self.validation.to_dict()
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
            stop_decompose=data.get("stop_decompose", False),
            stop_reason=data.get("stop_reason", ""),
            estimated_lines=data.get("estimated_lines", 0),
            code=data.get("code", ""),
            code_file=data.get("code_file", ""),
            validation=ValidationResult.from_dict(data.get("validation", {}))
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
        """
        contract = self.children_contracts.get(child_name)
        if contract:
            return {
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
