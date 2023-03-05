# ChatGPT in Slack

Introducing a transformative app for Slack users, specifically designed to enhance your communication with [ChatGPT](https://openai.com/blog/chatgpt)!
With this app, you can seamlessly interact with ChatGPT through Slack channels, streamlining your planning and writing processes with the power of AI.

If you want to see how this app works, you can install the live demo app from https://bit.ly/chat-gpt-in-slack.
Please note that this live demo app is being hosted personally by @seratch.
If you plan to use this app in your corporate Slack workspace, we highly recommend that you run it on your own infrastructure using the instructions provided below.

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
# Optional: include priming instructions for ChatGPT to fine tune the bot purpose
export SYSTEM_TEXT="You proofread text. When you receive a message, you will check
for mistakes and make suggestion to improve the language of the given text"

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Running the App for Company Workspaces

Confidentiality of information is top priority for businesses.

This app is open-sourced! so please feel free to fork it and deploy the app onto the infrastructure that you manage.
After going through the above local development process, you can deploy the app using `Dockerfile`, which is placed at the root directory of this project.

The `Dockerfile` is designed to establish a WebSocket connection with Slack via Socket Mode.
This means that there's no need to provide a public URL for communication with Slack.

## Contributions

You're always welcome to contribute! :raised_hands:
When you make changes to the code in this project, please keep these points in mind:
- When making changes to the app, please avoid anything that could cause breaking behavior. If such changes are absolutely necessary due to critical reasons, like security issues, please start a discussion in GitHub Issues before making significant alterations.
- When you have the chance, please write some unit tests. Especially when you touch `internals.py` and add/edit the code that do not call any web APIs, writing tests should be relatively easy.
- Before committing your changes, be sure to run `./validate.sh`. The script runs black (code formatter), flake8 and pytype (static code analyzers).

## The License

The MIT License
