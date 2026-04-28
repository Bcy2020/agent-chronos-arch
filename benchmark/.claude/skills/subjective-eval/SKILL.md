---
name: subjective-eval
description: 对分解树和代码进行主观质量评价。逐节点检查各维度，计算通过比例并换算分数。支持多LLM盲测评分。使用 `/subjective-eval` 手动触发。
disable-model-invocation: true
argument-hint: <evaluator_id> <project_dir> <output_dir>
arguments: [evaluator_id, project_dir, output_dir]
allowed-tools: Read Glob Agent Write
---

# 分解树主观质量评价

对PRD、分解树结构和生成的代码进行逐节点主观评价，计算通过比例并换算分数。

## 输入参数

- `$evaluator_id`: 评分员编号（如 `1`、`2`、`3`），用于多LLM盲测区分
- `$project_dir`: 待评审项目位置，包含分解树JSON和nodes目录
- `$output_dir`: 输出目录位置，评价结果将写入此目录

## 输出文件

评价结果将写入 `$output_dir/evaluator_$evaluator_id.json`

## 项目目录结构要求

待评审项目目录应包含：

```
$project_dir/
├── decomposition_tree.json    # 分解树JSON
├── nodes/                     # 生成的代码目录
│   ├── root_*.py
│   ├── root_0_*.py
│   └── ...
└── prd.md                     # PRD文档（可选）
```

## 评分标准

完整的评分维度、权重和换算规则请参阅 [scoring_criteria.md](scoring_criteria.md)。

简要概览：

- **代码维度**（60%）：正确性、可运行性、风格质量、边界遵守度、接口一致性
- **结构维度**（40%）：需求覆盖、粒度适当性、语义停止达成率、可维护性

## 辅助Agents

本项目使用两个辅助agent进行评价：

- **code-dimensions-eval**: 评估代码维度
- **structure-dimensions-eval**: 评估结构维度

## 执行步骤

1. **定位输入文件**
   - 分解树JSON: `$project_dir/decomposition_tree.json` 或 `$project_dir/*_decomposition_tree.json`
   - nodes目录: `$project_dir/nodes/`
   - PRD文档: `$project_dir/prd.md` 或从分解树顶层提取

2. **读取输入文件**
   - 读取分解树JSON
   - 遍历nodes目录读取所有.py代码文件

3. **并行调用辅助Agents**
   - 调用 `code-dimensions-eval` agent
   - 调用 `structure-dimensions-eval` agent
   - 两个agent并行执行

4. **汇总结果**
   - 合并两个agent的输出
   - 计算综合评分
   - 提取strengths、weaknesses、improvement_suggestions

5. **写入输出文件**
   - 输出路径: `$output_dir/evaluator_$evaluator_id.json`
   - 使用Write工具写入JSON

## 输出格式

```json
{
  "evaluator_id": "$evaluator_id",
  "project_dir": "$project_dir",
  "overall_score": 4.1,
  "weight_distribution": {
    "code_weight": 0.6,
    "structure_weight": 0.4
  },
  "code_dimensions": {
    "code_correctness": {
      "passed_nodes": 31,
      "failed_nodes": 2,
      "total_nodes": 33,
      "ratio": 0.9394,
      "score": 4,
      "weight": 0.15,
      "weighted_score": 0.60,
      "failed_details": [{"node_id": "...", "reason": "..."}]
    },
    "code_executability": { ... },
    "code_style": { ... },
    "boundary_adherence": { ... },
    "interface_consistency": { ... }
  },
  "structure_dimensions": {
    "requirement_coverage": { ... },
    "granulation": { ... },
    "semantic_stop": { ... },
    "maintainability": { ... }
  },
  "strengths": ["优点1", "优点2"],
  "weaknesses": ["弱点1", "弱点2"],
  "improvement_suggestions": ["建议1", "建议2"]
}
```

## 多LLM盲测使用方式

当进行多LLM盲测时，在不同LLM会话中分别调用：

```
# LLM 1 会话
/subjective-eval 1 ./project_output ./eval_results

# LLM 2 会话  
/subjective-eval 2 ./project_output ./eval_results

# LLM 3 会话
/subjective-eval 3 ./project_output ./eval_results
```

输出文件将分别为：
- `eval_results/evaluator_1.json`
- `eval_results/evaluator_2.json`
- `eval_results/evaluator_3.json`

后续可使用脚本计算评审者间一致性（Krippendorff's alpha）。

## 大项目分批策略

当节点数>=50时：

- 按深度分批：depth=0-1一批，depth=2-3一批，依此类推
- 或按子树分批：将大树拆分为子树独立评价
- 每批调用agent后汇总计算总体比例

## 权限说明

本skill具有以下权限：
- **Read**: 读取分解树JSON和代码文件
- **Glob**: 查找项目目录中的文件
- **Agent**: 调用辅助评价agent
- **Write**: 写入评价结果JSON文件