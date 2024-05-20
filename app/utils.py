import re

from app.env import (
    REDACT_EMAIL_PATTERN,
    REDACT_PHONE_PATTERN,
    REDACT_CREDIT_CARD_PATTERN,
    REDACT_SSN_PATTERN,
    REDACT_USER_DEFINED_PATTERN,
    REDACTION_ENABLED,
)


def redact_string(input_string: str) -> str:
    """
    Redact sensitive information from a string (inspired by @quangnhut123)

    Args:
        - input_string (str): the string to redact

    Returns:
        - str: the redacted string
    """
    output_string = input_string
    if REDACTION_ENABLED:
        output_string = re.sub(REDACT_EMAIL_PATTERN, "[EMAIL]", output_string)
        output_string = re.sub(
            REDACT_CREDIT_CARD_PATTERN, "[CREDIT CARD]", output_string
        )
        output_string = re.sub(REDACT_PHONE_PATTERN, "[PHONE]", output_string)
        output_string = re.sub(REDACT_SSN_PATTERN, "[SSN]", output_string)
        output_string = re.sub(REDACT_USER_DEFINED_PATTERN, "[REDACTED]", output_string)

    return output_string
