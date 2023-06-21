# ChatGPT in Slack

Introducing a transformative app for Slack users, specifically designed to enhance your communication with [ChatGPT](https://openai.com/blog/chatgpt)!
This app enables seamless interaction with ChatGPT via Slack channels, optimizing your planning and writing processes by leveraging AI technology.

Discover the app's functionality by installing the live demo from https://bit.ly/chat-gpt-in-slack. 
Keep in mind that the live demo is personally hosted by [@seratch](https://github.com/seratch).
For corporate Slack workspaces, we strongly advise deploying the app on your own infrastructure using the guidelines provided below.

If you're looking for a sample app operating on [Slack's next-generation hosted platform](https://api.slack.com/future), check out https://github.com/seratch/chatgpt-on-deno 🙌

## How It Works

You can interact with ChatGPT like you do in the website. In the same thread, the bot remember what you already said.

<img src="https://user-images.githubusercontent.com/19658/222405498-867f5002-c8ba-4dc9-bd86-fddc5192070c.gif" width=450 />

Consider this realistic scenario: ask the bot to generate a business email for communication with your manager.

<img width="700" src="https://user-images.githubusercontent.com/19658/222609940-eb581361-eeea-441a-a300-96ecdbc23d0b.png">

With ChatGPT, you don't need to ask a perfectly formulated question at first. Adjusting the details after receiving the bot's initial response is a great approach.

<img width="700" src="https://user-images.githubusercontent.com/19658/222609947-b99ace0d-4c90-4265-940d-3fc373429b80.png">

Doesn't that sound cool? 😎

## Running the App on Your Local Machine

To run this app on your local machine, you only need to follow these simple steps:

* Create a new Slack app using the manifest-dev.yml file
* Install the app into your Slack workspace
* Retrieve your OpenAI API key at https://platform.openai.com/account/api-keys
* Start the app

```bash
# Create an app-level token with connections:write scope
export SLACK_APP_TOKEN=xapp-1-...
# Install the app into your workspace to grab this token
export SLACK_BOT_TOKEN=xoxb-...
# Visit https://platform.openai.com/account/api-keys for this token
export OPENAI_API_KEY=sk-...

# Optional: gpt-3.5-turbo and gpt-4 are currently supported (default: gpt-3.5-turbo)
export OPENAI_MODEL=gpt-4
# Optional: Model temperature between 0 and 2 (default: 1.0)
export OPENAI_TEMPERATURE=1
# Optional: You can adjust the timeout seconds for OpenAI calls (default: 30)
export OPENAI_TIMEOUT_SECONDS=60
# Optional: You can include priming instructions for ChatGPT to fine tune the bot purpose
export OPENAI_SYSTEM_TEXT="You proofread text. When you receive a message, you will check
for mistakes and make suggestion to improve the language of the given text"
# Optional: When the string is "true", this app translates ChatGPT prompts into a user's preferred language (default: true)
export USE_SLACK_LANGUAGE=true
# Optional: Adjust the app's logging level (default: DEBUG)
export SLACK_APP_LOG_LEVEL=INFO
# Optional: When the string is "true", translate between OpenAI markdown and Slack mrkdwn format (default: false)
export TRANSLATE_MARKDOWN=true
# Optional: When the string is "true", perform some basic redaction on propmts sent to OpenAI (default: false)
export REDACTION_ENABLED=true

# To use Azure OpenAI, set the following optional environment variables according to your environment
# default: None
export OPENAI_API_TYPE=azure
# default: https://api.openai.com/v1
export OPENAI_API_BASE=https://YOUR_RESOURCE_NAME.openai.azure.com
# default: None
export OPENAI_API_VERSION=2023-05-15
# default: None
export OPENAI_DEPLOYMENT_ID=YOUR-DEPLOYMENT-ID

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Running the App for Company Workspaces

Confidentiality of information is top priority for businesses.

This app is open-sourced! so please feel free to fork it and deploy the app onto the infrastructure that you manage.
After going through the above local development process, you can deploy the app using `Dockerfile`, which is placed at the root directory.

The `Dockerfile` is designed to establish a WebSocket connection with Slack via Socket Mode.
This means that there's no need to provide a public URL for communication with Slack.

## Contributions

You're always welcome to contribute! :raised_hands:
When you make changes to the code in this project, please keep these points in mind:
- When making changes to the app, please avoid anything that could cause breaking behavior. If such changes are absolutely necessary due to critical reasons, like security issues, please start a discussion in GitHub Issues before making significant alterations.
- When you have the chance, please write some unit tests. Especially when you touch internal utility modules (e.g., `app/markdown.py` etc.) and add/edit the code that do not call any web APIs, writing tests should be relatively easy.
- Before committing your changes, be sure to run `./validate.sh`. The script runs black (code formatter), flake8 and pytype (static code analyzers).

## The License

The MIT License
