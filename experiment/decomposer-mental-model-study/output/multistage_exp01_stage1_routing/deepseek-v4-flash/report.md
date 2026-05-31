# Exp01: Expanded Stage 1 Routing Robustness Report

Model: `deepseek-v4-flash`
Domains: Order, Chat, Patient, BuildSystem, DataPipeline
Trials per domain: 5
Total trials: 25

## Results by Domain

| Domain | Trials | Routing | Top-Level Routing | Child Count Violations | Parse Errors | Avg Field Completion |
|--------|--------|---------|-------------------|----------------------|--------------|---------------------|
| Order | 5 | 4/5 | 1/5 | 1/5 | 0/5 | 100.0% |
| Chat | 5 | 5/5 | 1/5 | 0/5 | 0/5 | 100.0% |
| Patient | 5 | 3/5 | 1/5 | 0/5 | 0/5 | 100.0% |
| BuildSystem | 5 | 4/5 | 1/5 | 0/5 | 0/5 | 100.0% |
| DataPipeline | 5 | 0/5 | 0/5 | 0/5 | 0/5 | 100.0% |
| **TOTAL** | **25** | **16/25 (64%)** | **4/25** | **1/25** | **0/25** | **100.0%** |

## Routing Cases Detail

### Order_02
- Children: ['ParseCommand', 'PlaceOrder', 'CancelOrder', 'TrackOrder']
- Composition roles: ['validate', 'execute', 'execute', 'query']
- Orchestration model: conditional
- Sibling calls (extended):
  - ParseCommand -> PlaceOrder (structural_router)
  - ParseCommand -> CancelOrder (structural_router)
  - ParseCommand -> TrackOrder (structural_router)

### Order_01
- Children: ['ParseAndValidateInput', 'PlaceOrder', 'CancelOrder', 'TrackOrder']
- Composition roles: ['validate', 'execute', 'execute', 'query']
- Orchestration model: conditional
- Sibling calls (extended):
  - ParseAndValidateInput -> PlaceOrder (structural_router)
  - ParseAndValidateInput -> CancelOrder (structural_router)
  - ParseAndValidateInput -> TrackOrder (structural_router)

### Order_04
- Children: ['ParseAndValidateInput', 'PlaceOrder', 'CancelOrder', 'TrackOrder', 'FormatOutput']
- Composition roles: ['validate', 'execute', 'execute', 'query', 'transform']
- Orchestration model: conditional
- Sibling calls (extended):
  - ParseAndValidateInput -> PlaceOrder (structural_router)
  - ParseAndValidateInput -> CancelOrder (structural_router)
  - ParseAndValidateInput -> TrackOrder (structural_router)
  - ParseAndValidateInput -> FormatOutput (structural_router)

### Order_03
- Children: ['ParseAndValidateInput', 'PlaceOrder', 'CancelOrder', 'TrackOrder', 'ValidateItemsAndStock', 'ChargePayment', 'ReserveInventory', 'CreateOrderRecord', 'VerifyOrderNotShipped', 'RefundPayment', 'RestoreInventory', 'UpdateOrderStatus']
- Composition roles: ['validate', 'execute', 'execute', 'query', 'validate', 'execute', 'execute', 'execute', 'validate', 'execute', 'execute', 'execute']
- Orchestration model: conditional
- Sibling calls (extended):
  - PlaceOrder -> ValidateItemsAndStock (text_pattern)
  - CancelOrder -> VerifyOrderNotShipped (text_pattern)
  - ParseAndValidateInput -> PlaceOrder (structural_router)
  - ParseAndValidateInput -> CancelOrder (structural_router)
  - ParseAndValidateInput -> TrackOrder (structural_router)
  - ParseAndValidateInput -> ValidateItemsAndStock (structural_router)
  - ParseAndValidateInput -> ChargePayment (structural_router)
  - ParseAndValidateInput -> ReserveInventory (structural_router)
  - ParseAndValidateInput -> CreateOrderRecord (structural_router)
  - ParseAndValidateInput -> VerifyOrderNotShipped (structural_router)
  - ParseAndValidateInput -> RefundPayment (structural_router)
  - ParseAndValidateInput -> RestoreInventory (structural_router)
  - ParseAndValidateInput -> UpdateOrderStatus (structural_router)
- Top-level violations:
  - PlaceOrder -> ValidateItemsAndStock (dataflow_sketch_sibling_ref)
  - ValidateItemsAndStock -> PlaceOrder (dataflow_sketch_sibling_ref)
  - PlaceOrder -> ChargePayment (dataflow_sketch_sibling_ref)
  - ChargePayment -> PlaceOrder (dataflow_sketch_sibling_ref)
  - PlaceOrder -> ReserveInventory (dataflow_sketch_sibling_ref)
  - ReserveInventory -> PlaceOrder (dataflow_sketch_sibling_ref)
  - PlaceOrder -> CreateOrderRecord (dataflow_sketch_sibling_ref)
  - CreateOrderRecord -> PlaceOrder (dataflow_sketch_sibling_ref)
  - CancelOrder -> VerifyOrderNotShipped (dataflow_sketch_sibling_ref)
  - VerifyOrderNotShipped -> CancelOrder (dataflow_sketch_sibling_ref)
  - CancelOrder -> RefundPayment (dataflow_sketch_sibling_ref)
  - RefundPayment -> CancelOrder (dataflow_sketch_sibling_ref)
  - CancelOrder -> RestoreInventory (dataflow_sketch_sibling_ref)
  - RestoreInventory -> CancelOrder (dataflow_sketch_sibling_ref)
  - CancelOrder -> UpdateOrderStatus (dataflow_sketch_sibling_ref)
  - UpdateOrderStatus -> CancelOrder (dataflow_sketch_sibling_ref)

### Chat_04
- Children: ['ParseAndValidateCommand', 'SendMessageHandler', 'GetHistoryHandler', 'CreateChannelHandler', 'JoinChannelHandler', 'FormatResponse']
- Composition roles: ['validate', 'execute', 'query', 'execute', 'execute', 'aggregate']
- Orchestration model: conditional
- Sibling calls (extended):
  - ParseAndValidateCommand -> SendMessageHandler (structural_router)
  - ParseAndValidateCommand -> GetHistoryHandler (structural_router)
  - ParseAndValidateCommand -> CreateChannelHandler (structural_router)
  - ParseAndValidateCommand -> JoinChannelHandler (structural_router)
  - ParseAndValidateCommand -> FormatResponse (structural_router)

### Chat_02
- Children: ['ParseAndValidateCommand', 'SendMessage', 'GetHistory', 'CreateChannel', 'JoinChannel', 'FormatResponse']
- Composition roles: ['validate', 'execute', 'query', 'execute', 'execute', 'aggregate']
- Orchestration model: conditional
- Sibling calls (extended):
  - ParseAndValidateCommand -> SendMessage (structural_router)
  - ParseAndValidateCommand -> GetHistory (structural_router)
  - ParseAndValidateCommand -> CreateChannel (structural_router)
  - ParseAndValidateCommand -> JoinChannel (structural_router)
  - ParseAndValidateCommand -> FormatResponse (structural_router)

### Chat_03
- Children: ['ParseAndValidateInput', 'SendMessage', 'GetHistory', 'CreateChannel', 'JoinChannel', 'FormatResponse']
- Composition roles: ['validate', 'execute', 'query', 'execute', 'execute', 'transform']
- Orchestration model: conditional
- Sibling calls (extended):
  - ParseAndValidateInput -> SendMessage (structural_router)
  - ParseAndValidateInput -> GetHistory (structural_router)
  - ParseAndValidateInput -> CreateChannel (structural_router)
  - ParseAndValidateInput -> JoinChannel (structural_router)
  - ParseAndValidateInput -> FormatResponse (structural_router)

### Chat_00
- Children: ['ParseAndValidateInput', 'RouteCommand', 'HandleSendMessage', 'HandleGetHistory', 'HandleCreateChannel', 'HandleJoinChannel', 'FormatOutput']
- Composition roles: ['validate', 'decide', 'execute', 'query', 'execute', 'execute', 'transform']
- Orchestration model: sequence
- Sibling calls (extended):
  - RouteCommand -> ParseAndValidateInput (text_pattern)
  - ParseAndValidateInput -> RouteCommand (structural_router)
  - ParseAndValidateInput -> HandleSendMessage (structural_router)
  - ParseAndValidateInput -> HandleGetHistory (structural_router)
  - ParseAndValidateInput -> HandleCreateChannel (structural_router)
  - ParseAndValidateInput -> HandleJoinChannel (structural_router)
  - ParseAndValidateInput -> FormatOutput (structural_router)
  - RouteCommand -> ParseAndValidateInput (structural_router)
  - RouteCommand -> HandleSendMessage (structural_router)
  - RouteCommand -> HandleGetHistory (structural_router)
  - RouteCommand -> HandleCreateChannel (structural_router)
  - RouteCommand -> HandleJoinChannel (structural_router)
  - RouteCommand -> FormatOutput (structural_router)
- Top-level violations:
  - ParseAndValidateInput -> RouteCommand (dataflow_sketch_sibling_ref)
  - RouteCommand -> HandleSendMessage (dataflow_sketch_sibling_ref)
  - RouteCommand -> HandleGetHistory (dataflow_sketch_sibling_ref)
  - RouteCommand -> HandleCreateChannel (dataflow_sketch_sibling_ref)
  - RouteCommand -> HandleJoinChannel (dataflow_sketch_sibling_ref)
  - HandleSendMessage -> RouteCommand (dataflow_sketch_sibling_ref)
  - HandleGetHistory -> RouteCommand (dataflow_sketch_sibling_ref)
  - HandleCreateChannel -> RouteCommand (dataflow_sketch_sibling_ref)
  - HandleJoinChannel -> RouteCommand (dataflow_sketch_sibling_ref)
  - RouteCommand -> FormatOutput (dataflow_sketch_sibling_ref)

### Chat_01
- Children: ['ParseCommand', 'SendMessage', 'GetHistory', 'CreateChannel', 'JoinChannel', 'FormatOutput']
- Composition roles: ['validate', 'execute', 'query', 'execute', 'execute', 'aggregate']
- Orchestration model: conditional
- Sibling calls (extended):
  - ParseCommand -> SendMessage (structural_router)
  - ParseCommand -> GetHistory (structural_router)
  - ParseCommand -> CreateChannel (structural_router)
  - ParseCommand -> JoinChannel (structural_router)
  - ParseCommand -> FormatOutput (structural_router)

### Patient_01
- Children: ['ParseAndValidateInput', 'RegisterPatient', 'CheckPatientExists', 'CheckDoctorAvailability', 'CreateAppointment', 'RetrieveMedicalRecords', 'ValidateInsuranceExternal', 'UpdatePatientProfile', 'FormatOutput']
- Composition roles: ['validate', 'execute', 'query', 'query', 'execute', 'query', 'validate', 'execute', 'transform']
- Orchestration model: conditional
- Sibling calls (extended):
  - ParseAndValidateInput -> RegisterPatient (structural_router)
  - ParseAndValidateInput -> CheckPatientExists (structural_router)
  - ParseAndValidateInput -> CheckDoctorAvailability (structural_router)
  - ParseAndValidateInput -> CreateAppointment (structural_router)
  - ParseAndValidateInput -> RetrieveMedicalRecords (structural_router)
  - ParseAndValidateInput -> ValidateInsuranceExternal (structural_router)
  - ParseAndValidateInput -> UpdatePatientProfile (structural_router)
  - ParseAndValidateInput -> FormatOutput (structural_router)

### Patient_02
- Children: ['ParseAndValidateInput', 'RegisterPatient', 'CheckPatientExists', 'CheckDoctorAvailability', 'CreateAppointment', 'RetrieveMedicalRecords', 'ValidateInsuranceExternal', 'UpdatePatientProfile', 'FormatOutput']
- Composition roles: ['validate', 'execute', 'query', 'query', 'execute', 'query', 'validate', 'execute', 'transform']
- Orchestration model: mixed
- Sibling calls (extended):
  - ParseAndValidateInput -> RegisterPatient (structural_router)
  - ParseAndValidateInput -> CheckPatientExists (structural_router)
  - ParseAndValidateInput -> CheckDoctorAvailability (structural_router)
  - ParseAndValidateInput -> CreateAppointment (structural_router)
  - ParseAndValidateInput -> RetrieveMedicalRecords (structural_router)
  - ParseAndValidateInput -> ValidateInsuranceExternal (structural_router)
  - ParseAndValidateInput -> UpdatePatientProfile (structural_router)
  - ParseAndValidateInput -> FormatOutput (structural_router)

### Patient_00
- Children: ['ParseAndValidateInput', 'RegisterPatient', 'CheckPatientExists', 'CheckDoctorAvailability', 'CreateAppointment', 'ValidateAppointmentTime', 'RetrieveMedicalRecords', 'ValidateUpdateFields', 'UpdatePatientProfile', 'FormatResponse']
- Composition roles: ['validate', 'execute', 'query', 'query', 'execute', 'validate', 'query', 'validate', 'execute', 'aggregate']
- Orchestration model: conditional
- Sibling calls (extended):
  - ParseAndValidateInput -> RegisterPatient (structural_router)
  - ParseAndValidateInput -> CheckPatientExists (structural_router)
  - ParseAndValidateInput -> CheckDoctorAvailability (structural_router)
  - ParseAndValidateInput -> CreateAppointment (structural_router)
  - ParseAndValidateInput -> ValidateAppointmentTime (structural_router)
  - ParseAndValidateInput -> RetrieveMedicalRecords (structural_router)
  - ParseAndValidateInput -> ValidateUpdateFields (structural_router)
  - ParseAndValidateInput -> UpdatePatientProfile (structural_router)
  - ParseAndValidateInput -> FormatResponse (structural_router)
- Top-level violations:
  - rationale -> ParseAndValidateInput (rationale_sibling_ref)
  - rationale -> ParseAndValidateInput (rationale_sibling_ref)
  - rationale -> ParseAndValidateInput (rationale_sibling_ref)
  - rationale -> ParseAndValidateInput (rationale_sibling_ref)

### BuildSystem_04
- Children: ['ParseAndValidateInput', 'CheckBuildConstraint', 'TriggerBuild', 'GetBuildStatus', 'ListBuilds', 'CancelBuild', 'FormatOutput']
- Composition roles: ['validate', 'validate', 'execute', 'query', 'query', 'mutate', 'aggregate']
- Orchestration model: conditional
- Sibling calls (extended):
  - ParseAndValidateInput -> CheckBuildConstraint (structural_router)
  - ParseAndValidateInput -> TriggerBuild (structural_router)
  - ParseAndValidateInput -> GetBuildStatus (structural_router)
  - ParseAndValidateInput -> ListBuilds (structural_router)
  - ParseAndValidateInput -> CancelBuild (structural_router)
  - ParseAndValidateInput -> FormatOutput (structural_router)

### BuildSystem_02
- Children: ['ParseAndValidateInput', 'CheckBuildConflict', 'CreateBuildRecord', 'RunCompileStep', 'RunTestStep', 'PackageArtifacts', 'QueryBuildStatus', 'ListBuilds', 'CancelBuild', 'FormatOutput']
- Composition roles: ['validate', 'query', 'execute', 'execute', 'execute', 'execute', 'query', 'query', 'execute', 'aggregate']
- Orchestration model: mixed
- Sibling calls (extended):
  - ParseAndValidateInput -> CheckBuildConflict (structural_router)
  - ParseAndValidateInput -> CreateBuildRecord (structural_router)
  - ParseAndValidateInput -> RunCompileStep (structural_router)
  - ParseAndValidateInput -> RunTestStep (structural_router)
  - ParseAndValidateInput -> PackageArtifacts (structural_router)
  - ParseAndValidateInput -> QueryBuildStatus (structural_router)
  - ParseAndValidateInput -> ListBuilds (structural_router)
  - ParseAndValidateInput -> CancelBuild (structural_router)
  - ParseAndValidateInput -> FormatOutput (structural_router)

### BuildSystem_01
- Children: ['ParseAction', 'ValidateRepoBranch', 'CheckExistingBuild', 'CreateBuildRecord', 'RunCompile', 'RunTests', 'PackageArtifacts', 'GetBuildStatus', 'ListBuilds', 'CancelBuild']
- Composition roles: ['validate', 'validate', 'query', 'execute', 'execute', 'execute', 'execute', 'query', 'query', 'execute']
- Orchestration model: mixed
- Top-level violations:
  - ValidateRepoBranch -> CheckExistingBuild (dataflow_sketch_sibling_ref)
  - CreateBuildRecord -> RunCompile (dataflow_sketch_sibling_ref)
  - RunCompile -> RunTests (dataflow_sketch_sibling_ref)
  - RunTests -> PackageArtifacts (dataflow_sketch_sibling_ref)
  - rationale -> CreateBuildRecord (rationale_sibling_ref)
  - rationale -> GetBuildStatus (rationale_sibling_ref)
  - rationale -> ListBuilds (rationale_sibling_ref)
  - rationale -> CancelBuild (rationale_sibling_ref)

### BuildSystem_00
- Children: ['ParseAndValidateInput', 'CheckBuildConstraint', 'CreateBuildRecord', 'RunCompilation', 'RunTests', 'PackageArtifacts', 'QueryBuildStatus', 'ListBuilds', 'CancelBuild', 'FormatOutput']
- Composition roles: ['validate', 'query', 'execute', 'execute', 'execute', 'execute', 'query', 'query', 'execute', 'aggregate']
- Orchestration model: conditional
- Sibling calls (extended):
  - ParseAndValidateInput -> CheckBuildConstraint (structural_router)
  - ParseAndValidateInput -> CreateBuildRecord (structural_router)
  - ParseAndValidateInput -> RunCompilation (structural_router)
  - ParseAndValidateInput -> RunTests (structural_router)
  - ParseAndValidateInput -> PackageArtifacts (structural_router)
  - ParseAndValidateInput -> QueryBuildStatus (structural_router)
  - ParseAndValidateInput -> ListBuilds (structural_router)
  - ParseAndValidateInput -> CancelBuild (structural_router)
  - ParseAndValidateInput -> FormatOutput (structural_router)

### BuildSystem_03
- Children: ['ParseAndValidateInput', 'CheckBuildConflict', 'CreateBuildRecord', 'RunCompile', 'RunTests', 'PackageArtifacts', 'GetBuildStatus', 'ListBuilds', 'CancelBuild', 'FormatOutput']
- Composition roles: ['validate', 'query', 'execute', 'execute', 'execute', 'execute', 'query', 'query', 'mutate', 'aggregate']
- Orchestration model: mixed
- Sibling calls (extended):
  - ParseAndValidateInput -> CheckBuildConflict (structural_router)
  - ParseAndValidateInput -> CreateBuildRecord (structural_router)
  - ParseAndValidateInput -> RunCompile (structural_router)
  - ParseAndValidateInput -> RunTests (structural_router)
  - ParseAndValidateInput -> PackageArtifacts (structural_router)
  - ParseAndValidateInput -> GetBuildStatus (structural_router)
  - ParseAndValidateInput -> ListBuilds (structural_router)
  - ParseAndValidateInput -> CancelBuild (structural_router)
  - ParseAndValidateInput -> FormatOutput (structural_router)

## Verdict

- Routing rate: 64.0% (target: 0-17%)
- Child count violations: 1/25
- Field completion: 100.0%
- **Verdict: FAIL**
