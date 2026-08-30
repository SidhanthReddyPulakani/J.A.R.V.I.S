# Jarvis — Fix List, Foundation Evaluation, and Roadmap

Based on the full Round 2 review of `backend.zip`. This consolidates every verified finding into one actionable document: what to fix, how solid the foundation is for your stated goal, what order to do things in, and what to strengthen beyond the immediate fixes.

---

## Part 1 — Fix List

Ordered by how much they block "complete foundation + full Knowledge/State integration." Each item says what's wrong, where, and what verified it.

### P0 — Bugs (broken today, not just incomplete)

**1. `self.operation_results` AttributeError — 8 failing tests**
- **Where**: `jarvis/core/agent.py`, `_build_context()`
- **What**: Two test files (`test_agent_context_assembly.py`, `test_agent_retrieval_diary_assembly.py`) construct a bare `JarvisAgent` via `object.__new__()` and never set `operation_results`, but `_build_context` now reads `self.operation_results` unconditionally.
- **Verified**: `pytest` → 8 failed, 70 passed. Your own `.pytest_cache/v/cache/lastfailed` already lists these 8 — this was failing on your machine before you zipped it.
- **Fix**: Add `agent.operation_results = []` to both files' test-harness setup (mirror the pattern already used correctly in `test_agent_context_assembly_complete.py`, `test_agent_operation_result_assembly.py`, `test_agent_context_trace.py`). Better: change `_build_context` to use `getattr(self, "operation_results", [])` so any future lightweight test harness degrades gracefully instead of hard-failing.

**2. Current message retrieves itself every turn**
- **Where**: `jarvis/core/agent.py` (`run()` → `_build_context()`) + `jarvis/retrieval/providers.py` (`RecallProvider`)
- **What**: `run()` persists the user's message to Recall, *then* immediately searches Recall using that same text as the query. The just-stored message inevitably comes back as a top/perfect-score "RETRIEVED INFORMATION" result — duplicating what's already in the conversation section, wasting context budget, and defeating the purpose of Recall retrieval (surfacing *older* relevant history).
- **Verified**: Live smoke test — ran `agent.run("Remember that my main editor is Cursor.")` with a stubbed LLM and printed the actual compiled system prompt. The exact just-typed sentence appeared under `RETRIEVED INFORMATION` with `score=1.000`.
- **Fix** (pick one): run retrieval before persisting the current turn; exclude the just-added message's `id` from `RecallProvider` results; or filter `retrieval_results` in `_build_context` to drop any result whose `content` equals `user_input`.

### P1 — Missing write paths (the core remaining integration gap)

Every item here follows the same shape: the service is fully built and independently tested, but nothing in `agent.run()` calls it. This is the main thing standing between "read-integrated" (done) and "fully integrated" (not yet).

**3. Long-Term Memory is never written to**
- **Where**: should be called from `jarvis/core/agent.py`, using `jarvis/memory/formation/` (extractor → evaluator → service)
- **What**: `MemoryFormationService`, `MemoryCandidateExtractor`, `MemoryEvaluator` all exist and pass their own tests, but are never instantiated in `agent.py`. `self.memory.create()/.supersede()/.consolidate()` is never called.
- **Verified**: grepped `MemoryFormationService` usage — appears only inside `jarvis/memory/__init__.py`.
- **Fix**: after a turn completes (or after the user message is persisted), run it through the extractor → evaluator pipeline; if accepted, call `self.memory.create(...)`.

**4. Diary is never recorded to**
- **Where**: should be called from `jarvis/core/agent.py`, using `jarvis/diary/service.py`
- **What**: `DiaryService.record(...)` exists, is tested, and is read from (`.search`/`.recent`) — but never written to anywhere in application code.
- **Verified**: grepped `\.record\(` across `jarvis/` outside tests — zero matches.
- **Fix**: call `self.diary.record(event_type=..., description=..., conversation_id=self.state.conversation_id)` at a sensible point per turn — e.g., after each tool call, or once per completed turn as a v1.

**5. Operation Results are never populated**
- **Where**: `jarvis/core/agent.py`, tool-execution branch of `run()`
- **What**: `self.operation_results` is set to `[]` in `__init__`, read once in `_build_context`, and never appended to. Tool outcomes still only flow through the old `self.messages.append({"role": "tool", ...})` path, not through the new `OperationResult`/`OperationStatus` model.
- **Verified**: grepped `self.operation_results` in `agent.py` — exactly 2 hits (init + read), zero appends.
- **Fix**: in the tool-execution loop, wrap each result in an `OperationResult` (model already exists in `jarvis/memory/operation_results.py`) and append it to `self.operation_results`. This is the smallest of the four write-path fixes — the model and the compiler-side rendering are already done.

**6. Self-managed memory operations aren't callable by the LLM**
- **Where**: `jarvis/memory/operations.py` (`AgentMemoryOperations`), `jarvis/memory/operation_definitions.py` (`get_memory_operation_definitions()`), `jarvis/core/tools.py` (`AVAILABLE_TOOLS`)
- **What**: A full self-managed-memory tool surface exists (`memory_create`, `memory_replace_core`, `memory_append_core`, `recall_search`, `knowledge_search`, etc.), validated and tested — but never merged into `AVAILABLE_TOOLS`, and never passed to `self.llm.chat(tools=...)`. The LLM cannot call any of it today.
- **Verified**: grepped `AgentMemoryOperations` — appears only in its own module + `jarvis/memory/__init__.py`.
- **Fix**: merge `get_memory_operation_definitions()` into the tool list passed to the LLM, and route matching tool-call names through `AgentMemoryOperations` in the same branch that currently handles `AVAILABLE_TOOLS`. This is the largest of the four — treat it as the last piece before calling the foundation done.

**7. Knowledge has no ingestion path**
- **Where**: `jarvis/knowledge/ingestion.py` (`KnowledgeIngestionService`)
- **What**: Fully built (text → document → passages), but no call site anywhere outside its own tests. Knowledge retrieval is correctly wired but will always return empty because nothing ever puts anything in.
- **Verified**: grepped `ingest` — no hits in `agent.py` or any non-test, non-knowledge module.
- **Note**: this one's expected at this stage (no "give Jarvis a file" capability yet) — but worth listing explicitly so "Knowledge is integrated" isn't assumed to mean "Knowledge has content." At minimum, consider a manual/dev-only entry point (e.g., a small script that ingests `architecture.md` itself into Knowledge) so the retrieval path can be validated with real data before capabilities exist to automate it.

### P2 — Consistency and hygiene (not blocking, worth doing while you're in this code)

**8. `RelationshipStore` bypasses the migration system**
- **Where**: `jarvis/relationships/store.py`
- **What**: Calls `database.execute("CREATE TABLE IF NOT EXISTS relationships ...")` directly and lazily (`self.initialize()` inside `save()`/`find_exact()`), instead of going through `jarvis/storage/migrations.py` like every other subsystem — including the new Knowledge module, which did this correctly.
- **Fix**: fold relationship table creation into `migrations.py` as a versioned migration, same pattern as `migrate_to_v6` for Knowledge.

**9. Duplicate retrieval-wiring logic**
- **Where**: `jarvis/retrieval/container.py` (`build_retrieval_service`) vs `jarvis/core/agent.py.__init__`
- **What**: `container.py` defines a factory that assembles the same four providers `agent.py` already constructs by hand, inline. `agent.py` doesn't use the factory — so there are now two places describing "how retrieval is wired," which will drift.
- **Fix**: have `agent.py` call `build_retrieval_service(...)` instead of duplicating the construction.

**10. `test_suite_smoke.py` is stale**
- **Where**: `test_suite_smoke.py`, `TEST_MODULES` list
- **What**: Doesn't include the new `test_agent_*` files, `test_memory_operations*` files, or several new `test_context_*` files. Running just this aggregator gives false confidence — 8 real failures and a chunk of new coverage go unseen.
- **Fix**: either keep the list in sync or drop the file in favor of plain `pytest`, which discovers everything correctly.

**11. Missing `PySide6` dependency**
- **Where**: `requirements.txt`
- **What**: `jarvis/ui/frontend.py` imports `PySide6`, which isn't listed. Anyone running the GUI path fails on import until they `pip install` it manually.
- **Fix**: add `PySide6` to `requirements.txt`, or delete `frontend.py` if `main.py` + external frontend is the actual plan — pick one so the repo state matches intent.

**12. Orphaned modules**
- **Where**: `jarvis/ui/frontend.py`, `jarvis/system/hotkeys.py`, `jarvis/system/startup.py`, `jarvis/system/ollama.py`
- **What**: None are imported by `main.py` or each other. Your README describes hotkey toggle and startup launcher as delivered — the code is correct, but nothing calls it.
- **Fix**: not urgent for your current goal (pre-capabilities foundation work); revisit when you decide on the real entry-point/runtime story.

**13. Dead schema tables**
- **Where**: `jarvis/storage/schema.py` — `schedule_events`, `reminders`, `templates`, `template_apps`
- **What**: Defined with zero backing repository/service/model code. Harmless Phase 6 scaffolding, but schema drift.
- **Fix**: leave a comment marking them "reserved for Phase 6," or remove until built.

**14. No `.gitignore`, DB files shipped in review zip**
- **Where**: project root
- **What**: `data/jarvis.db`, `data/jarvis.db.backup-r2.2`, `.pytest_cache/`, and every module's `__pycache__/` are present in the zip. No `.gitignore` anywhere in the tree.
- **Fix**: add one covering `data/`, `__pycache__/`, `.pytest_cache/`, `*.pyc`.

---

## Part 2 — Foundation Evaluation (against your stated goal)

Your goal for this phase: **finish the base foundation and complete Knowledge/State ↔ Context ↔ Agent integration before starting capabilities.**

**Where it's genuinely strong:**

- **Data modeling discipline is excellent and consistent.** Every domain model (`MemoryBlock`, `LongTermMemory`, `MemoryCandidate`, `AgentState`, `RetrievalResult`, `KnowledgeSource/Document/Passage`, `OperationResult`) validates its own invariants in `__post_init__`. This held up across two full review rounds with no regressions — new code (Knowledge) matches the discipline of old code exactly.
- **Layering is real, not just diagrammed.** Service → Repository → Storage → SQLite is followed consistently, with one exception (Relationships — see fix #8). Migrations are properly versioned (`SCHEMA_VERSION`, sequential `migrate_to_vN` functions, idempotent, refuses to proceed if a version mismatch is detected).
- **The read/retrieval side of the architecture is now fully connected.** Recall, Core Memory, Long-Term Memory, Diary, Relationships, and Knowledge all have working paths into `ContextRequest`, and the compiler renders each conditionally. This was the central gap after round one; it's closed.
- **You now have the right kind of tests.** Round one's biggest structural risk was that every test was a unit test of an isolated subsystem — meaning a real integration bug (Core Memory not reaching context) could hide indefinitely behind 100% "PASS" unit tests. You've since added agent-level integration tests that construct a real (or near-real) `JarvisAgent` and assert on the actual compiled output. That category of test is what caught bug #1 in this list, and it's the right investment for a project of this shape.
- **The Apps capability** (unrelated to this phase, but worth naming) remains proof that when this team/agent-pairing finishes a vertical slice, it finishes it well — discovery, resolution, relationship learning, launch, and verification all connect end-to-end with graceful degradation.

**Where it falls short of "complete":**

- **Write paths are the one systematically missing piece.** Not a quality problem — a completeness problem. Four subsystems (Long-Term Memory, Diary, Operation Results, self-managed memory operations) have production-grade services with zero call sites in the actual agent loop. Functionally, this means a real conversation today only changes two things in the database: Agent State and Recall. Everything else is inert.
- **One live behavioral bug (self-referential retrieval) shipped alongside the retrieval integration.** This is a reminder that "the retrieval provider is registered and tests pass" isn't the same as "retrieval behaves sensibly in a live turn" — the bug only shows up when you actually run the sequence end-to-end, which is exactly why the live smoke test caught it and the unit tests didn't.
- **Test suite hygiene is starting to lag the pace of feature growth.** The stale `test_suite_smoke.py` and the two un-updated agent-test files are both symptoms of the same thing: the test suite is growing fast (that's good) but nothing is enforcing that every file stays current with `agent.py`'s actual attribute surface (that's a process gap, not a code gap).

**Overall assessment**: This is a **structurally sound foundation with a well-defined, bounded amount of finishing work left**, not a foundation with hidden architectural problems. The four missing write-paths are mechanical — the hard design work (models, validation, service contracts, migrations, retrieval abstraction, context compilation) is already done and has proven durable across two rounds of scrutiny. If you close the P0/P1 items above, you will have exactly what you're asking for: a foundation where every subsystem in your architecture doc both reads from and writes to the live agent loop, before any capability code exists to lean on it.

---

## Part 3 — Next Steps, In Order

This sequencing follows dependency order (fix bugs before building on top of them) and risk order (cheapest/highest-confidence fixes first, riskiest integration last).

**Step 1 — Fix the two live bugs (P0)**
1. Fix the `operation_results` AttributeError (either back-port the test fix or make `_build_context` defensive with `getattr`).
2. Fix self-referential Recall retrieval (reorder retrieval-before-persist, or filter it out).
3. Re-run full `pytest` and confirm 0 failures before moving on. Don't build write-paths on top of a context-assembly layer you haven't confirmed is currently correct.

**Step 2 — Wire Operation Results (smallest P1 item)**
4. In `run()`'s tool-execution branch, construct an `OperationResult` per tool call and append to `self.operation_results`.
5. Extend/write a test confirming a real tool call (e.g. `open_application`) produces an `OperationResult` that reaches the compiled context. You already have the test *shape* for this (`test_agent_operation_result_assembly.py`) — just point it at the real `run()` path instead of only manual injection.

**Step 3 — Wire Diary**
6. Add `self.diary.record(...)` calls at 1–2 clear trigger points (start with: one per tool execution, and/or one per completed turn). Keep it simple — this doesn't need to be smart yet, it needs to exist.
7. Verify with a live smoke test (like the one used in this review) that Diary entries from an earlier turn show up in a later turn's `_build_context()` output.

**Step 4 — Wire Memory Formation (Long-Term Memory)**
8. Instantiate `MemoryFormationService` (or its extractor/evaluator directly) in `agent.py`.
9. Call it once per user turn; on `CREATE`/`UPDATE` decisions, call `self.memory.create()`/`.update()`/`.supersede()` accordingly.
10. Test with a phrase the regex extractor is known to catch (e.g. "Remember that I use Cursor.") and confirm the memory persists and is retrievable by a later, unrelated turn via `self.retrieval.search(...)`.

**Step 5 — Wire self-managed memory operations (largest P1 item, do last)**
11. Merge `get_memory_operation_definitions()` into the tool list sent to the LLM.
12. Add a second routing branch in `run()` (alongside the existing `AVAILABLE_TOOLS` branch) that dispatches matched operation names to `AgentMemoryOperations`.
13. This is the one place I'd budget real testing time — it's the first place the LLM gets to *decide* to mutate persistent state, so validate: writable/non-writable Core Memory enforcement, capacity limits, and that a malformed or hallucinated operation call fails safely (returns an error result to the LLM) rather than raising an uncaught exception mid-turn.

**Step 6 — Consistency pass (P2 items, cheap to batch together)**
14. Fold `RelationshipStore`'s table creation into `migrations.py`.
15. Point `agent.py` at `retrieval/container.py`'s `build_retrieval_service(...)` instead of duplicating provider construction.
16. Sync or retire `test_suite_smoke.py`.
17. Add `PySide6` to `requirements.txt` (or remove `frontend.py` — decide which).
18. Add a `.gitignore` (`data/`, `__pycache__/`, `.pytest_cache/`, `*.pyc`).

**Step 7 — Final foundation acceptance check**
19. Run a manual end-to-end session (not a unit test): fresh DB, several turns including at least one tool call, one "remember that..." style statement, and one follow-up turn that should retrieve something from an earlier turn. Confirm via a smoke script (like the stubbed-LLM one used in this review) that Core Memory, Long-Term Memory, Diary, and Operation Results all show non-trivial content in a later turn's compiled context — not just Recall.
20. Once that passes, you have what you defined as done: complete Knowledge/State ↔ Context ↔ Agent integration. This is the point to start Phase 2 (Capability Core) per your own build plan.

---

## Part 4 — Beyond the Fix List: Strengthening the Foundation

These aren't blockers, but they're worth doing before or shortly after Step 7, because they'll pay for themselves as soon as you add capabilities on top.

**1. Add one "golden path" end-to-end test, checked into the repo (not just run manually).**
You have excellent unit and now-decent agent-assembly tests, but nothing that runs `agent.run()` against a real (temp) SQLite DB across multiple turns and asserts on cross-turn behavior (e.g., "a fact stated in turn 1 is retrievable in turn 3"). This is the test that would have caught both live bugs in this review before I did. It's also the test most likely to catch regressions once capability code starts touching state, memory, and diary concurrently.

**2. Decide the Operation Results / tool-call unification story now, not after capabilities.**
You currently have two parallel representations of "a tool did something": the old string-based `self.messages` tool entries, and the new `OperationResult` model. Once capabilities exist, every capability's output will need to become one or the other. Deciding this now (probably: capabilities always produce `OperationResult`, and `self.messages`'s tool-role entries become a rendering of that, not a separate source of truth) avoids a bigger refactor later.

**3. Establish a lightweight test-currency check.**
The two bugs in this review (`operation_results` AttributeError, stale smoke test) are both instances of "the test suite didn't keep pace with `agent.py`'s attribute surface." Since you're using code agents heavily, a cheap guardrail: whenever `agent.py`'s `__init__` or `_build_context` signature changes, grep for every `object.__new__(JarvisAgent)` test harness and confirm it still sets every attribute `_build_context` touches. This is exactly the kind of thing that's invisible to whoever's prompting the code agent turn-by-turn but obvious in a dedicated review pass — worth either automating (a small script) or making a standing checklist item.

**4. Give Memory Formation and Diary recording explicit, named trigger policies — write them down.**
Your architecture doc is very clear that "not every message becomes a memory" and diary/memory are conceptually distinct. Once you wire the call sites (Step 3–4 above), the *policy* of when they fire is a real design decision, not just an implementation detail — e.g., "Diary records one event per tool execution plus session start/end" and "Memory Formation runs the extractor once per user turn, never on assistant/tool turns." Writing that policy down next to the code (a short docstring or a section in your architecture doc) will matter a lot once capability code wants to also write diary entries or trigger memory formation — it needs a documented contract to call into, not just "whatever `agent.run()` currently happens to do."

**5. Consider a minimal, manual Knowledge-ingestion entry point before Phase 2.**
Not a capability yet — just a small script (`ingest_file.py` or similar) that calls `KnowledgeIngestionService.ingest_text(...)` directly, so you can put real content into Knowledge (e.g., ingest `architecture.md` itself) and validate that `KnowledgeProvider` retrieval actually surfaces relevant passages in a live context. Right now Knowledge retrieval has never been exercised against real data — only fixtures in tests — and it's cheap to close that gap before you're relying on it under a capability.

**6. Keep the "R2.x" section headers in `agent.py`'s comments as a running index.**
You're already doing this informally (`# R2.4G:`, `# R2.11 will expand this layer...`). This has been genuinely useful for me to reconstruct scope/intent quickly during review. Consider keeping a short `CHANGELOG.md` or a "Current R2 status" section in your architecture doc, updated each time a sub-phase closes — it'll make future review passes (by me or anyone else) faster, and it'll make it easier for you to spot exactly the kind of "reads wired, writes not wired" asymmetry this review surfaced, without needing an external pass to find it.
