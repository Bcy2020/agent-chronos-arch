> ## ⚠️ Successor notice
>
> This repository is the **predecessor** to **Axiom**
> ([`Bcy2020/Axiom`](https://github.com/Bcy2020/Axiom)), which supersedes the
> tree-centered direction documented here. Axiom derives structure from a PRD's
> **acceptance criteria** (acceptance-driven structure derivation) instead of
> recursive tree decomposition, and is captured as an MCP + skill + real
> decompositions. See [`CHRONOS-PREDECESSOR.md`](CHRONOS-PREDECESSOR.md) in Axiom
> and its [`docs/acceptance-driven-direction-change-zh.md`](docs/acceptance-driven-direction-change-zh.md).
>
> The tree-centered MVP modules in `mvp/` are preserved **as a historical archive**
> (`mvp/archive-tree-centered/`); the "Chronos" name is retired as the active
> direction and kept only as the historical reference here.

# Agent Chronos 2.0

**Tree-centered multi-agent software construction for large-scale projects.**

Agent Chronos 2.0 is not a phase-heavy AI coding workflow.  
It is a **tree-centered architecture** for building software with AI through:

- **decomposition**
- **node-local implementation**
- **composition-as-validation**
- **subtree-level governance**

Instead of forcing the whole project through fixed roles or rigid global phases, Chronos treats software as a structure that must be **progressively decomposed, locally implemented, continuously validated, and recursively repaired**.

---

## Why Agent Chronos 2.0 exists

Most AI coding systems are good at helping with **tasks**.

They can:
- generate code
- follow plans
- run steps in sequence
- parallelize small chunks of work
- recover from context-window limitations

But large-scale software projects are not only task execution problems.

They are also **structural problems**:

- Can the system be decomposed in a stable way?
- Can a parent capability truly be supported by its child nodes?
- Can local implementation be validated early?
- Can requirement changes and defects be localized to the affected part of the structure?
- Can AI parallelism scale without losing architectural coherence?

Agent Chronos 2.0 is built for this layer.

It is designed around one claim:

> For large-scale AI software construction, the core problem is not only workflow discipline.  
> The core problem is whether the system can be decomposed, composed, validated, and governed as a tree.

---

## What changed from 1.0 to 2.0

Agent Chronos 1.0 focused on engineering discipline:

- stage progression
- boundary control
- contract-first thinking
- controlled parallelism
- rollback and governance

That was useful, especially for Web-style projects.

But 2.0 moves the center of gravity.

**1.0 was phase-centered.**  
**2.0 is tree-centered.**

In 2.0:

- the project starts from a **root requirement**
- the system is expanded through **tree decomposition**
- nodes become the main unit of implementation
- validation is introduced **during construction**, not only at the end
- failures feed back into decomposition
- changes and defects are governed by the **affected subtree**, not only by phase rollback

This makes Chronos less like a process framework and more like a **software construction architecture**.

---

---

## Direction change (2026): from recursive tree decomposition to acceptance-driven structure derivation

The original Chronos 2.0 decomposed the system by infinitely recursing down a tree —
each node locally implemented, validated, and repaired, with a fresh agent per node.

That produced three compounding problems (recorded against MVP 0.4.5 / grade_prd):

- **cost & latency**: hundreds of serial LLM calls, input tokens re-serialized per call,
  near-zero prefix-cache hits, long wall-clock;
- **upstream distortion**: a parent cannot foresee what a child will actually need, so
  legitimate child requests were misread as violations (defensive overreach /
  resource underallocation / interface selection gap turned out to share one root cause);
- **no room for agent dialogue**: a one-shot, static, parent-dictates-all model cannot
  express the negotiation a real coordinated build requires.

Chronos is therefore shifting to **a few specialized agents**, deriving structure from the
PRD's **acceptance criteria** instead of from an abstract top-down goal.

### What stays the same (retained)

- decomposition is still the organizing principle;
- **composition-as-validation** (now "implementation-as-validation") is kept;
- the parent/coordinator still governs the resource boundary;
- validation locality (a failure is attributable to a block / subtree);
- contract-first boundaries (pre/postconditions, `boundary` = parent guarantees / out-of-scope);
- **invariant-first enforcement** — fix the invariant, don't pile on per-case patches;
- LLM explores, a deterministic validator enforces (LLM self-check is not the enforcement point);
- state-machine governance (`draft → compile → promote → snapshot`, accepted graph is read-only).

### What changes (the shift)

- a small number of agents (structure + implement + optional review) instead of many recursive nodes;
- one structure agent emits the block graph in one go, instead of per-node recursion;
- **graph instead of a mandatory tree** (blocks + ports + connectors + dependencies; shared
  blocks across flows produce a DAG);
- structure is derived from the **acceptance criteria**: AC → trigger→feedback tree → aggregated
  layered block graph (not an abstract top-down goal);
- **branching**: the trigger→feedback tree encodes the normal path plus each failure/degraded path;
- **traceability**: every branch/block carries a `source` back to an AC/FR (guards against
  defensive overreach);
- **reuse of BlockGraph MCP** (`kuang-tu_MCP`) as the carrier — its block/port/connector model,
  state machine, quality gates, and multi-agent governance are the already-built expression of
  this design philosophy;
- decomposition/aggregation has **no single correct answer**: invariants define legality,
  the validator judges legality, review judges reasonableness.

See [`docs/acceptance-driven-direction-change-zh.md`](docs/acceptance-driven-direction-change-zh.md)
for the full direction document (in Chinese), and [`docs/ai/log/`](docs/ai/log/) for archives.

---

## Core ideas

### 1. Tree decomposition is the main structure

Chronos 2.0 treats the system as a tree that is progressively unfolded.

A root node represents the overall goal.  
Each node is decomposed only as far as necessary.  
Children must jointly support the parent in a meaningful way.

The point is not to split work mechanically.  
The point is to build a structure that is:

- understandable
- locally implementable
- composable
- repairable

---

### 2. Decomposition, implementation, and validation form a tight loop

Chronos 2.0 does **not** assume this pattern:

> decompose → implement → validate at the end

Instead, it follows a tighter loop:

> decompose node → implement locally → validate immediately → feed failure back → re-decompose if necessary

This means code generation is not only production work.  
It is also a way to test whether the decomposition is actually viable.

---

### 3. Composition itself is a validation mechanism

This is one of the central ideas of Chronos 2.0.

When a node is decomposed, the implementation should realize the parent **through its child interfaces**.

If the parent can be implemented cleanly by composing its children, the decomposition is likely correct.

If the parent cannot close naturally, or must bypass children with hidden logic, then something is wrong:

- the node boundary may be unclear
- the child interfaces may be malformed
- the decomposition itself may be wrong

In Chronos 2.0, **composition is not only assembly.**  
It is a structural test.

---

### 4. Validation happens on multiple levels

Chronos 2.0 brings validation forward and keeps it close to construction.

It emphasizes three levels:

#### Node-level validation

Checks whether the node itself is valid:

- syntax correctness
- goal consistency
- input/output correctness
- boundary compliance

#### Parent-child composition validation

Checks whether a parent can be correctly implemented using its children.  

This is the most important validation layer.

#### Subtree-level validation

Checks whether local changes preserve consistency across related nodes.

---

### 5. Failures should reshape the structure

A failed implementation is not always just “bad code”.

It may indicate:

- weak implementation
- unclear node boundary
- incorrect child interfaces
- incorrect decomposition
- incorrect structural understanding

Failures should feed back into restructuring the tree.
