terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region  = var.region
  profile = var.aws_profile
}

# Lambda zip from ../reminder.py
data "archive_file" "lambda" {
  type        = "zip"
  output_path = "${path.module}/lambda.zip"
  source {
    content  = file("${path.module}/../reminder.py")
    filename = "reminder.py"
  }
}

# post_tweet Lambda uses a zip built with tweepy. Build it first: cd lambda && ./build_post_tweet.sh

# IAM role for Lambda
resource "aws_iam_role" "lambda" {
  name = "${var.function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda" {
  name = "inline"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = "ses:SendEmail"
        Resource = "*"
      }
    ]
  })
}

# Lambda function
resource "aws_lambda_function" "reminder" {
  function_name = var.function_name
  role          = aws_iam_role.lambda.arn
  handler       = "reminder.handler"
  runtime       = "python3.12"
  timeout       = 10
  filename      = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  environment {
    variables = {
      REMINDER_EMAIL = var.reminder_email
      FROM_EMAIL      = var.from_email
    }
  }
}

# EventBridge rule: daily at schedule_cron
resource "aws_cloudwatch_event_rule" "daily" {
  name                = "${var.function_name}-rule"
  schedule_expression = var.schedule_cron
  state               = "ENABLED"
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.daily.name
  target_id = "lambda"
  arn       = aws_lambda_function.reminder.arn
}

resource "aws_lambda_permission" "events" {
  statement_id  = "EventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.reminder.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily.arn
}

# --- Twitter auto-post (optional) ---

resource "aws_secretsmanager_secret" "twitter" {
  count       = var.enable_auto_tweet ? 1 : 0
  name        = "twitter-daily-reminder-credentials"
  description = "Twitter API OAuth 1.0a credentials (consumer_key, consumer_secret, access_token, access_token_secret)"
}

resource "aws_secretsmanager_secret_version" "twitter" {
  count     = var.enable_auto_tweet ? 1 : 0
  secret_id = aws_secretsmanager_secret.twitter[0].id
  secret_string = jsonencode({
    consumer_key         = var.twitter_consumer_key
    consumer_secret      = var.twitter_consumer_secret
    access_token        = var.twitter_access_token
    access_token_secret = var.twitter_access_token_secret
  })
}

resource "aws_iam_role" "post_tweet" {
  count = var.enable_auto_tweet ? 1 : 0

  name = "${var.post_tweet_function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "post_tweet" {
  count  = var.enable_auto_tweet ? 1 : 0
  name   = "inline"
  role   = aws_iam_role.post_tweet[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [aws_secretsmanager_secret.twitter[0].arn]
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = "arn:aws:ssm:${var.region}:*:parameter/twitter/tweets/*"
      }
    ]
  })
}

resource "aws_lambda_function" "post_tweet" {
  count = var.enable_auto_tweet ? 1 : 0

  function_name     = var.post_tweet_function_name
  role              = aws_iam_role.post_tweet[0].arn
  handler           = "post_tweet.handler"
  runtime           = "python3.12"
  timeout           = 15
  filename          = "${path.module}/../post_tweet.zip"
  source_code_hash  = filebase64sha256("${path.module}/../post_tweet.zip")

  environment {
    variables = {
      TWITTER_SECRET_ARN = aws_secretsmanager_secret.twitter[0].arn
    }
  }
}

# 8 AM IST = 02:30 UTC, 1 PM IST = 07:30 UTC, 6 PM IST = 12:30 UTC
locals {
  post_slots = var.enable_auto_tweet ? [
    { name = "twitter-post-morning", slot = "morning", cron = "cron(30 2 * * ? *)" },
    { name = "twitter-post-afternoon", slot = "afternoon", cron = "cron(30 7 * * ? *)" },
    { name = "twitter-post-evening", slot = "evening", cron = "cron(30 12 * * ? *)" }
  ] : []
}

resource "aws_cloudwatch_event_rule" "post_tweet" {
  for_each            = { for s in local.post_slots : s.name => s }
  name                = each.value.name
  schedule_expression = each.value.cron
  state               = "ENABLED"
}

resource "aws_cloudwatch_event_target" "post_tweet" {
  for_each  = { for s in local.post_slots : s.name => s }
  rule      = aws_cloudwatch_event_rule.post_tweet[each.key].name
  target_id = "lambda"
  arn       = aws_lambda_function.post_tweet[0].arn

  input = jsonencode({ slot = each.value.slot })
}

resource "aws_lambda_permission" "post_tweet_events" {
  for_each      = { for s in local.post_slots : s.name => s }
  statement_id  = "EventBridgeInvoke-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.post_tweet[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.post_tweet[each.key].arn
}

# SSM parameters: tweet text for 8 AM / 1 PM / 6 PM IST. Update daily or leave as DevOps defaults.
resource "aws_ssm_parameter" "tweet_morning" {
  count       = var.enable_auto_tweet ? 1 : 0
  name        = "/twitter/tweets/morning"
  type        = "String"
  value       = "one thing that actually moved the needle for our SLOs: ..."
  description = "8 AM – educational (DevOps/SRE)"
}

resource "aws_ssm_parameter" "tweet_afternoon" {
  count       = var.enable_auto_tweet ? 1 : 0
  name        = "/twitter/tweets/afternoon"
  type        = "String"
  value       = "hot take: most outages aren't infra. they're deployment and config. what's yours?"
  description = "1 PM – story/hot take"
}

resource "aws_ssm_parameter" "tweet_evening" {
  count       = var.enable_auto_tweet ? 1 : 0
  name        = "/twitter/tweets/evening"
  type        = "String"
  value       = "what do you do when on-call gets paged at 2am and the runbook is outdated? 👇"
  description = "6 PM – engagement"
}
