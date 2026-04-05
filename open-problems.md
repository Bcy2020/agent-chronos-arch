# Open Problems

This document tracks the key engineering and research problems that must be solved to make the Agent Chronos architecture practical.

This repository is not only about implementation. It is also about identifying, refining, and solving the hardest problems behind the architecture.

## How to use this file

You can contribute by:

- proposing a new problem
- refining an existing problem
- suggesting solution directions
- building a small prototype or experiment
- documenting trade-offs or implementation constraints

When opening an issue, please reference the relevant problem ID when possible.

## Problem status

- `OPEN` — important and unresolved
- `REFINING` — problem is known, but needs clearer framing
- `EXPERIMENTING` — candidate solutions are being explored
- `PARTIALLY SOLVED` — a partial solution exists, but is incomplete
- `SOLVED` — sufficiently resolved for the current architecture stage

---

## P1. Workflow runtime mapping
**Status:** OPEN

How should the 8-phase architecture be mapped to a real workflow runtime?

### Why it matters
The architecture is phase-driven, but phase definitions alone are not enough. A real system needs executable control flow, transitions, rollback rules, and state persistence.

### Open questions
- Should the runtime be graph-based, event-driven, or queue-based?
- Should phases be first-class runtime states?
- How should side-flows interrupt and re-enter the main flow?

### Useful contributions
- orchestration design proposals
- runtime state diagrams
- prototype implementations in an existing workflow framework

---

## P2. Git as state source of truth
**Status:** OPEN

Can Git serve as the primary state carrier for the system, or is an additional metadata store required?

### Why it matters
Git is central to this architecture, but some runtime information may not fit cleanly into commits and branches alone.

### Open questions
- What belongs in Git, and what belongs outside Git?
- Should logs, checkpoints, and experience entries live in the repository?
- How do we prevent Git history from becoming noisy or unmanageable?

### Useful contributions
- Git-only vs hybrid-state comparisons
- repository structure proposals
- minimal prototypes using Git branches / worktrees as runtime state

---

## P3. Clone isolation model
**Status:** OPEN

What is the correct isolation unit for a clone during Phase 7?

### Why it matters
The architecture depends on safe parallel work. Weak isolation causes interference; overly strong isolation increases complexity and cost.

### Open questions
- Should clones use branches, worktrees, containers, or temporary sandboxes?
- What is the minimum isolation needed for safe parallel function implementation?
- How should clone lifecycle creation and cleanup work?

### Useful contributions
- experiments comparing branch/worktree/container approaches
- cost and complexity analysis
- cleanup and workspace management designs

---

## P4. Boundary enforcement for clone edits
**Status:** OPEN

How can the system enforce that a clone only edits its allowed area?

### Why it matters
The architecture assumes strict local modification boundaries. Without enforcement, the system collapses back into uncontrolled editing.

### Open questions
- How should allowed edit regions be declared?
- Can AST-based checks enforce function-level edit boundaries?
- How should legitimate local helper additions be handled?

### Useful contributions
- static analysis prototypes
- whitelist / patch validation designs
- examples of acceptable vs invalid changes

---

## P5. Machine-readable contract format
**Status:** OPEN

What format should contracts use so they are both readable by humans and actionable by tools?

### Why it matters
Contract-first development is one of the architecture’s core ideas. If contracts are too vague, they cannot support safe parallelization.

### Open questions
- Should contracts be Markdown, JSON, YAML, OpenAPI-like specs, or a mixed format?
- How should function signatures, inputs, outputs, errors, and invariants be represented?
- How should front-end/back-end alignment be encoded?

### Useful contributions
- contract schema proposals
- example contract documents
- contract parsers or validators

---

## P6. Contract-to-scaffold generation
**Status:** OPEN

How much implementation scaffolding should be generated automatically from contracts?

### Why it matters
If contracts are precise enough, they may be able to generate framework code, stubs, interfaces, and test skeletons.

### Open questions
- What artifacts can be safely generated?
- How do we keep generated code aligned with updated contracts?
- Should generated code be overwritten, patched, or versioned separately?

### Useful contributions
- code generation experiments
- stub generation tools
- regeneration / diff strategies

---

## P7. Dependency graph generation
**Status:** OPEN

How should function and module dependencies be identified and represented?

### Why it matters
Batch planning and checkpoint design depend on a reliable dependency graph.

### Open questions
- Can dependency graphs be inferred from contracts automatically?
- How should shared utilities and implicit dependencies be handled?
- What granularity is appropriate: module-level, function-level, or both?

### Useful contributions
- dependency extraction proposals
- visualization prototypes
- graph generation from contract documents

---

## P8. Batch partitioning strategy
**Status:** OPEN

How should the system split implementation work into batches?

### Why it matters
Chronos depends on batch-based parallelization. Poor batch design leads to idle time, conflicts, or fragile integration points.

### Open questions
- Should batches be manually designed, automatically derived, or hybrid?
- What optimization target matters most: speed, safety, reviewability, or integration risk?
- How large should a batch be?

### Useful contributions
- batch scheduling heuristics
- dependency-aware partitioning strategies
- case studies on batch sizing

---

## P9. Checkpoint design
**Status:** OPEN

What makes a checkpoint useful rather than bureaucratic?

### Why it matters
Checkpoints are supposed to reduce rework cost. Too many checkpoints slow the system down; too few allow defects to accumulate.

### Open questions
- What kinds of checkpoints are essential?
- Which checkpoints should be automated?
- What objective criteria should decide checkpoint pass/fail?

### Useful contributions
- checkpoint taxonomy
- checkpoint evaluation criteria
- lightweight checkpoint process proposals

---

## P10. Experience pool structure
**Status:** OPEN

How should batch experience be represented, stored, and reused?

### Why it matters
The architecture relies on batch-to-batch learning without real-time contamination. The experience pool is central to that design.

### Open questions
- Should experience entries be free-form summaries or structured records?
- How should entries be tagged by scope, validity, and confidence?
- How do we prevent noisy or low-quality experience from propagating?

### Useful contributions
- experience entry schema
- scoring / ranking mechanisms
- retrieval strategies for batch-relevant experience

---

## P11. Experience quality control
**Status:** OPEN

How can the system distinguish useful experience from misleading experience?

### Why it matters
A bad experience pool may amplify wrong assumptions across later batches.

### Open questions
- Should experience entries require review before being stored?
- Should later outcomes be allowed to invalidate earlier experience?
- How should contradictory experience be handled?

### Useful contributions
- quality filters
- review workflows
- confidence and expiry models for experience entries

---

## P12. Change request classification
**Status:** OPEN

How can G / M / S change severity be made more objective?

### Why it matters
The architecture treats change handling as a first-class side-flow. If severity classification is vague, change handling becomes inconsistent.

### Open questions
- What measurable criteria define G, M, and S?
- Can affected artifact count or dependency impact help classify changes?
- How should user insistence interact with technical risk?

### Useful contributions
- classification rubrics
- example change scenarios
- decision trees for change routing

---

## P13. Defect classification and rollback policy
**Status:** OPEN

How should L1 / L2 / L3 defect classification be made reliable and actionable?

### Why it matters
Rollback policy depends on distinguishing implementation defects from contract or architecture defects.

### Open questions
- What signals indicate a contract defect rather than an implementation defect?
- When should a defect force rework of completed functions?
- How should rollback scope be computed?

### Useful contributions
- defect classification guidelines
- defect examples with routing decisions
- rollback scope algorithms

---

## P14. Review agent reliability
**Status:** OPEN

How can review agents avoid becoming superficial or rubber-stamping reviewers?

### Why it matters
The architecture assumes review is meaningful. Weak review undermines all later governance mechanisms.

### Open questions
- What should review agents check automatically?
- What should require human review?
- How can review quality be measured?

### Useful contributions
- review checklists
- review rubric design
- reviewer calibration experiments

---

## P15. Human-in-the-loop policy
**Status:** OPEN

Where should human intervention be optional, recommended, or mandatory?

### Why it matters
A fully autonomous interpretation may be unsafe or unrealistic, but excessive human intervention weakens the automation value.

### Open questions
- Which phases should always allow human override?
- Which side-flow decisions should require human approval?
- How should human feedback be stored and propagated?

### Useful contributions
- HITL policy proposals
- governance boundary recommendations
- practical examples from existing agent systems

---

## P16. Architecture-to-framework adaptation
**Status:** OPEN

Which existing workflow or agent frameworks are the best substrate for implementing Chronos?

### Why it matters
This architecture does not need to be implemented from scratch. Reusing an existing framework may dramatically reduce MVP cost.

### Open questions
- Is LangGraph the best fit for phase/state control?
- Is CrewAI better for role-based collaboration?
- Is a visual orchestration layer like n8n or Langflow useful for early prototyping?

### Useful contributions
- comparison documents
- proof-of-concept adaptations
- framework selection criteria

---

## P17. MVP scope definition
**Status:** OPEN

What is the smallest version of Chronos that is still meaningfully Chronos?

### Why it matters
A full implementation is too large for an early-stage project. A clear MVP boundary is necessary to attract contributors and validate ideas.

### Open questions
- Which phases are essential for a first MVP?
- Which mechanisms can be simulated manually at first?
- What should be excluded from v0.1?

### Useful contributions
- MVP proposals
- phased rollout plans
- “core vs optional” architecture breakdowns

---

## P18. Evaluation methodology
**Status:** OPEN

How should the architecture be evaluated fairly?

### Why it matters
Claims about cost reduction, traceability, and reduced rework need evidence.

### Open questions
- What baseline should Chronos be compared against?
- What metrics matter most: token cost, elapsed time, defect rate, rollback rate, integration failures?
- What tasks should be used for benchmarking?

### Useful contributions
- benchmark design
- evaluation metrics
- experiment plans comparing Chronos-style workflows with simpler agent workflows

---

## P19. Repository and artifact structure
**Status:** OPEN

What repository layout best supports phase artifacts, generated outputs, logs, contracts, and code?

### Why it matters
The architecture depends on artifact clarity. A poor repository structure will make governance harder, not easier.

### Open questions
- Should each phase own its own directory?
- How should temp files be stored and cleaned?
- How should generated artifacts be separated from canonical artifacts?

### Useful contributions
- repository layout proposals
- sample project structures
- file lifecycle rules

---

## P20. Contributor-friendly research process
**Status:** OPEN

How can the project remain open to low-barrier contributors while still maintaining rigor?

### Why it matters
This project should allow contribution through problem discovery, design analysis, and validation work, not only code.

### Open questions
- What issue templates best support high-quality problem proposals?
- How should accepted problems be tracked?
- How should non-code contributors be credited?

### Useful contributions
- contribution process design
- issue template suggestions
- contributor credit guidelines

---

## How to propose a new problem

If you think an important problem is missing, open an issue with:

- a clear title
- the problem statement
- why it matters
- where it appears in the architecture
- possible solution directions (optional)

High-quality problem discovery is a real contribution to this project.