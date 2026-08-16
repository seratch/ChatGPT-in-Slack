import app.openai_ops as ops
from app.openai_ops import (
    format_assistant_reply,
    format_openai_message_content,
)
from app.openai_constants import (
    GPT_4O_MODEL,
    GPT_5_CHAT_LATEST_MODEL,
    GPT_5_SEARCH_API_MODEL,
    GPT_5_3_CHAT_LATEST_MODEL,
    GPT_5_4_MODEL,
    GPT_5_5_MODEL,
    GPT_5_6_MODEL,
    GPT_5_6_SOL_MODEL,
    GPT_5_6_TERRA_MODEL,
    GPT_5_6_LUNA_MODEL,
    MAX_TOKENS,
)
import pytest


class _FakeResponse:
    def __init__(self, payload=None):
        # Minimal dump similar to SDK's pydantic objects
        self._payload = payload or {"choices": [{"message": {"content": "ok"}}]}

    def model_dump(self):
        return self._payload


@pytest.fixture
def fake_clients(monkeypatch):
    """Patch OpenAI with a fake and capture init/create kwargs.

    Returns a dict store capturing:
    - init_openai_kwargs
    - create_kwargs
    """
    import app.openai_api_utils as api_utils

    store: dict = {}

    class _FakeCompletions:
        def create(self, **kwargs):
            store["create_kwargs"] = kwargs
            return _FakeResponse()

    class _FakeChat:
        def __init__(self):
            self.completions = _FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            store["init_openai_kwargs"] = kwargs
            self.chat = _FakeChat()

    monkeypatch.setattr(api_utils, "OpenAI", FakeOpenAI)
    return store


def test_format_assistant_reply():
    for content, expected in [
        (
            "\n\nSorry, I cannot answer the question.",
            "Sorry, I cannot answer the question.",
        ),
        ("\n\n```python\necho 'foo'\n```", "```\necho 'foo'\n```"),
        ("\n\n```ruby\nputs 'foo'\n```", "```\nputs 'foo'\n```"),
        (
            "\n\n```java\nSystem.out.println(123);\n```",
            "```\nSystem.out.println(123);\n```",
        ),
        ("\n\n```C\n#include <stdio.h>\n```", "```\n#include <stdio.h>\n```"),
        ("\n\n```c\n#include <stdio.h>\n```", "```\n#include <stdio.h>\n```"),
        ("\n\n```C++\n#include <iostream>\n```", "```\n#include <iostream>\n```"),
        ("\n\n```c++\n#include <iostream>\n```", "```\n#include <iostream>\n```"),
        ("\n\n```Cpp\n#include <iostream>\n```", "```\n#include <iostream>\n```"),
        ("\n\n```cpp\n#include <iostream>\n```", "```\n#include <iostream>\n```"),
        ("\n\n```Csharp\nusing System;\n```", "```\nusing System;\n```"),
        ("\n\n```csharp\nusing System;\n```", "```\nusing System;\n```"),
        ("\n\n```Matlab\ndisp('foo');\n```", "```\ndisp('foo');\n```"),
        ("\n\n```matlab\ndisp('foo');\n```", "```\ndisp('foo');\n```"),
        ("\n\n```JSON\n{\n```", "```\n{\n```"),
        ("\n\n```json\n{\n```", "```\n{\n```"),
        (
            "\n\n```LaTeX\n\\documentclass{article}\n```",
            "```\n\\documentclass{article}\n```",
        ),
        (
            "\n\n```latex\n\\documentclass{article}\n```",
            "```\n\\documentclass{article}\n```",
        ),
        ("\n\n```lua\nx = 1\n```", "```\nx = 1\n```"),
        (
            "\n\n```cmake\ncmake_minimum_required(VERSION 3.24)\n```",
            "```\ncmake_minimum_required(VERSION 3.24)\n```",
        ),
        ("\n\n```bash\n#!/bin/bash\n```", "```\n#!/bin/bash\n```"),
        ("\n\n```zsh\n#!/bin/zsh\n```", "```\n#!/bin/zsh\n```"),
        ("\n\n```sh\n#!/bin/sh\n```", "```\n#!/bin/sh\n```"),
    ]:
        result = format_assistant_reply(content, False)
        assert result == expected


def test_format_openai_message_content():
    # https://github.com/seratch/ChatGPT-in-Slack/pull/5
    for content, expected in [
        (
            """#include &lt;stdio.h&gt;
int main(int argc, char *argv[])
{
    printf("Hello, world!\n");
    return 0;
}""",
            """#include <stdio.h>
int main(int argc, char *argv[])
{
    printf("Hello, world!\n");
    return 0;
}""",
        ),
    ]:
        result = format_openai_message_content(content, False)
        assert result == expected


def test_messages_within_context_window_passes_model(monkeypatch):
    """Ensures token counting receives the actual OPENAI_MODEL from context."""
    captured = {"model": None, "calls": 0}

    def fake_calculate_num_tokens(messages, model=None):  # type: ignore[no-redef]
        captured["model"] = model
        captured["calls"] += 1
        return 0  # Keep under threshold to avoid loop iterations

    monkeypatch.setattr(ops, "calculate_num_tokens", fake_calculate_num_tokens)

    messages = [{"role": "user", "content": "hi"}]
    context = {
        "OPENAI_MODEL": GPT_4O_MODEL,
        "OPENAI_FUNCTION_CALL_MODULE_NAME": None,
    }

    # Execute
    ops.messages_within_context_window(messages, context)  # type: ignore[arg-type]

    # Assert the model used for token counting matches context
    assert captured["calls"] >= 1
    assert captured["model"] == GPT_4O_MODEL


@pytest.mark.parametrize(
    "model,expected",
    [
        ("chat-latest", False),
        ("gpt-5-chat-latest", False),
        ("gpt-5.1-chat-latest", False),
        ("gpt-5.2-chat-latest", False),
        ("gpt-5.3-chat-latest", False),
        ("gpt-5-search-api", False),
        ("gpt-5.1-2025-11-13", True),
        ("gpt-5.2-2025-12-11", True),
        ("gpt-5.4", True),
        ("gpt-5.4-mini", True),
        ("gpt-5.4-nano", True),
        ("gpt-5.5", True),
        ("gpt-5.5-2026-04-23", True),
        (GPT_5_6_MODEL, True),
        (GPT_5_6_SOL_MODEL, True),
        (GPT_5_6_TERRA_MODEL, True),
        (GPT_5_6_LUNA_MODEL, True),
        ("gpt-5-nano", True),
        ("o3", True),
        ("o4-mini", True),
        ("o1-preview", True),
        ("gpt-4o", False),
    ],
)
def test_is_reasoning_heuristics(model, expected):
    assert ops._is_reasoning(model) is expected


@pytest.mark.parametrize("api_type", ["openai", "azure"])
@pytest.mark.parametrize(
    "model,is_reasoning,temperature,timeout,user",
    [
        ("chat-latest", False, 0.6, 10, "U111"),
        (GPT_4O_MODEL, False, 0.7, 12, "U123"),
        ("o3", True, 1.0, 5, "U234"),
        (GPT_5_SEARCH_API_MODEL, False, 0.5, 8, "U345"),
        (GPT_5_CHAT_LATEST_MODEL, False, 0.6, 10, "U456"),
        ("gpt-5.1-chat-latest", False, 0.55, 11, "U567"),
        ("gpt-5.2-chat-latest", False, 0.55, 11, "U678"),
        (GPT_5_3_CHAT_LATEST_MODEL, False, 0.55, 11, "U789"),
        (GPT_5_4_MODEL, True, 0.55, 11, "U890"),
        (GPT_5_5_MODEL, True, 0.55, 11, "U895"),
        (GPT_5_6_MODEL, True, 0.55, 11, "U896"),
        (GPT_5_6_SOL_MODEL, True, 0.55, 11, "U897"),
        (GPT_5_6_TERRA_MODEL, True, 0.55, 11, "U898"),
        (GPT_5_6_LUNA_MODEL, True, 0.55, 11, "U899"),
        ("gpt-5.4-mini", True, 0.55, 11, "U901"),
        ("gpt-5.4-nano", True, 0.55, 11, "U902"),
    ],
)
def test_sync_tokens_and_sampling_behavior(
    fake_clients, api_type, model, is_reasoning, temperature, timeout, user
):
    import app.openai_ops as ops

    _ = ops.make_synchronous_openai_call(
        openai_api_key="k",
        model=model,
        temperature=temperature,
        messages=[{"role": "user", "content": "hi"}],
        user=user,
        openai_api_type=api_type,
        openai_api_base=(
            "https://example.invalid/v1"
            if api_type == "openai"
            else "https://azure.example"
        ),
        openai_deployment_id=("" if api_type == "openai" else "dep-xyz"),
        openai_organization_id=None,
        timeout_seconds=timeout,
    )

    kwargs = fake_clients["create_kwargs"]
    is_search = model.startswith("gpt-5-search")
    token_keys = {"max_tokens", "max_completion_tokens"} & kwargs.keys()
    assert len(token_keys) == 1, f"Expected exactly one token key, got {token_keys}"
    token_key = token_keys.pop()

    if is_reasoning:
        assert token_key == "max_completion_tokens"
        assert kwargs.get("max_completion_tokens") == MAX_TOKENS
        for k in (
            "temperature",
            "presence_penalty",
            "frequency_penalty",
            "logit_bias",
            "top_p",
        ):
            assert k not in kwargs
    elif is_search:
        assert token_key == "max_completion_tokens"
        assert kwargs.get("max_completion_tokens") == MAX_TOKENS
        for k in (
            "temperature",
            "presence_penalty",
            "frequency_penalty",
            "logit_bias",
            "top_p",
        ):
            assert k not in kwargs
    else:
        if model == "chat-latest":
            assert token_key == "max_completion_tokens"
            assert kwargs.get("max_completion_tokens") == MAX_TOKENS
        elif model.lower().startswith("gpt-5"):
            assert token_key == "max_completion_tokens"
            assert kwargs.get("max_completion_tokens") == MAX_TOKENS
        else:
            assert token_key == "max_tokens"
            assert kwargs.get("max_tokens") == MAX_TOKENS
        sampling_keys = {
            k
            for k in (
                "temperature",
                "presence_penalty",
                "frequency_penalty",
                "logit_bias",
                "top_p",
            )
            if k in kwargs
        }
        ml = model.lower()
        if model == "chat-latest":
            assert sampling_keys == set()
        elif ml.startswith(("gpt-5.1", "gpt-5.2", "gpt-5.3")):
            assert sampling_keys == set()
        elif ml.startswith("gpt-5"):
            assert sampling_keys == {
                "temperature",
                "presence_penalty",
                "frequency_penalty",
                "logit_bias",
                "top_p",
            }
            assert kwargs.get("temperature") == temperature
            assert kwargs.get("presence_penalty") == 0
            assert kwargs.get("frequency_penalty") == 0
            assert isinstance(kwargs.get("logit_bias"), dict)
            assert kwargs.get("top_p") == 1
        else:
            assert sampling_keys == {
                "temperature",
                "presence_penalty",
                "frequency_penalty",
                "logit_bias",
                "top_p",
            }
            assert kwargs.get("temperature") == temperature
            assert kwargs.get("presence_penalty") == 0
            assert kwargs.get("frequency_penalty") == 0
            assert isinstance(kwargs.get("logit_bias"), dict)
            assert kwargs.get("top_p") == 1
    if is_search:
        assert "n" not in kwargs
    else:
        assert kwargs.get("n") == 1
    assert kwargs.get("user") == user
    assert kwargs.get("stream") is False
    assert kwargs.get("timeout") == timeout
    assert kwargs.get("model") == ("dep-xyz" if api_type == "azure" else model)


@pytest.mark.parametrize("api_type", ["openai", "azure"])
@pytest.mark.parametrize("with_functions", [True, False])
def test_stream_functions_and_timeout(
    fake_clients, api_type, with_functions, monkeypatch
):
    import app.openai_ops as ops
    import sys
    import types

    module_name = "app.fake_functions_mod"
    if with_functions:
        fake_mod = types.ModuleType(module_name)
        fake_mod.functions = [
            {"name": "add", "parameters": {"type": "object", "properties": {}}}
        ]
        sys.modules[module_name] = fake_mod
    else:
        if module_name in sys.modules:
            del sys.modules[module_name]

    _ = ops.start_receiving_openai_response(
        openai_api_key="k",
        model=GPT_4O_MODEL,
        temperature=0.5,
        messages=[{"role": "user", "content": "hi"}],
        user="U345",
        openai_api_type=api_type,
        openai_api_base=(
            "https://api.example/v1"
            if api_type == "openai"
            else "https://azure.example"
        ),
        openai_deployment_id=("" if api_type == "openai" else "dep-xyz"),
        openai_organization_id=None,
        function_call_module_name=(module_name if with_functions else None),
    )

    kwargs = fake_clients["create_kwargs"]
    assert kwargs.get("stream") is True
    assert "timeout" not in kwargs
    assert ("functions" in kwargs) is with_functions
    assert kwargs.get("model") == ("dep-xyz" if api_type == "azure" else GPT_4O_MODEL)


@pytest.mark.parametrize("base_url", ["", "   "])
def test_create_openai_client_openai_org_and_base_url_none(fake_clients, base_url):
    import app.openai_ops as ops
    from types import SimpleNamespace

    # base_url should be None if empty string provided
    ctx = SimpleNamespace(
        get=lambda k: {
            "OPENAI_API_TYPE": None,
            "OPENAI_API_KEY": "k",
            "OPENAI_API_BASE": base_url,
            "OPENAI_DEPLOYMENT_ID": None,
            "OPENAI_ORG_ID": "org_X",
        }.get(k)
    )
    _ = ops.create_openai_client(ctx)  # type: ignore[arg-type]
    init = fake_clients["init_openai_kwargs"]
    assert init.get("base_url") is None
    assert init.get("organization") == "org_X"


def test_create_openai_client_azure(fake_clients):
    import app.openai_ops as ops
    from types import SimpleNamespace

    ctx = SimpleNamespace(
        get=lambda k: {
            "OPENAI_API_TYPE": "azure",
            "OPENAI_API_KEY": "k",
            "OPENAI_API_BASE": "https://azure.example",
            "OPENAI_DEPLOYMENT_ID": "dep-1",
            "OPENAI_ORG_ID": None,
        }.get(k)
    )
    _ = ops.create_openai_client(ctx)  # type: ignore[arg-type]
    init = fake_clients["init_openai_kwargs"]
    assert init.get("api_key") == "k"
    assert init.get("base_url") == "https://azure.example/openai/v1/"
    assert "organization" not in init


def test_stream_timeout_guard_raises(fake_clients):
    import app.openai_ops as ops

    with pytest.raises(ValueError):
        _ = ops._create_chat_completion(
            openai_api_key="k",
            model=GPT_4O_MODEL,
            temperature=0.2,
            messages=[{"role": "user", "content": "hi"}],
            user="U888",
            openai_api_type="openai",
            openai_api_base="https://api.example/v1",
            openai_deployment_id="",
            openai_organization_id=None,
            stream=True,
            timeout_seconds=10,
            function_call_module_name=None,
        )


@pytest.mark.parametrize(
    "api_type,base,deployment,org",
    [
        ("openai", "", "", "org_X"),
        ("azure", "https://azure.example", "dep-xyz", None),
    ],
)
def test_sync_client_init_params(fake_clients, api_type, base, deployment, org):
    import app.openai_ops as ops

    _ = ops.make_synchronous_openai_call(
        openai_api_key="k",
        model=GPT_4O_MODEL,
        temperature=0.2,
        messages=[{"role": "user", "content": "hi"}],
        user="U_init",
        openai_api_type=api_type,
        openai_api_base=base,
        openai_deployment_id=deployment,
        openai_organization_id=org,
        timeout_seconds=3,
    )

    if api_type == "openai":
        init = fake_clients["init_openai_kwargs"]
        assert init.get("api_key") == "k"
        assert init.get("base_url") is None  # empty string normalized
        assert init.get("organization") == "org_X"
    else:
        init = fake_clients["init_openai_kwargs"]
        assert init.get("api_key") == "k"
        assert init.get("base_url") == "https://azure.example/openai/v1/"
        assert "organization" not in init


def test_function_call_token_probe_uses_azure_deployment(monkeypatch):
    import app.openai_ops as ops
    from types import SimpleNamespace

    create_kwargs = []

    class FakeCompletions:
        def create(self, **kwargs):
            create_kwargs.append(kwargs)
            prompt_tokens = 20 if "functions" in kwargs else 5
            return _FakeResponse({"usage": {"prompt_tokens": prompt_tokens}})

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions()),
    )
    context = SimpleNamespace(
        get=lambda key: {
            "OPENAI_FUNCTION_CALL_MODULE_NAME": "app.fake_functions_mod",
            "OPENAI_MODEL": GPT_4O_MODEL,
            "OPENAI_API_TYPE": "azure",
            "OPENAI_DEPLOYMENT_ID": "dep-xyz",
        }.get(key)
    )
    module = SimpleNamespace(
        functions=[{"name": "test", "parameters": {"type": "object"}}]
    )
    monkeypatch.setattr(ops, "create_openai_client", lambda context: client)
    monkeypatch.setattr(ops, "import_module", lambda name: module)
    previous_cache = ops._prompt_tokens_used_by_function_call_cache
    ops._prompt_tokens_used_by_function_call_cache = None

    try:
        assert (
            ops.calculate_tokens_necessary_for_function_call(context)  # type: ignore[arg-type]
            == 15
        )
    finally:
        ops._prompt_tokens_used_by_function_call_cache = previous_cache

    assert [kwargs["model"] for kwargs in create_kwargs] == ["dep-xyz", "dep-xyz"]
