set -o allexport
source .env
set +o allexport

export SLACK_CLIENT_ID=$SLACK_CLIENT_ID
export SLACK_CLIENT_SECRET=$SLACK_CLIENT_SECRET
export SLACK_SIGNING_SECRET=$SLACK_SIGNING_SECRET
export SLACK_SCOPES=app_mentions:read,channels:history,groups:history,chat:write.public,chat:write,users:read
export SLACK_INSTALLATION_S3_BUCKET_NAME=$SLACK_INSTALLATION_S3_BUCKET_NAME
export SLACK_STATE_S3_BUCKET_NAME=$SLACK_STATE_S3_BUCKET_NAME
export OPENAI_S3_BUCKET_NAME=$OPENAI_S3_BUCKET_NAME
npm install -g serverless
serverless plugin install -n serverless-python-requirements
serverless deploy
