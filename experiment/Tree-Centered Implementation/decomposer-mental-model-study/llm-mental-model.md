# LLM 心智模型 — 分解器对 Expense_prd 的分解理解

> 基于 2026-05-16 交互式询问建立，模型: deepseek-chat

---

## 1. LLM 对"分解"的理解

### 核心直觉

> "Decompose a function block into smaller child function blocks."

LLM 将"分解"理解为：**把一个大函数按职责拆成多个小函数**。每个小函数应该：
- 有单一的、明确的职责（Single Responsibility）
- 可独立测试
- 低圈复杂度

### 对父节点代码的想象

当被要求写出父节点代码时，LLM 始终产生这种模式：

```python
def Expense_prd(raw_input):
    command, expense_data = parse_input(raw_input)    # 调孩子1
    result = route_command(command, expense_data)     # 调孩子2
    return result
```

**父节点只调 2 个孩子**（parse_input + route_command），跳过其余 5 个 handler。

---

## 2. LLM 对 RouteCommand 的角色认知

### 它是"中央分发器"

> "route_command acts as a dispatcher/controller that delegates to specific handlers."

### 它调用 handlers，handlers 不调它

> "route_command calls one of the five handler children based on command value."
> "Handlers: Called by route_command."

### Handlers 的产出返回给 RouteCommand，不是父节点

> "Handlers: Output used by route_command (returns result back to it)."

### RouteCommand 被视为合法的"更小函数"

> "route_command is smaller in the sense that it isolates the routing logic from the domain logic."

---

## 3. LLM 对父子关系的理解

### 父节点是"薄协调器"

> "The parent is intentionally thin — it only coordinates the two main phases (parsing and routing) without adding business logic itself."

### 父节点不需要知道 handlers

> "The parent's responsibility is minimal — it simply calls parse_input first, then passes the result to route_command. It doesn't need to know about the specific handlers."

### 调用链有两层

```
Layer 1 (父节点): Expense_prd
    → parse_input (always)
    → route_command (always)
Layer 2 (route_command 内部):
    → handle_add    (if command=='add')
    → handle_list   (if command=='list')
    → ...           (mutually exclusive)
```

---

## 4. LLM 对规则 5（同一抽象层级）的解读

### LLM 认为 RouteCommand 和 handlers 是同一层级

> "All children operate at the same abstraction level — they are all **command-handling operations** within an expense management system."

### 判定标准是"是否服务于同一目标"

LLM 的抽象层级判定逻辑：
- `parse_input` = "处理用户输入" → 领域操作 ✓
- `handle_add` = "处理 add 命令" → 领域操作 ✓
- `route_command` = "处理命令分发" → LLM 也视为领域操作 ✓

### LLM 不把"调度/分发"视为不同抽象层级

对 LLM 来说，"调度"和"增删改查"一样，都是"处理用户命令"的一个子任务。它不会自动将"控制流"识别为比"领域逻辑"更高的层级。

---

## 5. LLM 的自我矛盾（仅在被追问时暴露）

### 当被要求写实际父代码时

LLM 写的父代码只调了 parse_input + route_command。但当被要求"直接写父节点的 dispatch"时，它也能写出正确的 if/elif 版本——**且完全不调 route_command**：

```python
def Expense_prd(input):
    parsedData = ParseInput(input)
    command = parsedData.command
    if command == "add": HandleAdd(parsedData)
    elif command == "list": HandleList(parsedData)
    ...
```

### 承认冗余问题

> "If the parent calls both RouteCommand AND the individual handler children, you would have two separate routing mechanisms... creating confusion."

### 承认违反规则 5（仅在被直接追问时）

> "No, route_command is NOT at the same abstraction level... In my decomposition, I broke rule 5."

---

## 6. 心智模型总结

```
LLM 认为正确的分解：
  Expense_prd  →  decompose into:
      parse_input          (domain: input handling)
      handle_add           (domain: CRUD)
      handle_list          (domain: CRUD)
      handle_update        (domain: CRUD)
      handle_delete        (domain: CRUD)
      handle_summary       (domain: CRUD)
      route_command        (domain: dispatch)  ← LLM 认为这是同级职责

LLM 认为父节点代码：
  def Expense_prd(input):
      cmd, data = parse_input(input)
      return route_command(cmd, data)    # ← 只调2个

架构实际要求的父节点代码：
  def Expense_prd(input):
      cmd, data = parse_input(input)
      if cmd == 'add': return handle_add(data)
      elif cmd == 'list': return handle_list(data)
      ...                               # ← 调全部6个
```

**根本冲突：** LLM 将"dispatch"视为与"CRUD"同级的领域操作，但架构要求 dispatch 逻辑留在父节点中，不能提取为子节点。规则 5（同一抽象层级）没有定义"什么是同一层级"，导致 LLM 用自己的标准判断 route_command 合格。
