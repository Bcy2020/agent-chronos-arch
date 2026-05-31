# Exp01 Rejudge Report

Model: `deepseek-v4-flash`
Total trials: 25

## Old vs New Metrics

| Metric | Old Judge | New Judge |
|--------|-----------|-----------|
| routing rate | 64.0% (16/25) | 8.0% (2/25) |
| parent_mediated_dataflow | N/A | 100.0% |
| ambiguous_direct_dataflow | N/A | 12.0% |
| traditional_naming_residue | N/A | 4.0% |
| abstraction_level_mixing | N/A | 8.0% |
| field_completion_rate | 100.0% | same |
| child_count_violation | N/A | 4.0% |

## Verdict

- **PASS**: Hard routing rate is within the verified 0-17% range.

## Downgraded Cases (old=routing -> new=not hard_routing)

### Order/trial_01

- Old: has_routing=True
- New: hard_routing=False, parent_mediated=True, ambiguous=False
- Children: ParseAndValidateInput, PlaceOrder, CancelOrder, TrackOrder
  - [parent_mediated_dataflow] The parent OrderSystem handles three distinct commands. ParseAndValidateInput handles input validation and routing logic (parent decides which child t

### Order/trial_02

- Old: has_routing=True
- New: hard_routing=False, parent_mediated=True, ambiguous=False
- Children: ParseCommand, PlaceOrder, CancelOrder, TrackOrder
  - [parent_mediated_dataflow] The parent OrderSystem acts as a single entry point that routes to one of three distinct workflows based on the command. ParseCommand handles input va

### Order/trial_04

- Old: has_routing=True
- New: hard_routing=False, parent_mediated=True, ambiguous=False
- Children: ParseAndValidateInput, PlaceOrder, CancelOrder, TrackOrder, FormatOutput
  - [parent_mediated_dataflow] The parent OrderSystem routes based on command to one of three execution children (PlaceOrder, CancelOrder, TrackOrder), each handling a distinct work

### Chat/trial_01

- Old: has_routing=True
- New: hard_routing=False, parent_mediated=True, ambiguous=False
- Children: ParseCommand, SendMessage, GetHistory, CreateChannel, JoinChannel, FormatOutput
  - [parent_mediated_dataflow] The ChatApp node is decomposed into six children: ParseCommand for input validation, four command-specific children (SendMessage, GetHistory, CreateCh

### Chat/trial_02

- Old: has_routing=True
- New: hard_routing=False, parent_mediated=True, ambiguous=False
- Children: ParseAndValidateCommand, SendMessage, GetHistory, CreateChannel, JoinChannel, FormatResponse
  - [parent_mediated_dataflow] The parent ChatApp handles four distinct commands. Each command is decomposed into its own child function that performs the specific business logic. P

### Chat/trial_03

- Old: has_routing=True
- New: hard_routing=False, parent_mediated=True, ambiguous=False
- Children: ParseAndValidateInput, SendMessage, GetHistory, CreateChannel, JoinChannel, FormatResponse
  - [parent_mediated_dataflow] The parent ChatApp handles four distinct commands. Each command is decomposed into its own child function that performs the specific business logic. P

### Chat/trial_04

- Old: has_routing=True
- New: hard_routing=False, parent_mediated=True, ambiguous=False
- Children: ParseAndValidateCommand, SendMessageHandler, GetHistoryHandler, CreateChannelHandler, JoinChannelHandler, FormatResponse
  - [parent_mediated_dataflow] The ChatApp function block is decomposed into six children: one for parsing and validation, four command-specific handlers (send, history, create_chan

### Patient/trial_00

- Old: has_routing=True
- New: hard_routing=False, parent_mediated=True, ambiguous=False
- Children: ParseAndValidateInput, RegisterPatient, CheckPatientExists, CheckDoctorAvailability, CreateAppointment, ValidateAppointmentTime, RetrieveMedicalRecords, ValidateUpdateFields, UpdatePatientProfile, FormatResponse
  - [parent_mediated_dataflow] The children cover all four commands (register, book, records, update) by splitting validation, existence checks, availability checks, time validation

### Patient/trial_01

- Old: has_routing=True
- New: hard_routing=False, parent_mediated=True, ambiguous=False
- Children: ParseAndValidateInput, RegisterPatient, CheckPatientExists, CheckDoctorAvailability, CreateAppointment, RetrieveMedicalRecords, ValidateInsuranceExternal, UpdatePatientProfile, FormatOutput
  - [parent_mediated_dataflow] The children cover all four commands (register, book, records, update) by separating concerns: input parsing, patient existence check, doctor availabi

### Patient/trial_02

- Old: has_routing=True
- New: hard_routing=False, parent_mediated=True, ambiguous=False
- Children: ParseAndValidateInput, RegisterPatient, CheckPatientExists, CheckDoctorAvailability, CreateAppointment, RetrieveMedicalRecords, ValidateInsuranceExternal, UpdatePatientProfile, FormatOutput
  - [parent_mediated_dataflow] The children cover the four commands (register, book, records, update) with shared validation and output formatting. ParseAndValidateInput handles ini

### BuildSystem/trial_00

- Old: has_routing=True
- New: hard_routing=False, parent_mediated=True, ambiguous=False
- Children: ParseAndValidateInput, CheckBuildConstraint, CreateBuildRecord, RunCompilation, RunTests, PackageArtifacts, QueryBuildStatus, ListBuilds, CancelBuild, FormatOutput
  - [parent_mediated_dataflow] The children cover all four actions (trigger, status, list, cancel) by separating concerns: input validation, constraint checking, build lifecycle ste

### BuildSystem/trial_02

- Old: has_routing=True
- New: hard_routing=False, parent_mediated=True, ambiguous=False
- Children: ParseAndValidateInput, CheckBuildConflict, CreateBuildRecord, RunCompileStep, RunTestStep, PackageArtifacts, QueryBuildStatus, ListBuilds, CancelBuild, FormatOutput
  - [parent_mediated_dataflow] The children cover all four actions (trigger, status, list, cancel) by separating input validation, conflict checking, build record creation, sequenti

### BuildSystem/trial_03

- Old: has_routing=True
- New: hard_routing=False, parent_mediated=True, ambiguous=False
- Children: ParseAndValidateInput, CheckBuildConflict, CreateBuildRecord, RunCompile, RunTests, PackageArtifacts, GetBuildStatus, ListBuilds, CancelBuild, FormatOutput
  - [parent_mediated_dataflow] The children cover all four actions (trigger, status, list, cancel) by separating validation, conflict checking, build creation, sequential build step

### BuildSystem/trial_04

- Old: has_routing=True
- New: hard_routing=False, parent_mediated=True, ambiguous=False
- Children: ParseAndValidateInput, CheckBuildConstraint, TriggerBuild, GetBuildStatus, ListBuilds, CancelBuild, FormatOutput
  - [parent_mediated_dataflow] The parent BuildSystem handles four distinct actions (trigger, status, list, cancel) with shared validation and constraint checking. The decomposition

## Remained Hard Routing

### Order/trial_03

- Children: ParseAndValidateInput, PlaceOrder, CancelOrder, TrackOrder, ValidateItemsAndStock, ChargePayment, ReserveInventory, CreateOrderRecord, VerifyOrderNotShipped, RefundPayment, RestoreInventory, UpdateOrderStatus
- Router nodes: []
- Hard routing calls: [{'from': 'PlaceOrder', 'to': 'ValidateItemsAndStock', 'note': 'Validate stock'}, {'from': 'PlaceOrder', 'to': 'ChargePayment', 'note': 'Charge payment'}, {'from': 'ChargePayment', 'to': 'PlaceOrder', 'note': 'Payment result'}, {'from': 'PlaceOrder', 'to': 'ReserveInventory', 'note': 'Reserve stock'}, {'from': 'PlaceOrder', 'to': 'CreateOrderRecord', 'note': 'Create order'}, {'from': 'CancelOrder', 'to': 'VerifyOrderNotShipped', 'note': 'Verify not shipped'}, {'from': 'CancelOrder', 'to': 'RefundPayment', 'note': 'Refund payment'}, {'from': 'CancelOrder', 'to': 'RestoreInventory', 'note': 'Restore stock'}, {'from': 'CancelOrder', 'to': 'UpdateOrderStatus', 'note': 'Update status'}]
  - [hard_routing] Edge: PlaceOrder -> ValidateItemsAndStock; note: Validate stock
  - [hard_routing] Edge: PlaceOrder -> ChargePayment; note: Charge payment
  - [hard_routing] Edge: ChargePayment -> PlaceOrder; note: Payment result

### Chat/trial_00

- Children: ParseAndValidateInput, RouteCommand, HandleSendMessage, HandleGetHistory, HandleCreateChannel, HandleJoinChannel, FormatOutput
- Router nodes: ['RouteCommand']
- Hard routing calls: [{'from': 'RouteCommand', 'to': 'HandleSendMessage', 'note': 'when command is send'}, {'from': 'RouteCommand', 'to': 'HandleGetHistory', 'note': 'when command is history'}, {'from': 'RouteCommand', 'to': 'HandleCreateChannel', 'note': 'when command is create_channel'}, {'from': 'RouteCommand', 'to': 'HandleJoinChannel', 'note': 'when command is join'}, {'from': 'RouteCommand', 'to': 'FormatOutput', 'note': 'final result to format'}]
  - [hard_routing] Edge: RouteCommand -> HandleSendMessage; note: when command is send
  - [hard_routing] Edge: RouteCommand -> HandleGetHistory; note: when command is history
  - [hard_routing] Edge: RouteCommand -> HandleCreateChannel; note: when command is create_channel

## Manual Check Cases

### Order/trial_01

- **hard_routing**: False
- **parent_mediated_dataflow**: True
- **ambiguous_direct_dataflow**: False
- **router_node**: False
- **abstraction_level_mixing**: False
- Children: ParseAndValidateInput, PlaceOrder, CancelOrder, TrackOrder
  - [parent_mediated_dataflow]  -> parent: The parent OrderSystem handles three distinct commands. ParseAndValidateInput handles input validation and routing logic (parent decides which child t

### Chat/trial_02

- **hard_routing**: False
- **parent_mediated_dataflow**: True
- **ambiguous_direct_dataflow**: False
- **router_node**: False
- **abstraction_level_mixing**: False
- Children: ParseAndValidateCommand, SendMessage, GetHistory, CreateChannel, JoinChannel, FormatResponse
  - [parent_mediated_dataflow]  -> parent: The parent ChatApp handles four distinct commands. Each command is decomposed into its own child function that performs the specific business logic. P

### BuildSystem/trial_00

- **hard_routing**: False
- **parent_mediated_dataflow**: True
- **ambiguous_direct_dataflow**: False
- **router_node**: False
- **abstraction_level_mixing**: False
- Children: ParseAndValidateInput, CheckBuildConstraint, CreateBuildRecord, RunCompilation, RunTests, PackageArtifacts, QueryBuildStatus, ListBuilds, CancelBuild, FormatOutput
  - [parent_mediated_dataflow]  -> parent: The children cover all four actions (trigger, status, list, cancel) by separating concerns: input validation, constraint checking, build lifecycle ste

### Chat/trial_00

- **hard_routing**: True
- **parent_mediated_dataflow**: True
- **ambiguous_direct_dataflow**: True
- **router_node**: True
- **abstraction_level_mixing**: False
- Children: ParseAndValidateInput, RouteCommand, HandleSendMessage, HandleGetHistory, HandleCreateChannel, HandleJoinChannel, FormatOutput
- Router nodes: ['RouteCommand']
- Hard routing calls: [{'from': 'RouteCommand', 'to': 'HandleSendMessage', 'note': 'when command is send'}, {'from': 'RouteCommand', 'to': 'HandleGetHistory', 'note': 'when command is history'}, {'from': 'RouteCommand', 'to': 'HandleCreateChannel', 'note': 'when command is create_channel'}, {'from': 'RouteCommand', 'to': 'HandleJoinChannel', 'note': 'when command is join'}, {'from': 'RouteCommand', 'to': 'FormatOutput', 'note': 'final result to format'}]
- Ambiguous calls: [{'from': 'ParseAndValidateInput', 'to': 'RouteCommand', 'note': 'validated command and data'}, {'from': 'HandleSendMessage', 'to': 'RouteCommand', 'note': 'result from send'}, {'from': 'HandleGetHistory', 'to': 'RouteCommand', 'note': 'result from history'}, {'from': 'HandleCreateChannel', 'to': 'RouteCommand', 'note': 'result from create_channel'}, {'from': 'HandleJoinChannel', 'to': 'RouteCommand', 'note': 'result from join'}]
  - [router_node] RouteCommand -> : Route the parsed command to the appropriate handler based on command type | Use conditional logic to select which child to call based on parsed_comman
  - [hard_routing] RouteCommand -> HandleSendMessage: Edge: RouteCommand -> HandleSendMessage; note: when command is send
  - [hard_routing] RouteCommand -> HandleGetHistory: Edge: RouteCommand -> HandleGetHistory; note: when command is history
  - [hard_routing] RouteCommand -> HandleCreateChannel: Edge: RouteCommand -> HandleCreateChannel; note: when command is create_channel
  - [hard_routing] RouteCommand -> HandleJoinChannel: Edge: RouteCommand -> HandleJoinChannel; note: when command is join

### Order/trial_03

- **hard_routing**: True
- **parent_mediated_dataflow**: True
- **ambiguous_direct_dataflow**: True
- **router_node**: False
- **abstraction_level_mixing**: True
- Children: ParseAndValidateInput, PlaceOrder, CancelOrder, TrackOrder, ValidateItemsAndStock, ChargePayment, ReserveInventory, CreateOrderRecord, VerifyOrderNotShipped, RefundPayment, RestoreInventory, UpdateOrderStatus
- Hard routing calls: [{'from': 'PlaceOrder', 'to': 'ValidateItemsAndStock', 'note': 'Validate stock'}, {'from': 'PlaceOrder', 'to': 'ChargePayment', 'note': 'Charge payment'}, {'from': 'ChargePayment', 'to': 'PlaceOrder', 'note': 'Payment result'}, {'from': 'PlaceOrder', 'to': 'ReserveInventory', 'note': 'Reserve stock'}, {'from': 'PlaceOrder', 'to': 'CreateOrderRecord', 'note': 'Create order'}, {'from': 'CancelOrder', 'to': 'VerifyOrderNotShipped', 'note': 'Verify not shipped'}, {'from': 'CancelOrder', 'to': 'RefundPayment', 'note': 'Refund payment'}, {'from': 'CancelOrder', 'to': 'RestoreInventory', 'note': 'Restore stock'}, {'from': 'CancelOrder', 'to': 'UpdateOrderStatus', 'note': 'Update status'}]
- Ambiguous calls: [{'from': 'ValidateItemsAndStock', 'to': 'PlaceOrder', 'note': 'Stock validation result'}, {'from': 'ReserveInventory', 'to': 'PlaceOrder', 'note': 'Reservation result'}, {'from': 'CreateOrderRecord', 'to': 'PlaceOrder', 'note': 'Order record'}, {'from': 'VerifyOrderNotShipped', 'to': 'CancelOrder', 'note': 'Verification result'}, {'from': 'RefundPayment', 'to': 'CancelOrder', 'note': 'Refund result'}, {'from': 'RestoreInventory', 'to': 'CancelOrder', 'note': 'Restore result'}, {'from': 'UpdateOrderStatus', 'to': 'CancelOrder', 'note': 'Update result'}]
  - [hard_routing] PlaceOrder -> ValidateItemsAndStock: Edge: PlaceOrder -> ValidateItemsAndStock; note: Validate stock
  - [hard_routing] PlaceOrder -> ChargePayment: Edge: PlaceOrder -> ChargePayment; note: Charge payment
  - [hard_routing] ChargePayment -> PlaceOrder: Edge: ChargePayment -> PlaceOrder; note: Payment result
  - [hard_routing] PlaceOrder -> ReserveInventory: Edge: PlaceOrder -> ReserveInventory; note: Reserve stock
  - [hard_routing] PlaceOrder -> CreateOrderRecord: Edge: PlaceOrder -> CreateOrderRecord; note: Create order

## Per-Domain Breakdown

| Domain | Trials | hard_routing | parent_mediated | ambiguous | naming_residue |
|--------|--------|-------------|-----------------|-----------|----------------|
| Order | 5 | 1/5 | 5/5 | 1/5 | 0/5 |
| Chat | 5 | 1/5 | 5/5 | 1/5 | 1/5 |
| Patient | 5 | 0/5 | 5/5 | 0/5 | 0/5 |
| BuildSystem | 5 | 0/5 | 5/5 | 1/5 | 0/5 |
| DataPipeline | 5 | 0/5 | 5/5 | 0/5 | 0/5 |
