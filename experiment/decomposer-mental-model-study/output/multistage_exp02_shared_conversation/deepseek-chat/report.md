# Exp02b: Shared Conversation Memory vs Independent Context

Model: `deepseek-chat`
Samples per domain: 2
Repetitions per sample (chains): 5
Total samples: 10

## Purpose

Test whether keeping Stage 1, Stage 2, and Stage 3 inside the same message
history (shared_conversation) improves stage identity continuity and
interface-category discipline compared to separate API calls (independent_context).

## Hypothesis

Shared conversation memory may reduce identity drift, parse failures,
internal leaf resource leakage into call signatures, invalid dataflow
endpoints, and Stage3 resource-field inconsistency.

## Prompt Delta

- **independent_context**: Uses separate system prompts per stage (STAGE2_SYSTEM_PROMPT, STAGE3_SYSTEM_PROMPT).
  Stage1 JSON injected as assistant message before Stage2 user prompt.
  Stage2 JSON injected as assistant message before Stage3 user prompt.
- **shared_conversation**: Uses one SHARED_GLOBAL_SYSTEM_PROMPT for the entire conversation.
  Stage1 user prompt + assistant response + Stage2 user prompt + assistant response + Stage3 user prompt.
  No multiple system prompts in the same history.

- **Stage 2 prompt changes**: Separates `call_inputs` (parent-call parameters) from
  `internal_leaf_accesses` (child-internal resource access). Adds `interface_audit`
  with detail-first schema (audit reasoning before `final_status`).
- **Stage 3 prompt changes**: Uses `internal_leaf_accesses` as primary source for
  `global_vars`/`data_operations`. Adds `resource_audit` with detail-first schema.

## Primary Metrics Comparison

| Metric | independent_context | shared_conversation | Delta |
|--------|:-------------------:|:-------------------:|:-----:|
| Stage2 parse failures | 0 | 0 | 0 |
| Stage3 parse failures | 0 | 0 | 0 |
| Child identity drift (S2) | 0 | 15 | +15 |
| Child identity drift (S3) | 0 | 15 | +15 |
| Semantic drift (S2) | 1 | 1285 | +1284 |
| Semantic drift (S3) | 25 | 1285 | +1260 |
| Signature resource leaks | 0 | 0 | 0 |
| Dataflow schema violations | 0 | 0 | 0 |
| Stage3 signature drift | 12 | 111 | +99 |
| GV/DO sync gaps | 0 | 25 | +25 |

## Diagnostic Stability (old-style, cross-chain comparison)

| Domain | Sig Stability (A) | Sig Stability (B) | DF Stability (A) | DF Stability (B) | Res Stability (A) | Res Stability (B) |
|--------|:-----------------:|:-----------------:|:----------------:|:----------------:|:-----------------:|:-----------------:|
| Order | 53.1% | 100.0% | 12.5% | 100.0% | 25.0% | 0.0% |
| Chat | 55.0% | 87.5% | 25.0% | 100.0% | 50.0% | 37.5% |
| Patient | 82.1% | 53.1% | 50.0% | 100.0% | 62.5% | 37.5% |
| BuildSystem | 97.9% | 60.4% | 75.0% | 100.0% | 62.5% | 25.0% |
| DataPipeline | 81.2% | 87.5% | 100.0% | 100.0% | 87.5% | 87.5% |
| **TOTAL** | **73.9%** | **77.7%** | **52.5%** | **100.0%** | **57.5%** | **37.5%** |

## Per-Domain Primary Metrics

| Domain | Samples | S2 Parse Fail (A/B) | S3 Parse Fail (A/B) | Identity Drift S2 (A/B) | Sig Leak (A/B) | DF Violation (A/B) | S3 Sig Drift (A/B) | GV/DO Gap (A/B) |
|--------|:-------:|:-------------------:|:-------------------:|:-----------------------:|:--------------:|:------------------:|:------------------:|:---------------:|
| Order | 2 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/16 | 0/9 |
| Chat | 2 | 0/0 | 0/0 | 0/5 | 0/0 | 0/0 | 0/15 | 0/2 |
| Patient | 2 | 0/0 | 0/0 | 0/7 | 0/0 | 0/0 | 12/11 | 0/0 |
| BuildSystem | 2 | 0/0 | 0/0 | 0/3 | 0/0 | 0/0 | 0/33 | 0/14 |
| DataPipeline | 2 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/36 | 0/0 |

## Cases Where Shared Conversation Improved

### Patient/sample_01
- stage3_signature_drift_total: 12 -> 4

## Cases Where Shared Conversation Regressed

### BuildSystem/sample_00
- child_identity_drift_stage2: 0 -> 2
- child_identity_drift_stage3: 0 -> 2
- semantic_drift_stage2: 0 -> 132
- semantic_drift_stage3: 0 -> 132
- stage3_signature_drift_total: 0 -> 6
- gv_do_sync_gap_total: 0 -> 8

### BuildSystem/sample_01
- child_identity_drift_stage2: 0 -> 1
- child_identity_drift_stage3: 0 -> 1
- semantic_drift_stage2: 0 -> 252
- semantic_drift_stage3: 0 -> 252
- stage3_signature_drift_total: 0 -> 27
- gv_do_sync_gap_total: 0 -> 6

### Chat/sample_00
- child_identity_drift_stage2: 0 -> 4
- child_identity_drift_stage3: 0 -> 4
- semantic_drift_stage2: 0 -> 55
- semantic_drift_stage3: 0 -> 55
- stage3_signature_drift_total: 0 -> 5

### Chat/sample_01
- child_identity_drift_stage2: 0 -> 1
- child_identity_drift_stage3: 0 -> 1
- semantic_drift_stage2: 1 -> 145
- semantic_drift_stage3: 1 -> 145
- stage3_signature_drift_total: 0 -> 10
- gv_do_sync_gap_total: 0 -> 2

### DataPipeline/sample_00
- semantic_drift_stage2: 0 -> 140
- semantic_drift_stage3: 0 -> 140
- stage3_signature_drift_total: 0 -> 20

### DataPipeline/sample_01
- semantic_drift_stage2: 0 -> 136
- semantic_drift_stage3: 0 -> 136
- stage3_signature_drift_total: 0 -> 16

### Order/sample_00
- semantic_drift_stage2: 0 -> 140
- semantic_drift_stage3: 0 -> 140
- stage3_signature_drift_total: 0 -> 16
- gv_do_sync_gap_total: 0 -> 6

### Order/sample_01
- semantic_drift_stage2: 0 -> 140
- semantic_drift_stage3: 0 -> 140
- gv_do_sync_gap_total: 0 -> 3

### Patient/sample_00
- child_identity_drift_stage2: 0 -> 4
- child_identity_drift_stage3: 0 -> 4
- semantic_drift_stage2: 0 -> 77
- semantic_drift_stage3: 0 -> 77
- stage3_signature_drift_total: 0 -> 7

### Patient/sample_01
- child_identity_drift_stage2: 0 -> 3
- child_identity_drift_stage3: 0 -> 3
- semantic_drift_stage2: 0 -> 68
- semantic_drift_stage3: 24 -> 68

## Manual Audit Notes

### Order

**independent_context**: S2 parse fail=0, sig_leak=0, df_violation=0, s3_drift=0
**shared_conversation**: S2 parse fail=0, sig_leak=0, df_violation=0, s3_drift=16

### Chat

**independent_context**: S2 parse fail=0, sig_leak=0, df_violation=0, s3_drift=0
**shared_conversation**: S2 parse fail=0, sig_leak=0, df_violation=0, s3_drift=5

### DataPipeline

**independent_context**: S2 parse fail=0, sig_leak=0, df_violation=0, s3_drift=0
**shared_conversation**: S2 parse fail=0, sig_leak=0, df_violation=0, s3_drift=20

### Patient/sample_01 parse behavior

**independent_context**: S2 parse fail=0, S3 parse fail=0, identity_drift_s2=0
**shared_conversation**: S2 parse fail=0, S3 parse fail=0, identity_drift_s2=3

## Verdict

| Metric | independent_context | shared_conversation |
|--------|:-------------------:|:-------------------:|
| Stage2 parse failures | 0 | 0 |
| Stage3 parse failures | 0 | 0 |
| Child identity drift (total) | 0 | 30 |
| Signature resource leaks | 0 | 0 |
| Dataflow schema violations | 0 | 0 |
| Stage3 signature drift | 12 | 111 |
| GV/DO sync gaps | 0 | 25 |

**Verdict: INCONCLUSIVE_PARSE_OR_INFRA_FAILURE**

### Verdict Boundary

This experiment can only support or reject the narrower hypothesis:
> shared conversation memory improves Stage2/3 continuity and interface-category discipline

It does NOT establish migration readiness. Migration requires additional validation
including real codegen integration and production-domain testing.
