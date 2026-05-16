# MVP-0.5.1 — BFS 自顶向下 Codegen + 全流程验证

## 工程与研究双重视角

本项目有两个层面的目标：

**工程层**：构建树中心多 Agent 软件构造架构，从 PRD 到代码的全自动生成管道。

**研究层**：利用工程化手段**从根本上理解和解决 LLM 不确定性**。每个 MVP 迭代不仅是功能新增，更是对 LLM 行为模式的系统探索。

## 本版本研究进展

### 强制输出：能缓解，不能治愈

从 MVP-0.2.1（JSON Mode）开始，我们一直在用"强制输出"约束 LLM：

| 机制 | 解决的问题 | 局限性 |
|------|-----------|--------|
| JSON Mode（`response_format: json_object`） | 输出格式不可解析 | LLM 可以在 JSON 内塞任意内容 |
| 两步代码生成（REVIEW → IMPLEMENT） | LLM 跳过关键检查（65%→100% 检出格式问题） | 不能检出结构性问题（dispatcher 模式） |
| Step 2 VERIFY（独立 LLM 自检） | 隔离审查，有代码可追溯 | 语义层面松弛匹配，**漏放 dispatcher** |
| 签名锁定（Signature Locking） | 函数签名不匹配 | 不解决分解结构错误 |

关键发现：**强制输出可以让 LLM 遵守格式约束，但不能让 LLM 遵守架构约束。** 后者需要 LLM 在语义层面理解并执行规则，而 LLM 的"理解"是概率性的。

### VERIFY 与 AST Validator 的可靠性鸿沟

```
VERIFY（LLM 自检）
  → 规则："每个子函数必须以 ChildName( 的形式直接出现在代码中"
  → LLM 看到 handlers = {'create': CreateOrderHandler, ...}
  → LLM 判定：CreateOrderHandler 出现在代码中 → "已覆盖" → 放行
  → 本质：语义理解 ≠ 确定性执行

AST Validator（确定性调用图分析）
  → 解析 Python AST，提取 ast.Call 节点
  → CreateOrderHandler 只被引用，未被调用 → "未使用" → 拒绝
  → 本质：语法层精确匹配
```

这暴露了 LLM 作为验证器的固有缺陷：**LLM 做语义匹配，不做确定性执行。** 当规则要求"出现 `ChildName(` 模式"时，LLM 内部将其松弛为"看起来用到了这个 child"。

**重要推论**：验证器（Validator）永远只是下游补丁，不是主战场。真正的问题在分解阶段——LLM 为什么反复产生 dispatcher 模式？

### LLM 心智模型

通过交互式询问（`experiment/Tree-Centered Implementation/decomposer-mental-model-study/`），我们发现：

1. **LLM 有自己的"直觉架构"**——它认为 route_command 与 CRUD handlers 是"同一抽象层级"，因为"都是命令处理操作"。这不是随机错误，而是 LLM 对软件架构的固有认知模式。

2. **推理模型可自我纠正**——deepseek-reasoner 在 CoT 中会自行否定创建 dispatcher 的第一直觉，最终正确分解。chat 模型跳过推理直接输出第一直觉。

3. **提示词级别的禁止无效**——即使加入"children MUST NOT call each other"，deepseek-chat 仍约 80% 创建 RouteCommand。LLM 不是不理解规则，而是它的"架构直觉"压过了规则的表面约束。

4. **LLM 在"生产模式"和"审查模式"下行为不同**——同一模型在中立逐规则审查中能明确拒绝 dispatcher，但在生成代码时（"生产模式"）不会批判性审视自己的分解结构。

### 核心矛盾

**LLM 的不确定性不是 bug，是特性。** 提示词工程可以缓解、强制输出可以约束、验证器可以拦截——但这些都是在和模型的基本行为模式对抗。真正解决这个问题需要：

a) 理解 LLM 的"架构直觉"的来源和规律
b) 设计不依赖 LLM 合规性的工程结构（如确定性校验、架构级 enforcement）
c) 或者让 LLM 在推理模式下工作（但成本高、速度慢）

## 工程成果

### BFS 自顶向下 Codegen

- 修复：codegen 顺序从自底向上改为**自顶向下**，与架构要求对齐
- 原则："组合即验证"——节点分解后立即 codegen，失败则立即重分解
- 不改变 BFS 逐层扩展的基本流程

### order_prd 全流程验证

```
PRD: 订单管理系统
数据源: 3 (users, products, orders)
接口: 18
生成代码文件: 48
最大深度: 5
重分解轮次: 3 (根节点 dispatcher 模式被拒绝)
结果: Validation PASSED
```

- expense_prd（简单 CRUD）：1 轮重分解后通过
- order_prd（复杂业务流程）：3 轮重分解后通过，树结构完整

### 已知失败模式

- `RefundBalance` 节点 codegen 失败，capability 分配不完整
- Max redecompose retries（3）耗尽后未自动恢复
- VERIFY 对 dispatcher 模式间歇性漏放

## 测试套件

```
tests/
├── test_codegen_verify_cannot_compose.py  # VERIFY 拒绝 dispatcher 测试
├── test_formal_leaf_rejection.py           # 叶节点能力拒绝（15/15）
└── test_e2e_redecompose.py                 # 端到端重分解（2/2）
```

```bash
# 激活虚拟环境
source venv/Scripts/activate  # 或 venv\Scripts\activate

# 运行测试
python -m pytest tests/ -v

# 全流程运行
python main.py --input ../../benchmark/test_cases/basic/expense_prd.md --output output
python main.py --input ../../benchmark/test_cases/medium/order_prd.md --output output
```

## 项目文件

| 文件 | 职责 |
|------|------|
| `main.py` | CLI 入口，支持 PRD 输入和测试 |
| `tree_builder.py` | BFS 分解 + 自顶向下 codegen 循环 |
| `code_generator.py` | 两步代码生成（IMPLEMENT + VERIFY） |
| `decomposer.py` | LLM 驱动的节点分解 |
| `validator.py` | AST 验证器（语法、签名、子节点使用、守恒） |
| `models.py` | 数据模型（Node, SubPRD, Contract 等） |
| `interface_planner.py` | 接口规划（ResourceSpec → InterfaceSpec） |
| `interface_codegen.py` | 接口代码生成 |

## 研究方向迭代

| 迭代 | 假说 | 验证结果 |
|------|------|---------|
| 0.1 | 树分解 + 重分解可行 | 可行，但信息跨层丢失 |
| 0.2.0 | JsonPRD/SubPRD 解决信息丢失 | 改善，但 LLM 输出不稳定 |
| 0.2.1 | JSON Mode 强制格式 | 格式稳定了，内容仍不可控 |
| 0.3.1 | 签名锁定 + AttemptRecord 减少重犯 | 签名合规提升，分解结构未改善 |
| 0.4.1-2 | Interface Layer 隔离全局变量访问 | 叶节点更可靠，但 dispatcher 模式未解决 |
| 0.4.3-4 | Architecture Feedback Loop（CANNOT_COMPOSE + INSUFFICIENT_CAPABILITIES） | 反馈回路完整，但 LLM compliance 仍不稳定 |
| 0.5.1 | 强制 VERIFY 两步自检拦截 dispatcher | **部分有效**——VERIFY 不可靠，AST Validator 是真正 enforcement 点 |

## 核心认识

**验证器不是主战场。** 确定性校验（AST Validator）可以拦截错误，但不能预防错误。真正的问题是：LLM 为什么在分解阶段反复产生违反架构的模式？

这个仓库的目的不是"让 LLM 输出正确的代码"，而是**通过工程手段理解 LLM 的认知模式，设计与之兼容的架构约束**。强制输出、验证器、提示词规则都是表面工具——真正的答案藏在对 LLM "心智"的更深理解中。
