"""
PRD Converter: Converts natural language PRD into structured JsonPRD.
Used once at project initialization, output cached to .chronos/prd.json.
"""
import json
import os
from typing import Any, Dict, Optional

from config import Config
from api_client import APIClient
from models import JsonPRD, FunctionalRequirement, NonFunctionalRequirement, \
    AcceptanceCriterion, TechnicalConstraints, GlobalStateSource

PRD_CONVERSION_SYSTEM_PROMPT = """You are a PRD (Product Requirements Document) analyzer. Your task is to convert a natural language PRD into a structured JSON format.

ANALYSIS RULES:
1. Extract ALL functional requirements - each represents a distinct feature
2. Assign each functional requirement an ID (FR-001, FR-002, etc.)
3. Identify non-functional requirements (performance, security, usability)
4. Extract acceptance criteria and link them to functional requirements
5. Identify technical constraints (storage, UI, language, concurrency)
6. Identify ALL global data sources from the PRD - every shared data store
7. For each global state source, determine: type (list/dict/set/queue), item schema, initial state
8. Extract glossary terms for domain-specific terminology
9. Extract input/output format specifications - if the PRD has sections like "Input/Output Format", "Usage", "API" that describe how the system receives input and produces output, capture them in input_spec and output_spec

Return ONLY valid JSON with this exact structure:
{
  "metadata": {
    "project_name": "Project name derived from PRD",
    "project_id": "com.example.project",
    "version": "1.0.0"
  },
  "functional_requirements": [
    {
      "fr_id": "FR-001",
      "title": "Feature title",
      "description": "Detailed description",
      "priority": "high|medium|low",
      "related_nfr_ids": [],
      "depends_on": []
    }
  ],
  "non_functional_requirements": [
    {
      "nfr_id": "NFR-001",
      "category": "performance|security|usability|reliability",
      "description": "Description"
    }
  ],
  "acceptance_criteria": [
    {
      "ac_id": "AC-001",
      "description": "Criterion description",
      "verification_method": "automated_test|manual_review",
      "related_fr_ids": ["FR-001"]
    }
  ],
  "technical_constraints": {
    "storage": {"type": "memory|sqlite|postgresql", "details": ""},
    "concurrency": {"model": "single-user|multi-user", "auth_required": false},
    "ui": {"type": "cli|web|mobile|api"},
    "language": "Python"
  },
  "glossary": {
    "term": "definition"
  },
  "global_state_sources": [
    {
      "source_id": "data_store_name",
      "type": "list|dict|set|queue",
      "description": "What this store holds",
      "initial_state": [],
      "item_schema": {"field": "type"}
    }
  ],
  "input_spec": {
    "format": "json|text|cli-args",
    "description": "How the system receives input",
    "schema": {"field_name": "type description"},
    "examples": [{"input_example_1": "value"}]
  },
  "output_spec": {
    "format": "json|text",
    "description": "How the system produces output",
    "schema": {"field_name": "type description"},
    "examples": [{"output_example_1": "value"}]
  }
}"""


class PRDConverter:
    def __init__(self, config: Config, api_client: APIClient):
        self.config = config
        self.api_client = api_client

    def convert(self, prd_text: str) -> Optional[JsonPRD]:
        messages = [
            {"role": "system", "content": PRD_CONVERSION_SYSTEM_PROMPT},
            {"role": "user", "content": f"Convert this PRD to structured JSON:\n\n{prd_text}"}
        ]
        try:
            response = self.api_client.chat(messages, max_tokens=16384)
            parsed = self._parse_response(response)
            if parsed:
                return JsonPRD.from_dict(parsed)
        except Exception as e:
            print(f"PRD conversion failed: {e}")
        return None

    def convert_and_save(self, prd_text: str, output_dir: str) -> Optional[JsonPRD]:
        chronos_dir = os.path.join(output_dir, ".chronos")
        os.makedirs(chronos_dir, exist_ok=True)
        prd_json_path = os.path.join(chronos_dir, "prd.json")

        json_prd = self.convert(prd_text)
        if json_prd:
            with open(prd_json_path, "w", encoding="utf-8") as f:
                json.dump(json_prd.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"JsonPRD saved to {prd_json_path}")
        else:
            print("Warning: PRD conversion failed, will use fallback text-based approach")
        return json_prd

    def load_prd_json(self, output_dir: str) -> Optional[JsonPRD]:
        prd_json_path = os.path.join(output_dir, ".chronos", "prd.json")
        if os.path.exists(prd_json_path):
            with open(prd_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return JsonPRD.from_dict(data)
        return None

    def _parse_response(self, content: str) -> Optional[Dict[str, Any]]:
        content = content.strip()
        if content.startswith("```"):
            import re
            content = re.sub(r"^```[a-zA-Z0-9]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            print(f"Failed to parse PRD conversion response")
            return None
