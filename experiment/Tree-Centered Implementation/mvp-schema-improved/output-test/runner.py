"""Runner: concatenates all node files and executes the pipeline."""
import json
import datetime
import os
from typing import Any, Optional, Tuple

tasks = []
next_id = {'value': 1}

nodes_dir = os.path.join(os.path.dirname(__file__), 'nodes')
code_parts = []
for f in sorted(os.listdir(nodes_dir)):
    if f.endswith('.py'):
        filepath = os.path.join(nodes_dir, f)
        with open(filepath, encoding='utf-8') as fp:
            code_parts.append(fp.read())

full_code = '\n'.join(code_parts)
exec(full_code, globals())

test_inputs = [
    '{"command": "create", "task_data": {"title": "Buy groceries", "description": "Milk, eggs, bread"}}',
    '{"command": "create", "task_data": {"title": "Write report"}}',
    '{"command": "list", "task_data": {"status_filter": "all"}}',
    '{"command": "list", "task_data": {}}',
    '{"command": "complete", "task_data": {"id": 1}}',
    '{"command": "list", "task_data": {"status_filter": "all"}}',
    '{"command": "list", "task_data": {"status_filter": "pending"}}',
    '{"command": "delete", "task_data": {"id": 2}}',
    '{"command": "list", "task_data": {"status_filter": "all"}}',
]

for i, inp in enumerate(test_inputs, 1):
    print(f"\n{'='*60}")
    print(f"Test {i} >>> {inp}")
    print(f"{'='*60}")
    try:
        result = Test_prd(inp)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
