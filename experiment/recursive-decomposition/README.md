# Recursive Decomposition MVP

This directory contains an experimental MVP for validating a **recursive system decomposition** approach inside `agent-chronos-arch`.

Its goal is **not** to generate production-ready architecture directly.  
Its goal is to test whether a PRD can be recursively decomposed into a tree of function blocks with:

- explicit boundaries
- explicit inputs and outputs
- explicit child interaction flows
- explicit interface-preservation reasoning

## Why this exists

For complex systems, asking an AI to jump directly to function-level design is often unreliable.

The problem is usually not that the AI cannot decompose at all, but that:

- large-system context becomes noisy and unstable
- function-level granularity becomes inconsistent too early
- duplicated responsibilities and conflicts easily appear across branches
- the resulting decomposition is difficult to verify

This experiment explores a different path:  
a **top-down, recursive, minimum-context decomposition process**.

## Core idea

The decomposition methodology and design principles in this experiment were proposed by **Shining Pau**.  
The current prototype code was written by AI based on those ideas.

The core process is:

1. Treat the whole software system as a top-level function block.
2. Require every function block to define:
   - a clear `purpose`
   - clear `inputs`
   - clear `outputs`
   - a clear `boundary` (`in_scope` / `out_of_scope`)
3. Instead of asking AI to continuously reason over the entire system, let it work only on the **current block** and recursively decompose it into child blocks.
4. Apply the same constraints to each child block, until the decomposition reaches a sufficiently small, stable, and independently implementable/testable unit.
5. Require the decomposition to explain:
   - how information flows between child nodes
   - how child nodes jointly realize the parent node
   - whether the composed external interface of the children matches the parent interface

In other words, this experiment is not about “splitting requirements into smaller text fragments”.  
It is about recursively turning requirements into a **composable contract structure**.

## Minimum-context principle

One key assumption of this experiment is:

> When AI decomposes a local node, it should not carry the entire system context.  
> It should receive only the complete boundary of the current node.

So each recursive step should ideally receive only:

- the current node’s name and purpose
- the current node’s inputs and outputs
- the current node’s boundary
- the current node’s parent contract

The purpose of this design is to reduce irrelevant context and improve local decomposition stability.

## Interface-preservation principle

A core requirement of this method is:

> After a parent node is decomposed into child nodes, the composed system formed by those children should expose the same external interface as the parent.

That means:

- parent inputs must be consumed by the children
- parent outputs must be produced by the children
- additional intermediate artifacts must remain internal
- correctness must not depend on hidden or implied coordinators

This is one of the main differences between this experiment and ordinary task breakdown.

## What the current MVP does

The current MVP supports:

- taking a PRD as input
- using a real LLM or a stub backend for recursive decomposition
- generating, for each node:
  - `purpose`
  - `inputs`
  - `outputs`
  - `boundary`
  - `child_interaction_flow`
  - `coverage_explanation`
  - `interface_preservation_proof`
- performing lightweight local validation to detect issues such as:
  - leaked external interfaces
  - uncovered parent inputs
  - missing parent outputs
  - incomplete composition structure

## Current status

This is a **methodology-validation prototype**, not a production-ready system.

Its value is to test whether this decomposition paradigm is viable, not to replace formal software design workflows.

Current known limitations include:

- stopping conditions still partially depend on recursion depth
- implied coordinators may still appear in some outputs
- interface-preservation proofs are not always fully closed
- repeated responsibilities and shared dependencies are not yet fully modeled

## Attribution

- **System decomposition methodology, constraints, and design principles**: proposed by **Shining Pau**
- **Current experimental prototype code**: written by AI based on those ideas
- **Role of this directory**: an experimental validation module, not a final implementation

## Research question

This experiment is not trying to answer:

> “Can AI generate a decomposition tree?”

It is trying to answer:

> **Can AI, under minimum-context constraints, recursively decompose a system into a function-block tree with explicit boundaries, compositional reasoning, and interface-preservation evidence?**