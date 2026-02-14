#!/bin/bash
# Deploy daily tweet reminder Lambda + EventBridge (7 PM daily).
# Uses AWS profile: vikash-own
#
# Prereqs:
#   1. AWS CLI installed, profile vikash-own configured
#   2. In SES (same region): verify the email you want to receive reminders (and use as From if in sandbox)
#
# Usage:
#   REMINDER_EMAIL=you@example.com FROM_EMAIL=you@example.com ./deploy.sh
#   Or export REMINDER_EMAIL and FROM_EMAIL then ./deploy.sh

set -e
PROFILE="${AWS_PROFILE:-vikash-own}"
REGION="${AWS_REGION:-us-east-1}"
FUNC_NAME="twitter-daily-reminder"
ROLE_NAME="${FUNC_NAME}-role"
RULE_NAME="${FUNC_NAME}-rule"

# 7 PM IST = 13:30 UTC. For 7 PM UTC use "0 19 * * ? *"
CRON_UTC="${CRON_UTC:-cron(30 13 * * ? *)}"

if [ -z "$REMINDER_EMAIL" ] || [ -z "$FROM_EMAIL" ]; then
  echo "Set REMINDER_EMAIL and FROM_EMAIL (both must be verified in SES):"
  echo "  REMINDER_EMAIL=you@example.com FROM_EMAIL=you@example.com ./deploy.sh"
  exit 1
fi

echo "Profile: $PROFILE | Region: $REGION | To: $REMINDER_EMAIL | From: $FROM_EMAIL"
echo "EventBridge: $CRON_UTC (7 PM IST if default)"
echo ""

# IAM role for Lambda
echo "Creating IAM role..."
aws iam create-role \
  --profile "$PROFILE" \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' 2>/dev/null || true

aws iam put-role-policy \
  --profile "$PROFILE" \
  --role-name "$ROLE_NAME" \
  --policy-name inline \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {"Effect": "Allow", "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], "Resource": "*"},
      {"Effect": "Allow", "Action": "ses:SendEmail", "Resource": "*"}
    ]
  }'

ROLE_ARN=$(aws iam get-role --profile "$PROFILE" --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
echo "Role: $ROLE_ARN"

# Wait for role to be usable
sleep 5

# Zip and create/update Lambda
echo "Packaging Lambda..."
cd "$(dirname "$0")"
zip -q /tmp/twitter-reminder.zip reminder.py

echo "Creating/updating Lambda..."
aws lambda create-function \
  --profile "$PROFILE" \
  --region "$REGION" \
  --function-name "$FUNC_NAME" \
  --runtime python3.12 \
  --role "$ROLE_ARN" \
  --handler reminder.handler \
  --zip-file fileb:///tmp/twitter-reminder.zip \
  --environment "Variables={REMINDER_EMAIL=$REMINDER_EMAIL,FROM_EMAIL=$FROM_EMAIL}" \
  --timeout 10 \
  2>/dev/null || \
aws lambda update-function-code \
  --profile "$PROFILE" \
  --region "$REGION" \
  --function-name "$FUNC_NAME" \
  --zip-file fileb:///tmp/twitter-reminder.zip \
  --output text --query 'LastModified'

aws lambda update-function-configuration \
  --profile "$PROFILE" \
  --region "$REGION" \
  --function-name "$FUNC_NAME" \
  --environment "Variables={REMINDER_EMAIL=$REMINDER_EMAIL,FROM_EMAIL=$FROM_EMAIL}" \
  --output text --query 'LastModified' 2>/dev/null || true

FUNC_ARN=$(aws lambda get-function --profile "$PROFILE" --region "$REGION" --function-name "$FUNC_NAME" --query 'Configuration.FunctionArn' --output text)

# EventBridge rule
echo "Creating EventBridge rule..."
aws events put-rule \
  --profile "$PROFILE" \
  --region "$REGION" \
  --name "$RULE_NAME" \
  --schedule-expression "$CRON_UTC" \
  --state ENABLED

aws events put-targets \
  --profile "$PROFILE" \
  --region "$REGION" \
  --rule "$RULE_NAME" \
  --targets "[{\"Id\":\"1\",\"Arn\":\"$FUNC_ARN\"}]"

aws lambda add-permission \
  --profile "$PROFILE" \
  --region "$REGION" \
  --function-name "$FUNC_NAME" \
  --statement-id EventBridgeInvoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "arn:aws:events:${REGION}:$(aws sts get-caller-identity --profile "$PROFILE" --query Account --output text):rule/${RULE_NAME}" \
  2>/dev/null || true

echo ""
echo "Done. You'll get an email at $REMINDER_EMAIL daily at 7 PM IST (or per CRON_UTC)."
echo "To change time: CRON_UTC='cron(0 19 * * ? *)' ./deploy.sh  # 7 PM UTC"
