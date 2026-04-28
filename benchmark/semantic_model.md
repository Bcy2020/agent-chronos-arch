# 评测抽象模型语义清单

本文档定义评测系统的稳定语义概念，与具体schema无关。
适配器负责将具体schema字段映射到这些语义概念。

---

## 节点基本信息

| 概念 | 类型 | 说明 |
|------|------|------|
| node_id | str | 节点唯一标识符 |
| name | str | 节点/函数名称 |
| depth | int | 节点深度，根节点为0 |
| is_leaf | bool | 是否为叶节点（无子节点） |
| children_ids | List[str] | 子节点ID列表 |
| children_names | List[str] | 子节点名称列表 |

---

## 分解停止条件

| 概念 | 类型 | 说明 |
|------|------|------|
| stop_condition | str | 值为以下之一：<br>- `"semantic"`: 语义上已原子化（纯函数、原子操作）<br>- `"forced"`: 被外部约束强制截断（如max_depth、max_children）<br>- `"unknown"`: 未说明或无法判断 |

判断规则：
- 如果stop_reason包含"纯函数"、"原子操作"、"independently_implementable"等语义描述 → `"semantic"`
- 如果stop_reason包含"Max depth"、"max_children"等强制约束 → `"forced"`
- 否则 → `"unknown"`

---

## 全局状态操作声明

| 概念 | 类型 | 说明 |
|------|------|------|
| global_state_ops | List[GlobalStateOp] | 节点对全局数据源的操作声明 |

GlobalStateOp结构：
| 字段 | 类型 | 说明 |
|------|------|------|
| source_id | str | 数据源名称（如"tasks"、"next_id"） |
| op_type | str | 操作类型：`"read"` / `"write"` / `"read_then_write"` |

---

## 需求追溯

| 概念 | 类型 | 说明 |
|------|------|------|
| requirement_trace | List[str] | 该节点追溯到的需求ID列表（如["FR-001", "FR-002"]） |

---

## 接口定义

| 概念 | 类型 | 说明 |
|------|------|------|
| interface_inputs | List[InterfaceParam] | 输入参数列表 |
| interface_outputs | List[InterfaceParam] | 输出参数列表 |

InterfaceParam结构：
| 字段 | 类型 | 说明 |
|------|------|------|
| name | str | 参数名 |
| type | str | 类型字符串（如"str", "List[dict]"） |

---

## 代码

| 概念 | 类型 | 说明 |
|------|------|------|
| code | str | 生成的Python代码（完整字符串） |

---

## 全局变量可见性

| 概念 | 类型 | 说明 |
|------|------|------|
| global_var_names | Set[str] | 该节点可见的全局变量名集合 |

注：这是"可见性声明"，不等同于"实际操作"。实际操作由global_state_ops描述。

---

## 父节点信息

| 概念 | 类型 | 说明 |
|------|------|------|
| parent_id | str | 父节点ID，根节点为None或空字符串 |

---

## 分解与验证状态

| 概念 | 类型 | 说明 |
|------|------|------|
| validation_passed | bool | 代码是否通过验证 |
| needs_human_intervention | bool | 是否需要人工干预（分解失败） |
| retry_count | int | 重试次数（0表示首次成功） |

判断规则：
- `validation_passed = true` → 分解成功
- `validation_passed = false` 且 `needs_human_intervention = true` → 分解失败，需人工干预
- `retry_count > 0` → 需要重试才能成功

---

## 完整EvaluationNode结构（适配器输出目标）

```python
@dataclass
class EvaluationNode:
    node_id: str
    name: str
    depth: int
    is_leaf: bool
    parent_id: str
    children_ids: List[str]
    children_names: List[str]
    stop_condition: str  # "semantic" | "forced" | "unknown"
    global_state_ops: List[dict]  # [{source_id, op_type}, ...]
    requirement_trace: List[str]
    interface_inputs: List[dict]  # [{name, type}, ...]
    interface_outputs: List[dict]  # [{name, type}, ...]
    code: Optional[str]
    global_var_names: Set[str]
    # 分解与验证状态
    validation_passed: bool
    needs_human_intervention: bool
    retry_count: int
```