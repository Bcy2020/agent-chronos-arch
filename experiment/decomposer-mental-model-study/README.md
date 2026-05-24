# Decomposer Mental Model Study

研究 LLM decomposer 在系统分解中产生**路由模式**的因果机制。

## 核心问题（已修正）

LLM decomposer 经常生成 `ParseInput → RouteCommand → [Handler A, Handler B, ...]` 的分解模式。我们曾认为这违反了树结构规则（子节点调用兄弟节点），但**访谈证实这是误解**：

**LLM 意图的是父节点编排的流水线（parent-orchestrated pipeline），而非子节点直接互调：**

```
父节点 → ParseCommand (解析) → 返回父节点
      → RouteCommand (路由判断) → 返回父节点  
      → Handler (执行) → 返回父节点
```

每个子节点执行后**返回父节点**，父节点决定下一个调谁。这完全符合树结构规则。真正的路由违规发生在 **codegen 层**——它把兄弟节点关系理解为"直接调用"，而不是模型意图的"父节点编排"。

因此本实验的**实际问题**是：

1. **什么导致 LLM 选择"CommandRouter + Handler"分解模式？** — 提示词因素分析
2. **这种模式是否天然违规？** — 否，违规发生在 codegen 层，而非 decomposer 层
3. **如何让 codegen 正确理解父节点编排意图？** — 后续需解决的问题

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
