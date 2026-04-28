"""
Benchmark汇总脚本

汇总自动化评测和主观评测结果，输出CSV格式。

权重分配：
- 自动化评分: 40%（客观可量化指标）
- 主观评分: 60%（需要人工/LLM判断的质量维度）

用法：
python summarize_benchmark.py --input <评分JSON文件夹> --output <CSV输出路径>
"""

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Dict, List, Any


# ============================================================
# 权重配置
# ============================================================

WEIGHTS = {
    "automated": 0.30,  # 自动化评分权重（客观可量化）
    "subjective": 0.70  # 主观评分权重（需要LLM判断的质量维度）
}

# 自动化指标权重（在自动化部分内部）
AUTOMATED_METRICS_WEIGHTS = {
    # 分解树结构指标 (50%)
    "semantic_stop_rate": 0.10,       # 语义停止达成率
    "forced_stop_rate": 0.05,         # 强制停止率（负向指标，已转换）
    "decomposition_success_rate": 0.15,  # 分解成功率（核心指标）
    "first_try_success_rate": 0.10,   # 首次成功率
    "traceability_rate": 0.05,        # 追溯覆盖率
    "global_ops_rate": 0.05,          # 全局状态声明率
    # 代码质量指标 (50%)
    "syntax_pass_rate": 0.15,         # 语法正确率（核心指标）
    "annotation_pass_rate": 0.10,     # 类型注解率
    "no_conflict_rate": 0.15,         # 无冲突率（核心指标）
}

# 主观维度权重（在主观部分内部，已在skill中定义，此处用于汇总）
SUBJECTIVE_DIMENSIONS_WEIGHTS = {
    # 代码维度 (60%)
    "code_correctness": 0.15,
    "code_executability": 0.10,
    "code_style": 0.10,
    "boundary_adherence": 0.15,
    "interface_consistency": 0.10,
    # 结构维度 (40%)
    "requirement_coverage": 0.15,
    "granulation": 0.10,
    "semantic_stop": 0.10,
    "maintainability": 0.05,
}


# ============================================================
# 数据加载
# ============================================================

def load_json_files(input_dir: str) -> Dict[str, List[Dict]]:
    """加载文件夹中的所有JSON文件"""
    results = {
        "automated": [],
        "subjective": []
    }

    for filename in os.listdir(input_dir):
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(input_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 判断文件类型
        if filename.startswith('evaluator_'):
            results["subjective"].append({
                "evaluator_id": data.get("evaluator_id", filename),
                "data": data
            })
        elif filename in ['tree_report.json', 'code_report.json']:
            results["automated"].append({
                "type": "tree" if filename == 'tree_report.json' else "code",
                "data": data
            })

    return results


# ============================================================
# 自动化评分计算
# ============================================================

def calculate_automated_score(automated_data: List[Dict]) -> Dict:
    """计算自动化评分"""
    tree_data = None
    code_data = None

    for item in automated_data:
        if item["type"] == "tree":
            tree_data = item["data"]
        elif item["type"] == "code":
            code_data = item["data"]

    if not tree_data or not code_data:
        return {"score": 0, "details": "缺少自动化评测数据"}

    metrics = {}

    # 从tree_report提取
    if "metrics" in tree_data:
        metrics["semantic_stop_rate"] = tree_data["metrics"].get("semantic_stop_rate", 0)
        metrics["forced_stop_rate"] = tree_data["metrics"].get("forced_stop_rate", 0)
        metrics["decomposition_success_rate"] = tree_data["metrics"].get("decomposition_success_rate", 0)
        metrics["first_try_success_rate"] = tree_data["metrics"].get("first_try_success_rate", 0)
        metrics["traceability_rate"] = tree_data["metrics"].get("traceability_rate", 0)
        metrics["global_ops_rate"] = tree_data["metrics"].get("global_ops_rate", 0)

    # 从code_report提取
    if "summary" in code_data:
        metrics["syntax_pass_rate"] = code_data["summary"].get("syntax_pass_rate", 0)
        metrics["annotation_pass_rate"] = code_data["summary"].get("annotation_pass_rate", 0)
        metrics["no_conflict_rate"] = 1 - code_data["summary"].get("conflict_rate", 0)  # 转为无冲突率

    # 计算加权分数（归一化到0-5）
    total_weight = sum(AUTOMATED_METRICS_WEIGHTS.values())

    # 强制停止率需要转换为正向（越低越好 → 越高越好）
    metrics["forced_stop_rate"] = 1 - metrics.get("forced_stop_rate", 0)

    weighted_sum = sum(
        metrics.get(k, 0) * AUTOMATED_METRICS_WEIGHTS[k] * 5  # 乘以5归一化
        for k in AUTOMATED_METRICS_WEIGHTS
    )

    score = weighted_sum / total_weight

    return {
        "score": round(score, 2),
        "metrics": metrics
    }


# ============================================================
# 主观评分计算
# ============================================================

def calculate_subjective_score(subjective_data: List[Dict]) -> Dict:
    """计算主观评分（多评审者平均）"""
    if not subjective_data:
        return {"score": 0, "details": "缺少主观评测数据", "evaluator_count": 0}

    # 收集各评审者的overall_score
    overall_scores = []
    dimension_scores = {}

    for item in subjective_data:
        data = item["data"]
        overall_scores.append(data.get("overall_score", 0))

        # 收集各维度分数
        if "code_dimensions" in data:
            for dim_name, dim_data in data["code_dimensions"].items():
                if dim_name not in dimension_scores:
                    dimension_scores[dim_name] = []
                dimension_scores[dim_name].append(dim_data.get("score", 0))

        if "structure_dimensions" in data:
            for dim_name, dim_data in data["structure_dimensions"].items():
                if dim_name not in dimension_scores:
                    dimension_scores[dim_name] = []
                dimension_scores[dim_name].append(dim_data.get("score", 0))

    # 计算平均分数
    avg_overall = sum(overall_scores) / len(overall_scores)

    avg_dimensions = {
        dim: round(sum(scores) / len(scores), 2)
        for dim, scores in dimension_scores.items()
    }

    # 计算一致性（标准差）
    if len(overall_scores) > 1:
        variance = sum((s - avg_overall) ** 2 for s in overall_scores) / len(overall_scores)
        std_dev = round(variance ** 0.5, 2)
    else:
        std_dev = 0

    return {
        "score": round(avg_overall, 2),
        "evaluator_count": len(subjective_data),
        "std_deviation": std_dev,
        "avg_dimensions": avg_dimensions
    }


# ============================================================
# 综合评分计算
# ============================================================

def calculate_final_score(automated: Dict, subjective: Dict) -> Dict:
    """计算综合评分"""
    auto_score = automated.get("score", 0)
    subj_score = subjective.get("score", 0)

    final_score = (
        auto_score * WEIGHTS["automated"] +
        subj_score * WEIGHTS["subjective"]
    )

    return {
        "final_score": round(final_score, 2),
        "automated_score": auto_score,
        "automated_weight": WEIGHTS["automated"],
        "subjective_score": subj_score,
        "subjective_weight": WEIGHTS["subjective"],
        "evaluator_count": subjective.get("evaluator_count", 0),
        "std_deviation": subjective.get("std_deviation", 0)
    }


# ============================================================
# CSV输出
# ============================================================

def generate_csv_row(final: Dict, automated: Dict, subjective: Dict, project_name: str) -> Dict:
    """生成CSV行数据"""
    row = {
        "project_name": project_name,
        "final_score": final["final_score"],
        "automated_score": final["automated_score"],
        "automated_weight": final["automated_weight"],
        "subjective_score": final["subjective_score"],
        "subjective_weight": final["subjective_weight"],
        "evaluator_count": final["evaluator_count"],
        "std_deviation": final["std_deviation"],
    }

    # 添加自动化指标详情
    metrics = automated.get("metrics", {})
    for k, v in metrics.items():
        row[f"auto_{k}"] = round(v, 4)

    # 添加主观维度详情
    dims = subjective.get("avg_dimensions", {})
    for k, v in dims.items():
        row[f"subj_{k}"] = v

    return row


def write_csv(rows: List[Dict], output_path: str):
    """写入CSV文件"""
    if not rows:
        print("No data to write")
        return

    # 确保输出路径有.csv扩展名
    if not output_path.endswith('.csv'):
        output_path = output_path + '.csv'

    # 获取所有字段名
    fieldnames = list(rows[0].keys())

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV written to: {output_path}")


# ============================================================
# CLI入口
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark汇总脚本")
    parser.add_argument("--input", "-i", required=True, help="评分JSON文件夹路径")
    parser.add_argument("--output", "-o", required=True, help="CSV输出路径")
    parser.add_argument("--project", "-p", default="unknown", help="项目名称")

    args = parser.parse_args()

    # 加载数据
    print(f"Loading JSON files from: {args.input}")
    data = load_json_files(args.input)

    print(f"Found {len(data['automated'])} automated reports")
    print(f"Found {len(data['subjective'])} subjective reports")

    # 计算各项评分
    automated_result = calculate_automated_score(data["automated"])
    subjective_result = calculate_subjective_score(data["subjective"])
    final_result = calculate_final_score(automated_result, subjective_result)

    # 生成CSV行
    row = generate_csv_row(final_result, automated_result, subjective_result, args.project)

    # 输出汇总
    print("\n" + "=" * 50)
    print("Benchmark Summary")
    print("=" * 50)
    print(f"Project: {args.project}")
    print(f"Final Score: {final_result['final_score']} / 5.00")
    print(f"  Automated ({WEIGHTS['automated']*100}%): {automated_result['score']}")
    print(f"  Subjective ({WEIGHTS['subjective']*100}%): {subjective_result['score']}")
    if subjective_result['evaluator_count'] > 0:
        print(f"  Evaluators: {subjective_result['evaluator_count']}, Std Dev: {subjective_result['std_deviation']}")
    print("=" * 50)

    # 写入CSV
    write_csv([row], args.output)