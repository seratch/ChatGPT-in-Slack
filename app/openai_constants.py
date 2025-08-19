MAX_TOKENS = 1024
GPT_3_5_TURBO_MODEL = "gpt-3.5-turbo"
GPT_3_5_TURBO_0301_MODEL = "gpt-3.5-turbo-0301"
GPT_3_5_TURBO_0613_MODEL = "gpt-3.5-turbo-0613"
GPT_3_5_TURBO_1106_MODEL = "gpt-3.5-turbo-1106"
GPT_3_5_TURBO_0125_MODEL = "gpt-3.5-turbo-0125"
GPT_3_5_TURBO_16K_MODEL = "gpt-3.5-turbo-16k"
GPT_3_5_TURBO_16K_0613_MODEL = "gpt-3.5-turbo-16k-0613"
GPT_4_MODEL = "gpt-4"
GPT_4_0314_MODEL = "gpt-4-0314"
GPT_4_0613_MODEL = "gpt-4-0613"
GPT_4_1106_PREVIEW_MODEL = "gpt-4-1106-preview"
GPT_4_0125_PREVIEW_MODEL = "gpt-4-0125-preview"
GPT_4_TURBO_PREVIEW_MODEL = "gpt-4-turbo-preview"
GPT_4_TURBO_MODEL = "gpt-4-turbo"
GPT_4_TURBO_2024_04_09_MODEL = "gpt-4-turbo-2024-04-09"
GPT_4_32K_MODEL = "gpt-4-32k"
GPT_4_32K_0314_MODEL = "gpt-4-32k-0314"
GPT_4_32K_0613_MODEL = "gpt-4-32k-0613"
GPT_4O_MODEL = "gpt-4o"
GPT_4O_2024_05_13_MODEL = "gpt-4o-2024-05-13"
GPT_4O_MINI_MODEL = "gpt-4o-mini"
GPT_4O_MINI_2024_07_18_MODEL = "gpt-4o-mini-2024-07-18"
GPT_4_1_MODEL = "gpt-4.1"
GPT_4_1_2025_04_14_MODEL = "gpt-4.1-2025-04-14"
GPT_4_1_MINI_MODEL = "gpt-4.1-mini"
GPT_4_1_MINI_2025_04_14_MODEL = "gpt-4.1-mini-2025-04-14"
GPT_4_1_NANO_MODEL = "gpt-4.1-nano"
GPT_4_1_NANO_2025_04_14_MODEL = "gpt-4.1-nano-2025-04-14"
GPT_5_CHAT_LATEST_MODEL = "gpt-5-chat-latest"
GPT_5_MODEL = "gpt-5"
GPT_5_MINI_MODEL = "gpt-5-mini"
GPT_5_NANO_MODEL = "gpt-5-nano"
O3_MODEL = "o3"
O4_MINI_MODEL = "o4-mini"
GPT_5_2025_08_07_MODEL = "gpt-5-2025-08-07"
GPT_5_MINI_2025_08_07_MODEL = "gpt-5-mini-2025-08-07"
GPT_5_NANO_2025_08_07_MODEL = "gpt-5-nano-2025-08-07"
O3_2025_04_16_MODEL = "o3-2025-04-16"
O4_MINI_2025_04_16_MODEL = "o4-mini-2025-04-16"

# Default model used for token counting when none specified
DEFAULT_TOKEN_COUNT_MODEL = GPT_3_5_TURBO_0613_MODEL

# Tuple: (tokens_per_message, tokens_per_name)
MODEL_TOKENS = {
    # GPT-3.5
    GPT_3_5_TURBO_0613_MODEL: (3, 1),
    GPT_3_5_TURBO_16K_0613_MODEL: (3, 1),
    GPT_3_5_TURBO_1106_MODEL: (3, 1),
    GPT_3_5_TURBO_0125_MODEL: (3, 1),
    GPT_3_5_TURBO_0301_MODEL: (
        4,  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        -1,  # if there's a name, the role is omitted
    ),
    # GPT-4
    GPT_4_0314_MODEL: (3, 1),
    GPT_4_32K_0314_MODEL: (3, 1),
    GPT_4_0613_MODEL: (3, 1),
    GPT_4_32K_0613_MODEL: (3, 1),
    GPT_4_1106_PREVIEW_MODEL: (3, 1),
    GPT_4_0125_PREVIEW_MODEL: (3, 1),
    GPT_4_TURBO_PREVIEW_MODEL: (3, 1),
    # GPT-4.1 family
    GPT_4_1_MODEL: (3, 1),
    GPT_4_1_2025_04_14_MODEL: (3, 1),
    GPT_4_1_MINI_MODEL: (3, 1),
    GPT_4_1_MINI_2025_04_14_MODEL: (3, 1),
    GPT_4_1_NANO_MODEL: (3, 1),
    GPT_4_1_NANO_2025_04_14_MODEL: (3, 1),
    GPT_4_TURBO_2024_04_09_MODEL: (3, 1),
    # GPT-4o
    GPT_4O_2024_05_13_MODEL: (3, 1),
    # GPT-4o mini
    GPT_4O_MINI_2024_07_18_MODEL: (3, 1),
    # GPT-5 chat latest
    GPT_5_CHAT_LATEST_MODEL: (3, 1),
    # GPT-5 family (dated)
    GPT_5_2025_08_07_MODEL: (3, 1),
    GPT_5_MINI_2025_08_07_MODEL: (3, 1),
    GPT_5_NANO_2025_08_07_MODEL: (3, 1),
    # Reasoning models (dated)
    O3_2025_04_16_MODEL: (3, 1),
    O4_MINI_2025_04_16_MODEL: (3, 1),
}

# Note that these fallbacks may change over time.
MODEL_FALLBACKS = {
    GPT_3_5_TURBO_MODEL: GPT_3_5_TURBO_0125_MODEL,
    GPT_3_5_TURBO_16K_MODEL: GPT_3_5_TURBO_16K_0613_MODEL,
    GPT_4_MODEL: GPT_4_0613_MODEL,
    GPT_4_TURBO_MODEL: GPT_4_TURBO_2024_04_09_MODEL,
    GPT_4_32K_MODEL: GPT_4_32K_0613_MODEL,
    GPT_4O_MODEL: GPT_4O_2024_05_13_MODEL,
    GPT_4O_MINI_MODEL: GPT_4O_MINI_2024_07_18_MODEL,
    GPT_4_1_MODEL: GPT_4_1_2025_04_14_MODEL,
    GPT_4_1_MINI_MODEL: GPT_4_1_MINI_2025_04_14_MODEL,
    GPT_4_1_NANO_MODEL: GPT_4_1_NANO_2025_04_14_MODEL,
    # GPT-5 and reasoning families to their dated variants
    GPT_5_MODEL: GPT_5_2025_08_07_MODEL,
    GPT_5_MINI_MODEL: GPT_5_MINI_2025_08_07_MODEL,
    GPT_5_NANO_MODEL: GPT_5_NANO_2025_08_07_MODEL,
    O3_MODEL: O3_2025_04_16_MODEL,
    O4_MINI_MODEL: O4_MINI_2025_04_16_MODEL,
}

MODEL_CONTEXT_LENGTHS = {
    # GPT-3.5
    GPT_3_5_TURBO_0301_MODEL: 4096,
    GPT_3_5_TURBO_0613_MODEL: 4096,
    GPT_3_5_TURBO_16K_0613_MODEL: 16384,
    GPT_3_5_TURBO_1106_MODEL: 16384,
    GPT_3_5_TURBO_0125_MODEL: 16384,
    # GPT-4
    GPT_4_0314_MODEL: 8192,
    GPT_4_0613_MODEL: 8192,
    GPT_4_32K_0314_MODEL: 32768,
    GPT_4_32K_0613_MODEL: 32768,
    GPT_4_1106_PREVIEW_MODEL: 128000,
    GPT_4_0125_PREVIEW_MODEL: 128000,
    GPT_4_TURBO_PREVIEW_MODEL: 128000,  # GPT_4_TURBO_PREVIEW_MODEL is an alias for GPT_4_0125_PREVIEW_MODEL
    GPT_4_TURBO_2024_04_09_MODEL: 128000,
    # GPT-4o
    GPT_4O_2024_05_13_MODEL: 128000,
    # GPT-4o mini
    GPT_4O_MINI_2024_07_18_MODEL: 128000,
    # GPT-4.1 family
    GPT_4_1_2025_04_14_MODEL: 1048576,
    GPT_4_1_MINI_2025_04_14_MODEL: 1048576,
    GPT_4_1_NANO_2025_04_14_MODEL: 1048576,
    # GPT-5 chat latest
    GPT_5_CHAT_LATEST_MODEL: 128000,
    # GPT-5 family (dated)
    GPT_5_2025_08_07_MODEL: 128000,
    GPT_5_MINI_2025_08_07_MODEL: 128000,
    GPT_5_NANO_2025_08_07_MODEL: 128000,
    # Reasoning models (dated)
    O3_2025_04_16_MODEL: 128000,
    O4_MINI_2025_04_16_MODEL: 128000,
}


def resolve_model_alias(model: str) -> str:
    """Resolves a model alias to a concrete version using MODEL_FALLBACKS.

    Raises ValueError on circular dependency.
    Returns the input when no fallback mapping is found.
    """
    if model is None:
        return model
    visited = {model}
    while model in MODEL_FALLBACKS:
        model = MODEL_FALLBACKS[model]
        if model in visited:
            raise ValueError(
                f"Circular dependency detected in MODEL_FALLBACKS for model {model}"
            )
        visited.add(model)
    return model
