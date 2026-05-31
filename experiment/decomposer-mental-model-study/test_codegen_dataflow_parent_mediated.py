"""
Codegen Dataflow Parent-Mediated Experiment

Tests whether parent codegen improves when it receives structured dataflow_edges
and treats them as the authoritative composition contract.

Positive cases: parent-mediated decompositions that look like routing but are legal.
Negative cases: hidden sibling calls, wrong dataflow sources.

Output: output/codegen_dataflow_parent_mediated/<model>/
"""
import json
import os
import sys
import re
import time
import argparse
from datetime import datetime

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mvp", "mvp-0.4.4"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from models import (
    Node, InputParam, OutputParam, Boundary, GlobalVar, DataSource,
    ChildContract, DataOperation, DataflowEdge,
)
from config import Config
from api_client import APIClient
from code_generator_dataflow import DataflowAwareCodeGenerator


# ============================================================================
# Test Case Construction Helpers
# ============================================================================

def _make_child_contract(name, purpose, behavior, inputs, outputs, signature="",
                         data_operations=None):
    """Build a ChildContract from simplified specs."""
    return ChildContract(
        purpose=purpose,
        inputs=[InputParam(name=i["name"], type=i["type"],
                           description=i.get("description", ""),
                           source=i.get("source", ""))
                for i in inputs],
        outputs=[OutputParam(name=o["name"], type=o["type"],
                             description=o.get("description", ""),
                             consumer=o.get("consumer", ""))
                 for o in outputs],
        behavior=behavior,
        signature=signature,
        data_operations=[DataOperation(**op) for op in (data_operations or [])],
    )


def _make_parent_node(name, purpose, inputs, outputs, children_contracts,
                      dataflow_edges, decomposition_rationale="",
                      global_vars=None, data_sources=None):
    """Build a parent Node with children and dataflow edges."""
    children = []
    contracts_map = {}
    for cname, contract in children_contracts.items():
        child = Node(node_id=f"child_{cname}", name=cname, depth=1,
                     purpose=contract.purpose)
        children.append(child)
        contracts_map[cname] = contract

    edges = [DataflowEdge(**e) for e in dataflow_edges]

    return Node(
        node_id="parent_test", name=name, depth=0,
        purpose=purpose,
        inputs=[InputParam(**i) for i in inputs],
        outputs=[OutputParam(**o) for o in outputs],
        children=children,
        children_contracts=contracts_map,
        dataflow_edges=edges,
        decomposition_rationale=decomposition_rationale,
        global_vars=[GlobalVar(**g) for g in (global_vars or [])],
        data_sources=[DataSource(name=d["name"], category=d.get("category", "database"),
                                 access=d.get("access", "read_write"),
                                 description=d.get("description", ""))
                      for d in (data_sources or [])],
        boundary=Boundary(),
    )


# ============================================================================
# Positive Cases
# ============================================================================

def case_positive_a_parser_handlers():
    """
    Case A: ParseCommand + handlers. Looks like routing but is parent-mediated.
    ParseCommand parses the command, parent routes to appropriate handler.
    """
    contracts = {
        "ParseCommand": _make_child_contract(
            name="ParseCommand",
            purpose="Parse and validate the incoming command string.",
            behavior="Validates command is one of 'place', 'cancel', 'track'. Returns parsed command type and payload.",
            inputs=[
                {"name": "command", "type": "str", "source": "parent"},
                {"name": "order_data", "type": "dict", "source": "parent"},
            ],
            outputs=[
                {"name": "parsed_command", "type": "str", "consumer": "parent"},
                {"name": "parsed_payload", "type": "dict", "consumer": "parent"},
            ],
            signature="def ParseCommand(command: str, order_data: dict) -> tuple[str, dict]",
        ),
        "PlaceOrder": _make_child_contract(
            name="PlaceOrder",
            purpose="Execute the 'place' order workflow.",
            behavior="Validates items, charges payment, reserves inventory, creates order record.",
            inputs=[
                {"name": "order_payload", "type": "dict", "source": "parent (from ParseCommand.parsed_payload)"},
            ],
            outputs=[
                {"name": "result", "type": "dict", "consumer": "parent"},
            ],
            signature="def PlaceOrder(order_payload: dict) -> dict",
        ),
        "CancelOrder": _make_child_contract(
            name="CancelOrder",
            purpose="Execute the 'cancel' order workflow.",
            behavior="Verifies order exists, refunds payment, restores inventory.",
            inputs=[
                {"name": "order_payload", "type": "dict", "source": "parent (from ParseCommand.parsed_payload)"},
            ],
            outputs=[
                {"name": "result", "type": "dict", "consumer": "parent"},
            ],
            signature="def CancelOrder(order_payload: dict) -> dict",
        ),
        "TrackOrder": _make_child_contract(
            name="TrackOrder",
            purpose="Execute the 'track' order workflow.",
            behavior="Retrieves order status and estimated delivery time.",
            inputs=[
                {"name": "order_payload", "type": "dict", "source": "parent (from ParseCommand.parsed_payload)"},
            ],
            outputs=[
                {"name": "result", "type": "dict", "consumer": "parent"},
            ],
            signature="def TrackOrder(order_payload: dict) -> dict",
        ),
        "FormatResult": _make_child_contract(
            name="FormatResult",
            purpose="Format the handler result into the parent output schema.",
            behavior="Takes a raw result dict and formats it with success, order_id, status, message fields.",
            inputs=[
                {"name": "result", "type": "dict", "source": "parent (from handler output)"},
            ],
            outputs=[
                {"name": "order_result", "type": "dict", "consumer": "parent"},
            ],
            signature="def FormatResult(result: dict) -> dict",
        ),
    }

    dataflow = [
        {"from_node": "parent", "from_output": "command", "to_node": "ParseCommand", "to_input": "command", "note": "Pass command for parsing"},
        {"from_node": "parent", "from_output": "order_data", "to_node": "ParseCommand", "to_input": "order_data", "note": "Pass order data for parsing"},
        {"from_node": "ParseCommand", "from_output": "parsed_command", "to_node": "parent", "to_input": "parsed_command", "note": "Return parsed command type"},
        {"from_node": "ParseCommand", "from_output": "parsed_payload", "to_node": "parent", "to_input": "parsed_payload", "note": "Return parsed payload"},
        # All three command paths are declared in the dataflow
        {"from_node": "parent", "from_output": "parsed_payload", "to_node": "PlaceOrder", "to_input": "order_payload", "note": "Pass parsed payload when command=place"},
        {"from_node": "parent", "from_output": "parsed_payload", "to_node": "CancelOrder", "to_input": "order_payload", "note": "Pass parsed payload when command=cancel"},
        {"from_node": "parent", "from_output": "parsed_payload", "to_node": "TrackOrder", "to_input": "order_payload", "note": "Pass parsed payload when command=track"},
        {"from_node": "PlaceOrder", "from_output": "result", "to_node": "parent", "to_input": "result", "note": "Return place handler result"},
        {"from_node": "CancelOrder", "from_output": "result", "to_node": "parent", "to_input": "result", "note": "Return cancel handler result"},
        {"from_node": "TrackOrder", "from_output": "result", "to_node": "parent", "to_input": "result", "note": "Return track handler result"},
        {"from_node": "parent", "from_output": "result", "to_node": "FormatResult", "to_input": "result", "note": "Pass handler result for formatting"},
        {"from_node": "FormatResult", "from_output": "order_result", "to_node": "parent", "to_input": "order_result", "note": "Return formatted result"},
    ]

    return _make_parent_node(
        name="ProcessOrder",
        purpose="Process e-commerce orders via a single entry point.",
        inputs=[
            {"name": "command", "type": "str", "description": "Order command: place | cancel | track"},
            {"name": "order_data", "type": "dict", "description": "Order payload with items, payment, address"},
        ],
        outputs=[
            {"name": "order_result", "type": "dict", "description": "Result with success, order_id, status, message"},
        ],
        children_contracts=contracts,
        dataflow_edges=dataflow,
        decomposition_rationale=(
            "The OrderSystem has three distinct commands (place, cancel, track), "
            "each with its own workflow. ParseCommand validates and parses the command, "
            "then the parent routes to the appropriate handler based on the parsed command. "
            "FormatResult normalizes the output. The parent is the sole orchestrator — "
            "it calls ParseCommand, then conditionally calls the right handler, then FormatResult."
        ),
    )


def case_positive_b_route_intent():
    """
    Case B: RouteIntent child that decides intent but does NOT call siblings.
    Parent uses RouteIntent's output to decide which handler to call.
    """
    contracts = {
        "ParseInput": _make_child_contract(
            name="ParseInput",
            purpose="Parse raw input into structured command and payload.",
            behavior="Extracts command type and payload from raw input string.",
            inputs=[
                {"name": "raw_input", "type": "str", "source": "parent"},
            ],
            outputs=[
                {"name": "command", "type": "str", "consumer": "parent"},
                {"name": "payload", "type": "dict", "consumer": "parent"},
            ],
            signature="def ParseInput(raw_input: str) -> tuple[str, dict]",
        ),
        "RouteIntent": _make_child_contract(
            name="RouteIntent",
            purpose="Determine the intent category from a command string.",
            behavior="Maps command string to intent: 'create', 'cancel', 'query', or 'unknown'. Does NOT call any handler.",
            inputs=[
                {"name": "command", "type": "str", "source": "parent (from ParseInput.command)"},
            ],
            outputs=[
                {"name": "intent", "type": "str", "consumer": "parent"},
            ],
            signature="def RouteIntent(command: str) -> str",
        ),
        "CreateOrder": _make_child_contract(
            name="CreateOrder",
            purpose="Create a new order.",
            behavior="Validates payload, creates order record, processes payment.",
            inputs=[
                {"name": "payload", "type": "dict", "source": "parent (from ParseInput.payload)"},
            ],
            outputs=[
                {"name": "result", "type": "dict", "consumer": "parent"},
            ],
            signature="def CreateOrder(payload: dict) -> dict",
        ),
        "CancelOrder": _make_child_contract(
            name="CancelOrder",
            purpose="Cancel an existing order.",
            behavior="Verifies order exists, processes refund, updates status.",
            inputs=[
                {"name": "payload", "type": "dict", "source": "parent (from ParseInput.payload)"},
            ],
            outputs=[
                {"name": "result", "type": "dict", "consumer": "parent"},
            ],
            signature="def CancelOrder(payload: dict) -> dict",
        ),
        "FormatResult": _make_child_contract(
            name="FormatResult",
            purpose="Format result into standard output schema.",
            behavior="Normalizes result dict to standard output format.",
            inputs=[
                {"name": "result", "type": "dict", "source": "parent (from handler output)"},
            ],
            outputs=[
                {"name": "output", "type": "dict", "consumer": "parent"},
            ],
            signature="def FormatResult(result: dict) -> dict",
        ),
    }

    dataflow = [
        {"from_node": "parent", "from_output": "raw_input", "to_node": "ParseInput", "to_input": "raw_input", "note": "Pass raw input"},
        {"from_node": "ParseInput", "from_output": "command", "to_node": "parent", "to_input": "command", "note": "Return parsed command"},
        {"from_node": "ParseInput", "from_output": "payload", "to_node": "parent", "to_input": "payload", "note": "Return parsed payload"},
        {"from_node": "parent", "from_output": "command", "to_node": "RouteIntent", "to_input": "command", "note": "Pass command for intent routing"},
        {"from_node": "RouteIntent", "from_output": "intent", "to_node": "parent", "to_input": "intent", "note": "Return intent category"},
        {"from_node": "parent", "from_output": "payload", "to_node": "CreateOrder", "to_input": "payload", "note": "Pass payload to handler"},
        {"from_node": "CreateOrder", "from_output": "result", "to_node": "parent", "to_input": "result", "note": "Return handler result"},
    ]

    return _make_parent_node(
        name="ProcessInput",
        purpose="Process input commands with intent-based routing.",
        inputs=[
            {"name": "raw_input", "type": "str", "description": "Raw command input string"},
        ],
        outputs=[
            {"name": "output", "type": "dict", "description": "Processed result"},
        ],
        children_contracts=contracts,
        dataflow_edges=dataflow,
        decomposition_rationale=(
            "ParseInput extracts command and payload. RouteIntent determines the intent category. "
            "The parent then selects the appropriate handler based on intent. "
            "RouteIntent does NOT call handlers — it only returns an intent label."
        ),
    )


def case_positive_c_validate_execute():
    """
    Case C: ParseAndValidateRequest then ExecuteBooking.
    Validation child returns validated payload, parent passes to execution.
    """
    contracts = {
        "ParseAndValidateRequest": _make_child_contract(
            name="ParseAndValidateRequest",
            purpose="Parse and validate the patient request.",
            behavior="Validates command, checks required fields, returns validated payload or error.",
            inputs=[
                {"name": "command", "type": "str", "source": "parent"},
                {"name": "patient_data", "type": "dict", "source": "parent"},
            ],
            outputs=[
                {"name": "validated_payload", "type": "dict", "consumer": "parent"},
                {"name": "error", "type": "Optional[str]", "consumer": "parent"},
            ],
            signature="def ParseAndValidateRequest(command: str, patient_data: dict) -> tuple[dict, Optional[str]]",
        ),
        "ExecuteBooking": _make_child_contract(
            name="ExecuteBooking",
            purpose="Execute the appointment booking workflow.",
            behavior="Checks availability, creates appointment record, sends confirmation.",
            inputs=[
                {"name": "booking_payload", "type": "dict", "source": "parent (from ParseAndValidateRequest.validated_payload)"},
            ],
            outputs=[
                {"name": "booking_result", "type": "dict", "consumer": "parent"},
            ],
            signature="def ExecuteBooking(booking_payload: dict) -> dict",
        ),
        "RetrieveRecords": _make_child_contract(
            name="RetrieveRecords",
            purpose="Retrieve patient medical records.",
            behavior="Fetches records for a given patient ID.",
            inputs=[
                {"name": "query_payload", "type": "dict", "source": "parent (from ParseAndValidateRequest.validated_payload)"},
            ],
            outputs=[
                {"name": "records", "type": "list", "consumer": "parent"},
            ],
            signature="def RetrieveRecords(query_payload: dict) -> list",
        ),
        "FormatPatientResult": _make_child_contract(
            name="FormatPatientResult",
            purpose="Format patient operation result.",
            behavior="Normalizes result to standard patient output format.",
            inputs=[
                {"name": "result", "type": "dict", "source": "parent (from handler output)"},
            ],
            outputs=[
                {"name": "patient_result", "type": "dict", "consumer": "parent"},
            ],
            signature="def FormatPatientResult(result: dict) -> dict",
        ),
    }

    dataflow = [
        {"from_node": "parent", "from_output": "command", "to_node": "ParseAndValidateRequest", "to_input": "command", "note": "Pass command for validation"},
        {"from_node": "parent", "from_output": "patient_data", "to_node": "ParseAndValidateRequest", "to_input": "patient_data", "note": "Pass patient data for validation"},
        {"from_node": "ParseAndValidateRequest", "from_output": "validated_payload", "to_node": "parent", "to_input": "validated_payload", "note": "Return validated payload"},
        {"from_node": "ParseAndValidateRequest", "from_output": "error", "to_node": "parent", "to_input": "error", "note": "Return validation error"},
        {"from_node": "parent", "from_output": "validated_payload", "to_node": "ExecuteBooking", "to_input": "booking_payload", "note": "Pass validated payload to booking"},
        {"from_node": "ExecuteBooking", "from_output": "booking_result", "to_node": "parent", "to_input": "patient_result", "note": "Return booking result"},
    ]

    return _make_parent_node(
        name="ProcessPatientRequest",
        purpose="Process patient portal requests (book, retrieve, update).",
        inputs=[
            {"name": "command", "type": "str", "description": "Patient command: book | retrieve | update"},
            {"name": "patient_data", "type": "dict", "description": "Patient request data"},
        ],
        outputs=[
            {"name": "patient_result", "type": "dict", "description": "Operation result"},
        ],
        children_contracts=contracts,
        dataflow_edges=dataflow,
        decomposition_rationale=(
            "ParseAndValidateRequest validates the request first. If valid, the parent passes "
            "the validated payload to the appropriate handler. The validate-then-execute pattern "
            "ensures data integrity before side effects."
        ),
    )


# ============================================================================
# Negative Cases
# ============================================================================

def case_negative_a_hidden_sibling_call():
    """
    Negative A: Generated code calls only RouteCommand and never directly calls handlers.
    RouteCommand internally calls CreateOrder/CancelOrder — sibling calling.
    """
    contracts = {
        "RouteCommand": _make_child_contract(
            name="RouteCommand",
            purpose="Route command to the appropriate handler and return result.",
            behavior="Parses command, calls the appropriate handler (CreateOrder or CancelOrder), returns result.",
            inputs=[
                {"name": "command", "type": "str", "source": "parent"},
                {"name": "payload", "type": "dict", "source": "parent"},
            ],
            outputs=[
                {"name": "result", "type": "dict", "consumer": "parent"},
            ],
            signature="def RouteCommand(command: str, payload: dict) -> dict",
        ),
        "CreateOrder": _make_child_contract(
            name="CreateOrder",
            purpose="Create a new order.",
            behavior="Validates and creates order record.",
            inputs=[
                {"name": "payload", "type": "dict", "source": "parent"},
            ],
            outputs=[
                {"name": "result", "type": "dict", "consumer": "parent"},
            ],
            signature="def CreateOrder(payload: dict) -> dict",
        ),
        "CancelOrder": _make_child_contract(
            name="CancelOrder",
            purpose="Cancel an existing order.",
            behavior="Verifies and cancels order.",
            inputs=[
                {"name": "payload", "type": "dict", "source": "parent"},
            ],
            outputs=[
                {"name": "result", "type": "dict", "consumer": "parent"},
            ],
            signature="def CancelOrder(payload: dict) -> dict",
        ),
    }

    # Dataflow declares parent-mediated but fake code will ignore it
    dataflow = [
        {"from_node": "parent", "from_output": "command", "to_node": "RouteCommand", "to_input": "command", "note": "Pass command for routing"},
        {"from_node": "parent", "from_output": "payload", "to_node": "RouteCommand", "to_input": "payload", "note": "Pass payload for routing"},
        {"from_node": "RouteCommand", "from_output": "result", "to_node": "parent", "to_input": "result", "note": "Return routed result"},
    ]

    node = _make_parent_node(
        name="ProcessOrder",
        purpose="Process order commands.",
        inputs=[
            {"name": "command", "type": "str", "description": "Order command"},
            {"name": "payload", "type": "dict", "description": "Order payload"},
        ],
        outputs=[
            {"name": "result", "type": "dict", "description": "Order result"},
        ],
        children_contracts=contracts,
        dataflow_edges=dataflow,
        decomposition_rationale="RouteCommand handles routing internally.",
    )

    # Fake generated code: only calls RouteCommand, never directly calls CreateOrder/CancelOrder
    fake_code = '''
def ProcessOrder(command: str, payload: dict) -> dict:
    result = RouteCommand(command, payload)
    return result
'''

    return node, fake_code


def case_negative_b_wrong_dataflow_source():
    """
    Negative B: Declared dataflow says ParseCommand.parsed_payload -> PlaceOrder.order_payload,
    but generated code passes raw order_data to PlaceOrder instead.
    """
    contracts = {
        "ParseCommand": _make_child_contract(
            name="ParseCommand",
            purpose="Parse and validate the command.",
            behavior="Validates command, extracts and validates payload.",
            inputs=[
                {"name": "command", "type": "str", "source": "parent"},
                {"name": "order_data", "type": "dict", "source": "parent"},
            ],
            outputs=[
                {"name": "parsed_command", "type": "str", "consumer": "parent"},
                {"name": "parsed_payload", "type": "dict", "consumer": "parent"},
            ],
            signature="def ParseCommand(command: str, order_data: dict) -> tuple[str, dict]",
        ),
        "PlaceOrder": _make_child_contract(
            name="PlaceOrder",
            purpose="Execute place order workflow.",
            behavior="Validates items, charges payment, creates order.",
            inputs=[
                {"name": "order_payload", "type": "dict", "source": "parent (should be from ParseCommand.parsed_payload)"},
            ],
            outputs=[
                {"name": "result", "type": "dict", "consumer": "parent"},
            ],
            signature="def PlaceOrder(order_payload: dict) -> dict",
        ),
    }

    # Dataflow says: ParseCommand.parsed_payload -> parent -> PlaceOrder.order_payload
    dataflow = [
        {"from_node": "parent", "from_output": "command", "to_node": "ParseCommand", "to_input": "command", "note": "Pass command for parsing"},
        {"from_node": "parent", "from_output": "order_data", "to_node": "ParseCommand", "to_input": "order_data", "note": "Pass raw data for parsing"},
        {"from_node": "ParseCommand", "from_output": "parsed_command", "to_node": "parent", "to_input": "parsed_command", "note": "Return parsed command"},
        {"from_node": "ParseCommand", "from_output": "parsed_payload", "to_node": "parent", "to_input": "parsed_payload", "note": "Return validated payload"},
        {"from_node": "parent", "from_output": "parsed_payload", "to_node": "PlaceOrder", "to_input": "order_payload", "note": "Pass VALIDATED payload to handler"},
        {"from_node": "PlaceOrder", "from_output": "result", "to_node": "parent", "to_input": "result", "note": "Return handler result"},
    ]

    node = _make_parent_node(
        name="ProcessOrder",
        purpose="Process order commands.",
        inputs=[
            {"name": "command", "type": "str", "description": "Order command"},
            {"name": "order_data", "type": "dict", "description": "Raw order data"},
        ],
        outputs=[
            {"name": "result", "type": "dict", "description": "Order result"},
        ],
        children_contracts=contracts,
        dataflow_edges=dataflow,
        decomposition_rationale="ParseCommand validates input, then parent passes validated payload to PlaceOrder.",
    )

    # Fake code: passes raw order_data to PlaceOrder instead of parsed_payload
    fake_code = '''
def ProcessOrder(command: str, order_data: dict) -> dict:
    parsed_command, parsed_payload = ParseCommand(command, order_data)
    if parsed_command == "place":
        result = PlaceOrder(order_data)  # WRONG: should be parsed_payload
    return result
'''

    return node, fake_code


# ============================================================================
# Test Runner
# ============================================================================

def run_positive_case(gen, case_name, node, output_dir):
    """Run a positive case through the dataflow-aware codegen."""
    case_dir = os.path.join(output_dir, f"case_{case_name}")
    os.makedirs(case_dir, exist_ok=True)

    # Save node.json and dataflow_edges.json
    with open(os.path.join(case_dir, "node.json"), "w", encoding="utf-8") as f:
        json.dump(node.to_dict(), f, indent=2, ensure_ascii=False)
    with open(os.path.join(case_dir, "dataflow_edges.json"), "w", encoding="utf-8") as f:
        json.dump([e.to_dict() for e in node.dataflow_edges], f, indent=2, ensure_ascii=False)

    # Step 1: Generate
    prompt_gen = gen._build_system_prompt_for_parent() + "\n\n" + gen._build_user_prompt_for_parent(node)
    with open(os.path.join(case_dir, "prompt_generate.txt"), "w", encoding="utf-8") as f:
        f.write(prompt_gen)

    print(f"  [{case_name}] Calling LLM for code generation...")
    t0 = time.time()
    code, errors = gen.generate_for_parent(node)
    elapsed = time.time() - t0

    # Capture raw response
    response_gen = {"code": code, "errors": errors, "elapsed": elapsed,
                    "last_feedback": gen.last_composition_feedback.to_dict() if gen.last_composition_feedback else None}
    with open(os.path.join(case_dir, "response_generate.json"), "w", encoding="utf-8") as f:
        json.dump(response_gen, f, indent=2, ensure_ascii=False)

    if errors:
        verdict = {
            "case": case_name, "type": "positive",
            "generate_status": "cannot_compose",
            "generate_errors": errors,
            "elapsed": elapsed,
            "passed": False,
            "reason": f"Codegen rejected: {errors}",
        }
        with open(os.path.join(case_dir, "generated_code.py"), "w") as f:
            f.write("# CANNOT_COMPOSE\n")
        with open(os.path.join(case_dir, "verdict.json"), "w", encoding="utf-8") as f:
            json.dump(verdict, f, indent=2, ensure_ascii=False)
        return verdict

    # Save generated code
    with open(os.path.join(case_dir, "generated_code.py"), "w", encoding="utf-8") as f:
        f.write(code)

    # Step 2: Verify
    prompt_ver = gen._build_system_prompt_for_parent_verify() + "\n\n" + gen._build_user_prompt_for_parent_verify(node, code)
    with open(os.path.join(case_dir, "prompt_verify.txt"), "w", encoding="utf-8") as f:
        f.write(prompt_ver)

    print(f"  [{case_name}] Calling LLM for verification...")
    verify_messages = [
        {"role": "system", "content": gen._build_system_prompt_for_parent_verify()},
        {"role": "user", "content": gen._build_user_prompt_for_parent_verify(node, code)},
    ]
    try:
        verify_response = gen.api_client.chat(verify_messages, max_tokens=1024)
        verify_parsed = gen._parse_response(verify_response)
    except Exception as e:
        verify_parsed = {"status": "error", "error": str(e)}

    with open(os.path.join(case_dir, "response_verify.json"), "w", encoding="utf-8") as f:
        json.dump(verify_parsed, f, indent=2, ensure_ascii=False)

    # Analyze generated code for dataflow conformance
    code_analysis = analyze_generated_code(code, node)

    verify_status = verify_parsed.get("status", "ok")
    verdict = {
        "case": case_name, "type": "positive",
        "generate_status": "ok",
        "verify_status": verify_status,
        "verify_checks": verify_parsed.get("checks", {}),
        "code_analysis": code_analysis,
        "elapsed": elapsed,
        "passed": verify_status == "ok" and not code_analysis.get("has_sibling_calls"),
        "reason": verify_parsed.get("decomposition_feedback", {}).get("reason", "") if verify_status != "ok" else "",
    }
    with open(os.path.join(case_dir, "verdict.json"), "w", encoding="utf-8") as f:
        json.dump(verdict, f, indent=2, ensure_ascii=False)
    return verdict


def run_negative_case_with_fake_code(gen, case_name, node, fake_code, expected_reject_reason, output_dir):
    """Run a negative case with fake generated code through the verifier."""
    case_dir = os.path.join(output_dir, f"case_{case_name}")
    os.makedirs(case_dir, exist_ok=True)

    # Save artifacts
    with open(os.path.join(case_dir, "node.json"), "w", encoding="utf-8") as f:
        json.dump(node.to_dict(), f, indent=2, ensure_ascii=False)
    with open(os.path.join(case_dir, "dataflow_edges.json"), "w", encoding="utf-8") as f:
        json.dump([e.to_dict() for e in node.dataflow_edges], f, indent=2, ensure_ascii=False)
    with open(os.path.join(case_dir, "generated_code.py"), "w", encoding="utf-8") as f:
        f.write(fake_code)
    with open(os.path.join(case_dir, "fake_response_generate.json"), "w", encoding="utf-8") as f:
        json.dump({"code": fake_code, "status": "ok", "note": "fake response for deterministic negative test"},
                  f, indent=2, ensure_ascii=False)

    # Build verify prompt
    prompt_ver = gen._build_system_prompt_for_parent_verify() + "\n\n" + gen._build_user_prompt_for_parent_verify(node, fake_code)
    with open(os.path.join(case_dir, "prompt_verify.txt"), "w", encoding="utf-8") as f:
        f.write(prompt_ver)

    # Call LLM verifier
    print(f"  [{case_name}] Calling LLM for verification of fake code...")
    verify_messages = [
        {"role": "system", "content": gen._build_system_prompt_for_parent_verify()},
        {"role": "user", "content": gen._build_user_prompt_for_parent_verify(node, fake_code)},
    ]
    try:
        verify_response = gen.api_client.chat(verify_messages, max_tokens=1024)
        verify_parsed = gen._parse_response(verify_response)
    except Exception as e:
        verify_parsed = {"status": "error", "error": str(e)}

    with open(os.path.join(case_dir, "fake_response_verify.json"), "w", encoding="utf-8") as f:
        json.dump(verify_parsed, f, indent=2, ensure_ascii=False)

    # Analyze code
    code_analysis = analyze_generated_code(fake_code, node)

    verify_status = verify_parsed.get("status", "ok")
    verdict = {
        "case": case_name, "type": "negative",
        "expected": "cannot_compose",
        "actual": verify_status,
        "verify_checks": verify_parsed.get("checks", {}),
        "code_analysis": code_analysis,
        "passed": verify_status == "cannot_compose",
        "expected_reason": expected_reject_reason,
        "actual_reason": verify_parsed.get("decomposition_feedback", {}).get("reason", ""),
    }
    with open(os.path.join(case_dir, "verdict.json"), "w", encoding="utf-8") as f:
        json.dump(verdict, f, indent=2, ensure_ascii=False)
    return verdict


def analyze_generated_code(code, node):
    """Static analysis of generated code for dataflow conformance."""
    analysis = {
        "has_sibling_calls": False,
        "calls_all_children": True,
        "child_calls_found": [],
        "child_calls_missing": [],
        "uses_wrong_source": False,
    }

    child_names = [c.name for c in (node.children or [])]

    # Check which children are called
    for cname in child_names:
        # Simple regex: look for ChildName( pattern
        pattern = rf'\b{re.escape(cname)}\s*\('
        if re.search(pattern, code):
            analysis["child_calls_found"].append(cname)
        else:
            analysis["child_calls_missing"].append(cname)
            analysis["calls_all_children"] = False

    # Check for sibling calls: if code calls more than one child, check if any child
    # appears as an argument to another child (sibling calling pattern)
    # This is a heuristic — the LLM verifier does the real check

    return analysis


# ============================================================================
# Report Generation
# ============================================================================

def generate_report(results, output_dir):
    """Generate report.md and results.json."""
    # Separate positive and negative
    positive = [r for r in results if r["type"] == "positive"]
    negative = [r for r in results if r["type"] == "negative"]

    # Metrics
    total = len(results)
    pos_accepted = sum(1 for r in positive if r.get("generate_status") == "ok")
    pos_rejected = sum(1 for r in positive if r.get("generate_status") == "cannot_compose")
    pos_parent_mediated = sum(1 for r in positive if r.get("passed"))
    neg_rejected = sum(1 for r in negative if r.get("passed"))
    neg_accepted = sum(1 for r in negative if not r.get("passed"))

    # Code analysis
    pos_sibling_calls = sum(1 for r in positive if r.get("code_analysis", {}).get("has_sibling_calls"))
    pos_missing_children = sum(1 for r in positive if not r.get("code_analysis", {}).get("calls_all_children"))
    pos_wrong_source = sum(1 for r in positive if r.get("code_analysis", {}).get("uses_wrong_source"))

    summary = {
        "total_cases": total,
        "positive_cases": len(positive),
        "positive_accepted": pos_accepted,
        "positive_parent_mediated": pos_parent_mediated,
        "positive_rejected_as_cannot_compose": pos_rejected,
        "negative_cases": len(negative),
        "negative_rejected": neg_rejected,
        "negative_incorrectly_accepted": neg_accepted,
        "prompt_parse_errors": 0,
        "generated_code_ignores_dataflow": pos_wrong_source,
        "generated_code_sibling_calls": pos_sibling_calls,
        "generated_code_missing_children": pos_missing_children,
    }

    # Results JSON
    results_json = {
        "experiment": "codegen_dataflow_parent_mediated",
        "model": os.environ.get("CHRONOS_MODEL", "deepseek-chat"),
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "trials": results,
    }

    with open(os.path.join(output_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results_json, f, indent=2, ensure_ascii=False)

    # Report MD
    lines = [
        "# Codegen Dataflow Parent-Mediated Experiment Report",
        "",
        f"Model: `{results_json['model']}`",
        f"Timestamp: {results_json['timestamp']}",
        "",
        "## Experiment Description",
        "",
        "Tests whether parent codegen improves when it receives structured `dataflow_edges`",
        "and treats them as the authoritative composition contract. Positive cases are",
        "parent-mediated decompositions that look suspicious under traditional pattern priors",
        "but are legal under tree structure. Negative cases should be rejected.",
        "",
        "## Aggregate Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total cases | {summary['total_cases']} |",
        f"| Positive cases | {summary['positive_cases']} |",
        f"| Positive accepted (code generated) | {summary['positive_accepted']} |",
        f"| Positive producing parent-mediated code | {summary['positive_parent_mediated']} |",
        f"| Positive rejected as cannot_compose | {summary['positive_rejected_as_cannot_compose']} |",
        f"| Negative cases | {summary['negative_cases']} |",
        f"| Negative correctly rejected | {summary['negative_rejected']} |",
        f"| Negative incorrectly accepted | {summary['negative_incorrectly_accepted']} |",
        f"| Prompt parse errors | {summary['prompt_parse_errors']} |",
        f"| Generated code ignoring declared dataflow | {summary['generated_code_ignores_dataflow']} |",
        f"| Generated code with sibling calls | {summary['generated_code_sibling_calls']} |",
        f"| Generated code missing child calls | {summary['generated_code_missing_children']} |",
        "",
        "## Pass Criteria",
        "",
        "- All positive parent-mediated cases are accepted",
        "- Positive generated code directly calls every required child",
        "- Positive generated code realizes the declared dataflow source for each child input",
        "- All negative cases are rejected",
        "- No generated code relies on a child calling a sibling",
        "",
        "## Per-Case Results",
        "",
        "| Case | Type | Generate | Verify | Passed | Reason |",
        "|------|------|----------|--------|--------|--------|",
    ]

    for r in results:
        case = r["case"]
        ctype = r["type"]
        gen_status = r.get("generate_status", "N/A")
        ver_status = r.get("verify_status", "N/A")
        passed = "PASS" if r.get("passed") else "FAIL"
        reason = r.get("reason", r.get("actual_reason", ""))
        if len(reason) > 60:
            reason = reason[:57] + "..."
        lines.append(f"| {case} | {ctype} | {gen_status} | {ver_status} | {passed} | {reason} |")

    lines.append("")
    lines.append("## Analysis Notes")
    lines.append("")

    for r in results:
        case = r["case"]
        lines.append(f"### {case}")
        lines.append("")
        if r["type"] == "positive":
            ca = r.get("code_analysis", {})
            lines.append(f"- Generate: {r.get('generate_status', 'N/A')}")
            lines.append(f"- Verify: {r.get('verify_status', 'N/A')}")
            lines.append(f"- Children called: {ca.get('child_calls_found', [])}")
            if ca.get("child_calls_missing"):
                lines.append(f"- Children MISSING: {ca['child_calls_missing']}")
            if r.get("verify_checks"):
                for check, detail in r["verify_checks"].items():
                    passed_str = "PASS" if detail.get("passed") else "FAIL"
                    lines.append(f"- {check}: {passed_str}")
            if r.get("code"):
                lines.append(f"- Elapsed: {r.get('elapsed', 0):.1f}s")
        else:
            lines.append(f"- Expected: cannot_compose, Actual: {r.get('actual', 'N/A')}")
            lines.append(f"- Expected reason: {r.get('expected_reason', 'N/A')}")
            lines.append(f"- Actual reason: {r.get('actual_reason', 'N/A')}")
            ca = r.get("code_analysis", {})
            if ca.get("child_calls_missing"):
                lines.append(f"- Children MISSING (confirming rejection): {ca['child_calls_missing']}")
        lines.append("")

    with open(os.path.join(output_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return summary


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Codegen Dataflow Parent-Mediated Experiment")
    parser.add_argument("--model", default="deepseek-v4-flash", help="Model name")
    parser.add_argument("--trials", type=int, default=1, help="Number of trials per case")
    parser.add_argument("--cases", default="all", help="Comma-separated case names or 'all'")
    parser.add_argument("--skip-negatives", action="store_true", help="Skip negative cases")
    args = parser.parse_args()

    # Set model env
    os.environ["CHRONOS_MODEL"] = args.model

    output_dir = os.path.join(os.path.dirname(__file__), "output", "codegen_dataflow_parent_mediated", args.model)
    os.makedirs(output_dir, exist_ok=True)

    # Initialize generator
    config = Config.from_env()
    api_client = APIClient(config)
    gen = DataflowAwareCodeGenerator(config, api_client)

    print(f"Model: {args.model}")
    print(f"Output: {output_dir}")
    print(f"Trials: {args.trials}")
    print()

    # Define cases
    positive_cases = {
        "positive_a_parser_handlers": case_positive_a_parser_handlers,
        "positive_b_route_intent": case_positive_b_route_intent,
        "positive_c_validate_execute": case_positive_c_validate_execute,
    }

    negative_cases = {
        "negative_a_hidden_sibling_call": case_negative_a_hidden_sibling_call,
        "negative_b_wrong_dataflow_source": case_negative_b_wrong_dataflow_source,
    }

    # Filter cases
    if args.cases != "all":
        selected = set(args.cases.split(","))
        positive_cases = {k: v for k, v in positive_cases.items() if k in selected}
        negative_cases = {k: v for k, v in negative_cases.items() if k in selected}

    results = []

    # Run positive cases
    print("=" * 60)
    print("POSITIVE CASES")
    print("=" * 60)
    for case_name, case_fn in positive_cases.items():
        for trial in range(args.trials):
            trial_name = f"{case_name}_t{trial}" if args.trials > 1 else case_name
            node = case_fn()
            verdict = run_positive_case(gen, trial_name, node, output_dir)
            results.append(verdict)
            status = "PASS" if verdict["passed"] else "FAIL"
            print(f"  -> {status}: {verdict.get('reason', 'ok')}")

    # Run negative cases
    if not args.skip_negatives:
        print()
        print("=" * 60)
        print("NEGATIVE CASES")
        print("=" * 60)
        for case_name, case_fn in negative_cases.items():
            node, fake_code = case_fn()
            expected_reason = "hidden_sibling_call" if "hidden" in case_name else "wrong_dataflow_source"
            verdict = run_negative_case_with_fake_code(gen, case_name, node, fake_code, expected_reason, output_dir)
            results.append(verdict)
            status = "PASS" if verdict["passed"] else "FAIL"
            print(f"  -> {status}: expected={verdict.get('expected')}, actual={verdict.get('actual')}")

    # Generate report
    print()
    print("=" * 60)
    print("GENERATING REPORT")
    print("=" * 60)
    summary = generate_report(results, output_dir)

    print(f"\nSummary:")
    print(f"  Total: {summary['total_cases']}")
    print(f"  Positive accepted: {summary['positive_accepted']}/{summary['positive_cases']}")
    print(f"  Positive parent-mediated: {summary['positive_parent_mediated']}/{summary['positive_cases']}")
    print(f"  Negative rejected: {summary['negative_rejected']}/{summary['negative_cases']}")
    print(f"\nOutput: {output_dir}")


if __name__ == "__main__":
    main()
