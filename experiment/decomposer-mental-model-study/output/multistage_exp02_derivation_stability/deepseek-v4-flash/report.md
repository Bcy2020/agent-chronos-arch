# Exp02: Stage 1 → Stage 2/3 Derivation Stability Report

Model: `deepseek-v4-flash`
Samples per domain: 2
Repetitions per stage: 5
Total samples: 10

## Results by Domain

| Domain | Samples | Identity Drift (S2) | Identity Drift (S3) | Semantic Drift (S2) | Semantic Drift (S3) | Sig Stability | DF Stability | Res Stability | S2 Parse Err | S3 Parse Err |
|--------|---------|--------------------|--------------------|--------------------|--------------------|--------------|-------------|--------------|-------------|-------------|
| Order | 2 | 0 | 0 | 0 | 0 | 76.2% | 100.0% | 37.5% | 0 | 0 |
| Chat | 2 | 0 | 0 | 0 | 0 | 43.2% | 87.5% | 50.0% | 0 | 0 |
| Patient | 2 | 1 | 0 | 0 | 0 | 50.0% | 37.5% | 50.0% | 0 | 0 |
| BuildSystem | 2 | 0 | 0 | 0 | 0 | 42.9% | 100.0% | 50.0% | 0 | 0 |
| DataPipeline | 2 | 0 | 0 | 0 | 0 | 84.4% | 25.0% | 87.5% | 0 | 0 |
| **TOTAL** | **10** | **1** | **0** | **0** | **0** | **59.3%** | **70.0%** | **55.0%** | **0** | **0** |

## Identity Drift Cases

### Patient/sample_01
- Added: set(), Removed: {'UpdateProfile', 'GetRecords', 'RegisterPatient', 'BookAppointment'}
  Stage1: ['RegisterPatient', 'BookAppointment', 'GetRecords', 'UpdateProfile']
  Derived: []

## Semantic Drift Cases

No semantic drift detected.

## Verdict

- Child identity drift (Stage 2): 1 occurrences
- Child identity drift (Stage 3): 0 occurrences
- Semantic drift (Stage 2): 0 field changes
- Semantic drift (Stage 3): 0 field changes
- Signature stability: 59.3%
- Dataflow topology stability: 70.0%
- Resource allocation stability: 55.0%
- **Verdict: FAIL**
