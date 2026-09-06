import sys
import time
import statistics
import types

from jarvis.core.agent import JarvisAgent


TEST_INPUT = "Open WhatsApp."
RUNS = 5


def safe_print(value):
    try:
        print(value)
    except UnicodeEncodeError:
        print(
            str(value)
            .encode("utf-8", errors="replace")
            .decode("utf-8")
        )


def median(values):
    values = [value for value in values if value is not None]

    if not values:
        return None

    return statistics.median(values)


def instrument_agent(agent):
    """
    Instrument the real JarvisAgent without changing production code.

    The benchmark observes the existing runtime boundaries:

        _build_context()
        _run_agent_turn()
        _execute_capability_request()

    The original methods are still executed normally.

    Returns:
        metrics: per-run metrics dictionary
        restore: function that restores the original methods
    """

    metrics = {
        "context_builds": 0,
        "context_times": [],
        "context_profiles": [],
        "context_tokens": [],
        "llm_calls": 0,
        "llm_times": [],
        "tool_calls": 0,
        "tool_times": [],
        "tool_names": [],
        "run_start": None,
        "run_end": None,
    }

    # ------------------------------------------------------------
    # Context instrumentation
    # ------------------------------------------------------------

    original_build_context = agent._build_context

    def timed_build_context(
        self,
        computation_state,
        demand_signals,
        user_input="",
        operation_results=None,
    ):
        started = time.perf_counter()

        context = original_build_context(
            computation_state=computation_state,
            demand_signals=demand_signals,
            user_input=user_input,
            operation_results=operation_results,
        )

        elapsed = time.perf_counter() - started

        metrics["context_builds"] += 1
        metrics["context_times"].append(elapsed)

        # Estimate the actual compiled context size using
        # the same ContextWindowManager used by production.
        try:
            token_count = agent.context_window.estimate_context_tokens(
                context
            )
        except Exception:
            token_count = None

        metrics["context_tokens"].append(token_count)

        return context

    agent._build_context = types.MethodType(
        timed_build_context,
        agent,
    )

    # ------------------------------------------------------------
    # Context-policy instrumentation
    # ------------------------------------------------------------

    original_policy_decide = agent.context_policy.decide

    def timed_policy_decide(state, signals):
        decision = original_policy_decide(
            state=state,
            signals=signals,
        )

        metrics["context_profiles"].append(
            decision.profile
        )

        return decision

    agent.context_policy.decide = timed_policy_decide

    # ------------------------------------------------------------
    # LLM instrumentation
    # ------------------------------------------------------------

    original_run_agent_turn = agent._run_agent_turn

    def timed_run_agent_turn(
        self,
        context,
    ):
        started = time.perf_counter()

        result = original_run_agent_turn(context)

        elapsed = time.perf_counter() - started

        metrics["llm_calls"] += 1
        metrics["llm_times"].append(elapsed)

        return result

    agent._run_agent_turn = types.MethodType(
        timed_run_agent_turn,
        agent,
    )

    # ------------------------------------------------------------
    # Capability/tool instrumentation
    # ------------------------------------------------------------

    original_execute_capability_request = (
        agent._execute_capability_request
    )

    def timed_execute_capability_request(
        self,
        request,
    ):
        started = time.perf_counter()

        result = original_execute_capability_request(request)

        elapsed = time.perf_counter() - started

        metrics["tool_calls"] += 1
        metrics["tool_times"].append(elapsed)
        metrics["tool_names"].append(request.operation)

        return result

    agent._execute_capability_request = types.MethodType(
        timed_execute_capability_request,
        agent,
    )

    def restore():
        """Restore every production method modified by this benchmark."""
        agent._build_context = original_build_context
        agent.context_policy.decide = original_policy_decide
        agent._run_agent_turn = original_run_agent_turn
        agent._execute_capability_request = (
            original_execute_capability_request
        )

    return metrics, restore


def profile_name(profile):
    if profile is None:
        return "unknown"

    try:
        return profile.name
    except AttributeError:
        return str(profile)


def print_run_result(
    agent,
    run_number,
    result,
    metrics,
    total_time,
):
    print("\\n" + "-" * 70)
    print("RUN RESULT")
    print("-" * 70)

    print(
        f"Total time:              "
        f"{total_time:.3f}s"
    )

    context_total = sum(metrics["context_times"])

    print(
        f"Context build time:      "
        f"{context_total:.3f}s"
    )

    print(
        f"Context builds:          "
        f"{metrics['context_builds']}"
    )

    valid_tokens = [
        value
        for value in metrics["context_tokens"]
        if value is not None
    ]

    if valid_tokens:
        print(
            f"Context tokens:          "
            f"{valid_tokens[-1]:.0f}"
        )

    if metrics["context_profiles"]:
        print(
            "Context profiles:        "
            + ", ".join(
                profile_name(profile)
                for profile in metrics["context_profiles"]
            )
        )

    print(
        f"LLM calls:               "
        f"{metrics['llm_calls']}"
    )

    if metrics["llm_times"]:
        print(
            f"LLM time:                "
            f"{sum(metrics['llm_times']):.3f}s"
        )

    print(
        f"Tool calls:              "
        f"{metrics['tool_calls']}"
    )

    if metrics["tool_names"]:
        print(
            "Tools:                   "
            + ", ".join(metrics["tool_names"])
        )

    if metrics["tool_times"]:
        print(
            f"Tool execution time:     "
            f"{sum(metrics['tool_times']):.3f}s"
        )

    if result:
        safe_print(
            f"Final response:          {result}"
        )

    trace = getattr(
        agent,
        "last_execution_trace",
        None,
    )

    if trace is not None:
        try:
            print(
                f"Trace steps:             "
                f"{len(trace.steps)}"
            )
        except Exception:
            pass

    print(
        f"Result status:           "
        f"{'SUCCESS' if result else 'NO RESPONSE'}"
    )


def run_once(agent, run_number):
    print("\\n" + "=" * 70)
    print(f"RUN {run_number}")
    print("=" * 70)

    metrics, restore = instrument_agent(agent)

    started = time.perf_counter()

    try:
        result = agent.run(TEST_INPUT)
    except Exception as exc:
        total_time = time.perf_counter() - started

        print(
            f"\\nRUN FAILED after "
            f"{total_time:.3f}s"
        )

        safe_print(
            f"{type(exc).__name__}: {exc}"
        )

        restore()

        return {
            "run": run_number,
            "success": False,
            "total_time": total_time,
            "context_time": sum(
                metrics["context_times"]
            ),
            "context_tokens": (
                metrics["context_tokens"][-1]
                if metrics["context_tokens"]
                else None
            ),
            "llm_time": sum(
                metrics["llm_times"]
            ),
            "llm_calls": metrics["llm_calls"],
            "tool_time": sum(
                metrics["tool_times"]
            ),
            "tool_calls": metrics["tool_calls"],
            "profiles": [
                profile_name(profile)
                for profile in metrics["context_profiles"]
            ],
            "tool_names": metrics["tool_names"],
        }

    total_time = time.perf_counter() - started

    print_run_result(
        agent=agent,
        run_number=run_number,
        result=result,
        metrics=metrics,
        total_time=total_time,
    )

    restore()

    return {
        "run": run_number,
        "success": bool(result),
        "total_time": total_time,
        "context_time": sum(
            metrics["context_times"]
        ),
        "context_tokens": (
            metrics["context_tokens"][-1]
            if metrics["context_tokens"]
            else None
        ),
        "llm_time": sum(
            metrics["llm_times"]
        ),
        "llm_calls": metrics["llm_calls"],
        "tool_time": sum(
            metrics["tool_times"]
        ),
        "tool_calls": metrics["tool_calls"],
        "profiles": [
            profile_name(profile)
            for profile in metrics["context_profiles"]
        ],
        "tool_names": metrics["tool_names"],
    }


def main():
    try:
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        pass

    print("=" * 70)
    print("JARVIS — O2.4")
    print("ADAPTIVE CONTEXT REAL RUNTIME BENCHMARK")
    print("=" * 70)

    print(
        f"Input:       {TEST_INPUT}"
    )
    print(
        f"Runs:        {RUNS}"
    )
    print(
        "Agent:       JarvisAgent"
    )
    print(
        "Pipeline:    Agent → O1 → O2 → Qwen → apps.launch"
    )
    print()

    # ------------------------------------------------------------
    # One real Agent instance.
    #
    # This preserves the normal Jarvis runtime lifecycle and
    # allows the benchmark to observe the same Agent across
    # repeated commands.
    # ------------------------------------------------------------

    agent = JarvisAgent()

    results = []

    for run_number in range(1, RUNS + 1):
        result = run_once(
            agent,
            run_number,
        )

        results.append(result)

    # ------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------

    print("\\n" + "=" * 70)
    print("O2.4 SUMMARY")
    print("=" * 70)

    successful = [
        result
        for result in results
        if result["success"]
    ]

    print(
        f"Successful runs:        "
        f"{len(successful)}/{len(results)}"
    )

    if not successful:
        print(
            "\\nNo successful runs were available "
            "for median analysis."
        )
        return

    total_times = [
        result["total_time"]
        for result in successful
    ]

    context_times = [
        result["context_time"]
        for result in successful
    ]

    llm_times = [
        result["llm_time"]
        for result in successful
    ]

    tool_times = [
        result["tool_time"]
        for result in successful
    ]

    context_tokens = [
        result["context_tokens"]
        for result in successful
        if result["context_tokens"] is not None
    ]

    llm_calls = [
        result["llm_calls"]
        for result in successful
    ]

    tool_calls = [
        result["tool_calls"]
        for result in successful
    ]

    print(
        f"Median total time:      "
        f"{median(total_times):.3f}s"
    )

    print(
        f"Median context time:    "
        f"{median(context_times):.3f}s"
    )

    if context_tokens:
        print(
            f"Median context tokens:  "
            f"{median(context_tokens):.0f}"
        )

    print(
        f"Median LLM time:        "
        f"{median(llm_times):.3f}s"
    )

    print(
        f"Median tool time:       "
        f"{median(tool_times):.3f}s"
    )

    print(
        f"Median LLM calls:       "
        f"{median(llm_calls):.0f}"
    )

    print(
        f"Median tool calls:      "
        f"{median(tool_calls):.0f}"
    )

    all_profiles = []

    for result in successful:
        all_profiles.extend(
            result["profiles"]
        )

    if all_profiles:
        print(
            "Context profiles:       "
            + " → ".join(all_profiles)
        )

    all_tools = []

    for result in successful:
        all_tools.extend(
            result["tool_names"]
        )

    if all_tools:
        print(
            "Operations observed:    "
            + ", ".join(
                sorted(set(all_tools))
            )
        )

    print("\\nInterpretation:")

    print(
        "This benchmark measures the real JarvisAgent "
        "runtime rather than a synthetic context pipeline."
    )

    print(
        "Context timings include retrieval, adaptive "
        "selection, compilation, and context-window preparation."
    )

    print(
        "LLM timings measure the actual model turn(s), "
        "while tool timings measure the real capability execution."
    )

    print(
        "These readings establish the O2.4 runtime baseline "
        "needed for comparison against later optimization changes."
    )


if __name__ == "__main__":
    main()


out = Path("/mnt/data/test_adaptive_context_runtime_fixed.py")
out.write_text(fixed, encoding="utf-8")

# Syntax validation without importing the Jarvis project.
compile(fixed, str(out), "exec")

print(f"Fixed file created: {out}")
print(f"Lines: {len(fixed.splitlines())}")
print("Syntax validation: PASSED")
