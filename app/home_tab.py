DEFAULT_MESSAGE = (
    "To enable this app in this Slack workspace, you need to save your OpenAI API key. "
    "Visit <https://platform.openai.com/account/api-keys|your developer page> to grap your key!"
)

DEFAULT_CONFIGURE_LABEL = "Configure"


def build_home_tab(message: str, configure_label: str) -> dict:
    return {
        "type": "home",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message,
                },
                "accessory": {
                    "action_id": "configure",
                    "type": "button",
                    "text": {"type": "plain_text", "text": configure_label},
                    "style": "primary",
                    "value": "api_key",
                },
            }
        ],
    }
