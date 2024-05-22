import os

DEFAULT_SYSTEM_TEXT = """
You are a bot in a slack chat room. You might receive messages from multiple people.
Format bold text *like this*, italic text _like this_ and strikethrough text ~like this~.
Slack user IDs match the regex `<@U.*?>`.
Your Slack user ID is <@{bot_user_id}>.
Each message has the author's Slack user ID prepended, like the regex `^<@U.*?>: ` followed by the message text.
"""
SYSTEM_TEXT = os.environ.get("OPENAI_SYSTEM_TEXT", DEFAULT_SYSTEM_TEXT)

DEFAULT_OPENAI_TIMEOUT_SECONDS = 30
OPENAI_TIMEOUT_SECONDS = int(
    os.environ.get("OPENAI_TIMEOUT_SECONDS", DEFAULT_OPENAI_TIMEOUT_SECONDS)
)

DEFAULT_OPENAI_MODEL = "gpt-3.5-turbo"
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)

DEFAULT_OPENAI_IMAGE_GENERATION_MODEL = "dall-e-3"
OPENAI_IMAGE_GENERATION_MODEL = os.environ.get(
    "OPENAI_IMAGE_GENERATION_MODEL", DEFAULT_OPENAI_IMAGE_GENERATION_MODEL
)

DEFAULT_OPENAI_TEMPERATURE = 1
OPENAI_TEMPERATURE = float(
    os.environ.get("OPENAI_TEMPERATURE", DEFAULT_OPENAI_TEMPERATURE)
)

DEFAULT_OPENAI_API_TYPE = None
OPENAI_API_TYPE = os.environ.get("OPENAI_API_TYPE", DEFAULT_OPENAI_API_TYPE)

DEFAULT_OPENAI_API_BASE = "https://api.openai.com/v1"
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", DEFAULT_OPENAI_API_BASE)

DEFAULT_OPENAI_API_VERSION = None
OPENAI_API_VERSION = os.environ.get("OPENAI_API_VERSION", DEFAULT_OPENAI_API_VERSION)

DEFAULT_OPENAI_DEPLOYMENT_ID = None
OPENAI_DEPLOYMENT_ID = os.environ.get(
    "OPENAI_DEPLOYMENT_ID", DEFAULT_OPENAI_DEPLOYMENT_ID
)

DEFAULT_OPENAI_ORG_ID = None
OPENAI_ORG_ID = os.environ.get("OPENAI_ORG_ID", DEFAULT_OPENAI_ORG_ID)

DEFAULT_OPENAI_FUNCTION_CALL_MODULE_NAME = None
OPENAI_FUNCTION_CALL_MODULE_NAME = os.environ.get(
    "OPENAI_FUNCTION_CALL_MODULE_NAME", DEFAULT_OPENAI_FUNCTION_CALL_MODULE_NAME
)

USE_SLACK_LANGUAGE = os.environ.get("USE_SLACK_LANGUAGE", "true") == "true"

SLACK_APP_LOG_LEVEL = os.environ.get("SLACK_APP_LOG_LEVEL", "DEBUG")

TRANSLATE_MARKDOWN = os.environ.get("TRANSLATE_MARKDOWN", "false") == "true"

REDACTION_ENABLED = os.environ.get("REDACTION_ENABLED", "false") == "true"
IMAGE_FILE_ACCESS_ENABLED = (
    os.environ.get("IMAGE_FILE_ACCESS_ENABLED", "false") == "true"
)

# Redaction patterns
#
REDACT_EMAIL_PATTERN = os.environ.get(
    "REDACT_EMAIL_PATTERN", r"\b[A-Za-z0-9.*%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)
REDACT_PHONE_PATTERN = os.environ.get(
    "REDACT_PHONE_PATTERN", r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)
REDACT_CREDIT_CARD_PATTERN = os.environ.get(
    "REDACT_CREDIT_CARD_PATTERN", r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"
)
REDACT_SSN_PATTERN = os.environ.get(
    "REDACT_SSN_PATTERN", r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b"
)
# For REDACT_USER_DEFINED_PATTERN, the default will never match anything
REDACT_USER_DEFINED_PATTERN = os.environ.get("REDACT_USER_DEFINED_PATTERN", r"(?!)")
