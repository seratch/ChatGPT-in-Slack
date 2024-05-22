from app.env import OPENAI_TIMEOUT_SECONDS

TIMEOUT_ERROR_MESSAGE = (
    f":warning: Apologies! It seems that OpenAI didn't respond within the {OPENAI_TIMEOUT_SECONDS}-second timeframe. "
    "Please try your request again later. "
    "If you wish to extend the timeout limit, "
    "you may consider deploying this app with customized settings on your infrastructure. :bow:"
)

DEFAULT_LOADING_TEXT = ":hourglass_flowing_sand: Wait a second, please ..."
