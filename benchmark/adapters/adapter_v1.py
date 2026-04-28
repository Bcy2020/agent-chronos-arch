"""
适配器示例：当前schema版本（mvp-schema-improved）

此文件作为模板，展示如何将具体schema映射到抽象评测模型。
当schema变化时，LLM应参照此模板生成新的适配器。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Any


# ============================================================
# 抽象评测模型（固定，不应修改）
# ============================================================

@dataclass
class InterfaceParam:
    name: str
    type: str


@dataclass
class GlobalStateOp:
    source_id: str
    op_type: str


@dataclass
class EvaluationNode:
    """评测用的抽象节点模型"""
    node_id: str
    name: str
    depth: int
    is_leaf: bool
    parent_id: str
    children_ids: List[str] = field(default_factory=list)
    children_names: List[str] = field(default_factory=list)
    stop_condition: str = "unknown"  # "semantic" | "forced" | "unknown"
    global_state_ops: List[GlobalStateOp] = field(default_factory=list)
    requirement_trace: List[str] = field(default_factory=list)
    interface_inputs: List[InterfaceParam] = field(default_factory=list)
    interface_outputs: List[InterfaceParam] = field(default_factory=list)
    code: Optional[str] = None
    global_var_names: Set[str] = field(default_factory=set)
    # 分解与验证状态
    validation_passed: bool = True
    needs_human_intervention: bool = False
    retry_count: int = 0


# ============================================================
# 适配器实现（根据具体schema编写）
# ============================================================

class SchemaAdapter:
    """Schema适配器：将具体JSON映射到抽象模型"""

    def adapt_node(self, raw_json: Dict[str, Any]) -> EvaluationNode:
        """将单个节点的raw JSON转换为EvaluationNode"""
        # ===== 基本信息映射 =====
        node_id = raw_json.get("node_id", "")
        name = raw_json.get("name", "")
        depth = raw_json.get("depth", 0)
        parent_id = raw_json.get("parent_id", "") or ""

        # 子节点信息
        children = raw_json.get("children", [])
        children_ids = [c.get("node_id", "") for c in children]
        children_names = [c.get("name", "") for c in children]
        is_leaf = len(children) == 0

        # ===== 停止条件映射 =====
        # 当前schema: stop_reason在节点顶层
        stop_reason = raw_json.get("stop_reason", "")
        stop_condition = self._parse_stop_condition(stop_reason)

        # ===== 全局状态操作映射 =====
        # 当前schema: 在subprd.global_state_operations中
        subprd = raw_json.get("subprd", {})
        global_state_ops = []
        for op in subprd.get("global_state_operations", []):
            global_state_ops.append(GlobalStateOp(
                source_id=op.get("source_id", ""),
                op_type=op.get("op_type", "")
            ))

        # ===== 需求追溯映射 =====
        # 当前schema: 在subprd.traceability.parent_requirement_ids中
        traceability = subprd.get("traceability", {})
        requirement_trace = traceability.get("parent_requirement_ids", [])

        # ===== 接口映射 =====
        interface_inputs = []
        for inp in raw_json.get("inputs", []):
            interface_inputs.append(InterfaceParam(
                name=inp.get("name", ""),
                type=inp.get("type", "")
            ))

        interface_outputs = []
        for out in raw_json.get("outputs", []):
            interface_outputs.append(InterfaceParam(
                name=out.get("name", ""),
                type=out.get("type", "")
            ))

        # ===== 代码映射 =====
        code = raw_json.get("code")

        # ===== 全局变量可见性映射 =====
        global_var_names = set()
        for gv in raw_json.get("global_vars", []):
            var_name = gv.get("name", "")
            if var_name:
                global_var_names.add(var_name)

        # ===== 验证状态映射 =====
        validation = raw_json.get("validation", {})
        validation_passed = validation.get("passed", True)
        needs_human_intervention = raw_json.get("needs_human_intervention", False)
        retry_count = validation.get("retry_count", 0)

        return EvaluationNode(
            node_id=node_id,
            name=name,
            depth=depth,
            is_leaf=is_leaf,
            parent_id=parent_id,
            children_ids=children_ids,
            children_names=children_names,
            stop_condition=stop_condition,
            global_state_ops=global_state_ops,
            requirement_trace=requirement_trace,
            interface_inputs=interface_inputs,
            interface_outputs=interface_outputs,
            code=code,
            global_var_names=global_var_names,
            validation_passed=validation_passed,
            needs_human_intervention=needs_human_intervention,
            retry_count=retry_count
        )

    def _parse_stop_condition(self, stop_reason: str) -> str:
        """解析停止条件字符串"""
        if not stop_reason:
            return "unknown"

        # 语义停止的关键词
        semantic_keywords = [
            "纯函数", "原子操作", "atomic",
            "independently_implementable",
            "pure function", "atomic operation"
        ]

        # 强制停止的关键词
        forced_keywords = [
            "Max depth", "max_depth",
            "Max children", "max_children",
            "强制", "forced", "limit"
        ]

        stop_lower = stop_reason.lower()

        for kw in semantic_keywords:
            if kw.lower() in stop_lower:
                return "semantic"

        for kw in forced_keywords:
            if kw.lower() in stop_lower:
                return "forced"

        return "unknown"

    def adapt_tree(self, raw_json: Dict[str, Any]) -> List[EvaluationNode]:
        """遍历整棵树，返回所有节点的列表"""
        nodes = []
        self._traverse(raw_json, nodes)
        return nodes

    def _traverse(self, raw_node: Dict[str, Any], nodes: List[EvaluationNode]):
        """递归遍历树"""
        nodes.append(self.adapt_node(raw_node))
        for child in raw_node.get("children", []):
            self._traverse(child, nodes)


# ============================================================
# 导出适配器实例（评测器会导入这个）
# ============================================================

adapter = SchemaAdapter()


# ============================================================
# 适配器元信息（供LLM生成新适配器时参考）
# ============================================================

ADAPTER_INFO = {
    "schema_version": "mvp-schema-improved-v1",
    "description": "当前MVP的schema适配器",
    "key_mappings": {
        "stop_condition": "从 stop_reason 字段解析，通过关键词判断semantic/forced",
        "global_state_ops": "从 subprd.global_state_operations 数组提取",
        "requirement_trace": "从 subprd.traceability.parent_requirement_ids 提取",
        "global_var_names": "从 global_vars 数组的 name 字段提取"
    }
}