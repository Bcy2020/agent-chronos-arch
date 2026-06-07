"""
Unit tests for three-stage decomposition (MVP 0.4.4).

Tests prompt correctness, merge logic, and staged flow with mock API.
Does NOT require a real LLM — uses stub responses for integration path tests.
"""
import json
import os
import sys
import unittest
from typing import Any, Dict, List
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from api_client import APIClient
from decomposer import Decomposer
from models import (
    Node, InputParam, OutputParam, Boundary, GlobalVar,
    DataSource, ChildContract, DataOperation, DataflowEdge, SubPRD,
)


def make_test_node(name="TestRoot", purpose="Test parent function", with_globals=False):
    """Build a minimal test Node for decomposition."""
    node = Node(
        node_id="root_0",
        name=name,
        depth=0,
        purpose=purpose,
        inputs=[InputParam(name="request", type="dict", description="Input request")],
        outputs=[OutputParam(name="response", type="dict", description="Output response")],
        boundary=Boundary(in_scope=["process request"], out_of_scope=["external API"]),
        data_sources=[
            DataSource(name="orders", category="database", access="read_write", description="Orders store"),
        ],
    )
    if with_globals:
        node.global_vars = [
            GlobalVar(variable="orders", op="read_write", description="Orders data"),
        ]
    return node


# ---- Mock Stage 2 output ----
MOCK_STAGE1 = {
    "children": [
        {
            "name": "ParseInput",
            "purpose": "Parse and validate the incoming request",
            "behavior": "Extract command and payload from request dict",
            "boundary": {"in_scope": ["request parsing"], "out_of_scope": ["business logic"]},
            "semantic_inputs": [
                {"name": "request", "description": "Raw request", "source": "parent input"},
            ],
            "semantic_outputs": [
                {"name": "parsed_command", "description": "Parsed command name", "consumer": "parent"},
                {"name": "parsed_payload", "description": "Parsed payload data", "consumer": "parent"},
            ],
            "preconditions": ["request is a dict"],
            "postconditions": ["parsed_command is a string"],
            "guarantees": ["outputs are validated"],
            "composition_role": "transform",
            "stop_decompose": False,
            "stop_reason": "",
        },
        {
            "name": "ExecuteCommand",
            "purpose": "Execute the parsed command",
            "behavior": "Perform the business logic for the given command",
            "boundary": {"in_scope": ["command execution"], "out_of_scope": ["input parsing"]},
            "semantic_inputs": [
                {"name": "command", "description": "Command to execute", "source": "previous child output"},
                {"name": "payload", "description": "Payload data", "source": "previous child output"},
                {"name": "orders", "description": "Orders database", "source": "internal leaf access"},
            ],
            "semantic_outputs": [
                {"name": "result", "description": "Execution result", "consumer": "parent"},
            ],
            "preconditions": ["command is valid"],
            "postconditions": ["result contains execution data"],
            "guarantees": ["orders accessed correctly"],
            "composition_role": "execute",
            "stop_decompose": False,
            "stop_reason": "",
        },
    ],
    "decomposition_rationale": "Parse then execute pattern",
    "orchestration_model": "conditional",
    "dataflow_sketch": [
        {"from": "parent", "to": "ParseInput", "data": "request", "note": "Pass input"},
        {"from": "ParseInput", "to": "parent", "data": "parsed_command", "note": "Return to parent"},
        {"from": "ParseInput", "to": "parent", "data": "parsed_payload", "note": "Return to parent"},
        {"from": "parent", "to": "ExecuteCommand", "data": "parsed_command", "note": "Parent mediates to executor"},
        {"from": "parent", "to": "ExecuteCommand", "data": "parsed_payload", "note": "Parent mediates to executor"},
        {"from": "ExecuteCommand", "to": "parent", "data": "result", "note": "Return to parent"},
    ],
}

MOCK_STAGE2 = {
    "children": [
        {
            "name": "ParseInput",
            "purpose": "(UNCHANGED)",
            "behavior": "(UNCHANGED)",
            "boundary": {"in_scope": ["(UNCHANGED)"], "out_of_scope": ["(UNCHANGED)"]},
            "preconditions": ["(UNCHANGED)"],
            "postconditions": ["(UNCHANGED)"],
            "guarantees": ["(UNCHANGED)"],
            "composition_role": "(UNCHANGED)",
            "stop_decompose": False,
            "stop_reason": "",
            "inputs": [
                {"name": "request", "type": "dict", "description": "Raw request", "source": "parent"},
            ],
            "outputs": [
                {"name": "parsed_command", "type": "str", "description": "Parsed command", "consumer": "parent"},
                {"name": "parsed_payload", "type": "dict", "description": "Parsed payload", "consumer": "parent"},
            ],
            "signature": "def ParseInput(request: dict) -> tuple[str, dict]",
        },
        {
            "name": "ExecuteCommand",
            "purpose": "(UNCHANGED)",
            "behavior": "(UNCHANGED)",
            "boundary": {"in_scope": ["(UNCHANGED)"], "out_of_scope": ["(UNCHANGED)"]},
            "preconditions": ["(UNCHANGED)"],
            "postconditions": ["(UNCHANGED)"],
            "guarantees": ["(UNCHANGED)"],
            "composition_role": "(UNCHANGED)",
            "stop_decompose": False,
            "stop_reason": "",
            "inputs": [
                {"name": "command", "type": "str", "description": "Command name", "source": "parent"},
                {"name": "payload", "type": "dict", "description": "Payload", "source": "parent"},
            ],
            "outputs": [
                {"name": "result", "type": "dict", "description": "Result", "consumer": "parent"},
            ],
            "signature": "def ExecuteCommand(command: str, payload: dict) -> dict",
        },
    ],
    "interface_preservation": {
        "parent_inputs_covered_by": {"request": "ParseInput"},
        "parent_outputs_produced_by": {"response": "ExecuteCommand"},
    },
    "dataflow_edges": [
        {"from_node": "parent", "from_output": "request", "to_node": "ParseInput", "to_input": "request", "note": "Pass input"},
        {"from_node": "ParseInput", "from_output": "parsed_command", "to_node": "parent", "to_input": "", "note": "Return"},
        {"from_node": "parent", "from_output": "parsed_command", "to_node": "ExecuteCommand", "to_input": "command", "note": "Parent mediates"},
    ],
}

MOCK_STAGE3 = {
    "children": [
        {
            "name": "ParseInput",
            "purpose": "(UNCHANGED)",
            "behavior": "(UNCHANGED)",
            "inputs": ["(UNCHANGED)"],
            "outputs": ["(UNCHANGED)"],
            "signature": "(UNCHANGED)",
            "global_vars": [],
            "data_operations": [],
            "requested_capabilities": [],
            "constraints": [],
            "acceptance_criteria": [],
            "traceability": {"parent_requirement_ids": ["FR-001"]},
            "node_type": "pure_function",
            "stop_decompose": False,
            "stop_reason": "",
        },
        {
            "name": "ExecuteCommand",
            "purpose": "(UNCHANGED)",
            "behavior": "(UNCHANGED)",
            "inputs": ["(UNCHANGED)"],
            "outputs": ["(UNCHANGED)"],
            "signature": "(UNCHANGED)",
            "global_vars": [
                {"variable": "orders", "op": "read_write", "description": "Access orders data"},
            ],
            "data_operations": [
                {"source_name": "orders", "operation_type": "read_write", "description": "Read and update orders"},
            ],
            "requested_capabilities": [],
            "constraints": [],
            "acceptance_criteria": [],
            "traceability": {"parent_requirement_ids": ["FR-001"]},
            "node_type": "atomic_operation",
            "stop_decompose": False,
            "stop_reason": "",
        },
    ],
    "governance_notes": "orders read_write covered by ExecuteCommand",
}


class TestMergeStagedOutputs(unittest.TestCase):
    """Test the _merge_staged_outputs method."""

    def setUp(self):
        self.config = Config()
        self.decomposer = Decomposer(self.config, None)

    def test_merge_preserves_child_names(self):
        merged = self.decomposer._merge_staged_outputs(MOCK_STAGE1, MOCK_STAGE2, MOCK_STAGE3)
        children = merged["children"]
        self.assertEqual(len(children), 2)
        self.assertEqual(children[0]["name"], "ParseInput")
        self.assertEqual(children[1]["name"], "ExecuteCommand")

    def test_merge_preserves_stage1_structure(self):
        merged = self.decomposer._merge_staged_outputs(MOCK_STAGE1, MOCK_STAGE2, MOCK_STAGE3)
        parse_child = merged["children"][0]
        self.assertEqual(parse_child["purpose"], "Parse and validate the incoming request")
        self.assertEqual(parse_child["behavior"], "Extract command and payload from request dict")
        self.assertEqual(parse_child["composition_role"], "transform")

    def test_merge_overrides_with_stage2_interfaces(self):
        merged = self.decomposer._merge_staged_outputs(MOCK_STAGE1, MOCK_STAGE2, MOCK_STAGE3)
        parse_child = merged["children"][0]
        self.assertIn("inputs", parse_child)
        self.assertIn("signature", parse_child)
        self.assertEqual(parse_child["signature"], "def ParseInput(request: dict) -> tuple[str, dict]")

    def test_merge_overrides_with_stage3_resources(self):
        merged = self.decomposer._merge_staged_outputs(MOCK_STAGE1, MOCK_STAGE2, MOCK_STAGE3)
        exec_child = merged["children"][1]
        self.assertIn("global_vars", exec_child)
        self.assertEqual(len(exec_child["global_vars"]), 1)
        self.assertEqual(exec_child["global_vars"][0]["variable"], "orders")
        self.assertEqual(exec_child["node_type"], "atomic_operation")

    def test_merge_includes_dataflow_edges(self):
        merged = self.decomposer._merge_staged_outputs(MOCK_STAGE1, MOCK_STAGE2, MOCK_STAGE3)
        self.assertIn("dataflow_edges", merged)
        self.assertEqual(len(merged["dataflow_edges"]), 3)

    def test_merge_fallback_dataflow_sketch(self):
        stage2_no_edges = dict(MOCK_STAGE2)
        stage2_no_edges["dataflow_edges"] = []
        merged = self.decomposer._merge_staged_outputs(MOCK_STAGE1, stage2_no_edges, MOCK_STAGE3)
        # Should use dataflow_sketch from Stage 1 as fallback
        self.assertIn("dataflow_edges", merged)
        self.assertGreater(len(merged["dataflow_edges"]), 0)

    def test_merge_ensures_stop_fields(self):
        s3_no_stop = dict(MOCK_STAGE3)
        for c in s3_no_stop["children"]:
            c.pop("stop_decompose", None)
            c.pop("stop_reason", None)
        merged = self.decomposer._merge_staged_outputs(MOCK_STAGE1, MOCK_STAGE2, s3_no_stop)
        for c in merged["children"]:
            self.assertIn("stop_decompose", c)
            self.assertIn("stop_reason", c)


class TestStagePrompts(unittest.TestCase):
    """Test that stage prompts contain expected content and exclude forbidden fields."""

    def setUp(self):
        self.config = Config()
        self.decomposer = Decomposer(self.config, None)
        self.node = make_test_node(with_globals=True)

    def test_stage1_prompt_excludes_interface_fields(self):
        prompt = self.decomposer._build_stage1_system_prompt()
        # Should NOT instruct LLM to output Stage 2/3 fields
        self.assertNotIn('"inputs"', prompt.split("OUTPUT FORMAT")[0] if "OUTPUT FORMAT" in prompt else prompt[:1000])

    def test_stage1_user_prompt_includes_context(self):
        prompt = self.decomposer._build_stage1_user_prompt(self.node)
        self.assertIn("TestRoot", prompt)
        self.assertIn("request: dict", prompt)
        self.assertIn("response: dict", prompt)
        self.assertIn("orders", prompt)

    def test_stage2_prompt_references_frozen_children(self):
        prompt = self.decomposer._build_stage2_system_prompt()
        self.assertIn("LOCKED", prompt)
        self.assertIn("UNCHANGED", prompt)
        self.assertTrue(
            "call input" in prompt.lower()
            or "LOCKED" in prompt
        )

    def test_stage3_prompt_includes_conservation(self):
        prompt = self.decomposer._build_stage3_system_prompt()
        self.assertIn("GLOBAL STATE CONSERVATION", prompt)
        self.assertIn("SELF-CHECK", prompt)

    def test_stage3_user_prompt_includes_conservation_ledger(self):
        prompt = self.decomposer._build_stage3_user_prompt(self.node, MOCK_STAGE1, MOCK_STAGE2)
        self.assertIn("CONSERVATION LEDGER", prompt)
        self.assertIn("orders", prompt)
        self.assertIn("read_write", prompt)


class TestFormatPreviousErrors(unittest.TestCase):
    """Test the _format_previous_errors helper."""

    def setUp(self):
        self.config = Config()
        self.decomposer = Decomposer(self.config, None)

    def test_dict_format(self):
        errors = {
            "previous_children": ["ChildA", "ChildB"],
            "previous_errors": ["Missing source for input X"],
            "validator_report": {
                "unused_children": ["ChildB"],
            },
        }
        output = self.decomposer._format_previous_errors(errors)
        self.assertIn("ChildA", output)
        self.assertIn("Missing source", output)
        self.assertIn("ChildB", output)

    def test_list_format(self):
        errors = ["API call failed", "JSON parse error"]
        output = self.decomposer._format_previous_errors(errors)
        self.assertIn("API call failed", output)
        self.assertIn("JSON parse error", output)


class TestStagedDecomposeIntegration(unittest.TestCase):
    """Integration test for decompose_staged with mock API responses."""

    def setUp(self):
        self.config = Config()
        self.api_client = MagicMock(spec=APIClient)
        self.decomposer = Decomposer(self.config, self.api_client)
        self.node = make_test_node(with_globals=True)

    def test_decompose_staged_calls_api_three_times(self):
        """Verify decompose_staged makes exactly 3 API calls."""
        # Return valid JSON for each stage
        self.api_client.chat.side_effect = [
            json.dumps(MOCK_STAGE1),
            json.dumps(MOCK_STAGE2),
            json.dumps(MOCK_STAGE3),
        ]
        node, errors = self.decomposer.decompose_staged(self.node)
        self.assertEqual(self.api_client.chat.call_count, 3)
        self.assertEqual(errors, [])
        self.assertEqual(len(node.children), 2)
        self.assertEqual(node.children[0].name, "ParseInput")
        self.assertEqual(node.children[1].name, "ExecuteCommand")

    def test_decompose_staged_preserves_dataflow_edges(self):
        self.api_client.chat.side_effect = [
            json.dumps(MOCK_STAGE1),
            json.dumps(MOCK_STAGE2),
            json.dumps(MOCK_STAGE3),
        ]
        node, errors = self.decomposer.decompose_staged(self.node)
        self.assertEqual(errors, [])
        self.assertGreater(len(node.dataflow_edges), 0)
        # Edges should have correct structure
        for edge in node.dataflow_edges:
            self.assertTrue(hasattr(edge, 'from_node'))
            self.assertTrue(hasattr(edge, 'to_node'))

    def test_decompose_staged_handles_stage1_parse_failure(self):
        """Stage 1 parse failure with no children should return error."""
        self.api_client.chat.return_value = "{invalid json"
        node, errors = self.decomposer.decompose_staged(self.node)
        # Stage 1 failure with no children = error
        self.assertTrue(len(errors) > 0)

    def test_decompose_staged_saves_messages_on_node(self):
        self.api_client.chat.side_effect = [
            json.dumps(MOCK_STAGE1),
            json.dumps(MOCK_STAGE2),
            json.dumps(MOCK_STAGE3),
        ]
        node, errors = self.decomposer.decompose_staged(self.node)
        self.assertEqual(errors, [])
        self.assertTrue(hasattr(node, '_staged_messages'))
        self.assertGreater(len(node._staged_messages), 0)
        # Messages should contain system + 3 user + 3 assistant = 7 messages for the user-assistant pairs
        # Actually: [system, user, assistant, system, user, assistant, system, user, assistant] = 9
        self.assertGreaterEqual(len(node._staged_messages), 6)

    def test_decompose_staged_merge_includes_child_contracts(self):
        self.api_client.chat.side_effect = [
            json.dumps(MOCK_STAGE1),
            json.dumps(MOCK_STAGE2),
            json.dumps(MOCK_STAGE3),
        ]
        node, errors = self.decomposer.decompose_staged(self.node)
        self.assertEqual(errors, [])
        self.assertIn("ParseInput", node.children_contracts)
        self.assertIn("ExecuteCommand", node.children_contracts)
        # ExecuteCommand should have data_operations from Stage 3
        exec_contract = node.children_contracts["ExecuteCommand"]
        self.assertGreater(len(exec_contract.data_operations), 0)

    def test_staged_with_history_uses_provided_messages(self):
        """decompose_staged_with_history should continue from provided message history."""
        existing_messages = [
            {"role": "system", "content": "old system prompt"},
            {"role": "user", "content": "Stage 1 request"},
            {"role": "assistant", "content": json.dumps(MOCK_STAGE1)},
        ]
        self.api_client.chat.side_effect = [
            json.dumps(MOCK_STAGE1),  # New Stage 1 (after re-decompose feedback)
            json.dumps(MOCK_STAGE2),  # New Stage 2
            json.dumps(MOCK_STAGE3),  # New Stage 3
        ]
        node, errors = self.decomposer.decompose_staged_with_history(
            self.node,
            previous_errors={"previous_errors": ["Child missing source"]},
            message_history=existing_messages,
        )
        self.assertEqual(errors, [])
        # The first API call should include the existing message history
        first_call_messages = self.api_client.chat.call_args_list[0][0][0]
        # Should have old messages + feedback + new system + new user
        self.assertGreaterEqual(len(first_call_messages), len(existing_messages) + 2)


if __name__ == "__main__":
    unittest.main()
