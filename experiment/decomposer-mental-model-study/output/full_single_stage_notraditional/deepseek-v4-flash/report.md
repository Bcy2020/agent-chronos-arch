# Full Single-Stage + No-Traditional: Missing Cell Experiment Report

Model: `deepseek-v4-flash`
Domains: Order, Chat, Patient, BuildSystem, DataPipeline
Trials per domain: 5
Total trials: 25

## Purpose

Test the missing experimental cell: full single-stage decomposer schema + no-traditional rule.

> Does the no-traditional rule still suppress hard routing when the decomposer
> is asked to produce the full original single-stage schema?

## Prompt Condition

System prompt: full original single-stage schema from `mvp-0.4.4/decomposer.py`
plus the DO NOT ASSUME TRADITIONAL DEVELOPMENT PATTERNS block.

No stage separation — all fields (inputs, outputs, signature, data_operations,
global_vars, traceability, dataflow_edges, etc.) in a single LLM call.

## Results by Domain

| Domain | Trials | Hard Routing | Ambiguous Dataflow | Parent-Mediated | Child Count Violations | Parse Errors | Avg Field Completion |
|--------|--------|-------------|-------------------|-----------------|----------------------|--------------|---------------------|
| Order | 5 | 5/5 | 5/5 | 4/5 | 0/5 | 0/5 | 100.0% |
| Chat | 5 | 5/5 | 5/5 | 5/5 | 0/5 | 0/5 | 100.0% |
| Patient | 5 | 5/5 | 5/5 | 5/5 | 0/5 | 0/5 | 100.0% |
| BuildSystem | 5 | 5/5 | 5/5 | 2/5 | 0/5 | 0/5 | 100.0% |
| DataPipeline | 5 | 0/5 | 5/5 | 4/5 | 0/5 | 0/5 | 100.0% |
| **TOTAL** | **25** | **20/25 (80%)** | **25/25** | **20/25** | **0/25** | **0/25** | **100.0%** |

## Verdict

- **Hard routing rate**: 20/25 (80%)
- **Child count violations**: 0/25
- **Field completion**: 100.0%
- **Verdict: FAIL** — Hard routing rate is clearly above the target range.

## Comparison with Staged No-Traditional

| Condition | Hard Routing | Notes |
|-----------|-------------|-------|
| Staged Phase 1 + no-traditional (Exp01 rejudged) | 8% (2/25) | Lean output, no inputs/outputs/signature |
| Staged baseline (no no-traditional) | 100% (5/5) | Two-phase, Order domain only |
| Cross-domain staged + no-traditional | 17% (1/6) | 3 additional domains |
| **Full single-stage + no-traditional (this experiment)** | **80% (20/25)** | Full original schema in one call |

## Hard Routing Cases Detail

### Order_00
- Children: ParseAndValidateCommand, RouteCommand, PlaceOrder, CancelOrder, TrackOrder
- Node types: ['pure_function', 'pure_function', 'pure_function', 'pure_function', 'atomic_operation']
- Router nodes: ['RouteCommand']

### Order_01
- Children: ParseAndValidateCommand, RouteCommand, PlaceOrder, CancelOrder, TrackOrder
- Node types: ['pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteCommand']

### Order_03
- Children: ParseCommand, RouteCommand, PlaceOrder, CancelOrder, TrackOrder
- Node types: ['pure_function', 'pure_function', 'pure_function', 'pure_function', 'atomic_operation']
- Router nodes: ['RouteCommand']

### Order_02
- Children: ParseAndValidateInput, RouteCommand, PlaceOrder, CancelOrder, TrackOrder
- Node types: ['pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteCommand']

### Order_04
- Children: ParseAndValidateInput, RouteCommand, PlaceOrder, CancelOrder, TrackOrder
- Node types: ['pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteCommand']

### Chat_00
- Children: ParseInput, RouteCommand, SendMessage, GetHistory, CreateChannel, JoinChannel
- Node types: ['atomic_operation', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteCommand']

### Chat_03
- Children: ParseInput, RouteCommand, SendMessage, GetHistory, CreateChannel, JoinChannel
- Node types: ['pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteCommand']

### Chat_02
- Children: ParseCommand, RouteCommand, SendMessage, GetHistory, CreateChannel, JoinChannel
- Node types: ['pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteCommand']

### Chat_01
- Children: ParseInput, RouteCommand, SendMessage, GetHistory, CreateChannel, JoinChannel
- Node types: ['pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteCommand']

### Chat_04
- Children: ParseInput, RouteCommand, SendMessage, GetHistory, CreateChannel, JoinChannel
- Node types: ['pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteCommand']
- Hard routing sibling calls:
  - RouteCommand -> SendMessage: Message data for sending
  - RouteCommand -> GetHistory: Message data for history retrieval
  - RouteCommand -> CreateChannel: Message data for channel creation
  - RouteCommand -> JoinChannel: Message data for joining

### Patient_02
- Children: ParseInput, RouteCommand, RegisterPatient, BookAppointment, GetRecords, UpdateProfile
- Node types: ['pure_function', 'pure_function', 'pure_function', 'pure_function', 'pure_function', 'pure_function']
- Router nodes: ['RouteCommand']
- Hard routing sibling calls:
  - ParseInput -> RouteCommand: Command is routed

### Patient_01
- Children: ParseInput, RouteCommand, RegisterPatient, BookAppointment, GetRecords, UpdateProfile
- Node types: ['pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteCommand']

### Patient_00
- Children: ParseAndValidateInput, RouteCommand, RegisterPatient, BookAppointment, GetRecords, UpdateProfile
- Node types: ['pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteCommand']

### Patient_04
- Children: ParseInput, RouteCommand, RegisterPatient, BookAppointment, GetRecords, UpdateProfile
- Node types: ['pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteCommand']

### Patient_03
- Children: ParseInput, RouteCommand, RegisterPatient, BookAppointment, GetRecords, UpdateProfile
- Node types: ['pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteCommand']

### BuildSystem_01
- Children: ParseInput, RouteAction, TriggerBuild, GetStatus, ListBuilds, CancelBuild
- Node types: ['pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteAction']

### BuildSystem_03
- Children: ParseInput, RouteAction, TriggerBuild, GetStatus, ListBuilds, CancelBuild
- Node types: ['pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteAction']

### BuildSystem_02
- Children: ParseInput, RouteAction, TriggerBuild, GetStatus, ListBuilds, CancelBuild
- Node types: ['pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteAction']

### BuildSystem_00
- Children: ParseInput, RouteAction, TriggerBuild, GetStatus, ListBuilds, CancelBuild
- Node types: ['pure_function', 'pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'pure_function']
- Router nodes: ['RouteAction']

### BuildSystem_04
- Children: ParseAndValidateInput, RouteAction, TriggerBuild, GetBuildStatus, ListBuilds, CancelBuild, CompileCode, RunTests, PackageArtifacts
- Node types: ['pure_function', 'pure_function', 'pure_function', 'atomic_operation', 'atomic_operation', 'atomic_operation', 'atomic_operation', 'atomic_operation', 'atomic_operation']
- Router nodes: ['RouteAction']
- Hard routing sibling calls:
  - RouteAction -> TriggerBuild: Pass repo to trigger
  - RouteAction -> TriggerBuild: Pass branch to trigger
  - RouteAction -> TriggerBuild: Pass config to trigger
  - RouteAction -> GetBuildStatus: Pass build_id to status query
  - RouteAction -> ListBuilds: Pass repo filter
  - RouteAction -> ListBuilds: Pass branch filter
  - RouteAction -> CancelBuild: Pass build_id to cancel
  - TriggerBuild -> CompileCode: Pass repo to compile
  - TriggerBuild -> CompileCode: Pass branch to compile
  - TriggerBuild -> CompileCode: Pass config to compile
  - TriggerBuild -> RunTests: Pass repo to tests
  - TriggerBuild -> RunTests: Pass branch to tests
  - TriggerBuild -> RunTests: Pass config to tests
  - TriggerBuild -> PackageArtifacts: Pass repo to packaging
  - TriggerBuild -> PackageArtifacts: Pass branch to packaging
  - TriggerBuild -> PackageArtifacts: Pass config to packaging

## Ambiguous Direct Dataflow Cases

### DataPipeline_03
- Children: IngestData, TransformData, ValidateData, ExportData
  - IngestData -> TransformData: Raw records to transform
  - TransformData -> ValidateData: Transformed records to validate
  - ValidateData -> ExportData: Validated records to export

### DataPipeline_02
- Children: IngestData, TransformData, ValidateData, ExportData
  - IngestData -> TransformData: Raw records to transform
  - TransformData -> ValidateData: Transformed records to validate
  - ValidateData -> ExportData: Validated records to export

### DataPipeline_04
- Children: IngestData, TransformData, ValidateData, ExportData
  - IngestData -> TransformData: Raw records to transform
  - TransformData -> ValidateData: Transformed records to validate
  - ValidateData -> ExportData: Validated records to export

### DataPipeline_01
- Children: IngestData, TransformData, ValidateData, ExportData
  - IngestData -> TransformData: Pass raw data to transformation
  - TransformData -> ValidateData: Pass processed data to validation
  - ValidateData -> ExportData: Pass validated data to export

### DataPipeline_00
- Children: IngestData, TransformData, ValidateData, ExportData
  - IngestData -> TransformData: Raw records to transform
  - TransformData -> ValidateData: Transformed records to validate
  - ValidateData -> ExportData: Validated records to export

## Parent-Mediated Dataflow (not counted as hard routing)

- Order_01: ParseAndValidateCommand, RouteCommand, PlaceOrder, CancelOrder, TrackOrder
- Order_03: ParseCommand, RouteCommand, PlaceOrder, CancelOrder, TrackOrder
- Order_02: ParseAndValidateInput, RouteCommand, PlaceOrder, CancelOrder, TrackOrder
- Order_04: ParseAndValidateInput, RouteCommand, PlaceOrder, CancelOrder, TrackOrder
- Chat_00: ParseInput, RouteCommand, SendMessage, GetHistory, CreateChannel, JoinChannel

## Interpretation

### Does full single-stage + no-traditional suppress hard routing?
No. Hard routing rate 20/25 (80%) is significantly
above the staged no-traditional baseline.

### Is the result comparable to lean staged no-traditional?
No. The full schema load substantially reduces no-traditional's effectiveness.

### What remains inconclusive?
- Field completion: full schema requires ~20 fields per child plus top-level fields;
  LLM may omit sub-fields even if no-traditional routing suppression works.
- The no-traditional block was not separately ablated — we cannot distinguish
  full-schema effects from no-traditional effects without a full-schema baseline.
- Single model (deepseek-v4-flash) only; generalizability to other models unknown.
- The stop rule was followed: no prompt tuning, no judge patching, no fixture changes.

## Stop Rule Compliance

This experiment was implemented as a single pass with no follow-up modifications.
After producing results, no prompt tuning, judge patching, fixture changes,
MVP modifications, or hot.md updates were made.
