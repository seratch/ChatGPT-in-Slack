FROM python:3.11.2-slim-buster as builder
COPY requirements.txt /build/
WORKDIR /build/
RUN pip install -U pip && pip install -r requirements.txt

FROM python:3.11.2-slim-buster as app
WORKDIR /app/
COPY *.py /app/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY --from=builder /usr/local/lib/ /usr/local/lib/
ENTRYPOINT python app.py

# docker build . -t your-repo/chat-gpt-in-slack
# export SLACK_APP_TOKEN=xapp-...
# export SLACK_BOT_TOKEN=xoxb-...
# export OPENAI_API_KEY=sk-...
# docker run -e SLACK_APP_TOKEN=$SLACK_APP_TOKEN -e SLACK_BOT_TOKEN=$SLACK_BOT_TOKEN -e OPENAI_API_KEY=$OPENAI_API_KEY -it your-repo/chat-gpt-in-slack
