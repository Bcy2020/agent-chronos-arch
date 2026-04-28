# 树中心实现

针对**树中心实现优化**架构的概念验证实现，通过递归分解实现自动化代码生成。

## 项目变体

| 目录 | 状态 | 说明 |
|------|------|------|
| `mvp-schema-improved/` | **当前活跃** | 最新实现：JsonPRD/SubPRD 模式、全局状态守恒、签名锁定 |
| `mvp-chinese/` | 已跟踪 | 原始 MVP（中文分解支持） |
|                        |              |                                                       |

## 概述

本实现验证了树中心分解方法的核心概念：

1. **结构化 PRD 模式** — 自然语言 PRD 转换为 JsonPRD，再分解为每个节点的 SubPRD
2. **签名锁定** — 子节点的函数签名是父节点锁定的契约，由 AST 验证强制执行
3. **全局状态守恒** — 父节点将所有数据操作委托给子节点；系统验证完整性和正确性
4. **分解-验证循环** — 每次分解在继续前都通过组合进行验证；根据错误类型触发重分解或代码重生成

## 架构

### 核心组件

| 文件 | 用途 |
|------|------|
| `main.py` | CLI 入口点，根据 JsonPRD 构造根节点 |
| `prd_converter.py` | 自然语言 → JsonPRD 转换（基于 LLM），缓存至 `.chronos/prd.json` |
| `models.py` | 数据模型：JsonPRD、SubPRD、节点、契约、状态操作 |
| `decomposer.py` | 基于 LLM 的节点分解，带签名锁定 |
| `code_generator.py` | 基于 LLM 的代码生成，带签名强制 |
| `validator.py` | AST 验证、签名检查、子节点使用验证、状态守恒检查 |
| `tree_builder.py` | 递归树构建，带每节点紧耦合回路 |
| `api_client.py` | OpenAI 兼容 API 客户端 |
| `config.py` | 配置，支持环境变量覆盖 |

### 每节点紧耦合回路

```
[tree_builder._process_parent_node]
     │
     ├─ ① 分解 (LLM) → 带锁定签名的子节点
     │     失败: 重试分解
     │
     ├─ ② 守恒检查 → 验证父节点状态操作 = Σ(子节点状态操作)
     │     失败: 清空子节点 → 重分解
     │
     ├─ ③ 代码生成 (LLM) → 使用子接口的 Python 代码
     │     失败: 重试代码生成
     │
     ├─ ④ AST 验证 → 语法 + 签名 + 子节点使用
     │     ├─ "子函数未使用": 清空子节点 → 重分解
     │     └─ 其他错误 (签名、语法): 重试代码生成
     │
     └─ 预算耗尽 → 标记 needs_human_intervention
```

## 特性

### 模式改进（相较于原始 MVP）

| 特性 | 说明 |
|------|------|
| **JsonPRD** | 结构化 PRD：元数据、功能需求、全局状态源、I/O 规范 |
| **SubPRD** | 每节点任务规范：可追溯性、约束、验收标准 |
| **PRD 转换器** | 基于 LLM 的自然语言 → JsonPRD 转换，可缓存复现 |
| **全局状态源** | 所有共享数据存储的形式化声明（类型、模式、初始状态） |
| **状态操作** | 每节点对全局状态的读/写/删除操作声明 |

### 验证

| 验证项 | 方法 | 触发条件 |
|--------|------|----------|
| **AST 正确性** | `ast.parse()` | 生成代码的语法有效性 |
| **签名匹配** | `validate_signature()` | 参数名、类型、返回类型与节点声明一致 |
| **子节点使用** | `check_child_usage()` | 父代码调用所有声明的子函数 |
| **状态守恒** | `check_conservation()` | 父状态操作 ⊆ Σ(子状态操作)：完整性、正确性 |
| **接口保持** | 输入/输出匹配 | 父 I/O 与 SubPRD 规范一致 |

### 签名锁定

子节点签名在**分解时锁定**。分解 LLM 声明每个子节点的精确输入/输出类型；代码生成 LLM 必须严格遵循。验证器检查：

- 函数名匹配节点名
- 参数名与声明一致
- 参数类型与声明一致（通过类型注解）
- 返回类型与声明一致

签名验证错误触发**代码重生成**（而非重分解），因为属于代码质量层面的问题，接口本身不变。

### 全局状态守恒

状态守恒定律：父节点的全局操作必须等于其所有子节点操作的**并集**。

三种检查：

1. **完整性** — 每个子节点的状态操作引用的数据源都必须在父节点 SubPRD 中定义
2. **正确性** — 父节点的每个状态操作都至少有一个子节点覆盖
3. **原子性** —（宽松）每个数据源至少被一个子节点操作

守恒违反触发**重分解**，因为属于接口设计层面的问题。

## 安装

```bash
# 进入当前实现目录
cd experiment/Tree-Centered\ Implementation/mvp-schema-improved

# 创建虚拟环境
python -m venv venv

# 激活（Windows）
venv\Scripts\activate
# 激活（Linux/Mac）
source venv/bin/activate

# 安装依赖
pip install openai python-dotenv
```

## 配置

创建 `.env` 文件：

```
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

## 使用

### 基本用法

```bash
python main.py --input test_prd.md --output ./output
```

### CLI 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--input`, `-i` | 必填 | PRD 输入文件路径 |
| `--output`, `-o` | `output` | 输出目录 |
| `--max-depth` | 3 | 最大分解深度 |
| `--max-children` | 4 | 每个节点最大子节点数 |
| `--temperature`, `-t` | 0.3 | LLM 温度参数 |
| `--model` | `deepseek-chat` | LLM 模型名称 |
| `--verbose`, `-v` | 无 | 启用详细输出 |

### 输出结构

```
output/
├── assessment_report.md           # 完整验证评估报告
├── decomposition_tree.json        # 完整树结构（含元数据）
├── .chronos/
│   └── prd.json                   # 缓存的 JsonPRD
└── nodes/
    ├── root_PersonalTaskManager.py       # 根节点
    ├── root_0_ParseCommand.py            # 第一层节点
    ├── root_0_0_ValidateCommandType.py   # 第二层节点（叶子）
    └── ...                               # 所有生成的节点
```

## 相关文档

- [Tree-Centered Implementation Refinement (英文)](../../docs/Tree-Centered%20Implementation%20Refinement.md) - 完整架构规范
- [Tree-Centered Implementation Refinement (中文)](../../docs/Tree-Centered%20Implementation%20Refinement-zh.md) - 中文版架构文档
