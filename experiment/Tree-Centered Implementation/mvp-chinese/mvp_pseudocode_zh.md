# Tree-Centered Implementation MVP - 详细伪代码流程

## 整体架构概述

```
PRD文档 → main.py → TreeBuilder → Decomposer(LMM) → 生成子节点 → CodeGenerator(LLM) → 生成代码 → Validator(验证) → 失败则重新分解
```

---

## 1. 程序入口 - main.py

### 1.1 读取配置文件

```
程序启动
    ↓
解析命令行参数（argparse）
    ├── --input: PRD文件路径（必填）
    ├── --output: 输出目录（默认"output"）
    ├── --max-depth: 最大分解深度（默认3）
    ├── --max-children: 每个节点最大子节点数（默认4）
    └── ...其他参数
    ↓
检查API密钥（环境变量或命令行参数）
    ↓
创建Config配置对象
    ↓
调用 create_root_from_prd() 创建根节点
        ├── 读取PRD文件内容
        ├── 提取前10行非注释行作为目的描述
        ├── 根据文件名或--name参数生成系统名称
        └── 返回Node对象（根节点）
    ↓
创建TreeBuilder对象
    ↓
调用 builder.build_tree(root_node) 开始分解
    ↓
保存分解树到JSON文件
    ↓
输出汇总信息
```

### 1.2 主函数伪代码

```python
def main():
    # 1. 解析命令行参数
    args = parse_args()

    # 2. 验证输入文件存在
    if not file_exists(args.input):
        exit("错误：输入文件不存在")

    # 3. 获取API密钥
    api_key = args.api_key or env["DEEPSEEK_API_KEY"]
    if not api_key:
        exit("错误：需要API密钥")

    # 4. 创建配置对象
    config = Config(
        api_key=api_key,
        max_depth=args.max_depth,
        max_children=args.max_children,
        # ... 其他配置
    )

    # 5. 从PRD创建根节点
    root = create_root_from_prd(args.input, args.name)

    # 6. 创建树构建器并执行分解
    builder = TreeBuilder(config)
    result = builder.build_tree(root)

    # 7. 保存结果
    filename = f"{root.name.lower()}_decomposition_tree.json"
    builder.save_tree(result, filename)

    # 8. 输出汇总
    print(f"根节点: {result.name}")
    print(f"验证结果: {'通过' if result.validation.passed else '失败'}")
```

---

## 2. 核心控制器 - TreeBuilder

### 2.1 初始化

```
TreeBuilder初始化时：
    1. 创建APIClient（用于调用LLM）
    2. 创建Decomposer（用于分解节点）
    3. 创建CodeGenerator（用于生成代码）
    4. 创建Validator（用于验证代码）
    5. 创建输出目录（如果不存在）
```

### 2.2 构建树的递归流程（核心）

```
build_tree(root_node)
    │
    ▼
_build_tree_recursive(node)
    │
    ├──_process_node(node)  ──────────────────────────────────┐
    │   │                                                          │
    │   ├── 如果 node.stop_decompose == True                       │
    │   │   → 这是一个叶子节点                                      │
    │   │   → 调用 _process_leaf_node(node)                        │
    │   │                                                          │
    │   ├── 如果 node.depth >= max_depth                           │
    │   │   → 达到最大深度                                          │
    │   │   → 设置 stop_decompose = True                           │
    │   │   → 调用 _process_leaf_node(node)                         │
    │   │                                                          │
    │   └── 否则                                                     │
    │       → 这是一个父节点                                        │
    │       → 调用 _process_parent_node(node)                       │
    │                                                              │
    └────────────────────────── 返回 (node, success) ◄──────────────┘
                                │
                                ▼
                          如果 success == False
                              → 返回 node（可能包含错误）

                          如果 success == True 且 node.stop_decompose == True
                              → 这是一个叶子节点
                              → 直接返回 node

                          否则（有子节点需要处理）
                              ▼
                          对每个子节点循环：
                              child_node = _build_tree_recursive(child)
                              processed_children.append(child_node)

                          node.children = processed_children
                          return node
```

### 2.3 处理叶子节点（Leaf Node）

```
叶子节点：不需要继续分解的节点（Pure Function 或 Atomic Operation）

_process_leaf_node(node)
    │
    ▼
调用 CodeGenerator.generate_for_leaf(node)
    │
    ├── 发送请求到LLM
    ├── LLM生成完整的Python代码
    └── 返回 (code, errors)
    │
    ▼
如果有错误
    → node.validation.passed = False
    → node.validation.errors = errors
    → return (node, False)
    │
    ▼
否则
    → 调用 Validator.validate(node, code)
    │   ├── 验证语法（AST解析）
    │   ├── 验证接口保留（参数名、返回值）
    │   └── 验证子函数使用（叶子节点不需要）
    │
    ▼
如果验证通过
    → node.code = code
    → 保存代码到文件
    → return (node, True)
    │
    ▼
如果验证失败
    → return (node, False)
```

### 2.4 处理父节点（Parent Node）

```
父节点：需要分解为多个子节点的节点

_process_parent_node(node)
    │
    ▼
设置 retry_count = 0
设置 max_retries = config.max_decompose_retries（默认3）
    │
    ▼
循环 while retry_count < max_retries：
    │
    ├── 第1次尝试（或重试时）
    │   → 调用 Decomposer.decompose(node)
    │   │   ├── 发送请求到LLM
    │   │   │   └── LLM根据系统功能描述，将节点分解为多个子节点
    │   │   │       （每个子节点有自己的：名称、用途、输入、输出、边界）
    │   │   └── 返回 (node_with_children, errors)
    │   │
    │   └── 如果分解失败
    │       → retry_count += 1
    │       → 继续下一次循环
    │
    ├── 调用 CodeGenerator.generate_for_parent(node)
    │   ├── 发送请求到LLM
    │   ├── LLM生成调用子节点的代码
    │   └── 返回 (code, errors)
    │
    ├── 调用 Validator.validate(node, code)
    │   ├── 验证语法
    │   ├── 验证接口保留
    │   └── 验证"所有子函数都被父节点调用"
    │
    ├── 如果验证通过
    │   → 保存代码到文件
    │   → return (node, True)
    │
    └── 如果验证失败
        → 如果 Validator.should_redecompose() 返回 True
        │   → 清空子节点（准备重新分解）
        │   → retry_count += 1
        │   → 继续下一次循环
        │
        └── 否则
            → retry_count += 1
            → return (node, False)

如果超过最大重试次数
→ return (node, False)
```

---

## 3. 分解器 - Decomposer

### 3.1 分解流程

```
decompose(node)
    │
    ▼
构建发送给LLM的消息
    │
    ├── System Prompt（系统提示）
    │   └── 告诉LLM：
    │       1. 你是一个软件分解专家
    │       2. 所有描述性内容必须用中文
    │       3. 每个子节点必须是函数，不能是类
    │       4. 何时停止分解（Pure Function / Atomic Operation / 达到最大深度）
    │       5. 输出格式必须是JSON
    │
    └── User Prompt（用户提示）
        └── 告诉LLM：
            1. 要分解的节点信息（名称、用途、输入、输出）
            2. 边界约束
            3. 数据源信息
            4. 最大子节点数量限制
            5. 如果有之前的错误，也要告知
    │
    ▼
发送请求到APIClient.chat()
    │
    ▼
解析LLM返回的JSON响应
    │
    ▼
创建子节点对象
    │
    对于LLM返回的每个子节点数据：
        ├── 创建Node对象
        ├── 设置node_id = "父节点id_序号"
        ├── 设置depth = 父节点depth + 1
        ├── 判断是否应该停止分解
        └── 添加到node.children列表
    │
    ▼
保存子节点的契约信息（children_contracts）
    │
    ▼
返回 (更新后的node, errors)
```

### 3.2 分解结果示例

假设LLM返回的JSON如下：
```json
{
  "children": [
    {
      "name": "validate_input",
      "purpose": "验证用户输入是否合法",
      "inputs": [{"name": "user_input", "type": "str", "description": "用户输入"}],
      "outputs": [{"name": "is_valid", "type": "bool", "description": "是否有效"}],
      "node_type": "pure_function",
      "stop_decompose": true
    },
    {
      "name": "process_data",
      "purpose": "处理并转换数据",
      "inputs": [{"name": "data", "type": "dict", "description": "输入数据"}],
      "outputs": [{"name": "result", "type": "dict", "description": "处理结果"}],
      "node_type": "coordination",
      "stop_decompose": false
    }
  ]
}
```

分解后会创建这样的树结构：
```
原始节点
├── validate_input (stop_decompose=True, 类型: pure_function)
└── process_data (stop_decompose=False, 类型: coordination)
    ├── (process_data的子节点...)
    └── ...
```

---

## 4. 代码生成器 - CodeGenerator

### 4.1 为叶子节点生成代码

```
generate_for_leaf(node)
    │
    ▼
构建提示词
    ├── 告诉LLM这是一个叶子节点
    ├── 提供节点的完整信息（名称、用途、输入、输出）
    ├── 提供数据源信息（如果有）
    └── 要求生成完整的、可运行的Python代码
    │
    ▼
发送请求到LLM
    │
    ▼
LLM返回JSON格式：
{
  "code": "def function_name(...):\n    ...",
  "imports": ["import os", "from typing import ..."],
  "implementation_notes": "实现说明..."
}
    │
    ▼
返回 (code, errors)
```

### 4.2 为父节点生成代码

```
generate_for_parent(node)
    │
    ▼
构建提示词
    ├── 告诉LLM这是父节点
    ├── 提供父节点的接口信息
    ├── 提供所有子节点的契约信息（名称、用途、签名、数据操作）
    ├── 提供分解原理说明
    └── 要求生成调用子节点的代码
    │
    ▼
发送请求到LLM
    │
    ▼
LLM返回JSON格式：
{
  "code": "def parent_function(...):\n    child1_result = child1(...)\n    child2_result = child2(...)",
  "imports": [...],
  "child_calls": ["child1", "child2"],
  "implementation_notes": "..."
}
    │
    ▼
返回 (code, errors)
```

### 4.3 父节点代码示例

假设有3个子节点：child_a, child_b, child_c

LLM可能生成这样的父节点代码：
```python
def handle_create_task(command, task_data, tasks, next_id):
    # 验证输入数据
    is_valid, error = validate_task_data(command, task_data)
    if not is_valid:
        return {'success': False, 'message': error}

    # 生成任务ID
    new_id = generate_task_id(next_id)

    # 创建任务对象
    task = create_task_object(new_id, task_data)

    # 存储任务
    tasks[new_id] = task

    # 返回成功响应
    return {'success': True, 'message': f'Created task {new_id}'}
```

---

## 5. 验证器 - Validator

### 5.1 验证步骤

```
validate(node, code)
    │
    ▼
第一步：验证语法
    │
    ├── 使用Python的ast.parse()解析代码
    ├── 如果解析成功 → 语法正确
    └── 如果解析失败 → 返回语法错误
    │
    ▼
第二步：验证接口保留（仅当语法正确）
    │
    ├── 从node获取期望的参数名列表
    ├── 从生成的代码中提取实际函数定义
    ├── 比较两者是否一致
    └── 检查函数名是否匹配
    │
    ▼
第三步：验证子函数使用（仅当node有子节点时）
    │
    ├── 从node.children获取所有子节点名称
    ├── 从生成的代码中提取所有函数调用
    ├── 比较：是否有子节点函数未被调用？
    └── 如果有 → 返回错误
    │
    ▼
第四步：验证全局变量（仅当node声明了全局变量时）
    │
    ├── 检查代码中是否有未声明的global声明
    └── 如果有 → 返回错误
    │
    ▼
返回 ValidationResult(passed, errors)
```

### 5.2 验证失败示例

```python
# 假设某个父节点有3个子节点：child_a, child_b, child_c

# 但是生成的代码是：
def parent_func(x):
    result_a = child_a(x)  # 只调用了child_a
    return result_a

# 验证器会发现：
# - child_b 没有被调用
# - child_c 没有被调用
# → 验证失败，返回错误："Child functions not used: {child_b, child_c}"
```

### 5.3 决定是否重新分解

```
should_redecompose(node, validation)
    │
    ▼
如果 validation.passed == True
    → 返回 False（不需要重新分解）
    │
    ▼
如果 node.validation.retry_count >= max_retries
    → 返回 False（已达到最大重试次数）
    │
    ▼
检查错误类型：
    ├── 如果错误包含 "Child functions not used"
    │   → 返回 True（需要重新分解）
    │
    ├── 如果错误包含 "Missing parameters"
    │   → 返回 True（需要重新分解）
    │
    └── 如果错误包含 "Function name mismatch"
        → 返回 True（需要重新分解）
        │
        ▼
    否则
    → 返回 False（不需要重新分解）
```

---

## 6. API客户端 - APIClient

### 6.1 发送聊天请求

```
chat(messages, temperature, max_tokens)
    │
    ▼
设置重试次数 = 0
    │
    ▼
循环直到成功或达到最大重试次数：
    │
    ├── 尝试调用 OpenAI API
    │   ├── 发送 messages 到 DeepSeek
    │   ├── 设置 temperature（温度参数）
    │   └── 设置 max_tokens（最大token数）
    │
    ├── 如果成功
    │   → 返回 response.choices[0].message.content
    │
    └── 如果失败
        → last_error = 错误信息
        → retry_count += 1
        → 如果还有重试机会，等待 2^retry_count 秒后重试
        │
        ▼
如果所有重试都失败
→ 抛出 RuntimeError
```

---

## 7. 完整执行流程示例

假设我们运行：
```bash
python main.py --input test_prd.md --max-depth 3
```

### 7.1 执行步骤

```
1. main.py 启动
   ↓
2. 读取 test_prd.md，创建根节点 PersonalTaskManager
   ↓
3. TreeBuilder.build_tree() 开始
   │
   ├─ 处理根节点 PersonalTaskManager (depth=0)
   │   - 不是叶子，调用 _process_parent_node()
   │   - 调用 Decomposer.decompose()
   │   - LLM返回4个子节点：parse_user_input, handle_list_tasks, handle_complete_task, handle_delete_task
   │   - 调用 CodeGenerator.generate_for_parent()
   │   - 验证代码...
   │   - 通过！
   │
   ├─ 处理子节点 parse_user_input (depth=1)
   │   - 不是叶子，继续分解
   │   - 调用 Decomposer.decompose()
   │   - LLM返回3个子节点
   │   - ...
   │
   ├─ 处理 parse_user_input 的子节点 (depth=2)
   │   - 如果 stop_decompose==True，生成叶子代码
   │   - 否则继续分解...
   │
   └─ 继续递归处理所有节点...
   │
   ▼
4. 所有节点处理完成
   ↓
5. 保存 decomposition_tree.json
   ↓
6. 保存所有 Python 文件到 output/nodes/
   ↓
7. 输出汇总信息
```

### 7.2 最终输出结构

```
output/
├── personaltaskmanager_decomposition_tree.json
└── nodes/
    ├── root_PersonalTaskManager.py
    ├── root_0_parse_user_input.py
    ├── root_0_0_normalize_input_string.py
    ├── root_0_1_extract_command_and_tokens.py
    ├── root_0_2_validate_and_normalize_command.py
    ├── root_0_2_0_validate_command_exists.py
    ├── root_0_2_1_normalize_command_case.py
    ├── root_0_2_2_validate_command_type.py
    ├── root_0_2_3_handle_invalid_command.py
    ├── root_0_3_parse_arguments_for_command.py
    ├── root_0_3_0_parse_create_arguments.py
    ├── root_0_3_1_parse_list_arguments.py
    ├── root_0_3_2_parse_complete_arguments.py
    ├── root_0_3_3_parse_delete_arguments.py
    ├── root_1_handle_list_tasks.py
    ├── root_1_0_extract_status_filter.py
    ├── root_1_1_filter_tasks_by_status.py
    ├── root_1_2_format_task_list_result.py
    ├── root_2_handle_complete_task.py
    ├── root_2_0_validate_task_exists.py
    ├── root_2_1_update_task_status.py
    ├── root_2_2_create_success_response.py
    ├── root_2_3_create_error_response.py
    ├── root_3_handle_delete_task.py
    ├── root_3_0_validate_task_exists.py
    ├── root_3_1_remove_task_from_dict.py
    ├── root_3_2_create_success_response.py
    └── root_3_3_create_error_response.py
```

---

## 8. 关键概念解释

### 8.1 节点类型

| 类型 | 说明 | 何时标记 |
|------|------|----------|
| Coordination | 协调多个子节点 | 需要调用多个子函数 |
| Pure Function | 纯函数，无副作用 | 只做数学转换，无I/O |
| Atomic Operation | 原子操作 | 对单个数据源的单一操作 |

### 8.2 停止分解条件

满足以下任一条件，节点标记为叶子：
1. node_type 是 `pure_function` 或 `atomic_operation`
2. depth >= max_depth（达到最大深度）
3. LLM返回 `stop_decompose: true`

### 8.3 验证失败处理

如果验证失败，根据错误类型决定：
- 子函数未使用 → 重新分解
- 参数不匹配 → 重新分解
- 其他错误 → 不重新分解，直接标记失败

---

## 9. 数据流总结

```
PRD文档
    ↓
Node对象（根节点）
    ↓
┌─────────────────────────────────────────────────────────────┐
│                    递归分解循环                               │
│                                                             │
│  while 还有节点要处理:                                       │
│      获取一个节点                                            │
│          ↓                                                  │
│      是叶子节点? ─是→ 生成代码 → 验证 → 保存                   │
│          ↓否                                                 │
│      是父节点? ─是→ 分解成子节点 → 生成父代码 → 验证            │
│          ↓                                                   │
│      处理子节点 (递归)                                        │
└─────────────────────────────────────────────────────────────┘
    ↓
JSON树文件 + Python代码文件
```
