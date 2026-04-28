# Benchmark 评测系统

## 目录结构

```
benchmark/
├── semantic_model.md          # 语义概念清单（稳定）
├── run_benchmark.py           # 自动化评测入口脚本
├── adapters/
│   └── adapter_v1.py          # 当前schema适配器（示例）
├── results/                   # 评测结果存放目录
└── README.md
```

## 快速使用

```bash
# 机械化评测（自动化）
python run_benchmark.py \
    --tree <分解树JSON路径> \
    --nodes <nodes代码目录路径> \
    --adapter <适配器文件路径> \
    --output <输出目录路径>

# 主观评价（LLM评分）
/subjective-eval <evaluator_id> <project_dir> <output_dir>

# 汇总结果
python summarize_benchmark.py \
    --input <评分JSON文件夹> \
    --output <CSV输出路径> \
    --project <项目名称>
```

输出：
- `output/tree_report.json` 分解树结构评测结果
- `output/code_report.json` 代码质量评测结果
- `output/evaluator_*.json` 主观评价结果
- `summary.csv` 汇总CSV

## 权重分配

| 类型 | 权重 | 说明 |
|------|------|------|
| 自动化评分 | 30% | 可量化、客观指标（较少） |
| 主观评分 | 70% | 需要LLM判断的质量维度（主要） |

### 自动化指标权重（内部分配）

| 指标 | 权重 | 说明 |
|------|------|------|
| decomposition_success_rate | 15% | 分解成功率（核心） |
| syntax_pass_rate | 15% | 语法正确率（核心） |
| no_conflict_rate | 15% | 无冲突率（核心） |
| semantic_stop_rate | 10% | 语义停止达成率 |
| first_try_success_rate | 10% | 首次成功率 |
| annotation_pass_rate | 10% | 类型注解率 |
| forced_stop_rate | 5% | 非强制停止率 |
| traceability_rate | 5% | 追溯覆盖率 |
| global_ops_rate | 5% | 全局状态声明率 |

### 主观维度权重（内部分配）

| 维度 | 权重 | 说明 |
|------|------|------|
| 代码正确性 | 15% | 逻辑是否正确 |
| 边界遵守度 | 15% | 是否越界 |
| 需求覆盖完整性 | 15% | PRD覆盖度 |
| 代码可运行性 | 10% | 运行风险 |
| 代码风格质量 | 10% | 命名、注释 |
| 接口一致性 | 10% | 签名匹配 |
| 分解粒度适当性 | 10% | 粒度合理 |
| 语义停止达成率 | 10% | 语义停止 |
| 可维护性预估 | 5% | 易修改性 |

## 评测维度

### 分解树结构评测

| 维度 | 说明 | 计算方法 |
|------|------|----------|
| 语义停止达成率 | 因语义原因停止的叶节点比例 | `semantic_stop_leaf / total_leaf` |
| 强制停止率 | 因max_depth等强制截断的叶节点比例 | `forced_stop_leaf / total_leaf` |
| 需求追溯覆盖率 | 有追溯链的节点比例 | `traced_nodes / total_nodes` |
| 全局状态声明率 | 有global_state_ops的节点比例 | `global_ops_nodes / total_nodes` |
| **分解成功率** | 通过验证的节点比例 | `validation_passed / total_nodes` |
| **首次成功率** | 首次尝试即成功的节点比例 | `retry_count==0 and passed / total_nodes` |
| **平均重试次数** | 每节点平均重试次数 | `sum(retry_count) / total_nodes` |
| 深度分布 | 各深度的节点数量 | `{depth: count}` |
| 扇出分布 | 各扇出数的父节点数量 | `{children_count: count}` |

### 代码质量评测

| 维度 | 说明 | 计算方法 |
|------|------|----------|
| 语法正确率 | ast.parse成功率 | `syntax_ok / total_nodes` |
| 类型注解率 | 有完整类型注解的比例 | `has_annotation / total_nodes` |
| global使用率 | 使用global语句的比例 | `has_global / total_nodes` |
| 参数冲突率 | 参数与global重名的比例 | `has_conflict / total_nodes` |

## 输出格式

JSON格式，精简只保留汇总和问题节点：

```json
{
  "summary": { ... },
  "metrics": { ... },
  "distribution": { ... },
  "issues": {
    "forced_stop_nodes": ["node_id_1", "node_id_2"]
  }
}
```