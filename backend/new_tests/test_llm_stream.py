from types import SimpleNamespace

from jarvis.core.llm import LLMClient


def make_chunk(
    *,
    thinking="",
    content="",
    tool_calls=None,
    done=False,
    total_duration=None,
    eval_count=None,
):
    return SimpleNamespace(
        message=SimpleNamespace(
            thinking=thinking,
            content=content,
            tool_calls=tool_calls or [],
        ),
        done=done,
        total_duration=total_duration,
        load_duration=None,
        prompt_eval_count=None,
        prompt_eval_duration=None,
        eval_count=eval_count,
        eval_duration=None,
    )


def make_tool_call(
    call_id="call-1",
    name="apps.launch",
    arguments=None,
):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(
            name=name,
            arguments=arguments or {},
        ),
    )


def test_stream_yields_observations(monkeypatch):
    chunks = [
        make_chunk(thinking="I should act."),
        make_chunk(content="Opening WhatsApp."),
        make_chunk(done=True),
    ]

    client = LLMClient()

    calls = []

    def fake_chat(**kwargs):
        calls.append(kwargs)
        return iter(chunks)

    monkeypatch.setattr(client.client, "chat", fake_chat)

    observations = list(
        client.stream(
            messages=[{"role": "user", "content": "Open WhatsApp"}],
            tools=[],
        )
    )

    assert len(observations) == 3

    assert observations[0]["thinking"] == "I should act."
    assert observations[1]["content"] == "Opening WhatsApp."
    assert observations[2]["done"] is True

    assert calls[0]["stream"] is True


def test_stream_preserves_tool_calls_exactly(monkeypatch):
    tool_call = make_tool_call(
        call_id="call-42",
        name="apps.launch",
        arguments={"app": "WhatsApp"},
    )

    client = LLMClient()

    monkeypatch.setattr(
        client.client,
        "chat",
        lambda **kwargs: iter(
            [
                make_chunk(
                    tool_calls=[tool_call],
                    done=True,
                )
            ]
        ),
    )

    observations = list(
        client.stream(
            messages=[],
            tools=[],
        )
    )

    assert observations[0]["tool_calls"] == [tool_call]
    assert observations[0]["tool_calls"][0] is tool_call


def test_stream_exposes_thinking_and_content_separately(monkeypatch):
    client = LLMClient()

    monkeypatch.setattr(
        client.client,
        "chat",
        lambda **kwargs: iter(
            [
                make_chunk(thinking="Reasoning"),
                make_chunk(content="Final answer"),
                make_chunk(done=True),
            ]
        ),
    )

    observations = list(
        client.stream(
            messages=[],
            tools=[],
        )
    )

    assert observations[0]["thinking"] == "Reasoning"
    assert observations[0]["content"] == ""

    assert observations[1]["thinking"] == ""
    assert observations[1]["content"] == "Final answer"


def test_stream_exposes_timing_metadata(monkeypatch):
    client = LLMClient()

    monkeypatch.setattr(
        client.client,
        "chat",
        lambda **kwargs: iter(
            [
                make_chunk(
                    done=True,
                    total_duration=123456,
                    eval_count=17,
                )
            ]
        ),
    )

    observations = list(
        client.stream(
            messages=[],
            tools=[],
        )
    )

    timing = observations[0]["timing"]

    assert timing["total_duration"] == 123456
    assert timing["eval_count"] == 17


def test_stream_can_be_terminated_early(monkeypatch):
    tool_call = make_tool_call(
        name="apps.launch",
        arguments={"app": "WhatsApp"},
    )

    consumed = []

    def fake_stream():
        chunks = [
            make_chunk(thinking="thinking"),
            make_chunk(tool_calls=[tool_call]),
            make_chunk(content="This should not be consumed."),
            make_chunk(done=True),
        ]

        for chunk in chunks:
            consumed.append(chunk)
            yield chunk

    client = LLMClient()

    monkeypatch.setattr(
        client.client,
        "chat",
        lambda **kwargs: fake_stream(),
    )

    for observation in client.stream(
        messages=[],
        tools=[],
    ):
        if observation["tool_calls"]:
            break

    assert len(consumed) == 2


def test_follow_up_request_works_after_early_termination(monkeypatch):
    tool_call = make_tool_call(
        name="apps.launch",
        arguments={"app": "WhatsApp"},
    )

    requests = []

    def fake_chat(**kwargs):
        requests.append(kwargs)

        if len(requests) == 1:
            return iter(
                [
                    make_chunk(tool_calls=[tool_call]),
                    make_chunk(content="ignored"),
                ]
            )

        return iter(
            [
                make_chunk(content="WhatsApp is open."),
                make_chunk(done=True),
            ]
        )

    client = LLMClient()

    monkeypatch.setattr(
        client.client,
        "chat",
        fake_chat,
    )

    first_observation = None

    for observation in client.stream(
        messages=[
            {
                "role": "user",
                "content": "Open WhatsApp",
            }
        ],
        tools=[],
    ):
        first_observation = observation

        if observation["tool_calls"]:
            break

    assert first_observation["tool_calls"] == [tool_call]

    follow_up = list(
        client.stream(
            messages=[
                {
                    "role": "user",
                    "content": "Open WhatsApp",
                },
                {
                    "role": "tool",
                    "content": "success",
                },
            ],
            tools=[],
        )
    )

    assert follow_up[-1]["done"] is True
    assert follow_up[0]["content"] == "WhatsApp is open."

    assert len(requests) == 2
    assert requests[0]["stream"] is True
    assert requests[1]["stream"] is True


def test_existing_chat_remains_non_streaming(monkeypatch):
    client = LLMClient()

    calls = []

    response = object()

    def fake_chat(**kwargs):
        calls.append(kwargs)
        return response

    monkeypatch.setattr(
        client.client,
        "chat",
        fake_chat,
    )

    result = client.chat(
        messages=[],
        tools=[],
    )

    assert result is response
    assert len(calls) == 1
    assert calls[0]["stream"] is False