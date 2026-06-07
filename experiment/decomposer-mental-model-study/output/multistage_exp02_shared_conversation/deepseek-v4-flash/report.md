# Exp02b: Shared Conversation Memory vs Independent Context

Model: `deepseek-v4-flash`
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
| Child identity drift (S2) | 0 | 0 | 0 |
| Child identity drift (S3) | 0 | 0 | 0 |
| Semantic drift (S2) | 0 | 0 | 0 |
| Semantic drift (S3) | 52 | 0 | -52 |
| Signature resource leaks | 0 | 0 | 0 |
| Dataflow schema violations | 0 | 0 | 0 |
| Stage3 signature drift | 24 | 0 | -24 |
| GV/DO sync gaps | 0 | 0 | 0 |

## Diagnostic Stability (old-style, cross-chain comparison)

| Domain | Sig Stability (A) | Sig Stability (B) | DF Stability (A) | DF Stability (B) | Res Stability (A) | Res Stability (B) |
|--------|:-----------------:|:-----------------:|:----------------:|:----------------:|:-----------------:|:-----------------:|
| Order | 50.0% | 37.5% | 87.5% | 50.0% | 50.0% | 62.5% |
| Chat | 87.1% | 83.9% | 62.5% | 100.0% | 87.5% | 50.0% |
| Patient | 100.0% | 84.4% | 100.0% | 37.5% | 100.0% | 100.0% |
| BuildSystem | 89.6% | 64.6% | 0.0% | 50.0% | 100.0% | 37.5% |
| DataPipeline | 100.0% | 3.1% | 100.0% | 0.0% | 100.0% | 62.5% |
| **TOTAL** | **85.3%** | **54.7%** | **70.0%** | **47.5%** | **87.5%** | **62.5%** |

## Per-Domain Primary Metrics

| Domain | Samples | S2 Parse Fail (A/B) | S3 Parse Fail (A/B) | Identity Drift S2 (A/B) | Sig Leak (A/B) | DF Violation (A/B) | S3 Sig Drift (A/B) | GV/DO Gap (A/B) |
|--------|:-------:|:-------------------:|:-------------------:|:-----------------------:|:--------------:|:------------------:|:------------------:|:---------------:|
| Order | 2 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| Chat | 2 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| Patient | 2 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 12/0 | 0/0 |
| BuildSystem | 2 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| DataPipeline | 2 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 12/0 | 0/0 |

## Cases Where Shared Conversation Improved

### DataPipeline/sample_01
- semantic_drift_stage3: 28 -> 0
- stage3_signature_drift_total: 12 -> 0

### Patient/sample_00
- semantic_drift_stage3: 24 -> 0
- stage3_signature_drift_total: 12 -> 0

## Cases Where Shared Conversation Regressed

No cases where shared conversation regressed on primary metrics.

## Manual Audit Notes

### Order

**independent_context**: S2 parse fail=0, sig_leak=0, df_violation=0, s3_drift=0
**shared_conversation**: S2 parse fail=0, sig_leak=0, df_violation=0, s3_drift=0

### Chat

**independent_context**: S2 parse fail=0, sig_leak=0, df_violation=0, s3_drift=0
**shared_conversation**: S2 parse fail=0, sig_leak=0, df_violation=0, s3_drift=0

### DataPipeline

**independent_context**: S2 parse fail=0, sig_leak=0, df_violation=0, s3_drift=0
**shared_conversation**: S2 parse fail=0, sig_leak=0, df_violation=0, s3_drift=0

### Patient/sample_01 parse behavior

**independent_context**: S2 parse fail=0, S3 parse fail=0, identity_drift_s2=0
**shared_conversation**: S2 parse fail=0, S3 parse fail=0, identity_drift_s2=0

## Verdict

| Metric | independent_context | shared_conversation |
|--------|:-------------------:|:-------------------:|
| Stage2 parse failures | 0 | 0 |
| Stage3 parse failures | 0 | 0 |
| Child identity drift (total) | 0 | 0 |
| Signature resource leaks | 0 | 0 |
| Dataflow schema violations | 0 | 0 |
| Stage3 signature drift | 24 | 0 |
| GV/DO sync gaps | 0 | 0 |

**Verdict: SHARED_CONTEXT_IMPROVES_INTERFACE_DISCIPLINE**

### Verdict Boundary

This experiment can only support or reject the narrower hypothesis:
> shared conversation memory improves Stage2/3 continuity and interface-category discipline

It does NOT establish migration readiness. Migration requires additional validation
including real codegen integration and production-domain testing.
