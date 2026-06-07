# Step2 Verifier Schema-Order Experiment Report

**Model**: deepseek-chat
**Date**: 2026-06-07 08:53:49

## Hypothesis

Reordering the verify JSON schema from `status -> checks -> decomposition_feedback`
to `checks -> decomposition_feedback -> final_status` will reduce self-contradictory
outputs where status='ok' but failed_checks is non-empty.

## Cases

| Case | Expected | Mode | Description |
|------|----------|------|-------------|
| N1 | reject | verifier_only | Hardcoded runtime ID |
| N2a | reject | verifier_only | Literal substitutes child output |
| N2b | accept | full_generate | Full generate, child output required (positive control) |
| N3a | reject | verifier_only | Runtime status hardcoded |
| N3b | accept | full_generate | Full generate, status from child (positive control) |
| N4 | reject | verifier_only | Missing capability masked by literal |
| N5 | reject | full_generate | Sibling call violation (key case) |
| P1 | accept | full_generate | Unsupported command branch literal |
| P2 | accept | full_generate | Empty list PRD literal |
| P3 | accept | full_generate | Conditional dispatch, no literals |

## Per-Case Results

| Case | Expected | Old Status | New Status | Old Contradictory | New Contradictory | Old Verdict | New Verdict |
|------|----------|------------|------------|-------------------|-------------------|-------------|-------------|
| N1 | reject | cannot_compose | cannot_compose | no | no | correct_reject | correct_reject |
| N2a | reject | cannot_compose | cannot_compose | no | no | correct_reject | correct_reject |
| N2b | accept | ok | ok | no | no | correct_accept | correct_accept |
| N3a | reject | cannot_compose | cannot_compose | no | no | correct_reject | correct_reject |
| N3b | accept | ok | ok | no | no | correct_accept | correct_accept |
| N4 | reject | cannot_compose | cannot_compose | no | no | correct_reject | correct_reject |
| N5 | reject | ok | cannot_compose | YES | no | false_acceptance | correct_reject |
| P1 | accept | ok | ok | no | no | correct_accept | correct_accept |
| P2 | accept | ok | ok | no | no | correct_accept | correct_accept |
| P3 | accept | cannot_compose | cannot_compose | no | no | false_rejection | false_rejection |

## Summary

| Metric | Old Order | New Order |
|--------|-----------|-----------|
| Self-contradictions | 1/10 | 0/10 |
| Correct verdicts | 8/10 | 9/10 |

## Key Findings

### N5 (Sibling Call Violation — Key Case)

- **Old order**: status=`ok`, contradictory=True
- **New order**: final_status=`cannot_compose`, contradictory=False
- **Result**: Schema reordering FIXED the N5 contradiction.

### Positive False Rejection Check

- **WARNING**: new_order introduced false rejections on: P3

### Negative Rejection Check

- All negative cases correctly rejected in new_order.

## Conclusion

Mixed results. See per-case details above.

---
*Stop rule: single pass, no prompt tuning, no MVP modification.*