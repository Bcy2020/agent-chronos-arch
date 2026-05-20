# Agent Chronos 2.0 — 热知识

## 核心理念

Agent Chronos 2.0 是一个**树中心的多 Agent 软件构造架构**。它将软件视为一棵不断展开的树：从根需求开始，递归分解为可实现的节点，每个节点在局部上下文中被实现和验证，通过父子组合验证确保分解可行，通过子树定位实现变更与缺陷治理。

核心回路：**分解 → 实现 → 验证 → 反馈 → 重分解**。这是一个紧耦合的持续循环，而非分离的阶段。

关键原则：
- **树分解是主结构** — 系统从根需求开始，逐步展开为可实现的节点树，而非按前后端角色切分
- **组合即验证** — 父节点通过子节点接口实现，代码生成本身就是对分解可行性的检验。**必须即时，不能后置**。
- **多级验证** — 节点级（语法/签名）、父子组合级（子节点使用）、子树级（回归）
- **树化治理** — 需求变更和缺陷先在树中定位受影响节点/子树，再决定修正范围
- **并行发生在子树层级** — 上下文隔离按节点或子树进行，而非按角色副本

## MVP 演进谱系

| 版本 | 主题 | 解决的问题 |
|------|------|-----------|
| **MVP-0.1** | Proof of Concept | 基本树分解 + 重分解，中文实现 |
| **MVP-0.2.0** | Structured PRD | PRD 信息在跨层传递中的丢失/失真，引入 JsonPRD + SubPRD |
| **MVP-0.2.1** | JSON Mode | 强制 LLM 输出 `json_object` 格式 |
| **MVP-0.3.1** | Decomposition-Verification Loop | 重分解时 LLM 重复犯错的问题，引入签名锁定、AttemptRecord、StateOperation 系统 |
| **MVP-0.4.1** | Interface Layer (Phase 1+2) | 叶节点误用 `op_root_*` 操作 ID 作 Python 变量，引入 ResourceSpec/InterfaceSpec/InterfacePlan |
| **MVP-0.4.2** | Interface Layer (Phase 3+4) | Interface 代码生成 + Capability Allocation，叶节点通过 `granted_capabilities` 替代全局变量 |
| **MVP-0.4.3** | Architecture Feedback Loop | CodeGenerator 主动拒绝 (`CANNOT_COMPOSE`) + Validator 被动检测 + TreeBuilder 路由反馈到重分解 + Decomposer 生成 `dataflow_edges` |
| **MVP-0.4.4** | Leaf Rejection + Parent Redecomposition | 在 DFS 上加的重分解补丁，使递归结构复杂化 |
| **MVP-0.5.0** | BFS + Phase 2 codegen 后置 | BFS 遍历方向正确，但 codegen 后置违反"组合即验证" |
| **MVP-0.5.1** | BFS + 即时 codegen 尝试 | 修正了 codegen 时机，但 escalation 逻辑有缺陷，代码细节问题被误判为重分解 |
| **fix-dispatcher** | 概念纠偏 + verbose 日志 | 发现 escalation 逻辑缺陷，但 BFS 代码骨架的问题不是补丁能修的 |
| **rewrite-0.6.0** | BFS + 即时 codegen，正确实现 | 保留 BFS 遍历，修复 escalation 逻辑，区分结构性问题与代码细节问题 |

## 当前状态（2026-05-20）

**最新分支**：`rewrite-0.6.0`（基于 main，已删除 mvp-0.4.4 和 mvp-0.5.1）
**活跃目录**：
- `mvp/mvp-0.4.3/` — 保留作为参考，但其 DFS 遍历将被替代
- `rewrite-0.6.0` 将基于 BFS + 即时 codegen 重写

**核心教训**：BFS 遍历方向正确（逐层展开优于深度优先），**但 codegen 绝不能后置**。0.5.0 的 Phase 2 错误地把 decompose 和 codegen 拆成两个阶段，违反了"组合即验证"。0.5.1 试图修正（将 codegen 移入 BFS 循环），但 escalation 逻辑有缺陷——代码细节问题被错误地升级为结构重分解，且 BFS 骨架上的补丁越堆越多。正确路径：BFS 遍历 + 每个节点分解后**立即** codegen + 清晰区分结构性问题与代码细节问题。

### 本会话（2026-05-20）：决断 — 清理 0.4.4/0.5.x，基于 BFS+即时 codegen 重写

**回顾走过的弯路**：
- 0.4.4 在 DFS 上加 `while True` 重分解循环，补丁式修复，使递归复杂化
- 0.5.0 方向正确（BFS 逐层展开），但 Phase 2 codegen 后置违背"组合即验证"
- 0.5.1 试图把 codegen 拉回 BFS 循环（正确方向），但 escalation 逻辑有缺陷，且 BFS 骨架上的补丁越堆越多
- fix-dispatcher 发现了 escalation 逻辑缺陷——代码细节问题被误判为结构重分解

**当前决策**：
- 删除 mvp-0.4.4/ 和 mvp-0.5.1/ 目录（清理代码，git 历史仍在）
- 基于 BFS + 即时 codegen 重写 0.6.0
- 保留 0.4.3 及之前的历史版本作为参考

### 已验证的能力（来自 0.4.3 及之前）
- LLM 驱动的递归树分解，语义驱动的停止条件
- 签名锁定：子节点接口在分解时锁定，代码生成时强制遵守
- AST 验证：Python 语法、签名匹配、子节点使用检查
- 全局状态守恒：父节点状态操作必须是子节点操作并集
- 验证失败自动重分解（带 AttemptRecord 反馈上下文）
- PRD 转换器：自然语言 → JsonPRD 结构化格式
- Interface Planner：ResourceSpec / InterfaceSpec / CRUD whitelist
- Interface Normalizer：确定性规范化 + 结构验证 + 业务接口拦截
- Interface ImplGenerator：LLM 驱动、按 resource 分组、contract-aware 接口代码生成
- Interface Verifier：AST 签名匹配、跨资源全局变量、list filter 使用、返回类型校验
- Capability Allocator：叶节点能力声明 → InterfacePlan 匹配授予
- 多种失败恢复策略：签名错误 → 代码重生成；子节点未使用/状态不守恒 → 清空子节点重分解
- **CANNOT_COMPOSE 主动拒绝**：CodeGenerator 可主动拒绝不可实现的分解，带诊断反馈
- **被动结构检测**：Validator 检查直接资源访问、未授权接口调用、输入来源缺失
- **Dataflow Edge 声明**：Decomposer 输出显式 `dataflow_edges` 描述子节点间数据流

### 尚未完成（rewrite-0.6.0）

#### 核心设计目标
- **正确的失败恢复**：BFS 框架下区分"结构性问题→重分解"和"代码细节问题→codegen 重试"，不再共享 retry 计数器
- **叶节点能力拒绝**：基于 BFS + 即时 codegen 架构自然扩展
- **父子节点跨层传播**：子节点失败 → 正确的向上传播路径

#### MVP-1.0
- **代码执行管道**：生成的代码可连接执行
- **Real 组合验证**：通过 importlib 加载真实子节点代码
- **执行级验证反馈**：运行时错误 → 分解修正的闭环

#### 远期
- **子树级并行**：跨子树独立并行
- **树级运行时**：统一的树结构执行环境
- **RAG 复用**：跨子树原子能力复用机制
- **Git 集成**：树结构与 Git 分支/回滚的天然结合

### 已知问题
- 生成的代码可能缺少 import 语句
- **Provenance checker 非完整 SSA**：不跨函数边界、comprehension、闭包追踪变量
- **LLM compliance 不稳定**：分解器即使接收反馈仍可能生成结构无效的子节点
- **分解器的抽象层级问题**：LLM 倾向于将 dispatch 与 CRUD handlers 放在同一层级（如 `[ParseCommand, ExecuteCommand]`），虽然这**在树结构上合法**（无横切调用），但 `ExecuteCommand` 承载了过多职责
- **VERIFY（LLM 自检）不可靠**：规则明确要求直接调用，但 LLM 在语义层面做松弛匹配。AST Validator（确定性分析）是真正的 enforcement 点

### 最近修复
- **2026-05-20**: 删除 mvp-0.4.4 和 mvp-0.5.1，创建 rewrite-0.6.0 分支，回归 0.4.3 基石
- **2026-05-20**: fix-dispatcher PR #13 合并到 main，概念修正代码合入主线
- **2026-05-16**: 修复 codegen 顺序从自底向上改为自顶向下（后被回退，因为 BFS 结构本身有问题）

## 项目结构速览

```
agent-chronos-arch/
├── hot.md                                     ← 本文（项目热知识 + 当前状态）
├── architect/                                 ← 架构文档（中/英）
├── docs/                                      ← 细化文档
│   └── composition-validation-evolution.md    ← 父子组合验证演进路线
├── mvp/                                       ← 版本化 MVP 发布目录
│   ├── MVP_Tier_Standard.md                   ← MVP 分级标准
│   ├── mvp-0.1/
│   ├── mvp-0.2.0/
│   ├── mvp-0.2.1/
│   ├── mvp-0.3.1/
│   ├── mvp-0.4.1/
│   ├── mvp-0.4.2/
│   ├── mvp-0.4.3/                             ← 当前架构基石（DFS + 即时 codegen）
│   └── mvp-0.6.0/                             ← 即将开始重写
└── experiment/Tree-Centered Implementation/   ← 实验区
    ├── mvp-legacy/
    ├── mvp-chinese/
    ├── mvp-schema-improved/
    ├── mvp-schema-improved-json/
    └── decomposer-mental-model-study/         ← 分解器 LLM 心智模型研究
```
