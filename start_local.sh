set -o allexport
source .env
set +o allexport

# Create an app-level token with connections:write scope
export SLACK_APP_TOKEN=$SLACK_APP_TOKEN
# Install the app into your workspace to grab this token
export SLACK_BOT_TOKEN=$SLACK_BOT_TOKEN
# Visit https://platform.openai.com/account/api-keys for this token
export OPENAI_API_KEY=$OPENAI_API_KEY

# Optional: gpt-3.5-turbo and gpt-4 are currently supported (default: gpt-3.5-turbo)
export OPENAI_MODEL=$OPENAI_MODEL
# Optional: Model temperature between 0 and 2 (default: 1.0)
export OPENAI_TEMPERATURE=0.7
# Optional: You can adjust the timeout seconds for OpenAI calls (default: 30)
export OPENAI_TIMEOUT_SECONDS=300
# Optional: You can include priming instructions for ChatGPT to fine tune the bot purpose
export OPENAI_SYSTEM_TEXT="You are ChatGPT, a large language model trained by OpenAI, based on the GPT-4 architecture. Language: Japanese"
# Optional: When the string is "true", this app translates ChatGPT prompts into a user's preferred language (default: true)
export USE_SLACK_LANGUAGE=true
# Optional: Adjust the app's logging level (default: DEBUG)
export SLACK_APP_LOG_LEVEL=INFO
# Optional: When the string is "true", translate between OpenAI markdown and Slack mrkdwn format (default: false)
export TRANSLATE_MARKDOWN=true
# Optional: When the string is "true", perform some basic redaction on propmts sent to OpenAI (default: false)
export REDACTION_ENABLED=false

# Experimental: You can try out the Function Calling feature (default: None)
# export OPENAI_FUNCTION_CALL_MODULE_NAME=tests.function_call_example

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py