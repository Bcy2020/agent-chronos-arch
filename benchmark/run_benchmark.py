"""
Benchmark自动化评测入口脚本

统一执行分解树结构评测和代码质量评测。

用法：
python run_benchmark.py \
    --tree <分解树JSON路径> \
    --nodes <nodes代码目录路径> \
    --adapter <适配器文件路径> \
    --output <输出目录路径>

输出：
- output/tree_report.json  分解树结构评测结果
- output/code_report.json  代码质量评测结果
"""

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path


def load_adapter(adapter_path: str):
    """动态加载适配器模块"""
    spec = importlib.util.spec_from_file_location("adapter_module", adapter_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.adapter


def run_tree_evaluation(tree_path: str, adapter_path: str, output_path: str):
    """执行分解树结构评测"""
    # 加载适配器
    adapter = load_adapter(adapter_path)

    # 加载分解树
    with open(tree_path, 'r', encoding='utf-8') as f:
        tree_json = json.load(f)

    # 转换为抽象节点列表
    nodes = adapter.adapt_tree(tree_json)

    # 执行评测（内联实现，避免跨模块导入问题）
    result = evaluate_tree(nodes)

    # 输出结果
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[Tree] Report saved to {output_path}")
    return result


def run_code_evaluation(nodes_dir: str, output_path: str):
    """执行代码质量评测"""
    result = evaluate_code(nodes_dir)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[Code] Report saved to {output_path}")
    return result


# ============================================================
# 分解树评测逻辑（内联）
# ============================================================

def evaluate_tree(nodes):
    """分解树结构评测"""
    total_nodes = len(nodes)
    leaf_nodes = [n for n in nodes if n.is_leaf]
    parent_nodes = [n for n in nodes if not n.is_leaf]

    # 深度分布
    depth_dist = {}
    for n in nodes:
        d = n.depth
        depth_dist[d] = depth_dist.get(d, 0) + 1

    # 扇出分布
    fanout_dist = {}
    for n in parent_nodes:
        c = len(n.children_ids)
        fanout_dist[c] = fanout_dist.get(c, 0) + 1

    # 语义停止统计
    semantic_count = sum(1 for n in leaf_nodes if n.stop_condition == "semantic")
    forced_count = sum(1 for n in leaf_nodes if n.stop_condition == "forced")
    forced_stop_nodes = [n.node_id for n in leaf_nodes if n.stop_condition == "forced"]

    # 追溯统计
    traced_count = sum(1 for n in nodes if len(n.requirement_trace) > 0)

    # 全局状态统计
    global_ops_count = sum(1 for n in nodes if len(n.global_state_ops) > 0)

    # 分解成功率统计
    passed_count = sum(1 for n in nodes if n.validation_passed)
    failed_nodes = [n.node_id for n in nodes if n.needs_human_intervention]
    total_retry_count = sum(n.retry_count for n in nodes)
    first_success_count = sum(1 for n in nodes if n.validation_passed and n.retry_count == 0)

    return {
        "summary": {
            "total_nodes": total_nodes,
            "leaf_nodes": len(leaf_nodes),
            "parent_nodes": len(parent_nodes),
            "max_depth": max(n.depth for n in nodes) if nodes else 0
        },
        "metrics": {
            "semantic_stop_rate": round(semantic_count / len(leaf_nodes), 4) if leaf_nodes else 0,
            "forced_stop_rate": round(forced_count / len(leaf_nodes), 4) if leaf_nodes else 0,
            "traceability_rate": round(traced_count / total_nodes, 4) if total_nodes else 0,
            "global_ops_rate": round(global_ops_count / total_nodes, 4) if total_nodes else 0,
            # 分解成功率指标
            "decomposition_success_rate": round(passed_count / total_nodes, 4) if total_nodes else 0,
            "first_try_success_rate": round(first_success_count / total_nodes, 4) if total_nodes else 0,
            "avg_retry_count": round(total_retry_count / total_nodes, 4) if total_nodes else 0
        },
        "distribution": {
            "depth": dict(sorted(depth_dist.items())),
            "fanout": dict(sorted(fanout_dist.items()))
        },
        "issues": {
            "forced_stop_nodes": forced_stop_nodes,
            "failed_nodes": failed_nodes
        }
    }


# ============================================================
# 代码评测逻辑（内联）
# ============================================================

import ast

def evaluate_code(nodes_dir: str) -> dict:
    """代码质量评测"""
    py_files = sorted([
        os.path.join(nodes_dir, f)
        for f in os.listdir(nodes_dir)
        if f.endswith('.py')
    ])

    total = len(py_files)
    syntax_ok = 0
    annotation_ok = 0
    global_count = 0
    conflict_count = 0

    global_nodes = []
    problem_nodes = []

    for file_path in py_files:
        node_id = Path(file_path).stem
        result = evaluate_single_file(file_path, node_id)

        if result['syntax_ok']:
            syntax_ok += 1
        if result['has_annotation']:
            annotation_ok += 1
        if result['has_global']:
            global_count += 1
            global_nodes.append(node_id)
        if result['param_global_conflict']:
            conflict_count += 1
            problem_nodes.append({
                "node_id": node_id,
                "issue": "param_global_conflict"
            })

        if not result['syntax_ok'] or not result['has_annotation']:
            problem_nodes.append({
                "node_id": node_id,
                "syntax_ok": result['syntax_ok'],
                "has_annotation": result['has_annotation'],
                "error_msg": result['error_msg']
            })

    # 去重问题节点
    seen = set()
    unique_problems = []
    for p in problem_nodes:
        key = p['node_id']
        if key not in seen:
            seen.add(key)
            unique_problems.append(p)

    return {
        "summary": {
            "total_nodes": total,
            "syntax_pass_rate": round(syntax_ok / total, 4) if total else 0,
            "annotation_pass_rate": round(annotation_ok / total, 4) if total else 0,
            "global_usage_rate": round(global_count / total, 4) if total else 0,
            "conflict_rate": round(conflict_count / total, 4) if total else 0
        },
        "global_nodes": global_nodes,
        "problem_nodes": unique_problems
    }


def evaluate_single_file(file_path: str, node_id: str) -> dict:
    """评测单个代码文件"""
    result = {
        'syntax_ok': True,
        'has_annotation': True,
        'has_global': False,
        'param_global_conflict': False,
        'error_msg': None
    }

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
    except Exception as e:
        result['syntax_ok'] = False
        result['error_msg'] = f"无法读取: {e}"
        return result

    if not code.strip():
        result['syntax_ok'] = False
        result['error_msg'] = "代码为空"
        return result

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        result['syntax_ok'] = False
        result['error_msg'] = f"语法错误: {e.msg}"
        return result

    # 提取主函数
    func_def = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_def = node
            break

    if not func_def:
        result['error_msg'] = "无函数定义"
        return result

    # 类型注解检查
    result['has_annotation'] = func_def.returns is not None

    # global语句检查
    global_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            global_names.update(node.names)
    result['has_global'] = len(global_names) > 0

    # 参数与global冲突
    param_names = {arg.arg for arg in func_def.args.args}
    result['param_global_conflict'] = len(param_names & global_names) > 0

    return result


# ============================================================
# CLI入口
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark自动化评测")
    parser.add_argument("--tree", "-t", required=True, help="分解树JSON文件路径")
    parser.add_argument("--nodes", "-n", required=True, help="nodes代码目录路径")
    parser.add_argument("--adapter", "-a", required=True, help="适配器Python文件路径")
    parser.add_argument("--output", "-o", required=True, help="输出目录路径")

    args = parser.parse_args()

    # 确保输出目录存在
    os.makedirs(args.output, exist_ok=True)

    # 执行评测
    print("=" * 50)
    print("Benchmark Evaluation Started")
    print("=" * 50)

    tree_report_path = os.path.join(args.output, "tree_report.json")
    code_report_path = os.path.join(args.output, "code_report.json")

    tree_result = run_tree_evaluation(args.tree, args.adapter, tree_report_path)
    code_result = run_code_evaluation(args.nodes, code_report_path)

    # 打印摘要
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)

    print("\n[Tree Evaluation]")
    print(f"  Total nodes: {tree_result['summary']['total_nodes']}")
    print(f"  Semantic stop rate: {tree_result['metrics']['semantic_stop_rate']:.2%}")
    print(f"  Forced stop rate: {tree_result['metrics']['forced_stop_rate']:.2%}")
    print(f"  Traceability rate: {tree_result['metrics']['traceability_rate']:.2%}")
    print(f"  Decomposition success rate: {tree_result['metrics']['decomposition_success_rate']:.2%}")
    print(f"  First try success rate: {tree_result['metrics']['first_try_success_rate']:.2%}")
    print(f"  Avg retry count: {tree_result['metrics']['avg_retry_count']:.2f}")

    print("\n[Code Evaluation]")
    print(f"  Total nodes: {code_result['summary']['total_nodes']}")
    print(f"  Syntax pass rate: {code_result['summary']['syntax_pass_rate']:.2%}")
    print(f"  Annotation rate: {code_result['summary']['annotation_pass_rate']:.2%}")
    print(f"  Conflict rate: {code_result['summary']['conflict_rate']:.2%}")

    print("\n" + "=" * 50)
    print("Done. Reports saved to:")
    print(f"  {tree_report_path}")
    print(f"  {code_report_path}")
    print("=" * 50)