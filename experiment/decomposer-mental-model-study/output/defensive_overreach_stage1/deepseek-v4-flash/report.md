# Stage1 Defensive Overreach Experiment

Model: `deepseek-v4-flash`
Temperature: `0.3`
Trials: `15`

## Purpose

Test whether Stage1 decomposition adds defensive checks when the node boundary says the node should only insert a student record.

## Summary

| Condition | Expected Defense | Trials | Defense Present | Defensive Overreach | Required Defense Missing | Parse/API Errors |
|-----------|------------------|--------|-----------------|---------------------|--------------------------|------------------|
| baseline | False | 3 | 2 | 2 | 0 | 0 |
| weak_no_duplicate | False | 3 | 1 | 1 | 0 | 0 |
| parent_guarantee | False | 3 | 0 | 0 | 0 | 0 |
| strict_closed_boundary | False | 3 | 0 | 0 | 0 | 0 |
| positive_control_defense_required | True | 3 | 3 | 0 | 0 | 0 |

## Category Counts

| Condition | duplicate | existence/lookup | input validation | error/fallback | parent guarantee revalidation |
|-----------|-----------|------------------|------------------|----------------|-------------------------------|
| baseline | 0 | 0 | 2 | 0 | 0 |
| weak_no_duplicate | 0 | 0 | 1 | 0 | 0 |
| parent_guarantee | 0 | 0 | 0 | 0 | 0 |
| strict_closed_boundary | 0 | 0 | 0 | 0 | 0 |
| positive_control_defense_required | 3 | 3 | 0 | 0 | 0 |

## Per-Trial Details

### baseline / trial_00
- Children: PrepareStudentRecord, InsertRecordIntoStore
- Verdict: `NO_DEFENSIVE_OVERREACH`
- Categories: {"duplicate_check": false, "existence_or_lookup_check": false, "input_validation": false, "error_or_fallback_handling": false, "parent_guarantee_revalidation": false}

### baseline / trial_01
- Children: ValidateInput, InsertIntoStore
- Verdict: `DEFENSIVE_OVERREACH`
- Categories: {"duplicate_check": false, "existence_or_lookup_check": false, "input_validation": true, "error_or_fallback_handling": false, "parent_guarantee_revalidation": false}
- Evidence:
  - ValidateInput / input_validation / composition_role: validate

### baseline / trial_02
- Children: ValidateInput, InsertRecord
- Verdict: `DEFENSIVE_OVERREACH`
- Categories: {"duplicate_check": false, "existence_or_lookup_check": false, "input_validation": true, "error_or_fallback_handling": false, "parent_guarantee_revalidation": false}
- Evidence:
  - ValidateInput / input_validation / composition_role: validate

### weak_no_duplicate / trial_00
- Children: BuildStudentRecord, InsertRecord
- Verdict: `NO_DEFENSIVE_OVERREACH`
- Categories: {"duplicate_check": false, "existence_or_lookup_check": false, "input_validation": false, "error_or_fallback_handling": false, "parent_guarantee_revalidation": false}

### weak_no_duplicate / trial_01
- Children: ValidateInput, InsertRecord
- Verdict: `DEFENSIVE_OVERREACH`
- Categories: {"duplicate_check": false, "existence_or_lookup_check": false, "input_validation": true, "error_or_fallback_handling": false, "parent_guarantee_revalidation": false}
- Evidence:
  - ValidateInput / input_validation / composition_role: validate

### weak_no_duplicate / trial_02
- Children: BuildStudentRecord, InsertRecord
- Verdict: `NO_DEFENSIVE_OVERREACH`
- Categories: {"duplicate_check": false, "existence_or_lookup_check": false, "input_validation": false, "error_or_fallback_handling": false, "parent_guarantee_revalidation": false}

### parent_guarantee / trial_00
- Children: BuildStudentRecord, InsertRecord
- Verdict: `NO_DEFENSIVE_OVERREACH`
- Categories: {"duplicate_check": false, "existence_or_lookup_check": false, "input_validation": false, "error_or_fallback_handling": false, "parent_guarantee_revalidation": false}

### parent_guarantee / trial_01
- Children: BuildStudentRecord, InsertRecord
- Verdict: `NO_DEFENSIVE_OVERREACH`
- Categories: {"duplicate_check": false, "existence_or_lookup_check": false, "input_validation": false, "error_or_fallback_handling": false, "parent_guarantee_revalidation": false}

### parent_guarantee / trial_02
- Children: BuildStudentRecord, InsertRecord
- Verdict: `NO_DEFENSIVE_OVERREACH`
- Categories: {"duplicate_check": false, "existence_or_lookup_check": false, "input_validation": false, "error_or_fallback_handling": false, "parent_guarantee_revalidation": false}

### strict_closed_boundary / trial_00
- Children: InsertIntoDataStore
- Verdict: `NO_DEFENSIVE_OVERREACH`
- Categories: {"duplicate_check": false, "existence_or_lookup_check": false, "input_validation": false, "error_or_fallback_handling": false, "parent_guarantee_revalidation": false}

### strict_closed_boundary / trial_01
- Children: BuildStudentRecord, InsertRecordIntoStore
- Verdict: `NO_DEFENSIVE_OVERREACH`
- Categories: {"duplicate_check": false, "existence_or_lookup_check": false, "input_validation": false, "error_or_fallback_handling": false, "parent_guarantee_revalidation": false}

### strict_closed_boundary / trial_02
- Children: BuildStudentRecord, InsertRecord
- Verdict: `NO_DEFENSIVE_OVERREACH`
- Categories: {"duplicate_check": false, "existence_or_lookup_check": false, "input_validation": false, "error_or_fallback_handling": false, "parent_guarantee_revalidation": false}

### positive_control_defense_required / trial_00
- Children: CheckDuplicate, InsertRecord
- Verdict: `REQUIRED_DEFENSE_PRESENT`
- Categories: {"duplicate_check": true, "existence_or_lookup_check": true, "input_validation": false, "error_or_fallback_handling": false, "parent_guarantee_revalidation": false}
- Evidence:
  - CheckDuplicate / duplicate_check / purpose: Check if student_id already exists in students data store
  - CheckDuplicate / existence_or_lookup_check / purpose: Check if student_id already exists in students data store

### positive_control_defense_required / trial_01
- Children: CheckDuplicate, InsertRecord
- Verdict: `REQUIRED_DEFENSE_PRESENT`
- Categories: {"duplicate_check": true, "existence_or_lookup_check": true, "input_validation": false, "error_or_fallback_handling": false, "parent_guarantee_revalidation": false}
- Evidence:
  - CheckDuplicate / duplicate_check / purpose: Check if student_id already exists in the students data store
  - CheckDuplicate / existence_or_lookup_check / purpose: Check if student_id already exists in the students data store

### positive_control_defense_required / trial_02
- Children: CheckDuplicate, InsertRecord
- Verdict: `REQUIRED_DEFENSE_PRESENT`
- Categories: {"duplicate_check": true, "existence_or_lookup_check": true, "input_validation": false, "error_or_fallback_handling": false, "parent_guarantee_revalidation": false}
- Evidence:
  - CheckDuplicate / duplicate_check / purpose: Check if student_id already exists in the students data store
  - CheckDuplicate / existence_or_lookup_check / purpose: Check if student_id already exists in the students data store

## Notes

- The judge is deterministic keyword/field based; manually inspect raw responses for borderline cases.
- `positive_control_defense_required` should produce defense. If it does not, the model likely ignored task requirements.
- Defensive overreach in `baseline` or `weak_no_duplicate` indicates out-of-scope text alone is insufficient.
- Defensive overreach in `strict_closed_boundary` indicates prompt-only boundary enforcement is weak.
