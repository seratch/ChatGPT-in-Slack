# ChatGPT Bot in Slack

This app demonstrates how to build a Slack app that enables end-users to interact with a ChatGPT bot.
The bot can reply considering the context of a conversation.

## How It Works

You can interact with ChatGPT like you do in the website. In the same thread, the bot remember what you already said.

<img src="https://user-images.githubusercontent.com/19658/222392427-67e01de9-90f9-4412-819d-c1e3b7e18b33.gif" width=500 />

## Run The App

To run this app on your local machine, all you need to do are:

* Create a new Slack app using manifest-dev.yml
* Install the app into your Slack workspace
* Grab your OpenAI API key at https://platform.openai.com/account/api-keys
* Start your app

```bash
# Create an app-level token with connections:write scope
export SLACK_APP_TOKEN=xapp-1-...
# Install the app into your workspace to grab this token
export SLACK_BOT_TOKEN=xoxb-...
# Visit https://platform.openai.com/account/api-keys for this token
export OPENAI_API_KEY=sk-...

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## The License

The MIT License
