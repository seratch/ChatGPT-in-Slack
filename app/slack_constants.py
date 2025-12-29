from app.env import OPENAI_TIMEOUT_SECONDS

TIMEOUT_ERROR_MESSAGE = (
    f":warning: Apologies! It seems that OpenAI didn't respond within the {OPENAI_TIMEOUT_SECONDS}-second timeframe. "
    "Please try your request again later. "
    "If you wish to extend the timeout limit, "
    "you may consider deploying this app with customized settings on your infrastructure. :bow:"
)

DEFAULT_LOADING_TEXT = ":hourglass_flowing_sand: Wait a second, please ..."
LOADING_SUFFIX = " ... :writing_hand:"
MAX_MESSAGE_LENGTH = 3000
# Slack text practical safety limits (UTF-8 bytes)
# Keep well below Slack's ~40k hard cap to absorb rich text overhead.
SLACK_INTERIM_MESSAGE_BYTE_LIMIT = 3500  # for chat.update during streaming
SLACK_POST_MESSAGE_BYTE_LIMIT = 20000    # chunk size for chat.postMessage fallbacks

# Minimal hint when reasoning models exhaust completion tokens and produce no visible text
REASONING_EMPTY_OUTPUT_HINT = (
    ":warning: The reasoning model used all completion tokens and did not "
    "produce visible text. Increase the completion token budget or simplify the request."
)
