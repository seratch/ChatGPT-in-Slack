from dotenv import load_dotenv
import logging
import os

from slack_bolt import App, BoltContext
from slack_sdk.web import WebClient
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

from app.bolt_listeners import before_authorize, register_listeners
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
from app.slack_ui import build_home_tab

load_dotenv()

if __name__ == "__main__":
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    logging.basicConfig(level=SLACK_APP_LOG_LEVEL)

    app = App(
        token=os.environ["SLACK_BOT_TOKEN"],
        before_authorize=before_authorize,
        process_before_response=True,
    )
    app.client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=2))

    register_listeners(app)

    @app.event("app_home_opened")
    def render_home_tab(client: WebClient, context: BoltContext):
        already_set_api_key = os.environ["OPENAI_API_KEY"]
        client.views_publish(
            user_id=context.user_id,
            view=build_home_tab(
                openai_api_key=already_set_api_key,
                context=context,
                single_workspace_mode=True,
            ),
        )

    if USE_SLACK_LANGUAGE is True:

        @app.middleware
        def set_locale(
            context: BoltContext,
            client: WebClient,
            next_,
        ):
            user_id = context.actor_user_id or context.user_id
            user_info = client.users_info(user=user_id, include_locale=True)
            context["locale"] = user_info.get("user", {}).get("locale")
            next_()

    @app.middleware
    def set_openai_api_key(context: BoltContext, next_):
        context["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]
        context["OPENAI_MODEL"] = OPENAI_MODEL
        context["OPENAI_IMAGE_GENERATION_MODEL"] = OPENAI_IMAGE_GENERATION_MODEL
        context["OPENAI_TEMPERATURE"] = OPENAI_TEMPERATURE
        context["OPENAI_API_TYPE"] = OPENAI_API_TYPE
        context["OPENAI_API_BASE"] = OPENAI_API_BASE
        context["OPENAI_API_VERSION"] = OPENAI_API_VERSION
        context["OPENAI_DEPLOYMENT_ID"] = OPENAI_DEPLOYMENT_ID
        context["OPENAI_ORG_ID"] = OPENAI_ORG_ID
        context["OPENAI_FUNCTION_CALL_MODULE_NAME"] = OPENAI_FUNCTION_CALL_MODULE_NAME
        next_()

    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
