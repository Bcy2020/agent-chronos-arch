# Decomposer 心智测试报告 — deepseek-v4-flash

## 测试配置

- Model: deepseek-v4-flash
- Temperature: 0.3
- JSON mode: enabled
- Prompt: 包含 "YOU MUST DECOMPOSE" 强制分解指令 + 路由引导
- Test A: 分解 → 4 个中立追问
- Test B: 6 个字段理解对齐 → 分解

---

## 总体结果

| 指标 | Test A | Test B |
|------|--------|--------|
| 成功分解 | 10/10 | 10/10 |
| 出现路由模式 | 6/10 | 6/10 |
| 路由案例 | OrderSystem, ChatApp, PatientPortal, SocialFeed, TaskPlanner, NotificationHub | 同左 |

---

## 路由模式分析

### 出现路由的案例（6/10）

所有 command-dispatch 模式的案例都出现了路由子节点：

| 案例 | 路由子节点 | 目的 |
|------|-----------|------|
| OrderSystem | `command_router` | Parse the command string and return the corresponding handler name |
| ChatApp | `parse_command` | Validate and identify the command type from the input |
| PatientPortal | `command_router` | Validate the command and patient_data, and determine which handler to invoke |
| SocialFeed | `validate_and_route` | Validate the command and feed_data, returning parsed data for the specific command |
| TaskPlanner | `route_command` | Validate and extract the command type from input |
| NotificationHub | `router` | Parses the command and dispatches to the appropriate handler child function |

### 未出现路由的案例（4/10）

这些案例使用 action-based 模式，没有 command-dispatch 结构：

| 案例 | 分解方式 | 原因 |
|------|---------|------|
| BuildSystem | 按 action 拆分 (trigger/status/list/cancel) | PRD 结构直接列出 action 类型 |
| InventoryManager | 按 action 拆分 (add/update/check/report) | PRD 结构直接列出 action 类型 |
| DataPipeline | 按 ETL 阶段拆分 (ingest/transform/validate/export) | 顺序处理，无需路由 |
| BookingEngine | 按 action 拆分 (book/cancel/availability/list) | PRD 结构直接列出 action 类型 |

---

## 关键发现

### 1. 路由模式需要显式引导

**结论**：LLM 不会自发产生路由模式，需要在 prompt 中明确要求。

**证据**：
- 第一次测试（无路由引导）：0/10 出现路由
- 第二次测试（有路由引导）：6/10 出现路由

**影响**：
- Library PRD 的路由模式来自 MVP 管线的分解 prompt，而非 LLM 自发行为
- 测试案例设计需要考虑 prompt 结构，不能假设 LLM 会自动选择最佳分解模式

### 2. PRD 结构决定分解模式

**两种模式**：

| 模式 | PRD 特征 | 分解方式 | 示例 |
|------|---------|---------|------|
| Command-dispatch | `process_order(command, data)` | 路由 + 处理器 | OrderSystem, ChatApp |
| Action-based | `action: 'place' \| 'cancel' \| 'track'` | 直接按 action 拆分 | BuildSystem, DataPipeline |

**结论**：PRD 的输入格式直接影响 LLM 的分解策略。

### 3. 对齐（Test B）的双面效应

**正面影响**：
- 某些案例在 Test B 中分解更精细（如 ChatApp 多了 validate_input 子节点）

**负面影响**：
- 某些案例在 Test B 中被拒绝分解（如 BuildSystem_B, InventoryManager_B）

**结论**：对齐对分解结果有不确定影响，不能作为提高分解质量的可靠手段。

### 4. 拒绝分解问题

**现象**：即使有 "YOU MUST DECOMPOSE" 强制指令，仍有 2-3 个案例被拒绝分解。

**原因**：
- LLM 认为节点已"原子化"，无需进一步分解
- JSON mode 可能导致 LLM 返回空 JSON 而非有效分解

**解决方案**：
- 在 prompt 中更强调分解的必要性
- 提供分解示例，降低 LLM 的不确定性

---

## 测试案例设计建议

### 1. 避免过于简单的 PRD 结构

**问题**：直接列出 action 类型的 PRD（如 `action: 'place' | 'cancel' | 'track'`）不会产生路由模式。

**建议**：使用 command-dispatch 模式的 PRD（如 `process_order(command, data)`），并提供详细的输入格式示例。

### 2. 在 prompt 中明确分解策略

**问题**：LLM 不会自发选择最佳分解模式。

**建议**：在分解 prompt 中明确要求：
- 如果节点处理多个命令，应创建路由子节点
- 提供分解示例，引导 LLM 的思维

### 3. 提供足够的上下文

**问题**：缺乏上下文会导致 LLM 拒绝分解或分解不充分。

**建议**：
- 提供详细的 INPUT FORMAT 和 OUTPUT FORMAT 示例
- 列出 Functional Requirements，帮助 LLM 理解系统结构
- 提供 EXAMPLE CALLS，降低 LLM 的不确定性

---

## 结论

1. **路由模式需要显式引导** — LLM 不会自发产生路由模式，需要在 prompt 中明确要求
2. **PRD 结构决定分解模式** — command-dispatch 模式的 PRD 更容易产生路由
3. **对齐（Test B）效果不确定** — 可能改善分解，也可能导致拒绝
4. **拒绝分解仍需解决** — 需要更强的 prompt 工程或示例引导
5. **测试案例设计很重要** — 过于简单的 PRD 结构不会产生理想的分解结果

---

## 后续工作

1. **优化 prompt**：在 decomposer 的 system prompt 中添加路由引导规则
2. **增加示例**：在分解 prompt 中提供分解示例，降低 LLM 的不确定性
3. **测试更多模型**：使用不同的 LLM 模型测试路由模式的出现率
4. **验证路由质量**：检查路由子节点是否正确调用了其他子节点
