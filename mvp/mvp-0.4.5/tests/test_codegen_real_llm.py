"""
Real LLM test: CodeGenerator composition validation.

Tests the CodeGenerator's ability to correctly:
  - Accept correct decompositions (status: "ok" + valid code)
  - Reject incorrect decompositions (status: "cannot_compose" + diagnostic feedback)

Uses the real APIClient (DeepSeek API with JSON mode).
Saves all raw prompts, LLM responses, and structured results to output/

Design: 10 test cases
  4 correct (C1-C4): parent can compose children -> expect code
  6 wrong   (W1-W6): parent cannot compose children -> expect CANNOT_COMPOSE
"""
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from api_client import APIClient
from code_generator import CodeGenerator
from models import (
    Node, InputParam, OutputParam, Boundary, ChildContract,
    DataSource, GlobalVar, DataOperation
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "test_codegen_real_llm")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def make_signature(name, inputs, outputs):
    """Build a function signature string from inputs and outputs."""
    params = ", ".join(f"{i['name']}: {i['type']}" for i in inputs)
    if len(outputs) == 0:
        return f"def {name}({params}) -> None:"
    elif len(outputs) == 1:
        return f"def {name}({params}) -> {outputs[0]['type']}:"
    else:
        ret_types = ", ".join(o["type"] for o in outputs)
        return f"def {name}({params}) -> Tuple[{ret_types}]:"


def make_parent(name, purpose, inputs, outputs, children_data,
                global_vars=None, data_sources=None):
    """Create a parent Node with children and contracts for testing."""
    children = []
    children_contracts = {}

    for i, cd in enumerate(children_data):
        child_inputs = [InputParam(**ip) for ip in cd.get("inputs", [])]
        child_outputs = [OutputParam(**op) for op in cd.get("outputs", [])]

        child_node = Node(
            node_id=f"child_{i}",
            name=cd["name"],
            depth=2,
            parent_id="parent",
            purpose=cd.get("purpose", ""),
            inputs=child_inputs,
            outputs=child_outputs,
            stop_decompose=True,
            stop_reason="test leaf",
        )
        children.append(child_node)

        sig = cd.get("signature") or make_signature(cd["name"], cd.get("inputs", []), cd.get("outputs", []))
        contract = ChildContract(
            purpose=cd.get("purpose", ""),
            behavior=cd.get("behavior", ""),
            inputs=child_inputs,
            outputs=child_outputs,
            signature=sig,
            data_operations=[DataOperation(**dop) for dop in cd.get("data_operations", [])],
        )
        children_contracts[cd["name"]] = contract

    node = Node(
        node_id="parent",
        name=name,
        depth=1,
        purpose=purpose,
        inputs=[InputParam(**ip) for ip in inputs],
        outputs=[OutputParam(**op) for op in outputs],
        boundary=Boundary(in_scope=[], out_of_scope=[]),
        children=children,
        children_contracts=children_contracts,
        global_vars=[GlobalVar(**gv) for gv in (global_vars or [])],
        data_sources=[DataSource(**ds) for ds in (data_sources or [])],
    )
    return node


def capture_prompt(cg, node):
    """Build the messages that would be sent to the LLM and return them."""
    messages = [
        {"role": "system", "content": cg._build_system_prompt_for_parent()},
        {"role": "user", "content": cg._build_user_prompt_for_parent(node)}
    ]
    return messages


# =========================================================================
# TEST CASE DEFINITIONS
# =========================================================================

TEST_CASES = []

# ----- C1: Simple sequential pipeline -----
TEST_CASES.append({
    "id": "C1",
    "type": "correct",
    "description": "Simple sequential pipeline: ConvertCurrency -> ChargePayment -> SendConfirmation",
    "expect": "ok",
    "make_node": lambda: make_parent(
        name="ProcessPayment",
        purpose="Process a payment by converting currency, charging, and sending confirmation.",
        inputs=[
            {"name": "amount", "type": "float", "description": "Payment amount"},
            {"name": "currency", "type": "str", "description": "Currency code (e.g., USD, EUR, JPY)"},
        ],
        outputs=[
            {"name": "result", "type": "dict", "description": "Charge result with confirmation status"},
        ],
        children_data=[
            {
                "name": "ConvertCurrency",
                "purpose": "Convert amount from given currency to USD",
                "inputs": [{"name": "amount", "type": "float", "description": "Amount in source currency"},
                           {"name": "currency", "type": "str", "description": "Source currency code"}],
                "outputs": [{"name": "amount_usd", "type": "float", "description": "Converted amount in USD"}],
                "behavior": "Looks up exchange rate and converts the amount to USD",
                "signature": "def ConvertCurrency(amount: float, currency: str) -> float:",
            },
            {
                "name": "ChargePayment",
                "purpose": "Charge the given USD amount via payment gateway",
                "inputs": [{"name": "amount_usd", "type": "float", "description": "Amount to charge in USD"}],
                "outputs": [{"name": "charge_result", "type": "dict", "description": "Payment gateway response"}],
                "behavior": "Sends charge request to payment gateway and returns result",
                "signature": "def ChargePayment(amount_usd: float) -> dict:",
            },
            {
                "name": "SendConfirmation",
                "purpose": "Send payment confirmation notification",
                "inputs": [{"name": "charge_result", "type": "dict", "description": "Payment gateway response"}],
                "outputs": [{"name": "success", "type": "bool", "description": "Whether confirmation was sent"}],
                "behavior": "Sends email/push notification about the payment result",
                "signature": "def SendConfirmation(charge_result: dict) -> bool:",
            },
        ],
    ),
})

# ----- C2: Conditional branching -----
TEST_CASES.append({
    "id": "C2",
    "type": "correct",
    "description": "Conditional branching: GetOrder -> if valid -> CalculateRefund -> RefundToWallet -> NotifyUser",
    "expect": "ok",
    "make_node": lambda: make_parent(
        name="RefundOrder",
        purpose="Process a refund: validate order, calculate refund, refund to wallet, notify user.",
        inputs=[
            {"name": "order_id", "type": "int", "description": "ID of the order to refund"},
            {"name": "reason", "type": "str", "description": "Reason for the refund"},
        ],
        outputs=[
            {"name": "result", "type": "dict", "description": "Refund processing result"},
        ],
        children_data=[
            {
                "name": "GetOrder",
                "purpose": "Retrieve order details by order_id",
                "inputs": [{"name": "order_id", "type": "int", "description": "Order ID to look up"}],
                "outputs": [{"name": "order", "type": "dict", "description": "Order details"}],
                "behavior": "Looks up the order from the orders data store",
                "signature": "def GetOrder(order_id: int) -> dict:",
            },
            {
                "name": "CalculateRefund",
                "purpose": "Calculate the refund amount based on order and reason",
                "inputs": [{"name": "order", "type": "dict", "description": "Order details"},
                           {"name": "reason", "type": "str", "description": "Refund reason"}],
                "outputs": [{"name": "refund_amount", "type": "float", "description": "Calculated refund amount"}],
                "behavior": "Determines refund amount based on order total, items returned, and reason",
                "signature": "def CalculateRefund(order: dict, reason: str) -> float:",
            },
            {
                "name": "RefundToWallet",
                "purpose": "Credit the refund amount to user's wallet",
                "inputs": [{"name": "user_id", "type": "int", "description": "User to refund"},
                           {"name": "amount", "type": "float", "description": "Amount to credit"}],
                "outputs": [{"name": "refund_result", "type": "dict", "description": "Wallet credit result"}],
                "behavior": "Increments user's wallet balance by the refund amount",
                "signature": "def RefundToWallet(user_id: int, amount: float) -> dict:",
            },
            {
                "name": "NotifyUser",
                "purpose": "Send refund notification to the user",
                "inputs": [{"name": "user_id", "type": "int", "description": "User to notify"},
                           {"name": "message", "type": "str", "description": "Notification message"}],
                "outputs": [{"name": "notified", "type": "bool", "description": "Whether notification was sent"}],
                "behavior": "Sends email or push notification about the refund status",
                "signature": "def NotifyUser(user_id: int, message: str) -> bool:",
            },
        ],
    ),
})

# ----- C3: Loop with aggregation -----
TEST_CASES.append({
    "id": "C3",
    "type": "correct",
    "description": "Loop with aggregation: FetchAllProducts -> CategorizeProducts + FindLowStockItems",
    "expect": "ok",
    "make_node": lambda: make_parent(
        name="GenerateInventoryReport",
        purpose="Generate an inventory report: fetch all products, categorize them, find low stock items.",
        inputs=[
            {"name": "warehouse_id", "type": "int", "description": "Warehouse ID to report on"},
        ],
        outputs=[
            {"name": "report", "type": "dict", "description": "Inventory report with categories and low stock alerts"},
        ],
        children_data=[
            {
                "name": "FetchAllProducts",
                "purpose": "Retrieve all products in the warehouse",
                "inputs": [{"name": "warehouse_id", "type": "int", "description": "Warehouse ID"}],
                "outputs": [{"name": "products", "type": "list", "description": "List of all product dicts"}],
                "behavior": "Queries the warehouse inventory for all products",
                "signature": "def FetchAllProducts(warehouse_id: int) -> list:",
            },
            {
                "name": "CategorizeProducts",
                "purpose": "Group products by category",
                "inputs": [{"name": "products", "type": "list", "description": "Full product list"}],
                "outputs": [{"name": "categories", "type": "dict", "description": "Dict mapping category to product list"}],
                "behavior": "Iterates products and groups them by their category field",
                "signature": "def CategorizeProducts(products: list) -> dict:",
            },
            {
                "name": "FindLowStockItems",
                "purpose": "Find products with stock below threshold",
                "inputs": [{"name": "products", "type": "list", "description": "Full product list"}],
                "outputs": [{"name": "low_stock", "type": "list", "description": "Products with insufficient stock"}],
                "behavior": "Filters products where stock < min_stock_threshold",
                "signature": "def FindLowStockItems(products: list) -> list:",
            },
        ],
    ),
})

# ----- C4: Fan-out fan-in -----
TEST_CASES.append({
    "id": "C4",
    "type": "correct",
    "description": "Fan-out fan-in: CreateAccount + AssignDepartment + SetupEmail -> GenerateSummary",
    "expect": "ok",
    "make_node": lambda: make_parent(
        name="OnboardEmployee",
        purpose="Onboard a new employee: create account, assign department, setup email, generate summary.",
        inputs=[
            {"name": "employee", "type": "dict", "description": "Employee information dict"},
        ],
        outputs=[
            {"name": "summary", "type": "dict", "description": "Onboarding summary with all created resources"},
        ],
        children_data=[
            {
                "name": "CreateAccount",
                "purpose": "Create user account for the employee",
                "inputs": [{"name": "employee", "type": "dict", "description": "Employee info"}],
                "outputs": [{"name": "account", "type": "dict", "description": "Created account details"}],
                "behavior": "Creates a new user account in the system",
                "signature": "def CreateAccount(employee: dict) -> dict:",
            },
            {
                "name": "AssignDepartment",
                "purpose": "Assign employee to a department",
                "inputs": [{"name": "employee", "type": "dict", "description": "Employee info"}],
                "outputs": [{"name": "department", "type": "str", "description": "Assigned department name"}],
                "behavior": "Determines and assigns the appropriate department",
                "signature": "def AssignDepartment(employee: dict) -> str:",
            },
            {
                "name": "SetupEmail",
                "purpose": "Setup corporate email for the employee",
                "inputs": [{"name": "employee", "type": "dict", "description": "Employee info"}],
                "outputs": [{"name": "email", "type": "str", "description": "New email address"}],
                "behavior": "Creates email account and returns the address",
                "signature": "def SetupEmail(employee: dict) -> str:",
            },
            {
                "name": "GenerateSummary",
                "purpose": "Generate onboarding summary from all created resources",
                "inputs": [{"name": "account", "type": "dict", "description": "Created account"},
                           {"name": "department", "type": "str", "description": "Assigned department"},
                           {"name": "email", "type": "str", "description": "Created email address"}],
                "outputs": [{"name": "summary", "type": "dict", "description": "Complete onboarding summary"}],
                "behavior": "Assembles all onboarding results into a summary dict",
                "signature": "def GenerateSummary(account: dict, department: str, email: str) -> dict:",
            },
        ],
    ),
})

# =========================================================================
# WRONG DECOMPOSITIONS
# =========================================================================

# ----- W1: Missing data producer (clear) -----
TEST_CASES.append({
    "id": "W1",
    "type": "wrong",
    "description": "Missing data producer: total_price parameter has no source child",
    "expect": "cannot_compose",
    "make_node": lambda: make_parent(
        name="CreateOrder",
        purpose="Create an order: validate user, then save order. total_price is needed but no child computes it.",
        inputs=[
            {"name": "user_id", "type": "int", "description": "ID of the user creating the order"},
            {"name": "items", "type": "list", "description": "List of items with product_id and quantity"},
        ],
        outputs=[
            {"name": "order", "type": "dict", "description": "Created order record"},
        ],
        children_data=[
            {
                "name": "ValidateUser",
                "purpose": "Check if the user exists",
                "inputs": [{"name": "user_id", "type": "int", "description": "User ID to validate"}],
                "outputs": [{"name": "user", "type": "dict", "description": "User data if found"}],
                "behavior": "Looks up user in the users data store",
                "signature": "def ValidateUser(user_id: int) -> dict:",
            },
            {
                "name": "SaveOrder",
                "purpose": "Save the order record",
                "inputs": [{"name": "user_id", "type": "int", "description": "User ID"},
                           {"name": "items", "type": "list", "description": "Order items"},
                           {"name": "total_price", "type": "float", "description": "Calculated total price"}],
                "outputs": [{"name": "order", "type": "dict", "description": "Saved order record"}],
                "behavior": "Creates and stores an order record with status 'pending'",
                "signature": "def SaveOrder(user_id: int, items: list, total_price: float) -> dict:",
            },
        ],
    ),
})

# ----- W2: Direct resource access needed -----
TEST_CASES.append({
    "id": "W2",
    "type": "wrong",
    "description": "Direct resource access: no child reads the users data store",
    "expect": "cannot_compose",
    "make_node": lambda: make_parent(
        name="GetUserProfile",
        purpose="Get user profile: format user data and log access. No child reads the users data store.",
        inputs=[
            {"name": "user_id", "type": "int", "description": "User ID to look up"},
        ],
        outputs=[
            {"name": "profile", "type": "dict", "description": "Formatted user profile"},
        ],
        global_vars=[{"variable": "users", "op": "read", "description": "User data store"}],
        data_sources=[{"name": "users", "category": "memory", "access": "read",
                       "data_type": "dict", "description": "User data store keyed by user_id"}],
        children_data=[
            {
                "name": "FormatResponse",
                "purpose": "Format user data into a response dict",
                "inputs": [{"name": "data", "type": "dict", "description": "Raw user data to format"}],
                "outputs": [{"name": "response", "type": "dict", "description": "Formatted response dict"}],
                "behavior": "Transforms raw data into the standard response format",
                "signature": "def FormatResponse(data: dict) -> dict:",
            },
            {
                "name": "LogAccess",
                "purpose": "Log that a profile was accessed",
                "inputs": [{"name": "user_id", "type": "int", "description": "User ID that was accessed"}],
                "outputs": [{"name": "logged", "type": "bool", "description": "Whether access was logged"}],
                "behavior": "Records an audit log entry for the profile access",
                "signature": "def LogAccess(user_id: int) -> bool:",
            },
        ],
    ),
})

# ----- W3: Child output can't produce parent output -----
TEST_CASES.append({
    "id": "W3",
    "type": "wrong",
    "description": "Output type mismatch: parent must return str but children return dict. No child formats output.",
    "expect": "cannot_compose",
    "make_node": lambda: make_parent(
        name="GenerateInvoiceReport",
        purpose="Generate a formatted invoice report string. Children return dicts but parent must return str.",
        inputs=[
            {"name": "order_id", "type": "int", "description": "Order ID to generate report for"},
        ],
        outputs=[
            {"name": "report", "type": "str", "description": "Formatted invoice report as a string"},
        ],
        children_data=[
            {
                "name": "FetchOrder",
                "purpose": "Retrieve order details",
                "inputs": [{"name": "order_id", "type": "int", "description": "Order ID to fetch"}],
                "outputs": [{"name": "order", "type": "dict", "description": "Order details dict"}],
                "behavior": "Looks up order from the orders data store",
                "signature": "def FetchOrder(order_id: int) -> dict:",
            },
            {
                "name": "CalculateTotals",
                "purpose": "Calculate order totals from order data",
                "inputs": [{"name": "order", "type": "dict", "description": "Order details"}],
                "outputs": [{"name": "totals", "type": "dict", "description": "Dict with subtotal, tax, total fields"}],
                "behavior": "Computes subtotal, tax, and grand total from order items",
                "signature": "def CalculateTotals(order: dict) -> dict:",
            },
        ],
    ),
})

# ----- W4: Hidden intermediate data gap -----
TEST_CASES.append({
    "id": "W4",
    "type": "wrong",
    "description": "Hidden data gap: DeployApplication needs 'version' parameter that has no source anywhere",
    "expect": "cannot_compose",
    "make_node": lambda: make_parent(
        name="DeployService",
        purpose="Deploy a service: parse config, provision infra, deploy app. But 'version' is needed with no source.",
        inputs=[
            {"name": "config", "type": "dict", "description": "Deployment configuration dict"},
        ],
        outputs=[
            {"name": "result", "type": "dict", "description": "Deployment result with status and URL"},
        ],
        children_data=[
            {
                "name": "ParseConfig",
                "purpose": "Parse deployment configuration into structured format",
                "inputs": [{"name": "config", "type": "dict", "description": "Raw config dict"}],
                "outputs": [{"name": "parsed", "type": "dict", "description": "Structured configuration"}],
                "behavior": "Validates and normalizes the deployment configuration",
                "signature": "def ParseConfig(config: dict) -> dict:",
            },
            {
                "name": "ProvisionInfrastructure",
                "purpose": "Provision cloud resources based on parsed config",
                "inputs": [{"name": "parsed", "type": "dict", "description": "Parsed configuration"}],
                "outputs": [{"name": "resources", "type": "list", "description": "Provisioned resource list"}],
                "behavior": "Creates VMs, networks, and storage resources per config",
                "signature": "def ProvisionInfrastructure(parsed: dict) -> list:",
            },
            {
                "name": "DeployApplication",
                "purpose": "Deploy the application to provisioned infrastructure",
                "inputs": [{"name": "parsed", "type": "dict", "description": "Parsed configuration"},
                           {"name": "version", "type": "str", "description": "Application version to deploy"},
                           {"name": "resources", "type": "list", "description": "Provisioned resources"}],
                "outputs": [{"name": "deploy_result", "type": "dict", "description": "Deployment result with URL"}],
                "behavior": "Deploys the specified version to the provisioned infrastructure",
                "signature": "def DeployApplication(parsed: dict, version: str, resources: list) -> dict:",
            },
        ],
    ),
})

# ----- W5: Multiple simultaneous gaps -----
TEST_CASES.append({
    "id": "W5",
    "type": "wrong",
    "description": "Multiple gaps: parent output needs updated/added/removed/errors but child only returns int; no error handling",
    "expect": "cannot_compose",
    "make_node": lambda: make_parent(
        name="SyncProducts",
        purpose="Sync products between source and target: fetch both, compute diff, apply changes. "
                "Parent must return dict with updated/added/removed/errors but ApplyChanges only returns int.",
        inputs=[
            {"name": "source_url", "type": "str", "description": "Source API endpoint URL"},
            {"name": "target_url", "type": "str", "description": "Target API endpoint URL"},
        ],
        outputs=[
            {"name": "result", "type": "dict", "description": "Sync result with updated, added, removed counts and errors list"},
        ],
        children_data=[
            {
                "name": "FetchSourceProducts",
                "purpose": "Fetch products from the source system",
                "inputs": [{"name": "source_url", "type": "str", "description": "Source API URL"}],
                "outputs": [{"name": "products", "type": "list", "description": "List of source product dicts"}],
                "behavior": "Makes HTTP request to source API and returns product list",
                "signature": "def FetchSourceProducts(source_url: str) -> list:",
            },
            {
                "name": "FetchTargetProducts",
                "purpose": "Fetch existing products from the target system",
                "inputs": [{"name": "target_url", "type": "str", "description": "Target API URL"}],
                "outputs": [{"name": "products", "type": "list", "description": "List of target product dicts"}],
                "behavior": "Makes HTTP request to target API and returns product list",
                "signature": "def FetchTargetProducts(target_url: str) -> list:",
            },
            {
                "name": "ComputeDiff",
                "purpose": "Compare source and target to find differences",
                "inputs": [{"name": "source", "type": "list", "description": "Source products"},
                           {"name": "target", "type": "list", "description": "Target products"}],
                "outputs": [{"name": "diff", "type": "list", "description": "List of changes to apply (create/update/delete)"}],
                "behavior": "Compares products by ID and determines what needs to be created, updated, or deleted",
                "signature": "def ComputeDiff(source: list, target: list) -> list:",
            },
            {
                "name": "ApplyChanges",
                "purpose": "Apply the computed diff changes to the target system",
                "inputs": [{"name": "diff", "type": "list", "description": "List of changes to apply"}],
                "outputs": [{"name": "updated_count", "type": "int", "description": "Number of successfully applied changes"}],
                "behavior": "Iterates through diff and executes create/update/delete operations",
                "signature": "def ApplyChanges(diff: list) -> int:",
            },
        ],
    ),
})

# ----- W6: Contradictory data flow (no valid call order) -----
TEST_CASES.append({
    "id": "W6",
    "type": "wrong",
    "description": "Broken data flow: CheckWorkload needs 'schedule' which no child produces; "
                    "and 'urgency' needed by PrioritizeJobs also has no source",
    "expect": "cannot_compose",
    "make_node": lambda: make_parent(
        name="PlanMaintenance",
        purpose="Plan equipment maintenance: check crew workload, prioritize jobs, assign, generate schedule. "
                "But 'schedule' (needed by CheckWorkload) and 'urgency' (needed by PrioritizeJobs) have no sources.",
        inputs=[
            {"name": "equipment", "type": "list", "description": "List of equipment dicts needing maintenance"},
            {"name": "crew", "type": "list", "description": "List of crew member dicts"},
        ],
        outputs=[
            {"name": "plan", "type": "dict", "description": "Complete maintenance plan with schedule"},
        ],
        children_data=[
            {
                "name": "CheckWorkload",
                "purpose": "Check crew availability based on current workload and schedule",
                "inputs": [{"name": "crew", "type": "list", "description": "Crew member list"},
                           {"name": "schedule", "type": "dict", "description": "Current maintenance schedule to check against"}],
                "outputs": [{"name": "available_crew", "type": "list", "description": "Available crew members"}],
                "behavior": "Checks each crew member's existing assignments against the schedule",
                "signature": "def CheckWorkload(crew: list, schedule: dict) -> list:",
            },
            {
                "name": "PrioritizeJobs",
                "purpose": "Prioritize maintenance jobs based on urgency",
                "inputs": [{"name": "equipment", "type": "list", "description": "Equipment list"},
                           {"name": "urgency", "type": "dict", "description": "Urgency mapping for prioritization"}],
                "outputs": [{"name": "job_queue", "type": "list", "description": "Prioritized job queue"}],
                "behavior": "Ranks equipment by urgency criteria and returns ordered queue",
                "signature": "def PrioritizeJobs(equipment: list, urgency: dict) -> list:",
            },
            {
                "name": "AssignJobs",
                "purpose": "Assign prioritized jobs to available crew members",
                "inputs": [{"name": "available_crew", "type": "list", "description": "Available crew"},
                           {"name": "job_queue", "type": "list", "description": "Prioritized jobs"}],
                "outputs": [{"name": "assignments", "type": "dict", "description": "Job-to-crew assignments"}],
                "behavior": "Maps each job to a suitable crew member based on skills",
                "signature": "def AssignJobs(available_crew: list, job_queue: list) -> dict:",
            },
            {
                "name": "GenerateSchedule",
                "purpose": "Generate a maintenance schedule from assignments",
                "inputs": [{"name": "assignments", "type": "dict", "description": "Job assignments"}],
                "outputs": [{"name": "schedule", "type": "dict", "description": "Generated maintenance schedule"}],
                "behavior": "Creates a timeline-based schedule from the assignments",
                "signature": "def GenerateSchedule(assignments: dict) -> dict:",
            },
        ],
    ),
})


# =========================================================================
# TEST RUNNER
# =========================================================================

def run_single_test(cfg, api_client, test_case):
    """Run one test case and return structured results."""
    node = test_case["make_node"]()
    cg = CodeGenerator(cfg, api_client)

    # Capture prompts before running
    messages = capture_prompt(cg, node)

    print(f"  Starting...", end=" ", flush=True)
    start = time.time()
    try:
        code, errors = cg.generate_for_parent(node)
        elapsed = time.time() - start
        print(f"({elapsed:.1f}s)", flush=True)
    except Exception as e:
        elapsed = time.time() - start
        print(f"EXCEPTION ({elapsed:.1f}s): {e}", flush=True)
        return {
            "test_id": test_case["id"],
            "status": "error",
            "error": str(e),
            "elapsed": elapsed,
            "code": "",
            "errors": [],
            "composition_feedback": None,
            "prompt_system": messages[0]["content"],
            "prompt_user": messages[1]["content"],
            "node_dump": node.to_dict(),
        }

    # Determine verdict
    is_cannot_compose = any(e.startswith("CANNOT_COMPOSE") for e in errors)
    feedback = node.composition_feedback.to_dict() if node.composition_feedback else None

    if test_case["expect"] == "ok":
        if code and not errors:
            verdict = "PASS"
        elif is_cannot_compose:
            verdict = "FAIL (false negative: returned cannot_compose for correct decomposition)"
        else:
            verdict = f"FAIL (expected code, got errors={errors})"
    else:  # expect cannot_compose
        if is_cannot_compose:
            verdict = "PASS"
        elif code and not errors:
            verdict = f"FAIL (false positive: returned code instead of cannot_compose)"
        else:
            verdict = f"FAIL (expected cannot_compose, got code={code!r} errors={errors})"

    return {
        "test_id": test_case["id"],
        "type": test_case["type"],
        "description": test_case["description"],
        "expect": test_case["expect"],
        "verdict": verdict,
        "status": "cannot_compose" if is_cannot_compose else ("ok" if code else "error"),
        "code": code,
        "errors": errors,
        "composition_feedback": feedback,
        "elapsed": elapsed,
        "prompt_system": messages[0]["content"],
        "prompt_user": messages[1]["content"],
        "node_dump": node.to_dict(),
    }


def print_summary(results):
    """Print a clean summary of results."""
    passed = sum(1 for r in results if r["verdict"].startswith("PASS"))
    failed = sum(1 for r in results if r["verdict"].startswith("FAIL"))
    errors = sum(1 for r in results if r["status"] == "error")

    print()
    print("=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)
    for r in results:
        emoji = {"PASS": "  PASS", "FAIL": "!! FAIL"}.get(
            "PASS" if r["verdict"].startswith("PASS") else "FAIL", "???"
        )
        print(f"  {emoji}  {r['test_id']}: {r['description']}")
        if not r["verdict"].startswith("PASS"):
            print(f"       {r['verdict']}")
        if r.get("composition_feedback"):
            cf = r["composition_feedback"]
            print(f"       reason: {cf.get('reason', 'N/A')}")
            print(f"       suggested_fix: {cf.get('suggested_fix', 'N/A')[:100]}")
        if r.get("code"):
            # Show first line of code
            first_line = r["code"].strip().split("\n")[0][:80]
            print(f"       code: {first_line}")

    print()
    print(f"  Total: {len(results)} | PASS: {passed} | FAIL: {failed} | ERROR: {errors}")
    print("=" * 70)


def main():
    print("=" * 70)
    print("  REAL LLM TEST: CodeGenerator Composition Validation")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Model: {Config().model}")
    print("=" * 70)
    print()

    cfg = Config(temperature=0.0, max_retries=1)
    api_client = APIClient(cfg)
    print("  API client initialized (test prompts contain 'json' keyword for JSON mode)\n")

    all_results = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for i, tc in enumerate(TEST_CASES):
        label = f"[{i+1}/{len(TEST_CASES)}]"
        print(f"{label} {tc['id']} ({tc['type']}): {tc['description'][:70]}")
        try:
            result = run_single_test(cfg, api_client, tc)
            all_results.append(result)
        except Exception as e:
            print(f"  !! UNEXPECTED ERROR: {e}")
            all_results.append({
                "test_id": tc["id"],
                "status": "error",
                "error": str(e),
            })
        print()

    print_summary(all_results)

    # Save full results
    output = {
        "timestamp": datetime.now().isoformat(),
        "model": cfg.model,
        "temperature": cfg.temperature,
        "summary": {
            "total": len(all_results),
            "passed": sum(1 for r in all_results if r.get("verdict", "").startswith("PASS")),
            "failed": sum(1 for r in all_results if r.get("verdict", "").startswith("FAIL")),
            "errors": sum(1 for r in all_results if r.get("status") == "error"),
        },
        "results": all_results,
    }

    result_path = os.path.join(OUTPUT_DIR, f"results_{timestamp}.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nFull results saved to: {result_path}")


if __name__ == "__main__":
    main()
