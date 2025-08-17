import app.openai_ops as ops
from app.openai_ops import (
    format_assistant_reply,
    format_openai_message_content,
)
from app.openai_constants import GPT_4O_MODEL


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
