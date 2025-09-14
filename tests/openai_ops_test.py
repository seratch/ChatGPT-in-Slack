import app.openai_ops as ops
from app.openai_ops import (
    format_assistant_reply,
    format_openai_message_content,
)
from app.openai_constants import GPT_4O_MODEL
from app.openai_constants import MAX_TOKENS
import pytest


class _FakeResponse:
    def __init__(self, payload=None):
        # Minimal dump similar to SDK's pydantic objects
        self._payload = payload or {"choices": [{"message": {"content": "ok"}}]}

    def model_dump(self):
        return self._payload


@pytest.fixture
def fake_clients(monkeypatch):
    """Patch OpenAI/AzureOpenAI with fakes and capture init/create kwargs.

    Returns a dict store capturing:
    - init_openai_kwargs
    - init_azure_kwargs
    - create_kwargs
    """
    import app.openai_ops as ops

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

    class FakeAzureOpenAI:
        def __init__(self, **kwargs):
            store["init_azure_kwargs"] = kwargs
            self.chat = _FakeChat()

    monkeypatch.setattr(ops, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(ops, "AzureOpenAI", FakeAzureOpenAI)
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


@pytest.mark.parametrize("api_type", ["openai", "azure"])
@pytest.mark.parametrize(
    "model,is_reasoning,temperature,timeout,user",
    [
        (GPT_4O_MODEL, False, 0.7, 12, "U123"),
        ("o3", True, 1.0, 5, "U234"),
    ],
)
def test_sync_tokens_and_sampling_behavior(fake_clients, api_type, model, is_reasoning, temperature, timeout, user):
    import app.openai_ops as ops

    _ = ops.make_synchronous_openai_call(
        openai_api_key="k",
        model=model,
        temperature=temperature,
        messages=[{"role": "user", "content": "hi"}],
        user=user,
        openai_api_type=api_type,
        openai_api_base=("https://example.invalid/v1" if api_type == "openai" else "https://azure.example"),
        openai_api_version=("" if api_type == "openai" else "2025-01-01"),
        openai_deployment_id=("" if api_type == "openai" else "dep-xyz"),
        openai_organization_id=None,
        timeout_seconds=timeout,
    )

    kwargs = fake_clients["create_kwargs"]
    if is_reasoning:
        assert kwargs.get("max_completion_tokens") == MAX_TOKENS
        assert "max_tokens" not in kwargs
        for k in ("temperature", "presence_penalty", "frequency_penalty", "logit_bias"):
            assert k not in kwargs
    else:
        assert kwargs.get("max_tokens") == MAX_TOKENS
        assert kwargs.get("temperature") == temperature
        assert kwargs.get("presence_penalty") == 0
        assert kwargs.get("frequency_penalty") == 0
        assert isinstance(kwargs.get("logit_bias"), dict)
    if is_reasoning:
        assert "top_p" not in kwargs
    else:
        assert kwargs.get("top_p") == 1
    assert kwargs.get("n") == 1
    assert kwargs.get("user") == user
    assert kwargs.get("stream") is False
    assert kwargs.get("timeout") == timeout


@pytest.mark.parametrize("api_type", ["openai", "azure"])
@pytest.mark.parametrize("with_functions", [True, False])
def test_stream_functions_and_timeout(fake_clients, api_type, with_functions, monkeypatch):
    import app.openai_ops as ops
    import sys
    import types

    module_name = "app.fake_functions_mod"
    if with_functions:
        fake_mod = types.ModuleType(module_name)
        fake_mod.functions = [{"name": "add", "parameters": {"type": "object", "properties": {}}}]
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
        openai_api_base=("https://api.example/v1" if api_type == "openai" else "https://azure.example"),
        openai_api_version=("" if api_type == "openai" else "2025-01-01"),
        openai_deployment_id=("" if api_type == "openai" else "dep-xyz"),
        openai_organization_id=None,
        function_call_module_name=(module_name if with_functions else None),
    )

    kwargs = fake_clients["create_kwargs"]
    assert kwargs.get("stream") is True
    assert "timeout" not in kwargs
    assert ("functions" in kwargs) is with_functions


@pytest.mark.parametrize("base_url", ["", "   "])
def test_create_openai_client_openai_org_and_base_url_none(fake_clients, base_url):
    import app.openai_ops as ops
    from types import SimpleNamespace

    # base_url should be None if empty string provided
    ctx = SimpleNamespace(
        get=lambda k: {
            "OPENAI_API_TYPE": None,
            "OPENAI_API_KEY": "k",
            "OPENAI_API_VERSION": "v",
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
            "OPENAI_API_VERSION": "2025-01-01",
            "OPENAI_API_BASE": "https://azure.example",
            "OPENAI_DEPLOYMENT_ID": "dep-1",
            "OPENAI_ORG_ID": None,
        }.get(k)
    )
    _ = ops.create_openai_client(ctx)  # type: ignore[arg-type]
    init = fake_clients["init_azure_kwargs"]
    assert init.get("api_key") == "k"
    assert init.get("api_version") == "2025-01-01"
    assert init.get("azure_endpoint") == "https://azure.example"
    assert init.get("azure_deployment") == "dep-1"
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
            openai_api_version="",
            openai_deployment_id="",
            openai_organization_id=None,
            stream=True,
            timeout_seconds=10,
            function_call_module_name=None,
        )


@pytest.mark.parametrize(
    "api_type,base,version,deployment,org",
    [
        ("openai", "", "", "", "org_X"),
        ("azure", "https://azure.example", "2025-01-01", "dep-xyz", None),
    ],
)
def test_sync_client_init_params(fake_clients, api_type, base, version, deployment, org):
    import app.openai_ops as ops

    _ = ops.make_synchronous_openai_call(
        openai_api_key="k",
        model=GPT_4O_MODEL,
        temperature=0.2,
        messages=[{"role": "user", "content": "hi"}],
        user="U_init",
        openai_api_type=api_type,
        openai_api_base=base,
        openai_api_version=version,
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
        init = fake_clients["init_azure_kwargs"]
        assert init.get("api_key") == "k"
        assert init.get("api_version") == "2025-01-01"
        assert init.get("azure_endpoint") == "https://azure.example"
        assert init.get("azure_deployment") == "dep-xyz"
