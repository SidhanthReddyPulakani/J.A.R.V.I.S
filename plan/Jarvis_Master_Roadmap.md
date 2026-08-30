# J.A.R.V.I.S. — Master Roadmap

**This file replaces:** `JARVIS_long_term_vision_and_build_plan.txt`, `architecture.md/.txt`, `Jarvis_project_direction.txt`, `Roadmap.txt`, `R2_10A___Context_Contract_Audit.txt`, `current_path.txt`, `current_state.txt`.

Keep those as historical reference if you want, but stop updating them. From now on, update **this file only**. Every status below was checked against the actual `backend.zip` source and, where possible, a live run — not against what an earlier planning doc assumed. Where your own prior docs were stale, that's called out explicitly so you know why the numbers moved.

Status legend: ✅ Complete &nbsp;·&nbsp; 🟡 Partial (real code exists, gap remains) &nbsp;·&nbsp; 🔵 Active &nbsp;·&nbsp; 🔴 Not started

---

## 0. What Jarvis is

A persistent personal AI agent — not a chatbot, not a features list. The LLM is a replaceable reasoning engine; Jarvis is the surrounding system that gives it state, memory, context, retrieval, and (eventually) the ability to act. Current stack: Python 3.10, Qwen via Ollama, SQLite, PySide6 frontend (not currently wired to the main entrypoint — see §5).

## 1. The Letta question, answered directly

You investigated Letta/MemGPT, prototyped against it, and **abandoned it** — it was too heavy, too much infrastructure, and less controllable than building your own. That decision is sound and final; nothing in your current code depends on Letta or its client library.

What you kept: the **concepts**, mapped onto your own implementation —

| Letta/MemGPT concept | Your implementation | Status |
|---|---|---|
| Agent | `JarvisAgent` | ✅ built |
| Core memory blocks (human/persona, editable, bounded) | `MemoryBlock` / `CoreMemoryService` | ✅ built, ✅ reaches context |
| Recall storage | `RecallService` / `ConversationRepository` | ✅ built and live |
| Archival memory / data sources | `Knowledge` module (Source → Document → Passage) | ✅ built, 🔴 nothing ingested yet |
| Self-editing memory (agent calls `core_memory_replace`, etc.) | `AgentMemoryOperations` + `operation_definitions.py` | 🟡 built, 🔴 not callable by the LLM |
| Heartbeats / multi-step tool chaining | — | 🔴 not built (this is your Phase 1.7 / R2.9E) |
| Memory pressure / paging / eviction | `ContextWindowManager` | 🔴 message-count truncation only, no token budget |
| Agentic RAG (agent decides when/what to retrieve) | — | 🔴 not built (currently retrieval is automatic-per-turn, not agent-decided — see §4) |

You are **not** currently using Letta in any form — client, server, or SDK. Everything in the table above is your own code, inspired by the concepts in the papers/lessons you studied. That's exactly what your `Jarvis_project_direction.txt` says you set out to do, and it's what you actually did.

---

## 2. Where you actually are — corrected against the code

Your own `Roadmap.txt` and `current_path.txt`/`current_state.txt` were the right instinct (tracking status explicitly), but they were written **before** your most recent integration pass and are now stale in one important way: they mark R2.10 (Context Integration) as still mostly 🔴 with Core Memory and Retrieval not yet reaching the live agent. **That's no longer true — I checked the actual code and ran it.** Here's the corrected picture.

### Phase 0 — Architecture: ✅ Complete
No change. Your architecture doc is sound and nothing in later phases has required revising it.

### Phase 1 — Agent Core: 🟡 Partial
- LLM interface, Agent State, Recall, Core Memory, Diary (storage side), basic Context: all ✅.
- 1.7 (Agent Reasoning Loop) and 1.8 (Agent Protocol) remain the real gap: `JarvisAgent.run()` is still a single-shot "ask → maybe one tool round → answer" loop, not the repeated reason→act→observe→reason cycle your architecture calls for. No change from your own assessment here — still accurate.

### Phase 2 — Capability Core: 🔴 Not started
No change. No `capabilities/` package, no Controller, exists yet.

### Phase 3 — Apps Migration: 🔴 Not started
No change. `features/apps/` works well as a standalone subsystem but isn't yet exposed as a governed capability through a Controller.

### Phase 4 — Agent ↔ Capability Integration: 🔴 Not started
No change. Depends on Phase 2/3.

### Phase 5 — State & Knowledge: 🟡 Partial — **this is where the correction matters**

**R2.1–R2.8 (Core Memory, LTM, Diary, Knowledge, Relationships, Retrieval, Memory Formation, Memory Consolidation):** ✅ all confirmed complete as *infrastructure* — models, repositories, services, migrations, and independent tests all check out. No change from your own assessment.

**R2.9 (Agentic Memory Operations):** 🟡 more built than your docs credit, still not wired.
- `AgentMemoryOperations`, `get_memory_operation_definitions()`, validation, and result models are all built and independently tested (this is new since your last status doc — worth updating your own mental model here).
- Still 🔴: none of it is merged into `AVAILABLE_TOOLS` or passed to `llm.chat(tools=...)`. The LLM cannot call `memory_create`, `memory_replace_core`, `recall_search`, etc. today. This is genuinely the last big piece of R2.9.

**R2.10 (Context Integration): 🟡 substantially further along than `Roadmap.txt` says.** I verified this live, not just by reading code:
- Core Memory → Context: **✅ done and confirmed working** (I ran `JarvisAgent.run()` with a stubbed LLM and printed the actual compiled prompt — `[human]`/`[persona]` blocks appear). Your `Roadmap.txt` still lists this as 🔴 "Core Memory automatically supplied" — that's stale.
- Retrieval → Context: **✅ done and confirmed working** — `_build_context()` calls `self.retrieval.search(...)` every turn with Recall, Memory, Relationship, and Knowledge providers all registered. Also stale in `Roadmap.txt`.
- Diary → Context (read side): ✅ done (`.search`/`.recent` wired in).
- Context rebuild semantics (R2.10E): 🟡 — context *is* rebuilt fresh every call to `_build_context()` (no caching bug), but there's no explicit staleness/invalidation model; it works today by virtue of always rebuilding rather than by a designed contract. Fine for now, worth formalizing before R2.11.
- **Two real bugs found in this same integration pass** (not in any prior doc — new findings):
  1. 8 tests fail with `AttributeError: 'JarvisAgent' object has no attribute 'operation_results'` — confirmed failing on your own machine too (your shipped `.pytest_cache/lastfailed` already lists them).
  2. The current turn's message gets persisted to Recall and then immediately retrieves itself back as "relevant information" with a perfect match score, every single turn — confirmed via live run, not just static reading.
- **The real remaining gap in R2.10 is the write side, not the read side**: nothing in `agent.run()` calls `self.diary.record()`, `self.memory.create()`, or appends to `self.operation_results`. Long-Term Memory, Diary, and Operation Results are fully built and correctly *read from* — but a live conversation today never writes to any of them. Only Agent State and Recall actually change during a session.

**R2.11 (Context Window Management):** 🔴, unchanged — `ContextWindowManager` only does message-count truncation, no token estimation, budget, pressure detection, or summarization.

**R2.12 (Final Integration / E2E):** 🔴, unchanged — no full-lifecycle, restart-persistence, or memory-formation-to-retrieval end-to-end test exists yet.

### Phase 6–11: 🔴 Not started, as before. No change — these are correctly sequenced after Phase 5 finishes, not before.

---

## 3. Foundation evaluation, for your stated purpose

Your stated goal: **finish the foundation and complete Knowledge/State ↔ Context ↔ Agent integration before starting capabilities (Phase 2+).**

**Verdict: structurally sound, with a narrow and well-understood amount of work left — not a foundation with hidden problems.**

What's genuinely strong:
- Every domain model across two full review passes validates its own invariants consistently (`MemoryBlock`, `LongTermMemory`, `MemoryCandidate`, `RetrievalResult`, `KnowledgeSource/Document/Passage`, `OperationResult`) — this discipline hasn't slipped as the codebase grew, which is the thing most likely to rot first in a fast-moving project.
- Service → Repository → Storage → SQLite layering is followed consistently (one exception: Relationships still self-manages its own table instead of going through migrations — small, fixable).
- The retrieval/read side of Knowledge & State integration is **actually done**, confirmed live, not just by architecture diagrams matching code structure.
- You now have real agent-level integration tests (`test_agent_context_assembly*.py` etc.) — this is exactly the kind of test that catches the class of bug that isolated unit tests can't, and it's what caught bug #1 above.

What's incomplete, precisely:
- Four write-paths (Long-Term Memory, Diary, Operation Results, self-managed memory tool-calling) have complete, tested services with **zero call sites** in the live agent loop.
- Two live bugs from the current integration pass need fixing before you build further on top.
- Context Window Management (R2.11) hasn't started — token-blind truncation only.

None of this requires new design. The hard part (models, contracts, migrations, retrieval abstraction, context compilation) is done and has held up under two rounds of scrutiny. What's left is mechanical: wire four call sites, fix two bugs, then do token-aware window management and a real end-to-end test. That's a bounded, sequenceable list — which is exactly what the roadmap below gives you.

---

## 4. On "agentic" retrieval — a scope note worth locking in now

Your own `R2_10A` audit already drew this line correctly, and it's worth restating so it doesn't get blurred later: what you have now is **automatic** retrieval (the Agent runs `self.retrieval.search()` every turn, unconditionally) — not **agentic** retrieval (the LLM itself deciding whether to search, what to search for, and whether to search again). That's the right scope for this phase. Agentic retrieval is Phase 1.7 / R2.9E territory (it needs the multi-step reasoning loop to exist first — you can't have the LLM decide to retrieve-then-continue-reasoning without a loop that supports "continue reasoning"). Don't pull it forward; finishing automatic retrieval + write-paths first is the correct order, and it's what MemGPT's own design assumes too (the paper's Figure 2/6 examples all run inside a function-chaining loop your Agent doesn't have yet).

---

## 5. Everything else worth knowing (carried over, still accurate)

- `RelationshipStore` bypasses `migrations.py` (self-manages its table) — inconsistent with every other subsystem, including the newer Knowledge module which did it correctly. Fold it in.
- `jarvis/retrieval/container.py` (`build_retrieval_service`) duplicates what `agent.py.__init__` does by hand — pick one source of truth.
- `test_suite_smoke.py`'s module list is stale — doesn't include the new `test_agent_*` or `test_memory_operations*` files. Running it alone gives false confidence.
- `requirements.txt` is missing `PySide6`, needed by `jarvis/ui/frontend.py`. That file, plus `jarvis/system/hotkeys.py`, `startup.py`, `ollama.py`, are all orphaned — not imported by `main.py`. Not urgent for this phase; decide the real entrypoint story before Phase 2 needs one.
- Schema still carries `schedule_events`/`reminders`/`templates`/`template_apps` with zero backing code (harmless Phase 6 scaffolding).
- No `.gitignore` anywhere; `data/jarvis.db` + backup, `.pytest_cache/`, and `__pycache__/` are still getting shipped in zips.

---

## 6. The Roadmap — chronological, from here to "foundation done"

This is the one list to work from. Each step names the file(s) involved and what "done" looks like. Sequenced so nothing depends on something later in the list.

### Step 1 — Fix the two live bugs
1. `operation_results` AttributeError: add `agent.operation_results = []` to the two broken test harnesses (`test_agent_context_assembly.py`, `test_agent_retrieval_diary_assembly.py`), or better, make `_build_context` use `getattr(self, "operation_results", [])`.
2. Self-referential Recall retrieval: reorder so `self.retrieval.search(...)` runs before `self.recall.add_message(...)` persists the current turn, or filter results whose content matches `user_input` verbatim.
3. Run full `pytest` → confirm 0 failures. **Don't proceed to Step 2 until this is clean** — you'd be building write-paths on top of a context-assembly layer you haven't confirmed is currently correct.

### Step 2 — Wire Operation Results (smallest remaining write-path)
4. In `run()`'s tool-execution branch, construct an `OperationResult` per tool call (model already exists in `jarvis/memory/operation_results.py`) and append to `self.operation_results`.
5. Confirm via a live smoke run (stub the LLM, print the compiled prompt like this review did) that a real tool call's result reaches the `OPERATION RESULTS` context section.

### Step 3 — Wire Diary
6. Add `self.diary.record(...)` calls at 1–2 trigger points — start simple: once per tool execution, and/or once per completed turn.
7. Confirm live that a Diary entry written in turn N is visible in turn N+1's compiled context.

### Step 4 — Wire Memory Formation (Long-Term Memory)
8. Instantiate the extractor/evaluator pipeline (`jarvis/memory/formation/`) in `agent.py`; call it once per user turn.
9. On accepted candidates, call `self.memory.create()`/`.update()`/`.supersede()`.
10. Test with a phrase the existing regex extractor catches ("Remember that I use Cursor.") and confirm it's retrievable by a later, unrelated turn.

### Step 5 — Wire self-managed memory operations (R2.9, do last — biggest and riskiest)
11. Merge `get_memory_operation_definitions()` into the tool list sent to the LLM.
12. Add a routing branch in `run()` that dispatches matched operation names to `AgentMemoryOperations`, alongside the existing `AVAILABLE_TOOLS` branch.
13. Budget real testing time here — it's the first place the LLM can mutate persistent state on its own. Validate: writable/non-writable Core Memory enforcement, capacity limits, and safe failure on a malformed/hallucinated operation call.
14. **This closes R2.9.**

### Step 6 — Consistency pass (batch together, cheap)
15. Fold `RelationshipStore` into `migrations.py` as a proper versioned migration.
16. Point `agent.py` at `retrieval/container.py`'s `build_retrieval_service(...)` instead of duplicating provider construction.
17. Sync or retire `test_suite_smoke.py`.
18. Add `PySide6` to `requirements.txt`, or remove `frontend.py` — decide which and match the repo to it.
19. Add a `.gitignore` (`data/`, `__pycache__/`, `.pytest_cache/`, `*.pyc`).

### Step 7 — Foundation acceptance check (closes R2.10)
20. Manual multi-turn session against a fresh DB: several turns, at least one tool call, one "remember that..." statement, one follow-up turn that should retrieve something from earlier. Confirm Core Memory, Long-Term Memory, Diary, and Operation Results all show real content in a later turn's context — not just Recall.
21. Write this as a real, checked-in test (your "golden path" end-to-end test) — not just a manual script. This is the single test most likely to catch the next integration gap before a future review has to find it for you.
22. **This closes R2.10.**

### Step 8 — Context Window Management (R2.11)
23. Token estimation (even approximate — word count × constant is fine as v1) so you know when you're near budget.
24. Budget/pressure detection: define a threshold (à la MemGPT's "70% warning / 100% flush") and a system message the LLM sees when approaching it.
25. Eviction policy: what gets dropped from the FIFO/conversation window first, and confirm it's still reachable via Recall search afterward (nothing should become permanently unreachable — this is the core MemGPT guarantee, "evicted ≠ deleted").
26. Summarization is explicitly optional for v1 — your own architecture doc says don't build it before the foundation needs it. Skip unless real usage shows context overflowing regularly.

### Step 9 — R2.12 Final Integration / E2E
27. Full-lifecycle test: fresh DB → several turns → restart the agent (new `JarvisAgent()` instance against the same DB) → confirm State, Core Memory, Long-Term Memory, and Diary all reload correctly and are visible in the first post-restart context.
28. Failure-injection tests: LLM call fails mid-turn, a tool raises, a memory operation is invalid — confirm nothing corrupts persisted state and the agent recovers gracefully next turn.
29. **This closes Phase 5 entirely.** At this point, per your own stated goal, the foundation is done.

### Step 10 — Only now: start Phase 2 (Capability Core)
30. Capability contract, Operation contract, Capability Registry, Capability Controller — per your existing Phase 2 definition in `Jarvis_project_direction.txt` §13–17. Nothing about that design needs to change based on anything found in this review.

---

## 7. What to actively *not* do right now

Carried forward from your own architectural principles, because they still apply and are worth restating in one place:
- Don't build agentic (LLM-decided) retrieval before the multi-step reasoning loop exists (§4 above).
- Don't build summarization/recursive-summarization before you've observed real context pressure.
- Don't start Phase 2 (capabilities) before Step 9 closes — capabilities will want to read Long-Term Memory/Diary/Core Memory, and until Step 2–4 are done there's nothing in them to read.
- Don't add embeddings/vector search to Knowledge yet — your own docs already correctly deferred this, and nothing found in this review changes that.
- Don't let a stale planning doc keep telling you something is 🔴 when a live check would show it's ✅ (this is literally what happened between `Roadmap.txt` and the current code — a five-minute live smoke test would have caught the drift). That's the main reason to consolidate down to this one file: one source of truth, updated the moment code changes, checked against the running system periodically rather than trusted from memory.
