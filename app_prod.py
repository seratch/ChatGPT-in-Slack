# Unzip the dependencies managed by serverless-python-requirements
try:
    import unzip_requirements  # type:ignore
except ImportError:
    pass

#
# Imports
#

import logging
import os
from slack_bolt import App, Ack, BoltContext
import openai
from slack_sdk.web import WebClient
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

from app import register_listeners

#
# Product deployment (AWS Lambda)
#
# export SLACK_CLIENT_ID=
# export SLACK_CLIENT_SECRET=
# export SLACK_SIGNING_SECRET=
# export SLACK_SCOPES=app_mentions:read,channels:history,groups:history,im:history,mpim:history,chat:write.public,chat:write
# export SLACK_INSTALLATION_S3_BUCKET_NAME=
# export SLACK_STATE_S3_BUCKET_NAME=
# export OPENAI_S3_BUCKET_NAME=
# npm install -g serverless
# serverless plugin install -n serverless-python-requirements
# serverless deploy
#

import boto3
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from slack_bolt.adapter.aws_lambda.lambda_s3_oauth_flow import LambdaS3OAuthFlow

SlackRequestHandler.clear_all_log_handlers()
logging.basicConfig(format="%(asctime)s %(message)s", level=logging.WARN)

s3_client = boto3.client("s3")
openai_bucket_name = os.environ["OPENAI_S3_BUCKET_NAME"]

client = WebClient()
client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=2))


def register_revocation_handlers(app: App):
    # Handle uninstall events and token revocations
    @app.event("tokens_revoked")
    def handle_tokens_revoked_events(
        event: dict,
        context: BoltContext,
        logger: logging.Logger,
    ):
        user_ids = event.get("tokens", {}).get("oauth", [])
        if len(user_ids) > 0:
            for user_id in user_ids:
                app.installation_store.delete_installation(
                    enterprise_id=context.enterprise_id,
                    team_id=context.team_id,
                    user_id=user_id,
                )
        bots = event.get("tokens", {}).get("bot", [])
        if len(bots) > 0:
            app.installation_store.delete_bot(
                enterprise_id=context.enterprise_id,
                team_id=context.team_id,
            )
            try:
                s3_client.delete_object(Bucket=openai_bucket_name, Key=context.team_id)
            except Exception as e:
                logger.error(
                    f"Failed to delete an OpenAI auth key: (team_id: {context.team_id}, error: {e})"
                )

    @app.event("app_uninstalled")
    def handle_app_uninstalled_events(
        context: BoltContext,
        logger: logging.Logger,
    ):
        app.installation_store.delete_all(
            enterprise_id=context.enterprise_id,
            team_id=context.team_id,
        )
        try:
            s3_client.delete_object(Bucket=openai_bucket_name, Key=context.team_id)
        except Exception as e:
            logger.error(
                f"Failed to delete an OpenAI auth key: (team_id: {context.team_id}, error: {e})"
            )


def handler(event, context_):
    app = App(
        process_before_response=True,
        oauth_flow=LambdaS3OAuthFlow(),
        client=client,
    )
    app.oauth_flow.settings.install_page_rendering_enabled = False
    register_listeners(app)
    register_revocation_handlers(app)

    @app.middleware
    def set_s3_openai_api_key(context: BoltContext, next_):
        try:
            s3_response = s3_client.get_object(
                Bucket=openai_bucket_name, Key=context.team_id
            )
            api_key = s3_response["Body"].read().decode("utf-8")
            context["OPENAI_API_KEY"] = api_key
        except:  # noqa: E722
            context["OPENAI_API_KEY"] = None
        next_()

    @app.event("app_home_opened")
    def render_home_tab(client: WebClient, context: BoltContext):
        text = (
            "To enable this app in this Slack workspace, you need to save your OpenAI API key. "
            "Visit <https://platform.openai.com/account/api-keys|your developer page> to grap your key!"
        )
        try:
            s3_client.get_object(Bucket=openai_bucket_name, Key=context.team_id)
            text = "This app is ready to use in this workspace :raised_hands:"
        except:  # noqa: E722
            pass

        client.views_publish(
            user_id=context.user_id,
            view={
                "type": "home",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": text,
                        },
                        "accessory": {
                            "action_id": "configure",
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Configure"},
                            "style": "primary",
                            "value": "api_key",
                        },
                    }
                ],
            },
        )

    @app.action("configure")
    def handle_some_action(ack, body: dict, client: WebClient):
        ack()
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "configure",
                "submit": {"type": "plain_text", "text": "Submit"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "title": {"type": "plain_text", "text": "OpenAI API Key"},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "api_key",
                        "label": {
                            "type": "plain_text",
                            "text": "Save your OpenAI API key:",
                        },
                        "element": {"type": "plain_text_input", "action_id": "input"},
                    }
                ],
            },
        )

    def validate_api_key_registration(ack: Ack, view: dict, logger: logging.Logger):
        api_key = view["state"]["values"]["api_key"]["input"]["value"]
        try:
            openai.Model.retrieve(api_key=api_key, id="gpt-3.5-turbo")
            ack()
        except Exception as e:
            logger.exception(e)
            ack(
                response_action="errors",
                errors={"api_key": "This API key seems to be invalid"},
            )

    def save_api_key_registration(
        view: dict,
        logger: logging.Logger,
        context: BoltContext,
    ):
        api_key = view["state"]["values"]["api_key"]["input"]["value"]
        try:
            openai.Model.retrieve(api_key=api_key, id="gpt-3.5-turbo")
            s3_client.put_object(
                Bucket=openai_bucket_name, Key=context.team_id, Body=api_key
            )
        except Exception as e:
            logger.exception(e)

    app.view("configure")(
        ack=validate_api_key_registration,
        lazy=[save_api_key_registration],
    )

    slack_handler = SlackRequestHandler(app=app)
    return slack_handler.handle(event, context_)
