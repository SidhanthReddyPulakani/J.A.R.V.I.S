# J.A.R.V.I.S. — The Roadmap (P0 → P31)

for /d /r . %d in (__pycache__) do @if exist "%d" rmdir /s /q "%d"   

**This file replaces everything you've been maintaining**: `Roadmap.txt`, `JARVIS_long_term_vision_and_build_plan.txt`, `architecture.txt`, `Jarvis_project_direction.txt`, `R2_10A___Context_Contract_Audit.txt`, `current_path.txt`, `current_state.txt`, and my own earlier `Jarvis_Master_Roadmap.md`. The Phase 0–11 / R2.1–R2.12 numbering is retired. From here on there is **one number line, P0 through P31**, in the exact order you should do the work. Nothing from the old docs is lost — every phase, sub-phase, and future capability listed in your vision doc is folded in below, just renumbered and sequenced by actual dependency order rather than by which document it originally lived in.

**Status tags**: ✅ Done (verified) &nbsp;·&nbsp; 🔵 Do next &nbsp;·&nbsp; ⬜ Planned, not started &nbsp;·&nbsp; 🌫️ Aspirational (no fixed shape yet, intentionally vague until it's next)

Every entry has the same shape: **what it is, why it's positioned here, what "done" looks like.** Completed entries additionally show what I verified and how.

---

## P0 — Fix the two live agent bugs ✅ Done

**What**: (1) `AttributeError` on `self.operation_results` in two test harnesses. (2) The current turn's message retrieving itself back from Recall every turn.
**Verified**: Full `pytest` run → **78 passed, 0 failed**. Live 2-turn smoke test confirmed turn 1 produces no self-echo, and the fix (`getattr(self, "operation_results", [])`, plus reordering retrieval before persistence in `run()`) is in the shipped code exactly as intended.
**One loose end**: the old direct-access line is still sitting commented-out directly above the fix in `_build_context`. Harmless, but delete it next time you're in that function — no reason to keep two versions of the same line once you trust the fix.

---

## P1 — Wire every subsystem's write-path into the live agent loop ✅ Done

**What**: Long-Term Memory, Diary, Operation Results, and the self-managed memory tool-calling surface (formerly "R2.9 Agentic Memory Operations") all had complete, tested services with zero call sites in `agent.run()`. All four now have real call sites.
**Verified live**, not just read: a 2-turn session produced a real row in `memories` (extracted from "Remember that my main editor is Cursor"), two real rows in `diary_events`, and a simulated LLM tool call to `memory_replace_core` actually rewrote a Core Memory block in SQLite and the updated content was visible in the very next reasoning step's context, alongside a correct `OPERATION RESULTS` entry.
**Knowledge ingestion** remains the one part of this group still open — correctly, since there's no capability yet that produces documents to ingest. It becomes real work again at P17 (Files) or whenever you build a manual ingestion path; nothing about the current `KnowledgeService` needs to change for that.

---

## P2 — Consistency & hygiene pass ✅ Done

**Done**: `RelationshipStore` now goes through `migrations.py` properly (schema bumped to v7); `agent.py` now uses `retrieval/container.py`'s `build_retrieval_service(...)` instead of duplicating provider wiring; the dead `schedule_events`/`reminders`/`templates`/`template_apps` schema tables are removed (they'll come back for real at P19/P21, defined by actual code instead of speculative scaffolding).
- `test_suite_smoke.py`'s module list is stale and misses most of your newest tests — lowest-effort fix is to delete the file and rely on plain `pytest`, which already discovers everything correctly.
- `requirements.txt` is missing `PySide6`, needed by `jarvis/ui/frontend.py`.
- `jarvis/system/hotkeys.py`, `system/startup.py`, `system/ollama.py`, `ui/frontend.py` are orphaned — nothing imports them. Leave them as-is; they get a real home at P23 (System capability) and whenever you settle the entrypoint story.
- No `.gitignore`; `data/jarvis.db` still ends up in zips. Add one covering `data/`, `__pycache__/`, `.pytest_cache/`, `*.pyc`.

---

## P3 — Golden-path end-to-end test ✅ Done

**What**: Every behavior verified in P0/P1 was checked by hand with a throwaway script — none of it is a committed test. All your existing `test_agent_*.py` files construct `JarvisAgent` and call `_build_context()` directly; **none call `agent.run()`**.
**Build**: one file, `test_agent_run_end_to_end.py`, using a fake/stub `LLMClient` (the pattern from this review's smoke scripts is ready to lift directly). It should: send a message with a memorable fact → send a follow-up → assert the fact appears in retrieved context; assert a `diary_events` row exists after a turn; simulate a `memory_replace_core` tool call and assert the Core Memory change is visible in the same turn's second context build.
**Why here specifically**: this is the single test that would have caught every live bug found across all three review rounds. It converts "I manually verified this" into "the suite guarantees it," and every phase after this one builds on the assumption that the agent loop behaves correctly — worth locking that down with a real test before adding more on top of it.

---

## P4 — Agent restart / reload test ✅ Done

**What**: instantiate `JarvisAgent()` against a temp DB, run a few turns, discard the instance, create a **new** `JarvisAgent()` against the same DB path, and assert State, Core Memory, Long-Term Memory, and Diary all reload correctly and are visible in the first post-restart context build.
**Why it's missing**: you have reload tests at the repository level for nearly everything (`test_long_term_memory.py`, `test_diary.py`, etc.) but nothing tests the *whole agent* surviving a restart — which is the actual guarantee a user cares about ("does Jarvis remember me tomorrow").

---

## P5 — Context Window Management ✅ Done

**What**: `jarvis/context/window.py` currently only truncates by message count. Three concrete pieces, build in this order:
1. **Token estimation** — a crude `len(text) // 4` approximation is enough to start; no real tokenizer needed yet.
2. **Budget + pressure signal** — pick a threshold (MemGPT's own 70%-warning / 100%-flush is a reasonable default to just copy) and surface a system message to the LLM when approaching it.
3. **Eviction policy with a provable safety property**: whatever gets dropped from the active window must still be reachable via `self.recall.search(...)` afterward. Write this as a test — "evicted is not deleted" — since it's the one property this entire mechanism exists to guarantee.
**Explicitly skip for now**: recursive summarization. Your own architecture doc says not to build this before you've observed real context pressure happening — nothing found in review changes that advice.

P5.1 — Token accounting ✅ Done
P5.2 — Budget ✅ Done
P5.3 — Pressure ✅ Done
P5.4 — Token-aware eviction ✅ Done
P5.5 — Retrieval budget ✅ Done
P5.6 — Safety invariant ✅ Done
Agent Integration ✅ Done

---

## P6 — Failure-injection pass ✅ Done

**What**: three specific scenarios, each its own small test.
1. LLM call raises mid-turn — does `run()` leave `self.messages`/the DB in a consistent state, or does it half-persist a turn?
2. A tool raises an uncaught exception — mostly about locking in behavior you already have (`classify_operation_exception` already catches this) with a test, rather than new code.
3. `_execute_memory_operation` receives malformed argument types (e.g., `label=123`) — confirm it fails as a clean `OperationResult`, never an unhandled exception that crashes `run()`.
**Why here**: (1) is the one genuine unknown left in the agent loop; (2) and (3) are cheap to lock in now that you know they work.

Once these four are done, every information subsystem (State, Recall, Core Memory, Long-Term Memory, Diary, Knowledge, Relationships, Retrieval, Context) is not just built and wired but **proven**, by committed tests, to survive real use and real failure. This is the actual finish line for "the foundation," by your own definition of the term.

---

## P7 — Build a Real Agent Execution Loop ✅ Done

**What**: `agent.run()` currently has a fixed two-step interaction shape: one LLM call, optionally one round of tool/memory operations, then a final LLM call. P7 replaces this with a genuine **Agent Execution Loop** that can continue for an arbitrary number of model/tool turns within explicit safety limits.

The runtime should follow:

**reason → act → observe → reason again → … → terminate**

The loop must be an Agent-side orchestration layer, independent of the future Capability Controller.

---

### Build

#### 1. Agent Turn

Extract the existing model interaction into a clear, reusable **Agent Turn**.

A turn should:

* Assemble the current context.
* Call the LLM.
* Process the model response.
* Detect whether the model produced tool/memory-operation calls.
* Distinguish between a response requiring further action and a final response.

The Agent Turn should not expose or attempt to reproduce the model's private reasoning.

---

#### 2. Iterative Execution Loop

Replace the current hardcoded two-call structure with an actual execution loop:

**Model → tool calls → execution → observations → Model → …**

Each iteration should:

1. Build the current context.
2. Call the LLM.
3. Record the assistant response.
4. If there are no tool calls, terminate with the model's final response.
5. If tool/memory operations exist, execute them.
6. Record their structured results.
7. Feed those results back as observations.
8. Continue to the next model turn.

The existing tool and memory-operation dispatch mechanisms remain authoritative; P7 must not create a parallel execution system.

---

#### 3. Structured Tool Observations

Tool and memory-operation results must become explicit observations available to the next model turn.

The Agent should preserve the distinction between:

* successful operations,
* failed operations,
* recoverable failures,
* non-recoverable failures,
* malformed requests,
* and other existing `OperationResult` outcomes.

A failed operation should normally be observable by the model so that it can decide whether to retry, change strategy, or terminate.

---

#### 4. Explicit Termination

The loop terminates when the model produces **no further tool/memory-operation calls**.

This represents the model's observable completion signal:

**No requested operation → final response**

The runtime must also enforce a hard execution ceiling using `MAX_REASONING_STEPS`.

`MAX_REASONING_STEPS` is a **safety boundary**, not the normal completion mechanism.

A model that reaches the ceiling without producing a final response must be terminated safely and deterministically.

---

#### 5. Context Rebuild Between Turns

Every reasoning iteration must use the existing Context Assembly pipeline.

The loop must not construct one static context at the beginning and reuse it indefinitely.

Each iteration should be able to observe changes produced by previous operations through:

* Agent State
* Core Memory
* Recall
* Long-Term Memory
* Diary
* Knowledge
* Relationships
* Runtime conversation
* Tool/memory-operation results

This preserves the purpose of P5's context-management system when execution extends beyond two model calls.

---

#### 6. State, Diary, and Memory Continuity

Existing State, Diary, Memory, and persistence behavior must continue to operate naturally across every iteration.

P7 is an orchestration change, not a replacement of those systems.

Operations performed during step N must be capable of influencing the context available at step N+1.

---

#### 7. Execution Trace

Introduce an explicit runtime-level execution trace for the Agent loop.

At minimum, the trace should make it possible to identify:

* execution step,
* model turn,
* requested operations,
* operation results,
* continuation,
* termination reason.

This trace is for **observable execution/debugging**, not for exposing private model chain-of-thought.

The trace should eventually provide the foundation for visualizing how JARVIS is operating.

---

#### 8. Safety and Termination Controls

P7 must prevent runaway execution.

The initial hard boundary is:

`MAX_REASONING_STEPS = 10`

The architecture should keep this limit configurable so additional execution controls can be introduced later without redesigning the loop.

The loop must never depend on the model voluntarily stopping in order to remain safe.

---

### Tests

P7 must prove that the implementation is genuinely multi-step rather than merely replacing one hardcoded second call with a loop-shaped construct.

Tests should cover:

1. **Single-turn completion**

   * LLM returns no tool calls.
   * Agent terminates after one model turn.

2. **Two-step execution**

   * Model requests an operation.
   * Operation succeeds.
   * Model receives the result and produces the final response.

3. **Three-or-more-step execution**

   * Model requests an operation.
   * Receives the result.
   * Requests another operation.
   * Receives the result.
   * Eventually produces a final response.
   * Verify that all model turns actually occurred.

4. **Multiple operations in one turn**

   * Preserve the existing batch operation behavior.

5. **Tool failure recovery**

   * Operation fails.
   * Failure becomes an observation.
   * Model can respond with another operation or terminate.

6. **Maximum-step termination**

   * Model continually requests operations.
   * Agent stops exactly at `MAX_REASONING_STEPS`.
   * No infinite execution occurs.

7. **Context refresh**

   * An operation changes State/Memory/Diary/etc.
   * The subsequent model turn receives the updated context.

8. **Runtime persistence**

   * Multi-step execution does not lose or destructively mutate runtime conversation history.

9. **Execution trace**

   * Each model turn and operation result is represented in the trace.
   * The final trace identifies the correct termination reason.

---

### Why here, not later

P7 is Agent-side execution infrastructure and does not require the Capability Controller.

Building the execution loop now allows the future Capability Controller work in P9–P16 to plug into an Agent runtime that already supports arbitrary-length tool interaction.

The architectural dependency becomes:

**P7 Agent Execution Loop → P9–P16 Capability Controller**

rather than discovering and redesigning the two-step limitation after the Controller has already been introduced.

---

### P7 completion criteria

P7 is complete when:

* `agent.run()` no longer contains a hardcoded two-call reasoning structure.
* The Agent can perform an arbitrary number of model/tool turns within the configured safety ceiling.
* The model can terminate by producing no further operations.
* Tool and memory-operation results are observable by subsequent model turns.
* Context is rebuilt between turns.
* State/Diary/Memory behavior remains intact across multiple iterations.
* Tool failures can participate in the reasoning cycle.
* The maximum-step safety boundary is enforced.
* Execution is represented by an observable runtime trace.
* The active test suite proves genuine 3+ step execution and runaway-loop termination.


P7.1 — Define Agent Turn contract
P7.2 — Extract current single-turn model interaction
P7.3 — Formalize tool-result observation
P7.4 — Implement bounded execution loop
P7.5 — Rebuild context between turns
P7.6 — Add recovery from tool failures
P7.7 — Add execution trace
P7.8 — Multi-step integration tests
P7.9 — Infinite-loop / termination tests
P7.10 — Real JARVIS visual execution trace

## P8 — Formalize the operation/result protocol between Agent and future Capabilities ✅ Done

**What**: right now, tool calls and memory operations are dispatched via two separate hand-rolled `if name in {...}` branches in `run()`. Before the Capability Controller exists (P9–P12), define the actual contract the Agent will use to talk to it: a structured request shape (operation name + arguments + any invocation metadata) and confirm your existing `OperationResult` model (already solid, built at P1) is the one true result shape for capabilities too, not just memory operations.
**Why here**: P9 defines the Controller's *external* contract; this defines the *Agent's* side of that same conversation. Doing this first means P12 (the Controller itself) has a real contract to satisfy instead of being designed in a vacuum.

**→ P7–P8 close out the remaining half of what used to be "Phase 1 / Agent Core."**

---

## P9 — Capability & Operation contracts ✅ Done

**What**: the formal interfaces that every future capability will implement.
- Capability interface + metadata (name, identity, version).
- Operation interface + the `capability.operation` addressing scheme (e.g. `apps.launch`, `files.read`) you already settled on conceptually.
- Operation schema — inputs, outputs, requirements.
**Build target**: these are interfaces/contracts, not working code yet — the goal is a `capabilities/contracts.py` (or similar) that P11–P13 build against.

## P10 — Operation Request / Result / State models ✅ Done

**What**: `CapabilityRequest` (operation name + arguments + invocation metadata), a refined `OperationResult` (you already have a good one from P1 — extend it with the fuller state vocabulary from your own design: `SUCCESS`, `FAILED`, `PARTIAL`, `BLOCKED`, `INVALID`, `NOT_FOUND`, `REQUIRES_INPUT`, `IN_PROGRESS`, `CANCELLED` — you don't need every state on day one, add them as real capabilities need them), and `OperationState` lifecycle/cancellation semantics.
**Principle to hold onto**: an operation reports *what happened*, not just success/failure — `NOT_FOUND: "Could not find VS Code"` vs `REQUIRES_INPUT: "Found 3 matching applications"` are different things the Agent needs to reason differently about.

## P11 — Capability Registry ✅ Done

**What**: registration, lookup, discovery (`discover()` → all registered capabilities/operations), description (`describe(operation)` → purpose/inputs/outputs/requirements).

## P12 — Capability Controller ✅ Done

**What**: the single governed gateway — `execute(request)` — that every capability operation must go through. No separate `result()` method; `execute()` returns the result directly, per your own earlier design decision.
**Must include from day one**: validation, error normalization, logging. **Can wait**: permissions/governance beyond "did this validate," dependency management, versioning — add these when a real capability actually needs them, not preemptively.
**The one rule that matters most here**: capabilities must never call each other directly. If Capability A needs Capability B, it goes `A → Controller → B`. This is what keeps the whole ecosystem from turning into an unmanageable web of direct imports later — worth being strict about from the very first capability you migrate (P13), not just in principle.

**→ P9–P12 are what used to be "Phase 2 / Capability Core."**

---

## P13 — Migrate `features/apps/` into the first real Capability ✅ Done

**What**: wrap your existing, already-solid Apps subsystem (discovery, resolver, launcher, verification, manager) behind the P9–P12 contracts. Expose `apps.find`, `apps.resolve`, `apps.launch` (and `apps.close` later) through the Controller.
**Important**: this is packaging, not a rewrite. Your Apps internals are good — this phase proves the Controller works by putting one real, working capability through it, not by redesigning Apps.

## P14 — Retire the legacy direct tool-execution path for Apps ⬜ Planned

**What**: once `apps.*` operations work correctly through the Controller (P13), remove the old direct `AVAILABLE_TOOLS` entries and routing for Apps specifically. Don't touch the memory-operations dispatch (P1) — that's a separate, intentionally different surface (LLM-managed information, not capability actions) and should stay as-is.

**→ P13–P14 are what used to be "Phase 3 / Apps Migration."**

---

## P15 — Wire the P7 reasoning loop to the P12 Controller ⬜ Planned

**What**: the Agent's multi-step loop (P7) now calls `Controller.execute(request)` instead of the old direct dispatch, for capability operations specifically (memory operations from P1 keep their own dispatch — same reasoning as P14). Results flow back into Context exactly the way `OperationResult` already does today.

## P16 — Multi-capability execution test ⬜ Planned

**What**: once you have 2+ real capabilities (Apps from P13, plus at least one from P17–P23), write a test that exercises reason → act → observe → reason again → act on a *different* capability → respond, confirming the loop, the Controller, and Context all cooperate across capability boundaries, not just within one.

**→ P15–P16 are what used to be "Phase 4 / Agent ↔ Capability Integration."** This is the point where your architecture doc's core loop — *"perceive → understand → retrieve → reason → act → observe → record → learn/retain → continue"* — is fully real, not partially real. Everything before this point was foundation; everything after this point is building outward on solid ground.

---

## P17 — Files capability ⬜ Planned
Read, write, search, move, copy, delete, metadata. The first Phase-6-equivalent capability — also the natural first real Knowledge-ingestion trigger point (a file read can feed `KnowledgeService.ingest`, closing the one loose end from P1).

## P18 — Folders capability ⬜ Planned
Create, browse, search, organize.

## P19 — Scheduler capability ⬜ Planned
Create, cancel, list, trigger. This is where the `schedule_events`/`reminders` concept you removed from the schema at P2 comes back — for real this time, defined by working repository/service code instead of speculative empty tables.

## P20 — Projects capability ⬜ Planned
Project model, project state, project context, project operations. This is the capability most other Phase-6 capabilities will end up composing with later at P24–P25 (a "project" naturally touches Files, Git, and Apps together).

## P21 — Templates capability ⬜ Planned
Template storage, retrieval, application. Same note as P19 — this is the other schema table you removed at P2 coming back with real code behind it.

## P22 — Git capability ⬜ Planned
Status, diff, commit, branch, log — with safe execution (never destructive by default; anything that rewrites history or force-pushes should require explicit confirmation, matching your "LLM decides, code verifies" reliability principle).

## P23 — System capability ⬜ Planned
System information, process management, environment operations — and this is also the natural home for the orphaned `jarvis/system/hotkeys.py`, `startup.py`, `ollama.py` and `jarvis/ui/frontend.py` flagged back at P2. Once System is a real capability, decide the entrypoint story (stdio bridge vs. direct GUI) as part of this work, not before.

**→ P17–P23 are what used to be "Phase 6 / Core Capability Ecosystem."** This is the point where Jarvis stops being a memory-and-conversation foundation and becomes *practically useful* — the first phase where a user notices new things Jarvis can actually do, rather than how well it remembers.

---

## P24 — Capability-to-capability calls + dependency resolution ⬜ Planned
Real usage of the `A → Controller → B` rule from P12, now that there are enough capabilities (P13, P17–P23) for it to matter. Dependency resolution: if capability A's operation needs capability B to have run first, the Controller understands that ordering.

## P25 — Multi-capability workflows, shared operation state, failure recovery, goal-level orchestration ⬜ Planned
The "Get me ready for work" example from your own vision doc: Calendar → Projects → Files → Apps → Browser as one coherent goal, not five isolated commands. Failure recovery matters most here — if step 3 of 5 fails, the Agent needs to reason about a partial result, not just crash the whole chain.

**→ P24–P25 are what used to be "Phase 7 / Capability Composition."**

---

## P26 — Preference & workflow learning 🌫️ Aspirational
Jarvis starts noticing durable patterns (preferred apps, project organization habits, recurring task shapes) and feeding them into Long-Term Memory/Core Memory through the existing Memory Formation pipeline (P1) — this phase is mostly about *what* to extract and *when*, not new infrastructure.

## P27 — Relevance, historical understanding, project continuity, advanced consolidation 🌫️ Aspirational
Deepens P26 — better retrieval ranking based on what's actually mattered before, and richer memory consolidation than the duplicate/conflict handling you already have from P1.

**→ P26–P27 are what used to be "Phase 8 / Personalization & Learning."** Deliberately vague until P17–P25 exist — you need real usage data and real capabilities generating events before "learning" means anything concrete.

---

## P28 — Scheduled reasoning, monitoring, reminders 🌫️ Aspirational
Jarvis can act on a timer or a trigger, not only in response to a message. Builds directly on the Scheduler capability from P19.

## P29 — Background processing, preparation workflows, controlled autonomous action 🌫️ Aspirational
"You have a meeting in 20 minutes, I've prepared the workspace" — the example from your own vision doc. Requires P26–P27 (knowing what to prepare) and P19/P28 (knowing when to act).

**→ P28–P29 are what used to be "Phase 9 / Proactivity."**

---

## P30 — Skills, specialized/sub-agents, planning, delegation, background reasoning 🌫️ Aspirational
Explicitly kept as one bucket, matching your own vision doc's treatment — these are future possibilities, not things to prematurely scope. Revisit and break this into real P-numbers only once P17–P29 are real and you have concrete evidence of what a "sub-agent" would actually need to do.

**→ what used to be "Phase 10 / Advanced Agent Architecture."**

## P31 — Controlled self-improvement: learned workflows, skill/capability generation, self-evaluation 🌫️ Aspirational
Your own vision doc is explicit that this comes only after the foundation is extremely reliable, and nothing in three rounds of review changes that judgment — if anything, P3–P6 exist specifically to earn the right to say "reliable" with evidence rather than hope.

**→ what used to be "Phase 11 / Self-Improvement."** The final entry in the roadmap, same as it was the final phase in every prior version of your plan.

---

## How to actually use this file going forward

- Update statuses here, in place, the moment code changes — not in a separate doc. The entire reason `Roadmap.txt` went stale last round was that it lived apart from the code and nobody re-checked it against a live run before trusting it.
- When a P-item is marked ✅, it means **I ran something and watched it work**, not that the code merely exists. Hold yourself (and any code agent you're pairing with) to that same bar when you update this file yourself — "tests pass" is necessary but was never sufficient across any of the three review rounds so far; the real bugs were only ever caught by actually running `agent.run()` and looking at the database afterward.
- The order above is a dependency order, not a rigid law — but it's worth noticing that every time this project drifted (Core Memory built-but-disconnected, Retrieval built-but-disconnected, Diary built-but-unwritten), it was because a later, more visible piece got started before an earlier, less visible piece was actually finished. The sequencing here exists specifically to keep that from happening again as the project gets bigger and harder to hold in your head at once.
