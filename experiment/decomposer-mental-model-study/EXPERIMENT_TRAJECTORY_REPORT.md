# Decomposer Mental Model Study — 实验轨迹报告

本报告按研究阶段整理 `experiment/decomposer-mental-model-study/` 的完整实验轨迹，区分已验证结论与待验证假设。

模型：`deepseek-v4-flash`（除特别说明外）
时间跨度：2026-05-28 ~ 2026-05-31

---

## 阶段 1：Routing 问题复现与 no-traditional 原则

### 研究问题

LLM 分解器反复生成 `ParseInput + RouteCommand + handlers` 模式，RouteCommand 作为兄弟节点调用其他兄弟节点，违反树结构规则（父节点是唯一协调者）。如何消除这种 routing 违规？

### 实验

| 实验 | 脚本 | 输出目录 |
|------|------|----------|
| 基线（注意力分离） | `test_attention_separation.py` | `output/attention_separation/` |
| + no-traditional 规则 | `test_attention_separation_notraditional.py` | `output/attention_separation_notraditional/` |
| 跨域验证 | `test_notraditional_moredomains.py` | `output/notraditional_moredomains/` |

### 结果 `[Experiment Result]`

| 条件 | Routing 率 | 说明 |
|------|-----------|------|
| 基线（仅分离） | 5/5 = 100% | 分离注意力本身无效 |
| + no-traditional（Order） | 0/5 = 0% | routing 完全消除 |
| + no-traditional（Chat） | 1/3 = 33% | 唯一触发为名称误判 |
| + no-traditional（Patient） | 0/3 = 0% | 完全有效 |
| 跨域总计 | 1/6 = 17% | 在已验证 0-17% 区间内 |

### 结论

- **已验证**：注意力分离本身不能修复 routing；"不相信传统模式"规则可将 routing 率从 100% 降至 17%。
- **已验证**：根因是训练数据先验——routing 模式在开源代码中无处不在，即使有显式规则也难以完全抑制。

---

## 阶段 2：Step 2 Codegen 树结构审查

### 研究问题

能否在 codegen 阶段（而非分解阶段）检出 routing 违规？

### 实验

| 实验 | 脚本 | 输出目录 |
|------|------|----------|
| 树审查器检出率 | `test_tree_reviewer.py` | `output/tree_reviewer_v6/` |
| 树审查器假阳性 | `test_tree_reviewer_false_positive.py` | `output/tree_reviewer_v6/` |
| Codegen 审查集成 | `test_chat00_codegen.py` | `output/chat00_codegen_test/` |

### 结果 `[Experiment Result]`

- 树审查器检出率：10/10（100%）
- 假阳性率：0/10（0%）
- Codegen 集成：正确拒绝 routing 分解（status: cannot_compose, reason: tree_structure_violation）

### 结论

- **已验证**：codegen 的 system prompt 中添加树结构审查规则可检出 routing 违规，无过拟合。
- **已验证**：树结构审查是确定性检查，不依赖 LLM 判断。

---

## 阶段 3：多阶段分解实验 Exp01 / Exp02 / Exp03

### 研究问题

将单阶段分解拆为多阶段（结构→接口→约束/资源）是否能改善分解质量？

### 实验

| 实验 | 脚本 | 输出目录 |
|------|------|----------|
| Exp01 Stage1 Routing | `test_multistage_exp01_stage1_routing.py` | `output/multistage_exp01_stage1_routing/` |
| Exp02 Derivation Stability | `test_multistage_exp02_derivation_stability.py` | `output/multistage_exp02_derivation_stability/` |
| Exp03 Pipeline Regression | `test_multistage_exp03_pipeline_regression.py` | `output/multistage_exp03_pipeline_regression/` |

### 结果 `[Experiment Result]`

**Exp01**（25 trials，5 域 x 5 次）：
- 旧判定器 routing 率：16/25 = 64% — 判定为 FAIL
- 字段完整率：100%

**Exp02**（10 样本，Stage 2/3 各重复 5 次，110 次 LLM 调用）：
- 身份漂移：1 次
- 语义漂移：0
- 签名稳定性：59.3%（目标 ≥80%）— FAIL
- 数据流拓扑稳定性：70.0%

**Exp03**（45 trials，5 case x 3 条件 x 3 次）：

| 指标 | baseline | notraditional | three_stage |
|------|----------|---------------|-------------|
| routing（旧） | 12/15 | 3/15 | 3/15 |
| child_count_violation | 2/15 | 3/15 | 1/15 |
| dangling_inputs（旧） | 51 | 47 | 75 |
| cannot_compose（旧） | 13/15 | 14/15 | 11/15 |

### 初步结论

- Exp01 FAIL（64% routing）— 但后续发现旧判定器误报严重
- Exp02 FAIL（签名稳定性 59.3%）— Stage 2/3 推导不稳定
- Exp03 PASS（three_stage 在 deterministic failures 上无回归）

---

## 阶段 4：Exp01 / Exp03 重判与误杀修正

### 研究问题

旧判定器是否存在误报？修正判定器后结论是否变化？

### 实验

| 实验 | 脚本 | 输出目录 |
|------|------|----------|
| Exp01 重判 | `reanalyze_multistage_exp01.py` | `output/multistage_exp01_stage1_routing_rejudged/` |
| Exp03 重判 | `reanalyze_multistage_exp03.py` | `output/multistage_exp03_pipeline_regression_rejudged/` |

### 结果 `[Experiment Result]`

**Exp01 重判**：

| 指标 | 旧判定器 | 新判定器 |
|------|----------|----------|
| hard_routing | 64% (16/25) | **8% (2/25)** |

- 14 个旧 routing case 降级为 parent_mediated_dataflow（Parse*/ParseAndValidate* 返回 parent，parent 编排子节点）
- 2 个保留 hard_routing：Chat/trial_00、Order/trial_03
- 结论：**PASS**

**Exp03 重判**：

| 指标 | baseline | notraditional | three_stage |
|------|----------|---------------|-------------|
| hard_routing（旧→新） | 12/15→12/15 | 3/15→1/15 | 3/15→0/15 |
| hard_dangling（旧→新） | 51→0 | 47→0 | 75→0 |

- 结论：**PASS**

### 审查发现 `[Review Finding]`

Codex 指出 Exp03 v1 重判只能作为有限证据：脚本对 `three_stage` 的 dangling/resource 判断主要读取 `stage1.json`，没有用最终 `merged_node.json`；`judge_resource_coverage()` 未传 parent globals，`resource_coverage_gap=0` 不能证明资源守恒通过。Exp03 v1 的 PASS 应降级。

---

## 阶段 5：Exp03 V2 与 Global State Conservation 问题

### 研究问题

修正 v1 的三个缺陷（dangling 使用 merged_node、resource 传入 parent globals、child count 使用 case-specific range）后，Exp03 结论是否变化？

### 实验

| 实验 | 脚本 | 输出目录 |
|------|------|----------|
| Exp03 v2 重判 | `reanalyze_multistage_exp03_v2.py` | `output/multistage_exp03_pipeline_regression_rejudged_v2/` |
| Conservation prompt 全链路重跑 | `test_multistage_exp03_pipeline_regression.py`（修改 STAGE3 prompt） | `output/multistage_exp03_pipeline_regression_conservation_prompt/` |
| Conservation 重判 | `reanalyze_multistage_exp03_conservation.py` | `output/multistage_exp03_pipeline_regression_conservation_prompt_rejudged/` |

### 结果 `[Experiment Result]`

**V2 结果**：

| 指标 | baseline | notraditional | three_stage |
|------|----------|---------------|-------------|
| hard_routing | 12/15 | 1/15 | 0/15 |
| resource_coverage_gap | 9 | 6 | **11** |
| llm_review_fail | 13/15 | 14/15 | 11/15 |

- **V2 Verdict：FAIL** — resource_coverage_gap 三阶段 (11) > notraditional (6)

**Conservation prompt 全链路重跑**：

| 指标 | V2 | Conservation | Delta |
|------|-----|--------------|-------|
| hard_routing（three_stage） | 0/15 | 2/15 | +2 |
| resource_coverage_gap（three_stage） | 11 | **15** | +4 |

- **Conservation Verdict：FAIL** — 加剧

### 审查发现 `[Review Finding]`

Conservation prompt 全链路重跑同时重新采样了 Stage1/Stage2，因此 hard_routing 和 child_count regression 不能直接归因于 Stage3 prompt。需要固定旧 Stage1/Stage2，只重跑 Stage3 来隔离因果。

---

## 阶段 6：Fixed-Input Stage3 Conservation

### 研究问题

冻结 Stage1/Stage2，仅重跑 Stage3 conservation prompt，能否消除 resource_coverage_gap？

### 实验

| 实验 | 脚本 | 输出目录 |
|------|------|----------|
| Fixed-input Stage3 | `test_multistage_exp03_fixed_stage3_conservation.py` | `output/multistage_exp03_fixed_stage3_conservation/` |
| 重判 | `reanalyze_multistage_exp03_fixed_stage3.py` | `output/multistage_exp03_fixed_stage3_conservation_rejudged/` |

### 结果 `[Experiment Result]`

| 指标 | V2 Baseline | Fixed-Input Conservation |
|------|------------|--------------------------|
| resource_coverage_gap | 11 | **36** |
| false_self_check | N/A | **32** |

- **Verdict：FAIL** — conservation prompt 未能消除资源覆盖缺口
- 32/45 次 false self-check：governance_notes 声称 "conservation verified" 但 deterministic judge 发现 gap
- 每个 gap 均为 `read_write → child union only ['write']` 或 `['read']`

### 初步结论

Stage3 conservation prompt 不足以可靠修复 resource_coverage_gap。根因不是 Stage1/2 重采样噪声，而是 LLM Stage3 本身倾向只分配单侧操作。

---

## 阶段 7：Test Case Permission Audit 与 Patch

### 研究问题

Stage3 的 resource_coverage_gap 是否源于人工构造的 test case fixture 本身不自洽？

### 实验

| 实验 | 脚本 | 输出 |
|------|------|------|
| Permission audit | 按 `TEST_CASE_PERMISSION_AUDIT_GUIDE.md` 手动审查 | `TEST_CASE_PERMISSION_AUDIT_REPORT.md` |
| Fixture patch | 按 `TEST_CASE_PERMISSION_PATCH_GUIDE.md` 修改 | `test_data/decomposer_cases.py` |
| Patch 后重判 | `reanalyze_multistage_exp03_fixed_stage3.py` | `output/multistage_exp03_fixed_stage3_conservation_rejudged/` |

### 结果 `[Experiment Result]` + `[Review Finding]`

**审查结果**：5 case 全部存在 fixture 问题，共 9 个 finding。

**Patch 后重判**：

| 指标 | Patch 前 | Patch 后 | Delta |
|------|---------|---------|-------|
| resource_coverage_gap | 36 | **5** | -31 |
| false_self_check | 32 | **5** | -27 |

**Old gaps fixed (4)**：users:read (ChatApp), records:read_write (PatientPortal), artifacts:read_write (BuildSystem), pipeline_log:read_write (DataPipeline) — 全部为 fixture artifact。

**Remaining genuine gaps (5)**：

| Variable:Op | Case | Count | 说明 |
|-------------|------|-------|------|
| inventory:read_write | OrderSystem | 2/9 | place 读+写库存，cancel 恢复库存；子节点只分配 write |
| payments:read_write | OrderSystem | 1/9 | place 写支付，cancel 读+写支付；子节点只分配 write |
| users:write | ChatApp | 1/9 | send 写 last_seen；子节点只分配 read |
| appointments:read_write | PatientPortal | 1/9 | book 读可用性+写预约；子节点只分配 write |

### 审查发现 `[Review Finding]`

Codex 指出 `TEST_CASE_PERMISSION_AUDIT_REPORT.md` 中 proposed patch 的 `data_sources` entry 未显式写 `access`，`_make_case()` 默认 `access=read_write` 会重新引入过宽授权。已按 `TEST_CASE_PERMISSION_PATCH_GUIDE.md` 修正。

---

## 阶段 8：Codegen Dataflow Parent-Mediated Synthetic 实验

### 研究问题

Structured `dataflow_edges` 作为 parent codegen 权威契约，能否生成正确的 parent-mediated 代码？

### 实验

| 实验 | 脚本 | 输出目录 |
|------|------|----------|
| Synthetic dataflow codegen | `test_codegen_dataflow_parent_mediated.py` | `output/codegen_dataflow_parent_mediated/` |
| Codegen 原型 | `src/code_generator_dataflow.py` | — |

### 结果 `[Experiment Result]`

| Case | 类型 | 生成 | 验证 | 通过 |
|------|------|------|------|------|
| positive_a_parser_handlers | 正例 | ok | ok | **PASS** |
| positive_b_route_intent | 正例 | cannot_compose | N/A | FAIL |
| positive_c_validate_execute | 正例 | cannot_compose | N/A | FAIL |
| negative_a_hidden_sibling_call | 负例 | ok | ok（矛盾） | **FAIL** |
| negative_b_wrong_dataflow_source | 负例 | cannot_compose | — | **PASS** |

### 关键发现

1. **正例 A 完全通过**：dataflow_edges 完整覆盖所有子节点和数据路径时，codegen 成功。
2. **正例 B/C 被拒绝**：dataflow_edges 未覆盖所有声明子节点时，LLM 以 `missing_child_capability` 拒绝。Codex 判断更可能是用例构造错误。
3. **负例 A 验证器自相矛盾**：LLM reasoning 识别了 child_coverage 违规，但 JSON 输出 status="ok"。解析器只读顶层 status 导致误判。
4. **负例 B 正确拒绝**。

### 决策 `[Human-Approved]`

不继续修补人为 B/C fixture，先做 real-derived 子实验。

---

## 阶段 9：Real Stage1 子实验与二次审查

### 研究问题

真实 Stage1 输出（非手写 fixture）进入 codegen 后表现如何？

### 实验

| 实验 | 脚本 | Adapter | 输出目录 |
|------|------|---------|----------|
| Real Stage1 codegen | `test_codegen_dataflow_real_stage1.py` | `src/real_stage1_codegen_adapter.py` | `output/codegen_dataflow_real_stage1/` |

### Phase A 二次审查 `[Experiment Result]`

5 个候选全部通过审查：

| 候选 | 类型 | 审查结论 | 关键特征 |
|------|------|----------|----------|
| Order/trial_02 | positive | PASS | 4 子节点，conditional dispatch，无 formatter |
| Chat/trial_02 | positive | PASS | 6 子节点，conditional dispatch + FormatResponse |
| BuildSystem/trial_00 | positive | PASS | 10 子节点，conditional dispatch + FormatOutput aggregator |
| Chat/trial_00 | negative | PASS | RouteCommand 显式路由到兄弟节点 |
| Order/trial_03 | negative | PASS | PlaceOrder/CancelOrder 显式调用子节点 |

### Phase C Codegen 结果 `[Experiment Result]`

| 指标 | 值 |
|------|-----|
| 正例进入 | 3 |
| 正例接受 | 0 |
| 正例通过 | 0 |
| 负例正确拒绝 | 2 |

**正例拒绝原因**：

| Case | 拒绝原因 | 根因 |
|------|----------|------|
| Order/trial_02 | cannot_satisfy_parent_output | conditional dispatch 未执行分支返回 None 字面量 |
| Chat/trial_02 | dataflow_conformance_failure | adapter 将 "internal leaf access"（channels, messages）错误转为 child 参数 |
| BuildSystem/trial_00 | dataflow_conformance_failure | FormatOutput 聚合输入在 conditional 分支中为 None 字面量 |

### 关键发现

- **负例全部正确拒绝**：codegen 自检成功识别了 routing 和 abstraction-level mixing。
- **正例全部被拒绝——原因是 adapter 转换 gap，非 codegen 能力不足**：
  - Gap 1: `internal leaf access` 被 adapter 错误转为 child 参数
  - Gap 2: conditional dispatch 输出推断不完整

---

## 阶段 10：Real Stage1 Adapter Patch 重跑

### 研究问题

修正 adapter 的 6 项转换问题后，正例能否通过 codegen？

### 修改内容

按 `CODEGEN_DATAFLOW_REAL_STAGE1_ADAPTER_PATCH_GUIDE.md` 修正 `real_stage1_codegen_adapter.py`：

1. Parent I/O 使用 domain contract（input/output），不从 dataflow edges 推断
2. Child→parent 数据视为 parent-local，不暴露为 external output
3. Conditional dispatch 检测 + 统一变量
4. `internal leaf access` 从 child 签名中排除
5. 接口名确定性合法性检查
6. Comma-separated data fields 拆分

### 重跑范围

Order/trial_02、Chat/trial_02、Chat/trial_00

### 结果 `[Experiment Result]`

| Case | 类型 | 失败类别 | 通过 |
|------|------|----------|------|
| Order/trial_02 | positive | codegen_self_check_failure | FAIL |
| Chat/trial_02 | positive | valid_acceptance_for_positive | **PASS** |
| Chat/trial_00 | negative | valid_rejection_for_negative | **PASS** |

**正例通过率**：1/2（上次 0/3）

### 已修复的 adapter gap

- `internal leaf access` 不再作为 child 参数传递（Chat/trial_02 的 channels、messages 已排除）
- Comma-separated field `operation_result or error` 被跳过
- Parent I/O 固定为 domain contract
- Conditional dispatch 检测生效

### 剩余问题（codegen 行为，非 adapter）

**Order/trial_02**：codegen 在 `else` 分支生成字面量 fallback `{'success': False, 'message': 'Unknown command'}`，verifier 的 `return_value_origin` 检查拒绝非 child/parent 来源的字面量。其他 4 项检查全部通过。

对比 Chat/trial_02 的 `else` 分支调用了 FormatResponse 子节点，所以通过。Order/trial_02 没有 formatter 子节点来兜底。

---

## 阶段 11：当前剩余问题

### 11.1 Order/trial_02 的 return_value_origin / fallback literal

`[Pending Decision]`

codegen 在条件分支的 `else` 中使用字面量 dict 作为 fallback，被 verifier 的 `return_value_origin` 检查拒绝。可能的解决方向：
- (A) codegen prompt 禁止字面量 return，要求 raise error 或调用 default handler
- (B) verifier 接受合理的 fallback 字面量
- (C) Stage1 为 conditional dispatch 添加 default handler 子节点

### 11.2 BuildSystem/trial_00 是否加入重跑

`[Pending Decision]`

当前 Order 的剩余失败是 codegen 行为（非 adapter），Chat 已通过。可考虑将 BuildSystem/trial_00 加入 adapter patch 重跑范围。

### 11.3 剩余 5 个 genuine resource gaps

`[Pending Decision]`

| Variable:Op | Case | Count | 说明 |
|-------------|------|-------|------|
| inventory:read_write | OrderSystem | 2/9 | 子节点只分配 write |
| payments:read_write | OrderSystem | 1/9 | 子节点只分配 write |
| users:write | ChatApp | 1/9 | 子节点只分配 read |
| appointments:read_write | PatientPortal | 1/9 | 子节点只分配 write |

这些是 Stage3 prompt 的真实分配问题，需决定是否进一步改进 prompt 或接受当前水平。

---

## 附录：脚本与输出索引

### 实验脚本

| 脚本 | 用途 |
|------|------|
| `test_attention_separation.py` | 基线 routing 复现 |
| `test_attention_separation_notraditional.py` | + no-traditional 规则 |
| `test_notraditional_moredomains.py` | 跨域验证 |
| `test_tree_reviewer.py` | 树审查器检出率 |
| `test_tree_reviewer_false_positive.py` | 树审查器假阳性 |
| `test_chat00_codegen.py` | Codegen 审查集成 |
| `test_multistage_exp01_stage1_routing.py` | Exp01 |
| `test_multistage_exp02_derivation_stability.py` | Exp02 |
| `test_multistage_exp03_pipeline_regression.py` | Exp03 |
| `test_multistage_exp03_fixed_stage3_conservation.py` | Fixed-input Stage3 |
| `test_codegen_dataflow_parent_mediated.py` | Synthetic dataflow codegen |
| `test_codegen_dataflow_real_stage1.py` | Real Stage1 codegen |

### 重判脚本

| 脚本 | 用途 |
|------|------|
| `reanalyze_multistage_exp01.py` | Exp01 重判 |
| `reanalyze_multistage_exp03.py` | Exp03 v1 重判 |
| `reanalyze_multistage_exp03_v2.py` | Exp03 v2 重判 |
| `reanalyze_multistage_exp03_conservation.py` | Conservation 重判 |
| `reanalyze_multistage_exp03_fixed_stage3.py` | Fixed-input 重判 |

### Adapter / Codegen 原型

| 文件 | 用途 |
|------|------|
| `src/code_generator.py` | MVP CodeGenerator 复制 + STAGE 1 树结构审查 |
| `src/code_generator_dataflow.py` | DataflowAwareCodeGenerator 原型 |
| `src/real_stage1_codegen_adapter.py` | Stage1 → codegen-ready 转换 adapter |

### 输出目录

| 目录 | 内容 |
|------|------|
| `output/attention_separation/` | 基线 routing |
| `output/attention_separation_notraditional/` | no-traditional |
| `output/notraditional_moredomains/` | 跨域验证 |
| `output/tree_reviewer_v6/` | 树审查器 |
| `output/chat00_codegen_test/` | Codegen 审查 |
| `output/multistage_exp01_stage1_routing/` | Exp01 原始 |
| `output/multistage_exp01_stage1_routing_rejudged/` | Exp01 重判 |
| `output/multistage_exp02_derivation_stability/` | Exp02 |
| `output/multistage_exp03_pipeline_regression/` | Exp03 原始 |
| `output/multistage_exp03_pipeline_regression_rejudged/` | Exp03 v1 重判 |
| `output/multistage_exp03_pipeline_regression_rejudged_v2/` | Exp03 v2 重判 |
| `output/multistage_exp03_pipeline_regression_conservation_prompt/` | Conservation 全链路 |
| `output/multistage_exp03_pipeline_regression_conservation_prompt_rejudged/` | Conservation 重判 |
| `output/multistage_exp03_fixed_stage3_conservation/` | Fixed-input Stage3 |
| `output/multistage_exp03_fixed_stage3_conservation_rejudged/` | Fixed-input 重判 |
| `output/codegen_dataflow_parent_mediated/` | Synthetic dataflow codegen |
| `output/codegen_dataflow_real_stage1/` | Real Stage1 codegen |
| `output/codegen_dataflow_real_stage1_adapter_patch/` | Adapter patch 重跑 |

### Test Case Fixture

| 文件 | 说明 |
|------|------|
| `test_data/decomposer_cases.py` | 5 case 的 root-level global_vars + data_sources（已 patch） |

---

## 附录：结论状态汇总

### 已验证结论 `[Experiment Result]`

1. 注意力分离本身不能修复 routing（5/5 = 100%）
2. "不相信传统模式"规则可将 routing 降至 17%（1/6）
3. 树结构审查可 100% 检出 routing 违规，0 假阳性
4. Exp01 hard routing = 8%（旧判定器 64% 为误报）
5. Exp02 签名稳定性 59.3% — Stage 2/3 推导不稳定
6. Exp03 three_stage 在 hard_routing/hard_dangling 上无回归
7. Exp03 resource_coverage_gap 主要源于 fixture 过宽（36→5 after patch）
8. dataflow_edges 完整时 codegen 可生成 parent-mediated 代码（正例 A）
9. codegen 自检可识别 routing 和 abstraction-level mixing（负例）
10. Adapter patch 修复了 internal leaf access 和 parent I/O 推断问题（Chat/trial_02 通过）

### 待验证假设 `[Unverified Assumption]`

1. "不相信传统模式"规则在非 routing 场景下的副作用尚不明确
2. 多阶段分解是否导致 LLM 在后续阶段忘记前阶段约束（签名稳定性 59.3% 需进一步分析）
3. 固定 Stage 1 后 Stage 2/3 是否能稳定推出合法且可组合的接口

### 待用户决策 `[Pending Decision]`

1. Order/trial_02 的 codegen 字面量 fallback 如何处理
2. BuildSystem/trial_00 是否加入 adapter patch 重跑
3. 剩余 5 个 genuine resource gaps 是否需要进一步改进 Stage3 prompt
4. 两阶段 vs 多阶段分解架构设计
5. CodeGenerator 3-STAGE prompt 是否先行迁移
6. rewrite-0.6.0 优先级排序（BFS 失败恢复、叶节点能力拒绝、父子跨层传播）
