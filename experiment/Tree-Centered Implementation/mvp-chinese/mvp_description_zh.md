# Tree-Centered Implementation - MVP Description

## MVP 1.0 - Tree-Centered Implementation 架构概念验证

本MVP验证了基于递归分解的代码生成方法的核心概念：

### 语义停止条件 (Semantic Stop Conditions)
分解在节点变为纯函数或原子操作时停止，而非基于任意行数判断。

- **纯函数 (Pure Function)**: 无副作用、确定性执行
  - 示例: calculate_totals(prices, tax_rate) -> total
  - 特点: 仅数学转换，无状态依赖，无I/O操作

- **原子操作 (Atomic Operation)**: 对单个数据源的单一操作
  - 示例: reserve_inventory(product_id, quantity) -> bool
  - 特点: 读写/写单个数据源

### 全局状态保存 (Global State Conservation)
父节点将所有数据操作委托给子节点，确保可追踪的状态变更。

- 父节点代码必须使用所有声明的子函数
- 数据操作必须通过子节点执行
- 每个节点声明其数据操作（源名称、操作类型、描述）

### 分解-验证循环 (Decomposition-Verification Loop)
每个分解通过组合验证后才继续。

- AST验证: 代码语法正确性
- 子函数使用验证: 父节点调用所有子函数
- 接口保留验证: 父子节点输入/输出匹配

---

## MVP 测试结果 (Personal Task Manager 示例)

### 节点统计
| 指标 | 数值 |
|------|------|
| 总节点数 | 26 |
| 叶节点 | 20 |
| 通过验证 | 26/26 |
| 最大深度 | 3 |

### 停止条件分布
| 类型 | 数量 |
|------|------|
| Pure Function | 16 nodes |
| Atomic Operation | 4 nodes |

### 生成的节点树结构

```
PersonalTaskManager（个人任务管理器主入口）
│
├── root_0_parse_user_input（解析用户输入）
│   ├── root_0_0_normalize_input_string（规范化输入字符串）
│   │   └── 功能：将用户输入的原始字符串进行标准化处理，去除多余空白字符
│   │
│   ├── root_0_1_extract_command_and_tokens（提取命令和标记）
│   │   └── 功能：从规范化后的输入中解析出命令类型和参数标记
│   │
│   ├── root_0_2_validate_and_normalize_command（验证并规范化命令）
│   │   ├── root_0_2_0_validate_command_exists（验证命令是否存在）
│   │   │   └── 功能：检查输入命令是否为系统支持的有效命令
│   │   │
│   │   ├── root_0_2_1_normalize_command_case（规范化命令大小写）
│   │   │   └── 功能：将命令转换为标准的小写格式
│   │   │
│   │   ├── root_0_2_2_validate_command_type（验证命令类型）
│   │   │   └── 功能：确认命令属于create/list/complete/delete之一
│   │   │
│   │   └── root_0_2_3_handle_invalid_command（处理无效命令）
│   │       └── 功能：生成无效命令的错误响应信息
│   │
│   └── root_0_3_parse_arguments_for_command（为命令解析参数）
│       ├── root_0_3_0_parse_create_arguments（解析创建参数）
│       │   └── 功能：从用户输入中提取title和description字段
│       │
│       ├── root_0_3_1_parse_list_arguments（解析列表参数）
│       │   └── 功能：提取status_filter筛选条件
│       │
│       ├── root_0_3_2_parse_complete_arguments（解析完成参数）
│       │   └── 功能：提取要完成的任务ID
│       │
│       └── root_0_3_3_parse_delete_arguments（解析删除参数）
│           └── 功能：提取要删除的任务ID
│
├── root_1_handle_list_tasks（处理列出任务）
│   ├── root_1_0_extract_status_filter（提取状态筛选器）
│   │   └── 功能：从task_data中获取状态筛选条件（pending/completed/all）
│   │
│   ├── root_1_1_filter_tasks_by_status（按状态筛选任务）
│   │   └── 功能：根据筛选条件过滤任务列表
│   │
│   └── root_1_2_format_task_list_result（格式化任务列表结果）
│       └── 功能：将任务列表格式化为标准输出格式
│
├── root_2_handle_complete_task（处理完成任务）
│   ├── root_2_0_validate_task_exists（验证任务存在）
│   │   └── 功能：检查指定ID的任务是否存在于任务字典中
│   │
│   ├── root_2_1_update_task_status（更新任务状态）
│   │   └── 功能：将任务状态修改为completed
│   │
│   ├── root_2_2_create_success_response（创建成功响应）
│   │   └── 功能：生成任务完成操作的成功响应
│   │
│   └── root_2_3_create_error_response（创建错误响应）
│       └── 功能：生成任务完成操作的错误响应
│
└── root_3_handle_delete_task（处理删除任务）
    ├── root_3_0_validate_task_exists（验证任务存在）
    │   └── 功能：检查指定ID的任务是否存在于任务字典中
    │
    ├── root_3_1_remove_task_from_dict（从字典中移除任务）
    │   └── 功能：从内存字典中删除指定的任务记录
    │
    ├── root_3_2_create_success_response（创建成功响应）
    │   └── 功能：生成任务删除操作的成功响应
    │
    └── root_3_3_create_error_response（创建错误响应）
        └── 功能：生成任务删除操作的错误响应
```

---

## 当前问题

### 高优先级
| 问题 | 影响 | 描述 |
|------|------|------|
| Global State Reset | 运行时错误 | tasks 和 next_id 在每次函数调用时重新初始化，导致调用间数据丢失 |
| next_id Update Loss | 功能错误 | generate_task_id() 返回更新的 next_id 但未持久化回调用者 |
| Missing Imports | 运行时错误 | datetime 和类型导入被使用但未在生成代码中声明 |

### 中优先级
| 问题 | 影响 | 描述 |
|------|------|------|
| Function Name Conflicts | 潜在覆盖 | 不同分支中出现相同函数名（如 complete 和 delete 处理器中的 validate_task_exists） |
| Type Annotations | 不完整 | 某些生成代码使用类型但无正确导入 |
| State Management | 架构差距 | 应用中无统一状态管理 |

### 低优先级
| 问题 | 影响 | 描述 |
|------|------|------|
| No Execution Testing | 验证差距 | 代码通过AST验证但未实际执行 |
| No Error Handling | 健壮性 | 生成代码缺乏全面的错误处理 |
| No Cross-cutting Concerns | 架构差距 | 日志、缓存、身份验证未解决 |

---

## 通往 2.0 的路线图

### Phase 1: Auto-Assembly Module
**目标**: 自动将生成的节点文件组合成可运行应用

- [ ] Import management - 收集和去重所有所需导入
- [ ] State manager class - 用 TaskStore 类替换模块级全局变量
- [ ] Function namespace resolution - 解析命名冲突
- [ ] Entry point generation - 创建主CLI或API入口

### Phase 2: Execution Testing
**目标**: 验证语法和运行时行为

- [ ] Unit test generation for each leaf node
- [ ] Integration test generation for parent nodes
- [ ] Mock framework integration for data sources
- [ ] Test execution and feedback loop

### Phase 3: Enhanced Validation
**目标**: 在分解时捕获更多问题

- [ ] Global state conservation verification
- [ ] Data operation type checking
- [ ] Contract compatibility verification between parent and children
- [ ] Cycle detection in data dependencies

### Phase 4: Cross-cutting Concerns
**目标**: 解决非功能性需求

- [ ] Logging injection
- [ ] Error handling patterns
- [ ] Retry mechanisms for external services
- [ ] Basic caching strategies

---

## 核心组件

| 文件 | 用途 |
|------|------|
| main.py | 带配置选项的CLI入口点 |
| decomposer.py | 带语义停止条件的基于LLM的节点分解 |
| code_generator.py | 为父节点和叶节点生成基于LLM的代码 |
| validator.py | AST验证和子函数使用验证 |
| models.py | 节点、契约和数据源的数据结构 |
| tree_builder.py | 带深度优先遍历的递归树构建 |

---

## 节点类型

系统识别三种节点类型作为停止条件：

| 类型 | 描述 | 示例 |
|------|------|------|
| **Pure Function** | 无副作用、确定性 | calculate_totals(), validate_input() |
| **Atomic Operation** | 对单个数据源的单一操作 | store_task(), read_config() |
| **Coordination** | 编排多个子节点 | handle_create_task() |

---

## 验证流程

系统验证：
1. **AST正确性** - 生成代码必须是语法有效的Python
2. **子函数使用** - 父节点必须使用所有声明的子函数
3. **接口保留** - 父节点输入/输出与规范匹配

如果验证失败，系统自动使用错误反馈重新分解。

---

## 输出结构

```
output/
├── decomposition_tree.json    # 完整树，包含所有节点元数据
└── nodes/
    ├── root_PersonalTaskManager.py      # 根节点
    ├── root_0_handle_create_task.py     # Level 1 节点
    ├── root_0_0_validate_task_data.py   # Level 2 节点
    └── ...                              # 叶节点
```
