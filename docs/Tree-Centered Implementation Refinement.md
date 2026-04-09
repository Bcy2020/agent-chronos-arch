# Tree-Centered Implementation Refinement

> **Authorship note**
>
> The refinement described in this document was proposed by the repository author.
> This document itself was drafted with AI assistance.

## Overview

This document presents a refinement to the original architecture: making the **decomposition tree** the central structure for implementation, validation, and later maintenance.

Instead of keeping separate workflow-design and function-development phases, this approach lets the system implement each node **directly through its child-node interfaces** as soon as the node is decomposed.

The goal is to make the overall process simpler, more flexible, and easier to validate locally.

## Core Idea

After a node is decomposed into child nodes, a code-oriented LLM is asked to implement the **parent node** under one rule:

> The parent must be implemented by composing child-node functions.

At this point, child nodes may not yet be fully implemented, but their interfaces are already defined.

This gives an early structural check:

- If the parent cannot be implemented through child composition, the decomposition is likely flawed.
- If the child interfaces are missing or poorly shaped, the contracts should be revised.
- If the parent can be implemented cleanly from child calls, the decomposition gains practical support.

In this sense, composition becomes a validation mechanism.

## Semantic Stop Conditions

The decomposition should not rely on simple heuristics like line-count estimation. Instead, stop conditions are determined by **semantic analysis** of the node's nature.

### Node Type Classification

Every node can be classified into one of four types:

| Node Type | Description | Stop? |
|-----------|-------------|-------|
| **Pure Computation** | Mathematical function with no side effects. Same input always produces same output. | Yes |
| **Atomic Operation** | Direct manipulation of a single data source with a single operation type. | Yes |
| **Coordination Node** | Orchestrates multiple child nodes, contains business logic, branching, or loops. | No |
| **Mixed Node** | Contains both computation and coordination. | No |

### Stop Condition Rules

A node should stop decomposition when:

1. **Pure Function Test**: The node performs only mathematical transformations with no:
   - Global variable dependencies
   - I/O operations
   - State modifications
   - External API calls

2. **Atomic Operation Test**: The node performs exactly one operation on exactly one data source:
   - Read from a single data source
   - Write to a single data source
   - Read-modify-write on a single data source

3. **Maximum Depth Reached**: The tree has reached the configured maximum depth (forced stop).

If none of the above conditions are met, the node must be further decomposed.

### Example

```
process_order → coordination node → continue decomposition
├── validate_request → pure computation → STOP
├── reserve_inventory → atomic operation (inventory: write) → STOP
├── calculate_totals → pure computation → STOP
└── send_notification → atomic operation (notification_service: write) → STOP
```

## Global State Pre-Definition

Before decomposition begins, all data sources must be explicitly identified and defined. This transforms **implicit dependencies** into **explicit declarations**.

### Data Source Categories

| Category | Examples | Access Pattern |
|----------|----------|----------------|
| **Database** | Orders, Inventory, Customers | CRUD operations, transactions |
| **User Input** | API requests, CLI arguments, forms | Read-only during processing |
| **File System** | Config files, logs, templates | Read/write with I/O overhead |
| **External Services** | Payment gateway, shipping API | Async/sync calls, network failures |
| **Cache** | Session data, computed results | Fast read/write, TTL considerations |

### Pre-Definition Phase

Before decomposition starts:

1. Analyze the PRD to identify all data entities
2. Classify each entity by its data source category
3. Define access types for each data source:
   - **Read-only**: Reference data, configurations
   - **Read-write**: Orders, inventory, user profiles
   - **Write-only**: Logs, audit trails, notifications
4. Generate a **Data Source Manifest** that guides decomposition

### Data Source Manifest Example

```yaml
data_sources:
  - name: inventory_database
    category: database
    access: read_write
    entities: [products, stock_levels, reservations]
    operations:
      - reserve_stock(product_id, quantity)
      - release_stock(product_id, quantity)
      - check_availability(product_id)

  - name: order_database
    category: database
    access: read_write
    entities: [orders, order_items]
    operations:
      - create_order(order_data)
      - update_order(order_id, changes)
      - get_order(order_id)

  - name: payment_service
    category: external_service
    access: write_only
    operations:
      - process_payment(amount, method)
      - refund_payment(transaction_id)
```

## Global State Conservation

A fundamental principle: **parent nodes must not directly operate on global state**. All global operations must be delegated to child nodes. This is called **Global State Conservation**.

### The Conservation Law

```
Parent Global Operations = Σ(Child Global Operations)
```

When a parent node has global operations, they must be completely distributed to its children. No global operation may "disappear" during decomposition.

### Operation Decomposition Rules

| Parent Operation | Child Distribution | Constraint |
|------------------|-------------------|------------|
| `read(data_source)` | One or more `read(data_source)` | Can be split across children |
| `write(data_source)` | One or more `write(data_source)` | Can be split across children |
| `read_write(data_source)` | `read` + `write` to same source | Must be explicitly decomposed |

### Conservation Verification

During decomposition, the system verifies:

1. **Completeness**: All parent global operations are assigned to children
2. **Correctness**: Children only operate on declared data sources
3. **Atomicity**: Each child operates on at most one data source per operation

If conservation is violated, decomposition must be revised.

### Example: Conservation in Action

```
Parent: process_order
├── Global operations: {inventory: read_write, orders: read_write}
├── Child A: validate_items → {inventory: read}
├── Child B: reserve_inventory → {inventory: write}
├── Child C: create_order → {orders: write}
└── Child D: send_confirmation → {} (no global operations)

Verification:
- inventory.read_write = inventory.read + inventory.write ✓
- orders.read_write = orders.write (Child C reads implicitly via write operation) ✓
```

## Simplified Workflow

1. **Pre-Definition Phase**
   - Analyze PRD for data sources
   - Generate Data Source Manifest
   - Define access types and operations

2. **Decomposition Phase**
   - Build decomposition tree recursively
   - Assign global operations to each node
   - Verify global state conservation
   - Apply semantic stop conditions

3. **Implementation Phase**
   - Define interfaces and contracts for child nodes
   - Implement each parent node by composing child-node calls
   - Continue recursively until leaf nodes are reached

4. **Validation Phase**
   - Run tests bottom-up through the tree
   - Verify composition correctness
   - If a node fails, return to its original context and revise

## Main Advantages

### Early validation of decomposition

The system does not wait until final integration to discover that a decomposition is unusable.

### Semantic stop conditions

Instead of arbitrary line-count thresholds, decomposition stops when nodes reach their semantic essence: pure functions or atomic operations.

### Explicit global state management

By pre-defining data sources and enforcing conservation, the system eliminates hidden dependencies and ensures traceable state mutations.

### Simpler architecture

The decomposition tree becomes the main execution structure, reducing process overhead.

### Localized repair

Defects can be traced back to specific nodes and fixed in their original local context.

### Better handling of requirement changes

Requirement changes can be mapped more precisely to affected nodes through the tree structure and interface boundaries.

## Important Caveat

This refinement should not be understood as relying on function signatures alone.

In practice, each node usually needs a stronger contract, including some combination of:

- behavioral expectations,
- preconditions and postconditions,
- error semantics,
- state boundaries,
- composition constraints,
- **global operation declarations**.

Otherwise, a parent may appear composable at the syntax level while still being semantically wrong.

## Limitations

A decomposition tree is a strong backbone for responsibility decomposition, but real systems also contain cross-cutting concerns such as logging, authentication, caching, and shared infrastructure.

Because of that, the tree should be treated as the primary structural model, but not always the complete dependency model.

Additional considerations:

- **Concurrency**: The current model assumes single-threaded execution. Distributed systems require additional coordination protocols.
- **Transactions**: Multi-node operations spanning multiple data sources need transaction management not covered by this model.
- **Cross-cutting concerns**: These should be implemented as aspects or middleware, not as part of the tree structure.

## Summary

This refinement shifts the architecture:

- from **phase-centered development**
- to **tree-centered implementation and verification**

The main claims are:

> A decomposition should be judged not only by whether it looks reasonable, but also by whether a parent node can actually be implemented through composition of its child interfaces.

> A decomposition should not stop at arbitrary thresholds, but only when nodes reach their semantic essence: pure computation or atomic operations.

> Global state operations must be explicitly declared and conserved through the decomposition hierarchy.

This makes the decomposition tree not only a design artifact, but also the main structure for implementation, testing, and change localization.
