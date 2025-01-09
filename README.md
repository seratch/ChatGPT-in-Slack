# ChatGPT in Slack

Introducing a transformative app for Slack users, specifically designed to enhance your communication with [ChatGPT](https://openai.com/blog/chatgpt)!
This app enables seamless interaction with ChatGPT via Slack channels, optimizing your planning and writing processes by leveraging AI technology.

Discover the app's functionality by installing the live demo from https://bit.ly/chat-gpt-in-slack. 
Keep in mind that the live demo is personally hosted by [@seratch](https://github.com/seratch).
For corporate Slack workspaces, we strongly advise deploying the app on your own infrastructure using the guidelines provided below.

If you're looking for a sample app operating on [Slack's next-generation hosted platform](https://api.slack.com/future), check out https://github.com/seratch/chatgpt-on-deno 🙌

## How It Works

You can interact with ChatGPT as you do on the website. 

While communicating in the same thread, the bot remembers what you have already said:

<img width="700" src="https://github.com/seratch/ChatGPT-in-Slack/assets/19658/501709b0-639d-4b35-98a9-3d5102c41685" />

Consider this realistic scenario: ask the bot to generate a business email for communicating with your manager:

<img width="700" src="https://user-images.githubusercontent.com/19658/222609940-eb581361-eeea-441a-a300-96ecdbc23d0b.png">

With ChatGPT, you don't need to ask a perfectly formulated question at first. Adjusting the details after receiving the bot's initial response is a great approach:

<img width="700" src="https://user-images.githubusercontent.com/19658/222609947-b99ace0d-4c90-4265-940d-3fc373429b80.png">

Doesn't that sound cool? 😎

## Three Supported Interfaces

There are three interfaces to use. When you want to share a conversation with others in the Slack workspace, always using channel threads is the best option. If you wish to use ChatGPT privately, the other interfaces are more convenient for that purpose.

1. Talk to the bot in a channel thread
2. Talk to the bot in a 1:1 DM
3. Send prompts on your Home tab

### Talk to the bot in a channel thread

This is the most common way to use this app. You can start a conversation with ChatGPT Bot at any time just by mentioning the bot in a thread's initial message. Within the thread, you don't need to mention the bot anymore:

<img width="700" src="https://github.com/seratch/ChatGPT-in-Slack/assets/19658/8b3199a9-b413-4002-a702-b0b92e866658">

### Talk to the bot in a 1:1 DM

You can privately ask for help using a 1:1 DM with the bot. No need to mention the bot. Just send a message in the DM:

<img width="700" src="https://github.com/seratch/ChatGPT-in-Slack/assets/19658/eadb7930-4e43-4a95-80ff-7263d02313b1">

### Send prompts on your Home tab

On the Home tab, in addition to the OpenAI API key and model configuration, you can use the quick proofreader and free prompt sender dialogs. These are so handy that you can quickly send inquiries to OpenAI, even from a mobile device.

<img width="700" src="https://github.com/seratch/ChatGPT-in-Slack/assets/19658/13a06d0a-225f-4ff4-9e16-a5a95cc2d36b">


Here is an example of proofreading on Home tab:

<img width="400" src="https://github.com/seratch/ChatGPT-in-Slack/assets/19658/6dcc8a3d-27bc-4719-b495-e3a5e39d1cc7">
<img width="400" src="https://github.com/seratch/ChatGPT-in-Slack/assets/19658/ca4a8f18-9cbf-4e8d-b656-904596e5895f">


You can generate an image just by giving a prompt to the DALL-E 3 model too:

<img width="500" src="https://github.com/seratch/ChatGPT-in-Slack/assets/19658/3b6942d2-a370-4c5b-ae11-ea18922c3729">


To ask any other questions, you can use the from-scratch modal instead:

<img width="400" src="https://github.com/seratch/ChatGPT-in-Slack/assets/19658/72c663a4-b0d2-4ac5-9f75-25e776f500df">

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

# Optional: gpt-3.5-turbo and newer ones are currently supported (default: gpt-3.5-turbo)
export OPENAI_MODEL=gpt-4o
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
# Optional: When the string is "true", perform some basic redaction on prompts sent to OpenAI (default: false)
export REDACTION_ENABLED=true
# Optional: When the string is "true", this app shares image files with OpenAI (default: false)
export IMAGE_FILE_ACCESS_ENABLED=true

# To use Azure OpenAI, set the following optional environment variables according to your environment
# default: None
export OPENAI_API_TYPE=azure
# default: https://api.openai.com/v1
export OPENAI_API_BASE=https://YOUR_RESOURCE_NAME.openai.azure.com
# default: None
export OPENAI_API_VERSION=2023-05-15
# default: None
export OPENAI_DEPLOYMENT_ID=YOUR-DEPLOYMENT-ID

# Experimental: You can try out the Function Calling feature (default: None)
export OPENAI_FUNCTION_CALL_MODULE_NAME=tests.function_call_example

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Using .env for credential loading

If you prefer using .env file to load env variables for local development, you can rename .env.example file to .env:
    
```bash
cp .env.example .env
```
Then, replace the values in .env file with your own API keys and tokens:
```text
OPENAI_API_KEY=sk-your-openai-key
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_APP_TOKEN=xapp-1-your-slack-app-token
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

## Related Projects

- [iwamot/collmbo](https://github.com/iwamot/collmbo): @iwamot's forked project, which supports other LLM providers in addition to OpenAI by leveraging [LiteLLM](https://github.com/BerriAI/litellm)

## The License

The MIT License
