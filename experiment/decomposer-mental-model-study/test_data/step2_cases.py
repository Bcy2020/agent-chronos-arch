"""
Step 2 (Codegen Verify) mental model test: 10 incorrect decompositions with code.

Each case provides everything needed to call code_generator._build_user_prompt_for_parent_verify():
  - node: parent Node with children and children_contracts populated
  - code: generated parent code (string)
  - expected_verdict: "ok" or "cannot_compose"
  - error_type: label for analysis
  - description: what's wrong

The 5 routing cases use disguised names (not just "ExecuteCommand").
The 5 non-routing cases cover other structural errors.

Usage:
    from test_data.step2_cases import get_cases
    cases = get_cases()
    for case in cases:
        node = case["node"]
        code = case["code"]
        # pass to code_generator._build_user_prompt_for_parent_verify(node, code)
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "mvp", "mvp-0.4.4"))

from models import (
    Node, InputParam, OutputParam, Boundary, GlobalVar, DataSource,
    ChildContract, DataOperation,
)


def _make_node(node_id, name, purpose, inputs, outputs, global_vars, data_sources=None):
    return Node(
        node_id=node_id,
        name=name,
        purpose=purpose,
        depth=0,
        inputs=[InputParam(**i) for i in inputs],
        outputs=[OutputParam(**o) for o in outputs],
        global_vars=[GlobalVar(**g) for g in global_vars],
        data_sources=[DataSource(**d) for d in (data_sources or [])],
        boundary=Boundary(),
    )


def _add_children(parent, children_defs):
    """Add children and contracts to a parent node."""
    for cd in children_defs:
        child = Node(
            node_id=f"{parent.node_id}_{cd['name']}",
            name=cd["name"],
            purpose=cd["purpose"],
            depth=1,
            parent_id=parent.node_id,
            inputs=[InputParam(**i) for i in cd.get("inputs", [])],
            outputs=[OutputParam(name="result", type="dict", description="Operation result")],
            global_vars=[],
        )
        parent.children.append(child)
        ops = []
        for op in cd.get("data_operations", []):
            ops.append(DataOperation(
                source_name=op["resource"],
                operation_type=op["op"],
                description=op.get("description", ""),
            ))
        parent.children_contracts[cd["name"]] = ChildContract(
            purpose=cd["purpose"],
            inputs=[InputParam(**i) for i in cd.get("inputs", [])],
            outputs=[OutputParam(name="result", type="dict", description="Operation result")],
            signature=cd["signature"],
            behavior=cd.get("behavior", ""),
            data_operations=ops,
        )


def _make_case(node, code, expected_verdict, error_type, description, tags=None):
    return {
        "node": node,
        "code": code,
        "expected_verdict": expected_verdict,
        "error_type": error_type,
        "description": description,
        "tags": tags or [],
    }


# =======================================================================
# ROUTING PATTERNS (5) — disguised names
# =======================================================================

# --- R1: RouteOrder (OrderSystem) ---
def _case_r1():
    parent = _make_node(
        "r1", "ProcessOrder",
        "Process an e-commerce order: parse input, route to appropriate handler, return result.",
        inputs=[{"name": "order_request", "type": "dict", "description": "Order JSON"}],
        outputs=[{"name": "order_result", "type": "dict", "description": "Result JSON"}],
        global_vars=[
            {"variable": "orders", "op": "read_write", "description": "Order records"},
            {"variable": "inventory", "op": "read_write", "description": "Stock data"},
            {"variable": "payments", "op": "read_write", "description": "Payment records"},
        ],
    )
    _add_children(parent, [
        {
            "name": "ParseOrder",
            "purpose": "Parse the order request JSON and extract action, items, payment_method, and address fields.",
            "signature": "def ParseOrder(order_request: dict) -> Tuple[str, dict]",
            "behavior": "Parses order_request, validates required fields exist, returns (action, order_data).",
            "inputs": [{"name": "order_request", "type": "dict", "description": "Raw order input"}],
        },
        {
            "name": "RouteOrder",
            "purpose": "Route the order to the appropriate handler based on action type and return the result.",
            "signature": "def RouteOrder(action: str, order_data: dict) -> dict",
            "behavior": "Based on action, calls the corresponding child handler (HandlePayment, UpdateStock, NotifyCustomer) with order_data and returns the result.",
            "inputs": [
                {"name": "action", "type": "str", "description": "Order action type"},
                {"name": "order_data", "type": "dict", "description": "Parsed order data"},
            ],
            "data_operations": [
                {"resource": "orders", "op": "read_write", "description": "Read/write order records"},
            ],
        },
        {
            "name": "HandlePayment",
            "purpose": "Process payment for the order: validate payment method, charge amount, record transaction.",
            "signature": "def HandlePayment(order_data: dict) -> dict",
            "behavior": "Validates payment method, creates payment record, returns payment result.",
            "inputs": [{"name": "order_data", "type": "dict", "description": "Order data with payment info"}],
            "data_operations": [
                {"resource": "payments", "op": "read_write", "description": "Create payment record"},
            ],
        },
        {
            "name": "UpdateStock",
            "purpose": "Update inventory stock levels: reserve items for the order.",
            "signature": "def UpdateStock(order_data: dict) -> dict",
            "behavior": "Checks stock availability, reserves items, returns reservation result.",
            "inputs": [{"name": "order_data", "type": "dict", "description": "Order data with items"}],
            "data_operations": [
                {"resource": "inventory", "op": "read_write", "description": "Reserve stock"},
            ],
        },
        {
            "name": "NotifyCustomer",
            "purpose": "Send order confirmation notification to the customer.",
            "signature": "def NotifyCustomer(order_data: dict, payment_result: dict) -> dict",
            "behavior": "Formats confirmation message, sends notification, returns delivery status.",
            "inputs": [
                {"name": "order_data", "type": "dict", "description": "Order data"},
                {"name": "payment_result", "type": "dict", "description": "Payment result"},
            ],
        },
    ])
    code = """def ProcessOrder(order_request: dict) -> dict:
    action, order_data = ParseOrder(order_request)
    result = RouteOrder(action, order_data)
    return result"""
    return _make_case(parent, code, "cannot_compose", "routing",
                      "RouteOrder acts as router: internally calls HandlePayment, UpdateStock, NotifyCustomer. "
                      "Parent only calls ParseOrder and RouteOrder.",
                      tags=["routing", "route_order"])


# --- R2: CoordinateDelivery (ChatApp) ---
def _case_r2():
    parent = _make_node(
        "r2", "HandleMessage",
        "Handle a chat message request: authenticate, deliver, and track.",
        inputs=[{"name": "message_request", "type": "dict", "description": "Message JSON"}],
        outputs=[{"name": "message_result", "type": "dict", "description": "Result JSON"}],
        global_vars=[
            {"variable": "messages", "op": "read_write", "description": "Message store"},
            {"variable": "users", "op": "read", "description": "User data"},
            {"variable": "channels", "op": "read_write", "description": "Channel data"},
        ],
    )
    _add_children(parent, [
        {
            "name": "Authenticate",
            "purpose": "Verify the user's identity and check they have access to the target channel.",
            "signature": "def Authenticate(message_request: dict) -> Tuple[bool, dict]",
            "behavior": "Validates user_id exists, checks user is member of target channel, returns (is_valid, user_context).",
            "inputs": [{"name": "message_request", "type": "dict", "description": "Request with user_id and channel_id"}],
        },
        {
            "name": "CoordinateDelivery",
            "purpose": "Coordinate the full message delivery: persist, notify, and update presence.",
            "signature": "def CoordinateDelivery(user_context: dict, content: str) -> dict",
            "behavior": "Based on user context, calls the corresponding child handler (PersistMessage, NotifyRecipient, UpdatePresence) with content and returns the delivery result.",
            "inputs": [
                {"name": "user_context", "type": "dict", "description": "Authenticated user context"},
                {"name": "content", "type": "str", "description": "Message content"},
            ],
            "data_operations": [
                {"resource": "messages", "op": "read_write", "description": "Store message"},
            ],
        },
        {
            "name": "PersistMessage",
            "purpose": "Store the message in the message database with timestamp and metadata.",
            "signature": "def PersistMessage(user_context: dict, content: str) -> dict",
            "behavior": "Creates message record with channel_id, user_id, content, timestamp. Returns message_id.",
            "inputs": [
                {"name": "user_context", "type": "dict", "description": "User context"},
                {"name": "content", "type": "str", "description": "Message content"},
            ],
            "data_operations": [
                {"resource": "messages", "op": "create", "description": "Create message record"},
            ],
        },
        {
            "name": "NotifyRecipient",
            "purpose": "Send a notification to the message recipient about the new message.",
            "signature": "def NotifyRecipient(channel_id: str, sender_name: str) -> dict",
            "behavior": "Looks up channel members, sends notification to each member except sender.",
            "inputs": [
                {"name": "channel_id", "type": "str", "description": "Target channel"},
                {"name": "sender_name", "type": "str", "description": "Sender's display name"},
            ],
        },
        {
            "name": "UpdatePresence",
            "purpose": "Update the user's last-seen timestamp and online status.",
            "signature": "def UpdatePresence(user_id: str) -> dict",
            "behavior": "Updates user's last_seen timestamp and sets status to 'online'.",
            "inputs": [{"name": "user_id", "type": "str", "description": "User ID"}],
            "data_operations": [
                {"resource": "users", "op": "update", "description": "Update presence"},
            ],
        },
    ])
    code = """def HandleMessage(message_request: dict) -> dict:
    is_valid, user_context = Authenticate(message_request)
    if not is_valid:
        return {"success": False, "message": "Authentication failed"}
    content = message_request.get("content", "")
    result = CoordinateDelivery(user_context, content)
    return result"""
    return _make_case(parent, code, "cannot_compose", "routing",
                      "CoordinateDelivery acts as router: internally calls PersistMessage, NotifyRecipient, UpdatePresence. "
                      "Parent only calls Authenticate and CoordinateDelivery.",
                      tags=["routing", "coordinate"])


# --- R3: RunPipeline (BuildSystem) ---
def _case_r3():
    parent = _make_node(
        "r3", "ExecuteBuild",
        "Execute a CI/CD build: load config, run the build pipeline, return result.",
        inputs=[{"name": "build_request", "type": "dict", "description": "Build request JSON"}],
        outputs=[{"name": "build_result", "type": "dict", "description": "Build result JSON"}],
        global_vars=[
            {"variable": "builds", "op": "read_write", "description": "Build records"},
            {"variable": "artifacts", "op": "read_write", "description": "Build artifacts"},
        ],
    )
    _add_children(parent, [
        {
            "name": "LoadConfig",
            "purpose": "Load and validate the build configuration from the request.",
            "signature": "def LoadConfig(build_request: dict) -> dict",
            "behavior": "Parses build_request, validates repo exists, loads config, returns build_config.",
            "inputs": [{"name": "build_request", "type": "dict", "description": "Raw build request"}],
        },
        {
            "name": "RunPipeline",
            "purpose": "Execute the full build pipeline from compilation through testing to packaging.",
            "signature": "def RunPipeline(build_config: dict) -> dict",
            "behavior": "Based on build config, calls the corresponding child handler (CompileCode, ExecuteTests, PackageOutput) with build_config and returns the pipeline result.",
            "inputs": [{"name": "build_config", "type": "dict", "description": "Build configuration"}],
            "data_operations": [
                {"resource": "builds", "op": "update", "description": "Update build status"},
            ],
        },
        {
            "name": "CompileCode",
            "purpose": "Compile the source code according to the build configuration.",
            "signature": "def CompileCode(build_config: dict) -> dict",
            "behavior": "Invokes compiler with source paths and flags from config, returns compilation result.",
            "inputs": [{"name": "build_config", "type": "dict", "description": "Build config with source paths"}],
        },
        {
            "name": "ExecuteTests",
            "purpose": "Run the test suite and collect results.",
            "signature": "def ExecuteTests(build_config: dict, compile_result: dict) -> dict",
            "behavior": "Runs test runner, collects pass/fail counts, returns test results.",
            "inputs": [
                {"name": "build_config", "type": "dict", "description": "Build config"},
                {"name": "compile_result", "type": "dict", "description": "Compilation output"},
            ],
        },
        {
            "name": "PackageOutput",
            "purpose": "Package build artifacts into distributable format.",
            "signature": "def PackageOutput(compile_result: dict, test_result: dict) -> dict",
            "behavior": "Creates artifact archive from compiled output, stores reference, returns artifact info.",
            "inputs": [
                {"name": "compile_result", "type": "dict", "description": "Compilation output"},
                {"name": "test_result", "type": "dict", "description": "Test results"},
            ],
            "data_operations": [
                {"resource": "artifacts", "op": "create", "description": "Store artifact"},
            ],
        },
    ])
    code = """def ExecuteBuild(build_request: dict) -> dict:
    build_config = LoadConfig(build_request)
    result = RunPipeline(build_config)
    return result"""
    return _make_case(parent, code, "cannot_compose", "routing",
                      "RunPipeline acts as router: internally calls CompileCode, ExecuteTests, PackageOutput. "
                      "Parent only calls LoadConfig and RunPipeline.",
                      tags=["routing", "pipeline"])


# --- R4: TransformDataset (DataPipeline) ---
def _case_r4():
    parent = _make_node(
        "r4", "ProcessData",
        "Process data through the ETL pipeline: read source, transform, and write output.",
        inputs=[{"name": "pipeline_request", "type": "dict", "description": "Pipeline request JSON"}],
        outputs=[{"name": "pipeline_result", "type": "dict", "description": "Pipeline result JSON"}],
        global_vars=[
            {"variable": "raw_data", "op": "read_write", "description": "Raw ingested data"},
            {"variable": "processed_data", "op": "read_write", "description": "Transformed data"},
            {"variable": "pipeline_log", "op": "read_write", "description": "Pipeline execution log"},
        ],
    )
    _add_children(parent, [
        {
            "name": "ReadSource",
            "purpose": "Read raw data from the configured source (CSV, JSON, or API).",
            "signature": "def ReadSource(pipeline_request: dict) -> list",
            "behavior": "Connects to source, reads records, stores in raw_data, returns record list.",
            "inputs": [{"name": "pipeline_request", "type": "dict", "description": "Request with source config"}],
            "data_operations": [
                {"resource": "raw_data", "op": "create", "description": "Store raw records"},
            ],
        },
        {
            "name": "TransformDataset",
            "purpose": "Apply all transformation, validation, and normalization steps to the dataset.",
            "signature": "def TransformDataset(raw_records: list, config: dict) -> list",
            "behavior": "Based on transform config, calls the corresponding child handler (ValidateRecords, NormalizeFields, WriteDestination) with raw_records and returns the processed records.",
            "inputs": [
                {"name": "raw_records", "type": "list", "description": "Raw data records"},
                {"name": "config", "type": "dict", "description": "Transformation config"},
            ],
            "data_operations": [
                {"resource": "processed_data", "op": "create", "description": "Store processed records"},
            ],
        },
        {
            "name": "ValidateRecords",
            "purpose": "Validate data records against quality rules and assign quality scores.",
            "signature": "def ValidateRecords(records: list, rules: list) -> Tuple[list, list]",
            "behavior": "Checks each record against quality rules, assigns quality_score, "
                        "separates valid and invalid records.",
            "inputs": [
                {"name": "records", "type": "list", "description": "Records to validate"},
                {"name": "rules", "type": "list", "description": "Quality rules"},
            ],
        },
        {
            "name": "NormalizeFields",
            "purpose": "Standardize field formats: dates to ISO, strings to lowercase, numbers to consistent precision.",
            "signature": "def NormalizeFields(records: list, field_rules: dict) -> list",
            "behavior": "Applies format normalization to each record according to field_rules.",
            "inputs": [
                {"name": "records", "type": "list", "description": "Records to normalize"},
                {"name": "field_rules", "type": "dict", "description": "Normalization rules per field"},
            ],
        },
        {
            "name": "WriteDestination",
            "purpose": "Write processed records to the output destination.",
            "signature": "def WriteDestination(records: list, format: str) -> dict",
            "behavior": "Formats records according to output format, writes to destination, returns write result.",
            "inputs": [
                {"name": "records", "type": "list", "description": "Records to write"},
                {"name": "format", "type": "str", "description": "Output format (csv/json)"},
            ],
            "data_operations": [
                {"resource": "processed_data", "op": "create", "description": "Write output"},
            ],
        },
    ])
    code = """def ProcessData(pipeline_request: dict) -> dict:
    raw_records = ReadSource(pipeline_request)
    config = pipeline_request.get("transform_config", {})
    result = TransformDataset(raw_records, config)
    return {"success": True, "records_processed": len(result)}"""
    return _make_case(parent, code, "cannot_compose", "routing",
                      "TransformDataset acts as router: internally calls ValidateRecords, NormalizeFields, WriteDestination. "
                      "Parent only calls ReadSource and TransformDataset.",
                      tags=["routing", "transform"])


# --- R5: DispatchRequest (PatientPortal) ---
def _case_r5():
    parent = _make_node(
        "r5", "HandlePatientRequest",
        "Handle a patient portal request: validate input, dispatch to handler, return result.",
        inputs=[{"name": "patient_request", "type": "dict", "description": "Patient request JSON"}],
        outputs=[{"name": "patient_result", "type": "dict", "description": "Result JSON"}],
        global_vars=[
            {"variable": "patients", "op": "read_write", "description": "Patient records"},
            {"variable": "appointments", "op": "read_write", "description": "Appointment records"},
            {"variable": "records", "op": "read_write", "description": "Medical records"},
        ],
    )
    _add_children(parent, [
        {
            "name": "ValidateRequest",
            "purpose": "Validate the patient request structure and required fields.",
            "signature": "def ValidateRequest(patient_request: dict) -> Tuple[bool, dict]",
            "behavior": "Checks required fields exist based on action type, returns (is_valid, validated_data).",
            "inputs": [{"name": "patient_request", "type": "dict", "description": "Raw request"}],
        },
        {
            "name": "DispatchRequest",
            "purpose": "Route the validated request to the appropriate handler based on action type.",
            "signature": "def DispatchRequest(validated_data: dict) -> dict",
            "behavior": "Based on action, calls the corresponding child handler (BookAppointment, FetchRecords, UpdateProfile) with validated_data and returns the result.",
            "inputs": [{"name": "validated_data", "type": "dict", "description": "Validated request data"}],
            "data_operations": [
                {"resource": "patients", "op": "read", "description": "Read patient data"},
            ],
        },
        {
            "name": "BookAppointment",
            "purpose": "Book a medical appointment: check doctor availability, create appointment record.",
            "signature": "def BookAppointment(validated_data: dict) -> dict",
            "behavior": "Checks patient exists, checks doctor slot available, creates appointment.",
            "inputs": [{"name": "validated_data", "type": "dict", "description": "Booking data"}],
            "data_operations": [
                {"resource": "appointments", "op": "create", "description": "Create appointment"},
            ],
        },
        {
            "name": "FetchRecords",
            "purpose": "Retrieve medical records for a patient, sorted by date.",
            "signature": "def FetchRecords(patient_id: str) -> dict",
            "behavior": "Looks up all records for patient_id, sorts by timestamp descending.",
            "inputs": [{"name": "patient_id", "type": "str", "description": "Patient ID"}],
            "data_operations": [
                {"resource": "records", "op": "list", "description": "List patient records"},
            ],
        },
        {
            "name": "UpdateProfile",
            "purpose": "Update patient profile information: validate insurance, save changes.",
            "signature": "def UpdateProfile(patient_id: str, updates: dict) -> dict",
            "behavior": "Validates insurance if changed, updates patient record fields.",
            "inputs": [
                {"name": "patient_id", "type": "str", "description": "Patient ID"},
                {"name": "updates", "type": "dict", "description": "Fields to update"},
            ],
            "data_operations": [
                {"resource": "patients", "op": "update", "description": "Update patient record"},
            ],
        },
    ])
    code = """def HandlePatientRequest(patient_request: dict) -> dict:
    is_valid, validated_data = ValidateRequest(patient_request)
    if not is_valid:
        return {"success": False, "message": "Invalid request"}
    result = DispatchRequest(validated_data)
    return result"""
    return _make_case(parent, code, "cannot_compose", "routing",
                      "DispatchRequest acts as router: internally calls BookAppointment, FetchRecords, UpdateProfile. "
                      "Parent only calls ValidateRequest and DispatchRequest.",
                      tags=["routing", "dispatch"])


# =======================================================================
# NON-ROUTING PATTERNS (5)
# =======================================================================

# --- N6: Overlapping Responsibilities (InventoryManager) ---
def _case_n6():
    parent = _make_node(
        "n6", "ManageInventory",
        "Manage warehouse inventory operations: check stock, reconcile, and update quantities.",
        inputs=[{"name": "inventory_request", "type": "dict", "description": "Inventory request JSON"}],
        outputs=[{"name": "inventory_result", "type": "dict", "description": "Result JSON"}],
        global_vars=[
            {"variable": "stock", "op": "read_write", "description": "Stock levels"},
            {"variable": "suppliers", "op": "read", "description": "Supplier data"},
        ],
    )
    _add_children(parent, [
        {
            "name": "CheckStock",
            "purpose": "Check current stock levels for specified products.",
            "signature": "def CheckStock(product_ids: list) -> dict",
            "behavior": "Reads stock records for each product_id, returns quantities and availability status.",
            "inputs": [{"name": "product_ids", "type": "list", "description": "Products to check"}],
            "data_operations": [
                {"resource": "stock", "op": "read", "description": "Read stock levels"},
            ],
        },
        {
            "name": "ReconcileWarehouse",
            "purpose": "Reconcile warehouse stock by comparing system records with physical count.",
            "signature": "def ReconcileWarehouse(physical_counts: dict) -> dict",
            "behavior": "Reads stock records, compares with physical_counts, identifies discrepancies, "
                        "updates stock to match physical count, returns reconciliation report.",
            "inputs": [{"name": "physical_counts", "type": "dict", "description": "Physical inventory counts"}],
            "data_operations": [
                {"resource": "stock", "op": "read", "description": "Read current stock"},
                {"resource": "stock", "op": "update", "description": "Adjust stock to physical count"},
            ],
        },
        {
            "name": "UpdateQuantity",
            "purpose": "Update stock quantity for a specific product.",
            "signature": "def UpdateQuantity(product_id: str, quantity_change: int) -> dict",
            "behavior": "Adjusts stock quantity by quantity_change, validates non-negative result.",
            "inputs": [
                {"name": "product_id", "type": "str", "description": "Product to update"},
                {"name": "quantity_change", "type": "int", "description": "Change amount"},
            ],
            "data_operations": [
                {"resource": "stock", "op": "update", "description": "Update stock level"},
            ],
        },
        {
            "name": "ReconcileInventory",
            "purpose": "Reconcile inventory records by comparing system stock with physical warehouse counts.",
            "signature": "def ReconcileInventory(warehouse_counts: dict) -> dict",
            "behavior": "Reads all stock records, compares with warehouse_counts dict, "
                        "identifies mismatches, adjusts stock records to match, returns discrepancy report.",
            "inputs": [{"name": "warehouse_counts", "type": "dict", "description": "Physical warehouse counts"}],
            "data_operations": [
                {"resource": "stock", "op": "read", "description": "Read current stock"},
                {"resource": "stock", "op": "update", "description": "Correct stock levels"},
            ],
        },
    ])
    code = """def ManageInventory(inventory_request: dict) -> dict:
    action = inventory_request.get("action")
    if action == "check":
        return CheckStock(inventory_request.get("product_ids", []))
    elif action == "reconcile_warehouse":
        return ReconcileWarehouse(inventory_request.get("physical_counts", {}))
    elif action == "update":
        return UpdateQuantity(inventory_request["product_id"], inventory_request["quantity_change"])
    elif action == "reconcile_inventory":
        return ReconcileInventory(inventory_request.get("warehouse_counts", {}))
    return {"success": False, "message": "Unknown action"}"""
    return _make_case(parent, code, "cannot_compose", "overlapping_responsibilities",
                      "ReconcileWarehouse and ReconcileInventory have identical purposes: "
                      "both read stock, compare with physical counts, and update stock to match. "
                      "They are the same function with different names.",
                      tags=["overlap", "duplicate"])


# --- N7: God Node (TaskPlanner) ---
def _case_n7():
    parent = _make_node(
        "n7", "HandleTask",
        "Handle a task management request: parse input and process the task.",
        inputs=[{"name": "task_request", "type": "dict", "description": "Task request JSON"}],
        outputs=[{"name": "task_result", "type": "dict", "description": "Result JSON"}],
        global_vars=[
            {"variable": "tasks", "op": "read_write", "description": "Task records"},
            {"variable": "projects", "op": "read_write", "description": "Project records"},
            {"variable": "assignments", "op": "read_write", "description": "Assignment records"},
        ],
    )
    _add_children(parent, [
        {
            "name": "ParseRequest",
            "purpose": "Parse the task request and extract action and data fields.",
            "signature": "def ParseRequest(task_request: dict) -> Tuple[str, dict]",
            "behavior": "Validates request structure, extracts action and task_data.",
            "inputs": [{"name": "task_request", "type": "dict", "description": "Raw request"}],
        },
        {
            "name": "ProcessEntireTask",
            "purpose": "Handle all task operations: validate input, check project exists, create or update task, "
                       "assign to team member, send notification to assignee, update project progress, "
                       "and return the operation result.",
            "signature": "def ProcessEntireTask(action: str, task_data: dict) -> dict",
            "behavior": "Complete task lifecycle handler: validates data, checks project membership, "
                        "creates/updates task record, manages assignment, sends notification, "
                        "recalculates project completion percentage.",
            "inputs": [
                {"name": "action", "type": "str", "description": "Action type"},
                {"name": "task_data", "type": "dict", "description": "Task data"},
            ],
            "data_operations": [
                {"resource": "tasks", "op": "read_write", "description": "Full task CRUD"},
                {"resource": "projects", "op": "read_write", "description": "Update project progress"},
                {"resource": "assignments", "op": "read_write", "description": "Manage assignments"},
            ],
        },
    ])
    code = """def HandleTask(task_request: dict) -> dict:
    action, task_data = ParseRequest(task_request)
    result = ProcessEntireTask(action, task_data)
    return result"""
    return _make_case(parent, code, "cannot_compose", "god_node",
                      "ProcessEntireTask is a god node: it handles validation, assignment, notification, "
                      "and status update all in one function. Its purpose spans 4+ distinct responsibilities. "
                      "Should be decomposed into ValidateTask, ManageAssignment, NotifyAssignee, UpdateProgress.",
                      tags=["god_node", "too_many_responsibilities"])


# --- N8: Missing Child (SocialFeed) ---
def _case_n8():
    parent = _make_node(
        "n8", "GenerateFeed",
        "Generate a personalized social media feed for a user.",
        inputs=[{"name": "feed_request", "type": "dict", "description": "Feed request with user_id"}],
        outputs=[{"name": "feed_result", "type": "dict",
                  "description": "JSON with success, feed_items (list of {post_id, author, content, likes_count, timestamp}), message"}],
        global_vars=[
            {"variable": "posts", "op": "read_write", "description": "Post records"},
            {"variable": "users", "op": "read", "description": "User data"},
            {"variable": "feed_cache", "op": "read_write", "description": "Feed cache"},
        ],
    )
    _add_children(parent, [
        {
            "name": "FetchPosts",
            "purpose": "Fetch recent posts from users that the current user follows.",
            "signature": "def FetchPosts(user_id: str) -> list",
            "behavior": "Gets following list, retrieves their posts, returns raw post list.",
            "inputs": [{"name": "user_id", "type": "str", "description": "Current user"}],
            "data_operations": [
                {"resource": "posts", "op": "list", "description": "List posts"},
                {"resource": "users", "op": "read", "description": "Get following list"},
            ],
        },
        {
            "name": "RankContent",
            "purpose": "Rank posts by relevance: recency, engagement (likes), and user relationship strength.",
            "signature": "def RankContent(posts: list, user_id: str) -> list",
            "behavior": "Scores each post by recency and engagement, sorts descending by score.",
            "inputs": [
                {"name": "posts", "type": "list", "description": "Raw posts"},
                {"name": "user_id", "type": "str", "description": "User for personalization"},
            ],
        },
        {
            "name": "FilterDuplicates",
            "purpose": "Remove duplicate posts and posts the user has already seen.",
            "signature": "def FilterDuplicates(ranked_posts: list, seen_ids: list) -> list",
            "behavior": "Deduplicates by post_id, removes posts in seen_ids list.",
            "inputs": [
                {"name": "ranked_posts", "type": "list", "description": "Ranked posts"},
                {"name": "seen_ids", "type": "list", "description": "Already-seen post IDs"},
            ],
        },
    ])
    code = """def GenerateFeed(feed_request: dict) -> dict:
    user_id = feed_request.get("user_id", "")
    posts = FetchPosts(user_id)
    ranked = RankContent(posts, user_id)
    filtered = FilterDuplicates(ranked, [])
    return {"success": True, "feed_items": filtered, "message": "Feed generated"}"""
    return _make_case(parent, code, "cannot_compose", "missing_child",
                      "Parent output requires feed_items with {post_id, author, content, likes_count, timestamp}, "
                      "but no child formats the data. FetchPosts returns raw posts, RankContent and FilterDuplicates "
                      "only sort/filter. A FormatFeed child is needed to transform raw posts into the output schema.",
                      tags=["missing_child", "formatting_gap"])


# --- N9: Wrong Abstraction Level (DataPipeline) ---
def _case_n9():
    parent = _make_node(
        "n9", "MigrateData",
        "Migrate data from legacy system to new system: validate schema, transfer records, verify integrity.",
        inputs=[{"name": "migration_request", "type": "dict", "description": "Migration config with source and target"}],
        outputs=[{"name": "migration_result", "type": "dict", "description": "Result with records_migrated count and errors"}],
        global_vars=[
            {"variable": "source_db", "op": "read", "description": "Legacy database connection"},
            {"variable": "target_db", "op": "read_write", "description": "New database connection"},
            {"variable": "migration_log", "op": "read_write", "description": "Migration audit log"},
        ],
    )
    _add_children(parent, [
        {
            "name": "ValidateSchema",
            "purpose": "Validate that source and target schemas are compatible for migration.",
            "signature": "def ValidateSchema(migration_request: dict) -> dict",
            "behavior": "Compares source and target table schemas, identifies mapping issues.",
            "inputs": [{"name": "migration_request", "type": "dict", "description": "Migration config"}],
        },
        {
            "name": "OpenConnection",
            "purpose": "Establish database connections to both source and target systems.",
            "signature": "def OpenConnection(source_config: dict, target_config: dict) -> Tuple[Any, Any]",
            "behavior": "Creates JDBC/ODBC connections to source and target databases, returns connection handles.",
            "inputs": [
                {"name": "source_config", "type": "dict", "description": "Source DB config"},
                {"name": "target_config", "type": "dict", "description": "Target DB config"},
            ],
        },
        {
            "name": "CopyRows",
            "purpose": "Copy all rows from source table to target table with schema mapping.",
            "signature": "def CopyRows(source_conn: Any, target_conn: Any, mapping: dict) -> dict",
            "behavior": "Reads rows from source, applies field mapping, inserts into target, returns count.",
            "inputs": [
                {"name": "source_conn", "type": "Any", "description": "Source connection"},
                {"name": "target_conn", "type": "Any", "description": "Target connection"},
                {"name": "mapping", "type": "dict", "description": "Field mapping"},
            ],
            "data_operations": [
                {"resource": "target_db", "op": "create", "description": "Insert migrated rows"},
            ],
        },
        {
            "name": "CloseConnection",
            "purpose": "Close database connections and release resources.",
            "signature": "def CloseConnection(source_conn: Any, target_conn: Any) -> dict",
            "behavior": "Closes both connections, releases connection pool resources.",
            "inputs": [
                {"name": "source_conn", "type": "Any", "description": "Source connection"},
                {"name": "target_conn", "type": "Any", "description": "Target connection"},
            ],
        },
    ])
    code = """def MigrateData(migration_request: dict) -> dict:
    schema_result = ValidateSchema(migration_request)
    source_conn, target_conn = OpenConnection(migration_request["source"], migration_request["target"])
    copy_result = CopyRows(source_conn, target_conn, schema_result.get("mapping", {}))
    CloseConnection(source_conn, target_conn)
    return {"success": True, "records_migrated": copy_result.get("count", 0)}"""
    return _make_case(parent, code, "cannot_compose", "wrong_abstraction",
                      "OpenConnection and CloseConnection are infrastructure details (connection lifecycle), "
                      "not business-level decomposition children. They should be internal implementation details "
                      "of the data access layer, not peers of ValidateSchema and CopyRows in the decomposition tree.",
                      tags=["abstraction_level", "infrastructure"])


# --- N10: Data Flow Dependency (NotificationHub) ---
def _case_n10():
    parent = _make_node(
        "n10", "SendNotification",
        "Send a notification: format message, get recipient info, select delivery channel, deliver.",
        inputs=[{"name": "notification_request", "type": "dict", "description": "Notification request JSON"}],
        outputs=[{"name": "notification_result", "type": "dict", "description": "Result JSON"}],
        global_vars=[
            {"variable": "notification_queue", "op": "read_write", "description": "Notification queue"},
            {"variable": "templates", "op": "read", "description": "Message templates"},
            {"variable": "delivery_log", "op": "read_write", "description": "Delivery log"},
        ],
    )
    _add_children(parent, [
        {
            "name": "FormatMessage",
            "purpose": "Format the notification message using template and variables. "
                       "Requires channel type to select the correct template format.",
            "signature": "def FormatMessage(content: dict, channel: str) -> str",
            "behavior": "Looks up template for the channel type, substitutes variables, returns formatted message. "
                        "Different channels have different format requirements (email=HTML, SMS=plain text, push=JSON).",
            "inputs": [
                {"name": "content", "type": "dict", "description": "Content with template_id and variables"},
                {"name": "channel", "type": "str", "description": "Delivery channel (email/sms/push)"},
            ],
        },
        {
            "name": "GetRecipientInfo",
            "purpose": "Look up recipient contact information and notification preferences.",
            "signature": "def GetRecipientInfo(recipient_id: str) -> dict",
            "behavior": "Fetches recipient record, returns {email, phone, push_token, preferred_channel}.",
            "inputs": [{"name": "recipient_id", "type": "str", "description": "Recipient ID"}],
        },
        {
            "name": "SelectChannel",
            "purpose": "Select the best delivery channel based on recipient preferences and message type. "
                       "Requires recipient_info to determine available channels.",
            "signature": "def SelectChannel(recipient_info: dict, message_type: str) -> str",
            "behavior": "Checks recipient's preferred_channel, verifies channel is available "
                        "(e.g., has phone for SMS, has push_token for push), returns selected channel.",
            "inputs": [
                {"name": "recipient_info", "type": "dict", "description": "Recipient contact info"},
                {"name": "message_type", "type": "str", "description": "Type of notification"},
            ],
        },
        {
            "name": "DeliverMessage",
            "purpose": "Deliver the formatted message via the selected channel.",
            "signature": "def DeliverMessage(formatted_message: str, channel: str, recipient_info: dict) -> dict",
            "behavior": "Sends message through the appropriate channel API, logs delivery attempt.",
            "inputs": [
                {"name": "formatted_message", "type": "str", "description": "Formatted message"},
                {"name": "channel", "type": "str", "description": "Delivery channel"},
                {"name": "recipient_info", "type": "dict", "description": "Recipient contact info"},
            ],
            "data_operations": [
                {"resource": "delivery_log", "op": "create", "description": "Log delivery attempt"},
            ],
        },
    ])
    code = """def SendNotification(notification_request: dict) -> dict:
    content = notification_request.get("content", {})
    recipient_id = notification_request.get("recipient", "")
    message_type = notification_request.get("type", "general")

    formatted = FormatMessage(content, "email")
    recipient_info = GetRecipientInfo(recipient_id)
    channel = SelectChannel(recipient_info, message_type)
    result = DeliverMessage(formatted, channel, recipient_info)
    return result"""
    return _make_case(parent, code, "cannot_compose", "data_flow",
                      "Data flow contradiction: FormatMessage requires channel parameter, "
                      "but SelectChannel (which determines the channel) requires recipient_info "
                      "from GetRecipientInfo. The code calls FormatMessage before SelectChannel, "
                      "hardcoding 'email' as channel. The correct flow should be: "
                      "GetRecipientInfo -> SelectChannel -> FormatMessage -> DeliverMessage.",
                      tags=["data_flow", "ordering_dependency"])


# -----------------------------------------------------------------------
# Collection
# -----------------------------------------------------------------------
ALL_CASES = [
    _case_r1(),
    _case_r2(),
    _case_r3(),
    _case_r4(),
    _case_r5(),
    _case_n6(),
    _case_n7(),
    _case_n8(),
    _case_n9(),
    _case_n10(),
]


def get_cases():
    """Return all Step 2 test cases."""
    return ALL_CASES


def get_case(index: int):
    """Get a single case by index (0-based)."""
    return ALL_CASES[index]


def get_routing_cases():
    """Return only routing pattern cases."""
    return [c for c in ALL_CASES if c["error_type"] == "routing"]


def get_non_routing_cases():
    """Return only non-routing pattern cases."""
    return [c for c in ALL_CASES if c["error_type"] != "routing"]
