# Unzip the dependencies managed by serverless-python-requirements
try:
    import unzip_requirements  # type:ignore
except ImportError:
    pass

#
# Imports
#

import json
import logging
import os
from openai import OpenAI

from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler
from slack_bolt import App, Ack, BoltContext

from app.bolt_listeners import register_listeners, before_authorize
from app.env import (
    USE_SLACK_LANGUAGE,
    SLACK_APP_LOG_LEVEL,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_API_TYPE,
    OPENAI_API_BASE,
    OPENAI_API_VERSION,
    OPENAI_DEPLOYMENT_ID,
    OPENAI_FUNCTION_CALL_MODULE_NAME,
    OPENAI_ORG_ID,
    OPENAI_IMAGE_GENERATION_MODEL,
)
from app.slack_ui import (
    build_home_tab,
    DEFAULT_HOME_TAB_MESSAGE,
    build_configure_modal,
)
from app.i18n import translate

#
# Product deployment (AWS Lambda)
#
# export SLACK_CLIENT_ID=
# export SLACK_CLIENT_SECRET=
# export SLACK_SIGNING_SECRET=
# export SLACK_SCOPES=commands,app_mentions:read,channels:history,groups:history,im:history,mpim:history,chat:write.public,chat:write,users:read,files:read,files:write,im:write
# export SLACK_INSTALLATION_S3_BUCKET_NAME=
# export SLACK_STATE_S3_BUCKET_NAME=
# export OPENAI_S3_BUCKET_NAME=
# npm install -g serverless@3
# serverless plugin install -n serverless-python-requirements
# serverless deploy
#

import boto3
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from slack_bolt.adapter.aws_lambda.lambda_s3_oauth_flow import LambdaS3OAuthFlow

SlackRequestHandler.clear_all_log_handlers()
logging.basicConfig(format="%(asctime)s %(message)s", level=SLACK_APP_LOG_LEVEL)

s3_client = boto3.client("s3")
openai_bucket_name = os.environ["OPENAI_S3_BUCKET_NAME"]

client_template = WebClient()
client_template.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=2))


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
        before_authorize=before_authorize,
        oauth_flow=LambdaS3OAuthFlow(),
        client=client_template,
    )
    app.oauth_flow.settings.install_page_rendering_enabled = False
    register_listeners(app)
    register_revocation_handlers(app)

    if USE_SLACK_LANGUAGE is True:

        @app.middleware
        def set_locale(
            context: BoltContext,
            client: WebClient,
            logger: logging.Logger,
            next_,
        ):
            bot_scopes = context.authorize_result.bot_scopes
            if bot_scopes is not None and "users:read" in bot_scopes:
                user_id = context.actor_user_id or context.user_id
                try:
                    user_info = client.users_info(user=user_id, include_locale=True)
                    context["locale"] = user_info.get("user", {}).get("locale")
                except SlackApiError as e:
                    logger.debug(f"Failed to fetch user info due to {e}")
                    pass
            next_()

    @app.middleware
    def set_s3_openai_api_key(context: BoltContext, next_):
        try:
            s3_response = s3_client.get_object(
                Bucket=openai_bucket_name, Key=context.team_id
            )
            config_str: str = s3_response["Body"].read().decode("utf-8")
            if config_str.startswith("{"):
                config = json.loads(config_str)
                context["OPENAI_API_KEY"] = config.get("api_key")
                context["OPENAI_MODEL"] = config.get("model")
                context["OPENAI_IMAGE_GENERATION_MODEL"] = config.get(
                    "image_generation_model", OPENAI_IMAGE_GENERATION_MODEL
                )
                context["OPENAI_TEMPERATURE"] = config.get(
                    "temperature", OPENAI_TEMPERATURE
                )
            else:
                # The legacy data format
                context["OPENAI_API_KEY"] = config_str
                context["OPENAI_MODEL"] = OPENAI_MODEL
                context["OPENAI_IMAGE_GENERATION_MODEL"] = OPENAI_IMAGE_GENERATION_MODEL
                context["OPENAI_TEMPERATURE"] = OPENAI_TEMPERATURE
        except:  # noqa: E722
            context["OPENAI_API_KEY"] = None
            context["OPENAI_MODEL"] = None
            context["OPENAI_IMAGE_GENERATION_MODEL"] = None
            context["OPENAI_TEMPERATURE"] = None

        context["OPENAI_API_TYPE"] = OPENAI_API_TYPE
        context["OPENAI_API_BASE"] = OPENAI_API_BASE
        context["OPENAI_API_VERSION"] = OPENAI_API_VERSION
        context["OPENAI_DEPLOYMENT_ID"] = OPENAI_DEPLOYMENT_ID
        context["OPENAI_ORG_ID"] = OPENAI_ORG_ID
        context["OPENAI_FUNCTION_CALL_MODULE_NAME"] = OPENAI_FUNCTION_CALL_MODULE_NAME
        next_()

    #
    # Home tab rendering
    #

    @app.event("app_home_opened")
    def render_home_tab(client: WebClient, context: BoltContext):
        message = DEFAULT_HOME_TAB_MESSAGE
        try:
            s3_client.get_object(Bucket=openai_bucket_name, Key=context.team_id)
            message = "This app is ready to use in this workspace :raised_hands:"
        except:  # noqa: E722
            pass
        openai_api_key = context.get("OPENAI_API_KEY")
        client.views_publish(
            user_id=context.user_id,
            view=build_home_tab(
                openai_api_key=openai_api_key,
                context=context,
                message=message,
            ),
        )

    #
    # Configure
    #

    @app.action("configure")
    def handle_configure_button(
        ack, body: dict, client: WebClient, context: BoltContext
    ):
        ack()
        client.views_open(
            trigger_id=body["trigger_id"],
            view=build_configure_modal(context),
        )

    def validate_api_key_registration(ack: Ack, view: dict, context: BoltContext):
        already_set_api_key = context.get("OPENAI_API_KEY")

        inputs = view["state"]["values"]
        # Try to get the API key value, but handle if the field is missing or empty
        api_key_input = inputs.get("api_key", {}).get("input", {}).get("value", None)
        # If not provided, use the already-set API key from context
        api_key = api_key_input if api_key_input else already_set_api_key
        model = inputs["model"]["input"]["selected_option"]["value"]

        if not api_key:
            text = "An OpenAI API key is required."
            if already_set_api_key is not None:
                text = translate(
                    openai_api_key=already_set_api_key, context=context, text=text
                )
            ack(
                response_action="errors",
                errors={"api_key": text},
            )
            return
        try:
            # Verify if the API key is valid
            client = OpenAI(api_key=api_key)
            client.models.retrieve(model="gpt-3.5-turbo")
            try:
                # Verify if the given model works with the API key
                client.models.retrieve(model=model)
            except Exception:
                text = "This model is not yet available for this API key"
                if already_set_api_key is not None:
                    text = translate(
                        openai_api_key=already_set_api_key, context=context, text=text
                    )
                ack(
                    response_action="errors",
                    errors={"model": text},
                )
                return
            ack()
        except Exception:
            text = "This API key seems to be invalid"
            if already_set_api_key is not None:
                text = translate(
                    openai_api_key=already_set_api_key, context=context, text=text
                )
            ack(
                response_action="errors",
                errors={"api_key": text},
            )

    def save_api_key_registration(
        view: dict,
        logger: logging.Logger,
        context: BoltContext,
    ):
        inputs = view["state"]["values"]
        # Try to get the API key value, but handle if the field is missing or empty
        api_key_input = inputs.get("api_key", {}).get("input", {}).get("value", None)
        # If not provided, use the already-set API key from context
        already_set_api_key = context.get("OPENAI_API_KEY")
        api_key = api_key_input if api_key_input else already_set_api_key
        model = inputs["model"]["input"]["selected_option"]["value"]
        try:
            client = OpenAI(api_key=api_key)
            client.models.retrieve(model=model)
            s3_client.put_object(
                Bucket=openai_bucket_name,
                Key=context.team_id,
                Body=json.dumps({"api_key": api_key, "model": model}),
            )
        except Exception as e:
            logger.exception(e)

    app.view("configure")(
        ack=validate_api_key_registration,
        lazy=[save_api_key_registration],
    )

    #
    # Handle an AWS Lambda event
    #
    slack_handler = SlackRequestHandler(app=app)
    return slack_handler.handle(event, context_)
