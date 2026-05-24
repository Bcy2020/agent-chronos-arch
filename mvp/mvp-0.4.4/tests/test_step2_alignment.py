"""
Alignment experiment: present the Step 2 VERIFY prompt to the LLM
and ask it to explain its understanding of each rule — no review, no judgment.

Goal: verify the LLM's interpretation of the rules aligns with the intended
meaning before finalizing the prompt. Especially the "direct_calls" rule which
was previously misinterpreted as "calls are direct" rather than "every child
must be called by parent".

All LLM raw inputs/outputs are saved to tests/output/test_step2_alignment/.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from api_client import APIClient

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "test_step2_alignment")
LLM_LOG_DIR = os.path.join(OUTPUT_DIR, "llm_log")
os.makedirs(LLM_LOG_DIR, exist_ok=True)

_call_counter = 0


class LoggingAPIClient(APIClient):
    def chat(self, messages, temperature=None, max_tokens=4096, response_format=None):
        global _call_counter
        _call_counter += 1
        call_id = _call_counter

        req = {
            "call_id": call_id,
            "timestamp": time.time(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        req_path = os.path.join(LLM_LOG_DIR, f"{call_id:04d}_request.json")
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump(req, f, indent=2, ensure_ascii=False)

        print(f"  [LLM call #{call_id}] ...")
        start = time.time()
        # Use the parent's client directly to avoid response_format={"type": "json_object"}
        temp = temperature if temperature is not None else self.config.temperature
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temp,
            max_tokens=max_tokens,
        )
        response_text = response.choices[0].message.content
        elapsed = time.time() - start

        resp = {
            "call_id": call_id,
            "elapsed": round(elapsed, 2),
            "response": response_text,
        }
        resp_path = os.path.join(LLM_LOG_DIR, f"{call_id:04d}_response.json")
        with open(resp_path, "w", encoding="utf-8") as f:
            json.dump(resp, f, indent=2, ensure_ascii=False)

        print(f"    done ({elapsed:.1f}s)")
        return response_text


# ---------------------------------------------------------------------------
# Scenario: order_flat_dispatch (10 children, parent only calls 2)
# ---------------------------------------------------------------------------

def build_scenario():
    """Build the order_flat_dispatch scenario context (without review request)."""
    children = [
        ("ParseInput", "Parse input JSON into command and order_data",
         "def ParseInput(input: Any) -> Tuple[str, dict]"),
        ("RouteCommand", "Route command to appropriate handler",
         "def RouteCommand(command: str, order_data: dict) -> dict"),
        ("CreateOrderHandler", "Handle create_order: validate user, check stock, create order",
         "def CreateOrderHandler(order_data: dict) -> dict"),
        ("PayOrderHandler", "Handle pay_order: check order, deduct balance, update status",
         "def PayOrderHandler(order_data: dict) -> dict"),
        ("ShipOrderHandler", "Handle ship_order: check order is paid, update status to shipped",
         "def ShipOrderHandler(order_data: dict) -> dict"),
        ("CompleteOrderHandler", "Handle complete_order: check order is shipped, update status",
         "def CompleteOrderHandler(order_data: dict) -> dict"),
        ("CancelOrderHandler", "Handle cancel_order: check order, restore stock, refund",
         "def CancelOrderHandler(order_data: dict) -> dict"),
        ("ListOrdersHandler", "Handle list_orders: list orders with filters",
         "def ListOrdersHandler(order_data: dict) -> dict"),
        ("GetUserOrdersHandler", "Handle get_user_orders: get orders for a user",
         "def GetUserOrdersHandler(order_data: dict) -> dict"),
        ("ListProductsHandler", "Handle list_products: list products with optional filter",
         "def ListProductsHandler(order_data: dict) -> dict"),
    ]

    child_lines = "\n".join(
        f"- {name}：{purpose}。签名：{sig}"
        for name, purpose, sig in children
    )

    code = """def Order_prd(input: Any) -> Any:
    command, order_data = ParseInput(input)
    result = RouteCommand(command, order_data)
    return result"""

    return children, child_lines, code


def build_context_prompt(children, child_lines, code):
    """Build the narrative context portion (same as the verify prompt, minus the review request)."""
    return f"""有一个名为 Order_prd 的节点，其作用是：An order management system that coordinates users, products, and orders。

该节点接受输入：input: Any - System input，产生输出：output: Any - System output。

为了实现这个节点，我们计划将其分解为以下 {len(children)} 个子节点：

{child_lines}

现在有一份由其他开发者编写的实现代码，试图通过调用上述子节点来组合实现 Order_prd：

```python
{code}
```"""


CONTEXT = build_context_prompt(*build_scenario())


# ---------------------------------------------------------------------------
# Questions to ask (each is a separate LLM call)
# ---------------------------------------------------------------------------

QUESTIONS = [
    {
        "id": "understand_decomposition",
        "question": "请用你自己的话解释：什么是「分解」？在这个上下文中，「将一个节点分解为子节点」意味着什么？",
    },
    {
        "id": "understand_function_coverage",
        "question": """请解释你对「第一，功能覆盖」这条规则的理解：

> 代码是否覆盖了 Order_prd 的全部职责？每个子节点在分解中承担的功能，是否在代码中有所体现？如果有子节点的功能被遗漏，分解就不能通过。

请回答：
1. 你如何判断一个子节点的功能是否「在代码中有所体现」？
2. 如果代码中完全没有出现某个子节点的函数名，你会如何判断？""",
    },
    {
        "id": "understand_direct_calls",
        "question": """请解释你对「第二，直接调用与树结构」这条规则的理解：

> 这是一个树形分解，不是图。每个子节点必须由父节点直接调用——不能通过另一个子节点间接调用。如果代码中某个子节点没有被父节点直接调用（而是由它的兄弟节点调用），那说明分解结构有问题：要么该子节点应该成为调用它的那个子节点的下级，要么它根本不应该被分出来。

请回答：
1. 「直接调用」对你来说意味着什么？
2. 如果父节点的代码中根本没有调用某个子节点（既不是直接调用，也不是间接调用——就是完全没出现），你会怎么判断？这种情况是否属于这条规则的管辖范围？""",
    },
    {
        "id": "understand_information_sufficiency",
        "question": """请解释你对「第三，信息充分性」这条规则的理解：

> 代码中不能凭空产生信息。每个函数调用的参数必须有明确来源：要么是父节点的输入，要么是之前子节点的输出，要么是常量。如果某个子节点被调用时使用了没有来源的变量，说明分解时缺少了提供该信息的子节点。

请回答：
1. 你如何判断一个变量是否有「明确来源」？
2. 「之前子节点的输出」——你如何确定哪个子节点在「之前」？""",
    },
    {
        "id": "apply_to_scenario",
        "question": """现在请你基于上面的理解，对给出的 Order_prd 分解和代码做一个判断：

代码中直接出现了哪些子节点的调用？哪些子节点完全没有出现？

对于第二条规则（直接调用与树结构），你认为这段代码是否通过？为什么？""",
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_question(api_client, context_text, q):
    """Ask one alignment question with the scenario context prepended."""
    combined = context_text + "\n\n---\n\n" + q["question"]
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Answer the user's questions thoroughly in Chinese. Always provide detailed explanations."},
        {"role": "user", "content": combined},
    ]
    response = api_client.chat(messages, temperature=0.3, max_tokens=2048)
    return response


def main():
    cfg = Config(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        temperature=0.3,
    )
    if not cfg.api_key:
        print("ERROR: DEEPSEEK_API_KEY not set")
        sys.exit(1)

    api_client = LoggingAPIClient(cfg)

    results = []
    for q in QUESTIONS:
        print(f"\n{'='*60}")
        print(f"  Question: {q['id']}")
        print(f"{'='*60}")
        response = run_question(api_client, CONTEXT, q)
        results.append({
            "id": q["id"],
            "question": q["question"],
            "response": response,
        })
        print(f"  Response length: {len(response)} chars")

    # Save all results
    result_path = os.path.join(OUTPUT_DIR, "alignment_results.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  Results: {result_path}")
    print(f"  LLM log: {LLM_LOG_DIR}")

    # Also save a readable summary
    summary_path = os.path.join(OUTPUT_DIR, "alignment_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# Alignment Experiment Summary\n\n")
        f.write(f"Scenario: order_flat_dispatch (10 children, parent calls 2)\n\n")
        for r in results:
            f.write(f"## {r['id']}\n\n")
            f.write(f"**Question:** {r['question']}\n\n")
            f.write(f"**Response:**\n\n{r['response']}\n\n")
            f.write("---\n\n")
    print(f"  Summary: {summary_path}")


if __name__ == "__main__":
    main()
