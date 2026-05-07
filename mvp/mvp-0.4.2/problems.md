# 代码 LLM 缺少拒绝权和重分解请求通道

## 背景

架构文档（architect-latest-zh.md）期望：

> **组合本身就是验证机制。**
> 如果父节点必须绕开子节点、引入额外隐藏步骤、或者根本无法闭合，则说明当前分解并不可靠。
> 验证失败后...如果问题来自子节点接口或边界，就返回到当前分解重新调整。

即一个双向闭环：

```
分解 → 代码生成（验证分解合理性）→ 如果组合不畅 → 请求重分解
```

## 当前问题

### 1. 代码 LLM 没有拒绝权

父节点代码生成 prompt 要求 LLM 输出：

```json
{
  "code": "...",
  "imports": [],
  "child_calls": [],
  "implementation_notes": ""
}
```

**没有字段让 LLM 表达"这个分解有问题，我无法通过子节点组合实现"。**

当分解有缺陷时，LLM 只能：
- 绕路直接访问全局变量（`products.get(...)`）
- 发明子节点接口中不存在的逻辑
- 总之必须硬写出"能跑"的代码

### 2. 验证器只检查 UNUSED_CHILD

`validator.should_redecompose()` 仅在子节点完全未被调用时触发重分解。但像下面这种"子节点被调用了但数据流有缺口"的情况永远不会触发：

```
CreateOrder 的 children（分解器产出）：
  ValidateUser → users.get ✅
  CheckStock → 返回 (bool, str)，不含 product 数据
  CalculateTotal(items, products_data) ⚠️ products_data 无来源
  DeductStock → products.update ✅
  CreateOrderRecord → orders.create ✅
```

`CalculateTotal` 需要 `products_data`，但没有子节点提供它。LLM 在 `global_vars` 中看到 `products`，直接读取：

```python
products_data = []
for item in items:
    product = products.get(item['product_id'])  # 绕过子节点
    products_data.append(product)
total_price = CalculateTotal(items, products_data)
```

代码能运行、验证通过，但**架构原则已被绕过**。

### 3. conservation check 粒度不够

`validator.check_conservation()` 只检查变量级覆盖：

> 父节点要 `read_write on products`，有子节点覆盖了 `read on products` → ✅ 通过

但不检查**每个子节点的输入参数是否有来源**。`CalculateTotal` 需要 product 数据这一具体需求被漏检。

## 根因

- 代码 LLM 的输出格式缺少"拒绝/反馈"通道
- 验证器的重分解触发条件只有 `UNUSED_CHILD`
- conservation check 是变量级而非数据流级
- 架构的"代码验证分解"闭环中，代码生成器是被动的，没有反馈权利

## 修复方向

1. **给代码 LLM 拒绝权**：在父节点 prompt 中明确说明 LLM 可以拒绝组合，并在输出格式中增加 `decomposition_feedback` 字段

2. **增强重分解触发条件**：除了 `UNUSED_CHILD`，还要检测父节点是否直接访问了全局变量（绕过子节点）

3. **增强数据流检查**：验证每个子节点的输入参数在整个子树中是否有来源

4. **分解时确保数据流闭合**：分解器需要确保子节点的输入要么来自父节点入参，要么来自兄弟节点的输出，而非悬空依赖
