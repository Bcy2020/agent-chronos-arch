"""
Formal real LLM test: CodeGenerator composition validation.

7 wrong + 3 correct decompositions.
Run multiple iterations to assess consistency.
Saves each run + aggregate results to tests/output/test_codegen_formal/
"""
import json
import os
import sys
import time
from datetime import datetime
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from api_client import APIClient
from code_generator import CodeGenerator
from models import (
    Node, InputParam, OutputParam, Boundary, ChildContract,
    DataSource, GlobalVar, DataOperation
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "test_codegen_formal")
os.makedirs(OUTPUT_DIR, exist_ok=True)
MAX_RUNS = 3


def make_signature(name, inputs, outputs):
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
    children = []
    children_contracts = {}
    for i, cd in enumerate(children_data):
        child_inputs = [InputParam(**ip) for ip in cd.get("inputs", [])]
        child_outputs = [OutputParam(**op) for op in cd.get("outputs", [])]
        child_node = Node(
            node_id=f"child_{i}", name=cd["name"], depth=2,
            parent_id="parent", purpose=cd.get("purpose", ""),
            inputs=child_inputs, outputs=child_outputs,
            stop_decompose=True, stop_reason="test leaf",
        )
        children.append(child_node)
        sig = cd.get("signature") or make_signature(cd["name"], cd.get("inputs", []), cd.get("outputs", []))
        contract = ChildContract(
            purpose=cd.get("purpose", ""), behavior=cd.get("behavior", ""),
            inputs=child_inputs, outputs=child_outputs, signature=sig,
            data_operations=[DataOperation(**dop) for dop in cd.get("data_operations", [])],
        )
        children_contracts[cd["name"]] = contract
    node = Node(
        node_id="parent", name=name, depth=1, purpose=purpose,
        inputs=[InputParam(**ip) for ip in inputs],
        outputs=[OutputParam(**op) for op in outputs],
        boundary=Boundary(in_scope=[], out_of_scope=[]),
        children=children, children_contracts=children_contracts,
        global_vars=[GlobalVar(**gv) for gv in (global_vars or [])],
        data_sources=[DataSource(**ds) for ds in (data_sources or [])],
    )
    return node


# =========================================================================
# TEST CASES: 3 correct + 7 wrong
# =========================================================================
TEST_CASES = []

# --- C1. Sequential pipeline ---
TEST_CASES.append({
    "id": "C1", "type": "correct", "expect": "ok",
    "description": "Sequential deploy pipeline: ValidateEnvironment -> RunMigrations -> RestartServices -> VerifyDeployment",
    "make_node": lambda: make_parent(
        name="DeployApplication",
        purpose="Deploy application to target environment: validate, run migrations, restart services, verify.",
        inputs=[{"name": "build_id", "type": "str", "description": "Build artifact ID"},
                {"name": "target_env", "type": "str", "description": "Target environment (staging/production)"}],
        outputs=[{"name": "result", "type": "dict", "description": "Deployment result with status and endpoint"}],
        children_data=[
            {"name": "ValidateEnvironment", "purpose": "Check if target environment is ready for deployment",
             "inputs": [{"name": "target_env", "type": "str", "description": "Environment to validate"}],
             "outputs": [{"name": "is_ready", "type": "bool", "description": "Whether environment is ready"}],
             "behavior": "Checks environment health and deployment locks",
             "signature": "def ValidateEnvironment(target_env: str) -> bool:"},
            {"name": "RunMigrations", "purpose": "Run database migrations in target environment",
             "inputs": [{"name": "target_env", "type": "str", "description": "Target environment"}],
             "outputs": [{"name": "migration_result", "type": "dict", "description": "Migration output with applied changes"}],
             "behavior": "Executes pending database migrations",
             "signature": "def RunMigrations(target_env: str) -> dict:"},
            {"name": "RestartServices", "purpose": "Restart application services",
             "inputs": [{"name": "target_env", "type": "str", "description": "Target environment"}],
             "outputs": [{"name": "restart_status", "type": "dict", "description": "Service restart status"}],
             "behavior": "Restarts web server and worker processes",
             "signature": "def RestartServices(target_env: str) -> dict:"},
            {"name": "VerifyDeployment", "purpose": "Verify the deployment is healthy",
             "inputs": [{"name": "target_env", "type": "str", "description": "Target environment"}],
             "outputs": [{"name": "health_check", "type": "dict", "description": "Health check results"}],
             "behavior": "Runs smoke tests and health checks",
             "signature": "def VerifyDeployment(target_env: str) -> dict:"},
        ]),
})

# --- C2. Conditional branching ---
TEST_CASES.append({
    "id": "C2", "type": "correct", "expect": "ok",
    "description": "Conditional refund: GetTransaction -> if eligible -> IssueRefund -> NotifyUser",
    "make_node": lambda: make_parent(
        name="ProcessRefund",
        purpose="Process a refund: validate eligibility, issue refund, notify user.",
        inputs=[{"name": "transaction_id", "type": "str", "description": "Original transaction ID"},
                {"name": "amount", "type": "float", "description": "Refund amount"}],
        outputs=[{"name": "result", "type": "dict", "description": "Refund result with status and reference"}],
        children_data=[
            {"name": "GetTransaction", "purpose": "Retrieve original transaction details",
             "inputs": [{"name": "transaction_id", "type": "str", "description": "Transaction ID"}],
             "outputs": [{"name": "transaction", "type": "dict", "description": "Transaction details"}],
             "behavior": "Looks up transaction from payment system",
             "signature": "def GetTransaction(transaction_id: str) -> dict:"},
            {"name": "ValidateRefundEligibility", "purpose": "Check if transaction can be refunded",
             "inputs": [{"name": "transaction", "type": "dict", "description": "Transaction details"},
                        {"name": "amount", "type": "float", "description": "Requested refund amount"}],
             "outputs": [{"name": "is_eligible", "type": "bool", "description": "Whether refund is allowed"}],
             "behavior": "Checks refund policy, time limits, and amount limits",
             "signature": "def ValidateRefundEligibility(transaction: dict, amount: float) -> bool:"},
            {"name": "IssueRefund", "purpose": "Execute the refund via payment gateway",
             "inputs": [{"name": "transaction", "type": "dict", "description": "Original transaction"},
                        {"name": "amount", "type": "float", "description": "Amount to refund"}],
             "outputs": [{"name": "refund_result", "type": "dict", "description": "Gateway refund response"}],
             "behavior": "Sends refund request to payment gateway",
             "signature": "def IssueRefund(transaction: dict, amount: float) -> dict:"},
            {"name": "NotifyUser", "purpose": "Send refund notification to the user",
             "inputs": [{"name": "user_id", "type": "str", "description": "User ID to notify"},
                        {"name": "message", "type": "str", "description": "Notification message"}],
             "outputs": [{"name": "notified", "type": "bool", "description": "Whether notification was sent"}],
             "behavior": "Sends email or push notification",
             "signature": "def NotifyUser(user_id: str, message: str) -> bool:"},
        ]),
})

# --- C3. Fan-out fan-in ---
TEST_CASES.append({
    "id": "C3", "type": "correct", "expect": "ok",
    "description": "Fan-out fan-in: CountLines + AnalyzeDependencies + DetectSecrets -> GenerateReport",
    "make_node": lambda: make_parent(
        name="AnalyzeRepository",
        purpose="Analyze a git repository: count lines, analyze dependencies, detect secrets, generate report.",
        inputs=[{"name": "repo_url", "type": "str", "description": "Git repository URL"}],
        outputs=[{"name": "report", "type": "dict", "description": "Analysis report with metrics"}],
        children_data=[
            {"name": "CloneRepository", "purpose": "Clone the repository to local path",
             "inputs": [{"name": "repo_url", "type": "str", "description": "Repository URL"}],
             "outputs": [{"name": "repo_path", "type": "str", "description": "Local path to cloned repo"}],
             "behavior": "Runs git clone and returns local path",
             "signature": "def CloneRepository(repo_url: str) -> str:"},
            {"name": "CountLines", "purpose": "Count lines of code in the repository",
             "inputs": [{"name": "repo_path", "type": "str", "description": "Local repo path"}],
             "outputs": [{"name": "line_count", "type": "int", "description": "Total lines of code"}],
             "behavior": "Counts all source code lines excluding generated files",
             "signature": "def CountLines(repo_path: str) -> int:"},
            {"name": "AnalyzeDependencies", "purpose": "Analyze project dependencies",
             "inputs": [{"name": "repo_path", "type": "str", "description": "Local repo path"}],
             "outputs": [{"name": "dependencies", "type": "list", "description": "List of dependency dicts"}],
             "behavior": "Parses package files and extracts dependency tree",
             "signature": "def AnalyzeDependencies(repo_path: str) -> list:"},
            {"name": "DetectSecrets", "purpose": "Scan for hardcoded secrets in the repo",
             "inputs": [{"name": "repo_path", "type": "str", "description": "Local repo path"}],
             "outputs": [{"name": "secrets", "type": "list", "description": "List of detected secret locations"}],
             "behavior": "Scans for API keys, tokens, and credentials",
             "signature": "def DetectSecrets(repo_path: str) -> list:"},
            {"name": "GenerateReport", "purpose": "Generate comprehensive analysis report",
             "inputs": [{"name": "line_count", "type": "int", "description": "Line count metric"},
                        {"name": "dependencies", "type": "list", "description": "Dependency list"},
                        {"name": "secrets", "type": "list", "description": "Secret scan results"}],
             "outputs": [{"name": "report", "type": "dict", "description": "Complete analysis report"}],
             "behavior": "Assembles all metrics into a structured report",
             "signature": "def GenerateReport(line_count: int, dependencies: list, secrets: list) -> dict:"},
        ]),
})

# --- W1. Missing parameter (clear) ---
TEST_CASES.append({
    "id": "W1", "type": "wrong", "expect": "cannot_compose",
    "description": "Missing parameter: AwardBadge needs badge_id which has no source",
    "make_node": lambda: make_parent(
        name="AssignBadge",
        purpose="Assign a badge to a user: validate user, then award the badge.",
        inputs=[{"name": "user_id", "type": "int", "description": "User ID to badge"},
                {"name": "badge_name", "type": "str", "description": "Name of the badge to award"}],
        outputs=[{"name": "result", "type": "dict", "description": "Badge assignment result"}],
        children_data=[
            {"name": "ValidateUser", "purpose": "Check if user exists",
             "inputs": [{"name": "user_id", "type": "int", "description": "User ID"}],
             "outputs": [{"name": "user", "type": "dict", "description": "User data"}],
             "behavior": "Looks up user in the data store",
             "signature": "def ValidateUser(user_id: int) -> dict:"},
            {"name": "AwardBadge", "purpose": "Award the badge to the user",
             "inputs": [{"name": "user_id", "type": "int", "description": "User ID"},
                        {"name": "badge_name", "type": "str", "description": "Badge name"},
                        {"name": "badge_id", "type": "str", "description": "Unique badge identifier"}],
             "outputs": [{"name": "award_result", "type": "dict", "description": "Award confirmation"}],
             "behavior": "Creates badge assignment record",
             "signature": "def AwardBadge(user_id: int, badge_name: str, badge_id: str) -> dict:"},
        ]),
})

# --- W2. No data access ---
TEST_CASES.append({
    "id": "W2", "type": "wrong", "expect": "cannot_compose",
    "description": "No data access: no child reads server status, parent would need direct access",
    "make_node": lambda: make_parent(
        name="GetServerStatus",
        purpose="Get server status: retrieve and format server health data.",
        inputs=[{"name": "server_id", "type": "str", "description": "Server identifier"}],
        outputs=[{"name": "status", "type": "dict", "description": "Formatted server status"}],
        global_vars=[{"variable": "servers", "op": "read", "description": "Server data store"}],
        data_sources=[{"name": "servers", "category": "memory", "access": "read",
                       "data_type": "dict", "description": "Server status data keyed by server_id"}],
        children_data=[
            {"name": "FormatResponse", "purpose": "Format raw data into a status response",
             "inputs": [{"name": "data", "type": "dict", "description": "Raw server data to format"}],
             "outputs": [{"name": "response", "type": "dict", "description": "Formatted status response"}],
             "behavior": "Transforms raw data into standard API response format",
             "signature": "def FormatResponse(data: dict) -> dict:"},
        ]),
})

# --- W3. Missing parameter in chain ---
TEST_CASES.append({
    "id": "W3", "type": "wrong", "expect": "cannot_compose",
    "description": "Missing hidden parameter: InstallAgent needs api_key which has no source",
    "make_node": lambda: make_parent(
        name="ConfigureMonitoring",
        purpose="Configure monitoring for a service: setup alerts, install agent, validate.",
        inputs=[{"name": "service", "type": "str", "description": "Service name to monitor"},
                {"name": "environment", "type": "str", "description": "Deployment environment"}],
        outputs=[{"name": "result", "type": "dict", "description": "Monitoring configuration result"}],
        children_data=[
            {"name": "SetupAlerts", "purpose": "Configure alerting rules for the service",
             "inputs": [{"name": "service", "type": "str", "description": "Service name"},
                        {"name": "environment", "type": "str", "description": "Environment"}],
             "outputs": [{"name": "alerts_configured", "type": "list", "description": "Configured alert rules"}],
             "behavior": "Creates alert thresholds and notification channels",
             "signature": "def SetupAlerts(service: str, environment: str) -> list:"},
            {"name": "InstallAgent", "purpose": "Install monitoring agent on the service",
             "inputs": [{"name": "service", "type": "str", "description": "Service name"},
                        {"name": "environment", "type": "str", "description": "Environment"},
                        {"name": "api_key", "type": "str", "description": "Monitoring API key for authentication"}],
             "outputs": [{"name": "agent_result", "type": "dict", "description": "Agent installation result"}],
             "behavior": "Deploys and configures monitoring agent",
             "signature": "def InstallAgent(service: str, environment: str, api_key: str) -> dict:"},
            {"name": "ValidateMonitoring", "purpose": "Validate monitoring is working correctly",
             "inputs": [{"name": "service", "type": "str", "description": "Service name"},
                        {"name": "agent_result", "type": "dict", "description": "Agent install result"}],
             "outputs": [{"name": "validation", "type": "dict", "description": "Validation results"}],
             "behavior": "Runs test metric submission and verifies receipt",
             "signature": "def ValidateMonitoring(service: str, agent_result: dict) -> dict:"},
        ]),
})

# --- W4. Multiple missing output fields ---
TEST_CASES.append({
    "id": "W4", "type": "wrong", "expect": "cannot_compose",
    "description": "Multiple missing outputs: parent returns 5 fields but child only produces 1 value",
    "make_node": lambda: make_parent(
        name="ExecuteQuery",
        purpose="Execute SQL query and return structured results with metadata.",
        inputs=[{"name": "sql", "type": "str", "description": "SQL query string"},
                {"name": "database", "type": "str", "description": "Target database name"}],
        outputs=[{"name": "result", "type": "dict",
                  "description": "Query result with rows, columns, row_count, execution_time_ms, error fields"}],
        children_data=[
            {"name": "ValidateQuery", "purpose": "Validate SQL query syntax and permissions",
             "inputs": [{"name": "sql", "type": "str", "description": "SQL query"}],
             "outputs": [{"name": "is_valid", "type": "bool", "description": "Whether query is valid"}],
             "behavior": "Checks SQL syntax and access permissions",
             "signature": "def ValidateQuery(sql: str) -> bool:"},
            {"name": "RunQuery", "purpose": "Execute the SQL query on the target database",
             "inputs": [{"name": "sql", "type": "str", "description": "SQL query"},
                        {"name": "database", "type": "str", "description": "Target database"}],
             "outputs": [{"name": "rows", "type": "list", "description": "Query result rows"}],
             "behavior": "Executes query and fetches all result rows",
             "signature": "def RunQuery(sql: str, database: str) -> list:"},
            {"name": "FormatResults", "purpose": "Format query results for API response",
             "inputs": [{"name": "rows", "type": "list", "description": "Raw result rows"}],
             "outputs": [{"name": "formatted", "type": "dict", "description": "Formatted response"}],
             "behavior": "Wraps rows in standard response envelope",
             "signature": "def FormatResults(rows: list) -> dict:"},
        ]),
})

# --- W5. Orphan business fields ---
TEST_CASES.append({
    "id": "W5", "type": "wrong", "expect": "cannot_compose",
    "description": "Orphan fields: published_at, status, word_count have no source among children",
    "make_node": lambda: make_parent(
        name="PublishArticle",
        purpose="Publish an article: validate, schedule, notify reviewer.",
        inputs=[{"name": "title", "type": "str", "description": "Article title"},
                {"name": "content", "type": "str", "description": "Article body content"},
                {"name": "reviewer", "type": "str", "description": "Reviewer username"}],
        outputs=[{"name": "result", "type": "dict",
                  "description": "Publication result with article_id, published_at, reviewer, status, word_count"}],
        children_data=[
            {"name": "ValidateContent", "purpose": "Validate article content meets quality standards",
             "inputs": [{"name": "title", "type": "str", "description": "Article title"},
                        {"name": "content", "type": "str", "description": "Article body"}],
             "outputs": [{"name": "is_valid", "type": "bool", "description": "Whether content is valid"}],
             "behavior": "Checks formatting, links, and required fields",
             "signature": "def ValidateContent(title: str, content: str) -> bool:"},
            {"name": "SchedulePublish", "purpose": "Schedule the article for publication",
             "inputs": [{"name": "title", "type": "str", "description": "Article title"},
                        {"name": "content", "type": "str", "description": "Article body"}],
             "outputs": [{"name": "article_id", "type": "str", "description": "Published article ID"}],
             "behavior": "Creates publication record and returns article ID",
             "signature": "def SchedulePublish(title: str, content: str) -> str:"},
            {"name": "NotifyReviewer", "purpose": "Notify the reviewer about publication",
             "inputs": [{"name": "reviewer", "type": "str", "description": "Reviewer username"},
                        {"name": "article_id", "type": "str", "description": "Published article ID"}],
             "outputs": [{"name": "notified", "type": "bool", "description": "Whether notification was sent"}],
             "behavior": "Sends publication notification to reviewer",
             "signature": "def NotifyReviewer(reviewer: str, article_id: str) -> bool:"},
        ]),
})

# --- W6. Missing data producer ---
TEST_CASES.append({
    "id": "W6", "type": "wrong", "expect": "cannot_compose",
    "description": "Missing data producer: no child merges branches, parent can't merge itself",
    "make_node": lambda: make_parent(
        name="MergeBranches",
        purpose="Merge source branch into target branch in a git repository.",
        inputs=[{"name": "source_branch", "type": "str", "description": "Branch to merge from"},
                {"name": "target_branch", "type": "str", "description": "Branch to merge into"}],
        outputs=[{"name": "result", "type": "dict", "description": "Merge result with status and commit hash"}],
        global_vars=[{"variable": "repo", "op": "read_write", "description": "Git repository"}],
        children_data=[
            {"name": "FetchBranchCommits", "purpose": "Fetch commits from a branch",
             "inputs": [{"name": "branch", "type": "str", "description": "Branch name"},
                        {"name": "repo_path", "type": "str", "description": "Repository path"}],
             "outputs": [{"name": "commits", "type": "list", "description": "List of commit dicts"}],
             "behavior": "Runs git log on the specified branch",
             "signature": "def FetchBranchCommits(branch: str, repo_path: str) -> list:"},
        ],
        data_sources=[{"name": "repo", "category": "git", "access": "read_write",
                       "data_type": "object", "description": "Git repository object"}],
    ),
})

# --- W7. No data mutation ---
TEST_CASES.append({
    "id": "W7", "type": "wrong", "expect": "cannot_compose",
    "description": "No data mutation: no child updates the inventory data store",
    "make_node": lambda: make_parent(
        name="UpdateInventory",
        purpose="Update inventory quantity for an item: validate, update stock, log change.",
        inputs=[{"name": "item_id", "type": "str", "description": "Inventory item ID"},
                {"name": "quantity", "type": "int", "description": "New quantity to set"}],
        outputs=[{"name": "result", "type": "dict", "description": "Update result with new quantity"}],
        global_vars=[{"variable": "inventory", "op": "read_write", "description": "Inventory data store"}],
        data_sources=[{"name": "inventory", "category": "memory", "access": "read_write",
                       "data_type": "dict", "description": "Inventory items keyed by item_id"}],
        children_data=[
            {"name": "ValidateItem", "purpose": "Check if item exists in inventory",
             "inputs": [{"name": "item_id", "type": "str", "description": "Item ID to validate"}],
             "outputs": [{"name": "item", "type": "dict", "description": "Item data if found"}],
             "behavior": "Looks up item in inventory data store",
             "signature": "def ValidateItem(item_id: str) -> dict:"},
            {"name": "LogChange", "purpose": "Log the inventory change for audit trail",
             "inputs": [{"name": "item_id", "type": "str", "description": "Item ID changed"},
                        {"name": "new_quantity", "type": "int", "description": "New quantity value"}],
             "outputs": [{"name": "logged", "type": "bool", "description": "Whether change was logged"}],
             "behavior": "Creates an audit log entry for the inventory change",
             "signature": "def LogChange(item_id: str, new_quantity: int) -> bool:"},
        ]),
})


# =========================================================================
# RUNNER
# =========================================================================

def run_single_test(cfg, api_client, test_case):
    node = test_case["make_node"]()
    cg = CodeGenerator(cfg, api_client)
    start = time.time()
    try:
        code, errors = cg.generate_for_parent(node)
        elapsed = time.time() - start
    except Exception as e:
        elapsed = time.time() - start
        return {
            "test_id": test_case["id"], "status": "error", "error": str(e),
            "elapsed": elapsed, "code": "", "errors": [], "composition_feedback": None,
        }

    is_cannot_compose = any(e.startswith("CANNOT_COMPOSE") for e in errors)
    feedback = node.composition_feedback.to_dict() if node.composition_feedback else None

    if test_case["expect"] == "ok":
        verdict = "PASS" if (code and not errors) else "FAIL"
    else:
        verdict = "PASS" if is_cannot_compose else "FAIL"

    return {
        "test_id": test_case["id"], "type": test_case["type"],
        "description": test_case["description"], "expect": test_case["expect"],
        "verdict": verdict,
        "status": "cannot_compose" if is_cannot_compose else ("ok" if code else "error"),
        "code": code, "errors": errors,
        "composition_feedback": feedback, "elapsed": elapsed,
    }


def print_run_summary(results, run_num):
    passed = sum(1 for r in results if r["verdict"] == "PASS")
    failed = sum(1 for r in results if r["verdict"] == "FAIL")
    print(f"  PASS: {passed}  FAIL: {failed}  ", end="")
    for r in results:
        mark = "+" if r["verdict"] == "PASS" else "x"
        print(f"{mark}{r['test_id']} ", end="")
    print()
    for r in results:
        if r["verdict"] == "FAIL":
            fb = r.get("composition_feedback") or {}
            print(f"    {r['test_id']}: {fb.get('reason', 'N/A')}")


def main():
    print("=" * 70)
    print("  FORMAL TEST: CodeGenerator Composition Validation")
    print(f"  {len(TEST_CASES)} cases (3 correct + 7 wrong) x {MAX_RUNS} runs")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Model: {Config().model}")
    print("=" * 70)

    cfg = Config(temperature=0.0, max_retries=1)
    api_client = APIClient(cfg)
    print()

    all_runs = []
    per_case_results = {tc["id"]: [] for tc in TEST_CASES}

    for run in range(1, MAX_RUNS + 1):
        print(f"[Run {run}/{MAX_RUNS}]")
        run_results = []
        for i, tc in enumerate(TEST_CASES):
            label = f"  [{i+1}/{len(TEST_CASES)}] {tc['id']}"
            try:
                result = run_single_test(cfg, api_client, tc)
                run_results.append(result)
                per_case_results[tc["id"]].append(result["verdict"])
                icon = {"PASS": "PASS", "FAIL": "FAIL", "error": "ERR"}.get(result["verdict"] if result["verdict"] in ("PASS","FAIL") else "error", "???")
                print(f"  {label} {icon}  ({result['elapsed']:.1f}s)")
            except Exception as e:
                print(f"  {label} ERR ({e})")
                run_results.append({"test_id": tc["id"], "verdict": "ERROR", "status": "error", "error": str(e)})
                per_case_results[tc["id"]].append("ERROR")

        all_runs.append(run_results)
        print()
        print_run_summary(run_results, run)
        print()

    # Aggregate
    print("=" * 70)
    print("  AGGREGATE RESULTS")
    print("=" * 70)
    total_pass = 0
    total_fail = 0
    print(f"  {'Case':6s} {'Type':8s} {'Results':16s} {'Consistent?':10s}")
    print(f"  {'-'*42}")
    for tc in TEST_CASES:
        verdicts = per_case_results[tc["id"]]
        pass_count = verdicts.count("PASS")
        total_pass += pass_count
        total_fail += len(verdicts) - pass_count
        consistent = "YES" if len(set(verdicts)) == 1 else "NO"
        status_str = f"{pass_count}/{len(verdicts)} PASS"
        print(f"  {tc['id']:6s} {tc['type']:8s} {status_str:16s} {consistent:10s}")
        if not consistent:
            first_fail = next((r for r in all_runs if any(
                x["test_id"] == tc["id"] and x["verdict"] != "PASS" for x in r
            )), None)
            if first_fail:
                fb = next((x.get("composition_feedback") or {} for x in first_fail if x["test_id"] == tc["id"]), {})
                print(f"         reason: {fb.get('reason', 'N/A')}")

    total = len(TEST_CASES) * MAX_RUNS
    print(f"\n  Total: {total} | PASS: {total_pass} | FAIL: {total_fail} | Rate: {total_pass/total*100:.0f}%")

    # Save all
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = {
        "config": {"model": cfg.model, "temperature": cfg.temperature, "runs": MAX_RUNS},
        "summary": {
            "total_cases": len(TEST_CASES),
            "total_runs": MAX_RUNS,
            "total_executions": total,
            "total_pass": total_pass,
            "total_fail": total_fail,
            "pass_rate": f"{total_pass/total*100:.1f}%",
        },
        "per_case": {
            tc["id"]: {
                "type": tc["type"],
                "expect": tc["expect"],
                "description": tc["description"],
                "verdicts": per_case_results[tc["id"]],
                "consistent": len(set(per_case_results[tc["id"]])) == 1,
            } for tc in TEST_CASES
        },
        "runs": [
            {
                "run": r + 1,
                "results": all_runs[r],
            } for r in range(MAX_RUNS)
        ],
        "timestamp": datetime.now().isoformat(),
    }

    path = os.path.join(OUTPUT_DIR, f"formal_results_{timestamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nFull results saved to: {path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
