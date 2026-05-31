# Decomposer Mental Model Study

研究 LLM decomposer 在系统分解中产生**路由模式**的因果机制。

## 核心问题（三次修正 — 解决方案验证）

**三次修正结论（2026-05-28）**：通过"两阶段分离 + 不相信传统模式"规则，成功将 routing 率从 100% 降至 0-17%。

### 解决方案

1. **两阶段分离**：Phase 1 仅输出结构（name、purpose、behavior），Phase 2 再推导接口。分离本身不能修复 routing，但证明了注意力稀释不是根因。

2. **"不相信传统模式"规则**：在 Phase 1 prompt 中显式拒绝常见软件模式（dispatcher、router、controller、命令模式、策略模式等），覆盖训练数据先验。

### 实验结果

| 实验 | Phase 1 Routing | 说明 |
|------|:-:|------|
| 基线（仅分离） | 5/5 (100%) | 分离本身无效 |
| + 不相信传统模式（Order） | 0/5 (0%) | routing 完全消除 |
| + 不相信传统模式（Chat） | 1/3 (33%) | 唯一触发的是名称误判 |
| + 不相信传统模式（Patient） | 0/3 (0%) | 完全有效 |
| **跨域总计** | **1/6 (17%)** | |

### 树结构审查器

独立 LLM 审查器（只给定树结构规则）在已知违规和正确分解上测试：
- 正确检测违规：10/10 (100%)
- 正确通过合规分解：10/10 (100%)
- 假阳性：0/10

详见 `improve/复现与改进方案.md`。

### Step 2 Codegen 树结构审查（2026-05-28）

**问题**：Phase 2 codegen 没有检出 Chat_00 的 routing 违规，接受了 RouteCommand → handlers 的兄弟调用关系。

**解决方案**：在 codegen 的 system prompt 中添加树结构审查规则（STAGE 1），包括：
1. **Tree Structure Rules**（4 条）：Child independence, Sibling invisibility, Parent as sole orchestrator, Data flow goes through parent
2. **Trust the Structure, Not the Description**：结构事实优先于行为描述
3. **Do Not Trust the Decomposer's Description**：分解器的叙述不覆盖结构现实
4. **Do Not Trust Traditional Software Engineering Patterns**：传统软件模式在树分解中无效

**结果**：codegen 成功检出 Chat_00 的 routing 过拟合分析**：后两条规则可能过拟合（枚举具体模式名称），需要精化。

**过拟合风险**：
- "Do Not Trust Traditional Software Engineering Patterns" 明确列出了具体模式名称（Command Pattern, Strategy Pattern, Dispatcher, Router, Controller），如果未来有其他类似模式，这个规则无法覆盖
- "Do Not Trust the Decomposer's Description" 说 "coordinating" or "routing" are red flags，但 "coordinating" 在某些情况下可能是合法的（如协调自己的子树）

---

## 核心问题（二次修正）

LLM decomposer 经常生成 `ParseInput → RouteCommand → [Handler A, Handler B, ...]` 的分解模式。

**二次修正结论（2026-05-28）**：通过重新审查原始数据流（dataflow_edges）和 sibling_calls 检测结果，确认**路由确实是违规**，之前基于访谈的"认知修正是误解"的结论本身是错误的。

### 原始数据流分析

所有 trial 的 dataflow_edges 都是：
```
parent → ParseInput (input)
ParseInput → RouteCommand (command, order_data)
RouteCommand → parent (output)
```

**关键缺失**：没有 RouteCommand → CreateOrder/PayOrder/... 的边！

但 RouteCommand 的 behavior 明确声明它要调用其他 handlers：
> "Based on the command string, calls the appropriate child handler (CreateOrder, PayOrder, ...) with order_data and returns the result."

### sibling_calls 检测结果

检测器正确识别了结构性违规：
- ParseInput → RouteCommand (structural_router)
- ParseInput → CreateOrder (structural_router)
- ParseInput → PayOrder (structural_router)
- ...
- RouteCommand → CreateOrder (structural_router)
- RouteCommand → PayOrder (structural_router)
- ...

这说明 RouteCommand **在结构上**声明了对 handlers 的调用关系，但这种关系**违反了树结构规则**（兄弟节点不能互相调用）。

### 访谈是事后合理化

当被问到"ParseInput 会调用其他子节点"时，模型都澄清说：
> "ParseInput 并不会调用其他子节点"
> "调用链是：ParseInput → RouteCommand → (CreateOrder / PayOrder / ...)"

**但原始数据中没有这些边**！这是模型的事后合理化。

当被问到"如果要求所有子节点只能被父节点直接调用"时，模型承认需要"扁平化"结构，说明它**知道**自己的分解违反了树结构规则。

### 结论

1. **路由模式天然违规**：RouteCommand 作为兄弟节点不能调用其他兄弟节点，这违反了树结构的根本规则
2. **访谈是事后合理化**：模型在访谈中解释的"调用链"与原始数据流不符
3. **真正的违规发生在 decomposer 层**：不是 codegen 层的误解，而是 decomposer 本身就生成了违规的结构

因此本实验的**实际问题**是：

1. **什么导致 LLM 选择"CommandRouter + Handler"分解模式？** — 提示词因素分析
2. **这种模式是否天然违规？** — 是，RouteCommand 作为兄弟节点调用其他兄弟节点违反树结构规则
3. **如何抑制这种违规模式？** — SubPRD Context 是唯一有效的提示词级抑制因素（对部分模型有效）

## 实验设计：Routing Ablation

使用真实管线 `mvp-0.4.4/decomposer.py` 的提示词构建，通过**定向移除**特定段落来隔离每个因素的影响。

### 消融条件

| 条件 | 移除内容 | 目的 |
|------|---------|------|
| `baseline` | 无（完整真实管线提示词） | 基准线 |
| `no_coordinator` | TREE STRUCTURE 规则中的 coordinator 子句 | 测试协调者豁免是否导致路由 |
| `no_signature_lock` | SIGNATURE LOCKING 段落 | 测试签名锁定约束的影响 |
| `no_stop_conditions` | SEMANTIC STOP CONDITIONS 段落 | 测试停止条件的影响 |
| `no_dataflow_closure` | DATAFLOW CLOSURE RULES 段落 | 测试数据流闭包规则的影响 |
| `no_boundary` | Boundary 段落（user prompt） | 测试边界定义的影响 |
| `no_data_sources` | Data Sources 段落（user prompt） | 测试数据源信息的影响 |
| `no_subprd` | SubPRD Context 段落（user prompt） | 测试功能需求上下文的影响 |
| `specific_input` | `input: Any` → 具体类型 | 测试输入类型具体化的影响 |

### 每个条件

- **3 个 PRD**：`order_real`、`grade_real`、`project_real`（真实管线生成的英文 PRD）
- **5 次试验**（可配置）
- **Thinking disabled**（所有模型统一关闭思考模式）

## 运行

```bash
# 默认模型（deepseek-chat）
python test_routing_ablation.py

# 指定 MiMo 模型
python test_routing_ablation.py --model mimo-v2.5
python test_routing_ablation.py --model mimo-v2-flash

# 单个条件 / 单个 PRD
python test_routing_ablation.py --model mimo-v2.5 --experiment 0
python test_routing_ablation.py --model mimo-v2.5 --prd order_real

# 跳过 follow-up 访谈
python test_routing_ablation.py --model mimo-v2.5 --skip-interview

# 自定义试验次数
python test_routing_ablation.py --model mimo-v2.5 --trials 10
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CHRONOS_API_KEY` | API key（通用） | — |
| `CHRONOS_BASE_URL` | API base URL | `https://api.deepseek.com` |
| `CHRONOS_MODEL` | 模型名 | `deepseek-chat` |
| `CHRONOS_TEMPERATURE` | 温度 | `0.3` |
| `CHRONOS_MAX_TOKENS` | 最大 token | `16384` |
| `CHRONOS_MAX_CONCURRENCY` | 并发数 | `10` |
| `MIMO_API_KEY` | MiMo 专用 key | — |
| `DEEPSEEK_API_KEY` | DeepSeek 专用 key | — |

`--model` 以 `mimo-` 开头时自动使用 `MIMO_API_KEY` 和 MiMo base URL。

## 输出结构

```
output/routing_ablation/
├── prerequisites/              # 共用的 PRD 和接口计划
│   ├── order_real/
│   ├── grade_real/
│   └── project_real/
├── {model-name}/               # 每个模型独立目录
│   ├── results.json            # 全部试验结果
│   ├── report.md               # 自动生成的报告
│   └── experiment_{condition}/ # 每个条件的详细日志
│       └── {prd_name}/
│           ├── trial_00.json
│           ├── trial_00_interview.json  # 路由时的 follow-up
│           ├── 0001_request.json        # LLM 请求日志
│           └── 0001_response.json       # LLM 响应日志
├── thinking_enabled/           # 旧数据（有思考模式）
└── thinking_disabled/          # 旧数据（DeepSeek 初版）
```

## 已测试模型

| 模型 | 基线路由率 | no_subprd 路由率 | SubPRD 影响 | 访谈 | 报告 |
|------|-----------|-----------------|-------------|------|------|
| DeepSeek Chat | 15/15 = 100% | 15/15 = 100% | +0% | 134 份 | `deepseek-chat/report.md` |
| DeepSeek V4 Flash | 15/15 = 100% | 11/15 = 73% | -27% | — | `deepseek-v4-flash/report.md` |
| MiMo v2.5 | 15/15 = 100% | 8/15 = 53% | -47% | — | `mimo-v2.5/report.md` |
| MiMo v2 Flash | 15/15 = 100% | 4/15 = 27% | -73% | — | `mimo-v2-flash/report.md` |

### 关键发现

1. **Thinking mode 是 #1 变量**：开启 thinking 时路由率 ~20%，关闭时 ~100%
2. **SubPRD Context 是唯一有效的提示词级抑制因素**——但模型差异巨大：
   - DeepSeek Chat：完全不受影响（+0%）
   - DeepSeek V4 Flash：-27%
   - MiMo v2.5：-47%
   - MiMo v2 Flash：-73%
3. **其他系统提示词段落对全部模型都没有影响**：coordinator、signature locking、stop conditions、dataflow closure、boundary、data sources、specific input 移除后路由率不变
4. **访谈的重要修正（详见下文 "认知修正" 部分）**：模型描述的"路由"实际上是父节点编排的流水线，不是违规的子节点互调

### 认知修正——来自访谈分析

通过分析 134 份访谈记录，发现了我们对 LLM decomposer 的核心误解：

| 我们的假设 | 访谈证实的真相 |
|-----------|--------------|
| `CommandRouter` 直接调用 Handler（兄弟互调） | 每个子节点返回父节点，父节点编排下一步 |
| 路由模式 = 违反树结构规则 | 路由节点可以完全不违规（父节点编排） |
| ParseInput 和 RouteCommand 都是"中转节点" | ParseInput 被视为特殊节点（预处理步骤） |
| LLM 认识到了路由违规 | 仅 ~50% 明确承认 RouteCommand 涉及兄弟调用 |
| 分解输出决定了代码行为 | 分解设计不违规，违规在 codegen 实现 |

#### 关键证据

模型在访谈中普遍描述这样的调用链（以 `baseline/order_real/trial_02` 为例）：

> "ParseCommand 的职责仅限于：解析 JSON，提取 command 和 order_data，**返回处理后的结果给父节点**（而不是直接调用其他子节点）"
>
> "RouteCommand 接收 ParseCommand 处理后的 command 和 order_data，根据 command 的值，**告诉父节点应该调用哪个 Handler**"
>
> "Handler 收集结果**返回给 RouteCommand，RouteCommand 再汇总返回父节点**"

这实际上是一种**数据流管道模式（Pipe-and-Filter）**，模型把兄弟节点之间的关系理解为"阶段"而非"依赖"——每个阶段处理完的数据往上返回，供下一阶段使用。

#### 暗示

本实验的"路由检测"检测到的是 **分解层面的模式特征**（CommandRouter + Handler 的结构），而非 **代码层面的违规**（兄弟互调）。真正的违规（如果存在）需要 codegen 来确认。

## 添加新模型

1. 在 `test_routing_ablation.py` 的 `MIMO_MODELS` 集合中添加（如果是 MiMo 系列），或通过环境变量/CLI 参数配置 API
2. 运行实验：`python test_routing_ablation.py --model {new-model}`
3. 结果自动保存到 `output/routing_ablation/{new-model}/`，包含完整的访谈记录
4. 更新本 README 的"已测试模型"表格

## 路由检测

检测两种模式：

1. **结构检测**：子节点名包含 `route`、`dispatch`、`parse.*input`、`parse.*command`、`process.*command` 等路由关键词
2. **文本检测**：子节点的 purpose/behavior 中出现 `calls {sibling_name}`、`invokes {sibling_name}`、`dispatches to {sibling_name}` 等模式

不同模型家族的命名风格不同（DeepSeek 用 `CommandRouter`，MiMo 用 `Route_Order_Command`），检测模式已覆盖。

## 前置条件

- Python 3.10+
- `openai`、`python-dotenv` 包
- `mvp-0.4.4/` 目录（用于导入真实管线的 decomposer 和 models）
