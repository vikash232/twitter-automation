output "lambda_function_name" {
  value = aws_lambda_function.reminder.function_name
}

output "lambda_function_arn" {
  value = aws_lambda_function.reminder.arn
}

output "eventbridge_rule_name" {
  value = aws_cloudwatch_event_rule.daily.name
}

output "schedule_expression" {
  value = var.schedule_cron
}

output "twitter_secret_arn" {
  value     = var.enable_auto_tweet ? aws_secretsmanager_secret.twitter[0].arn : null
  sensitive = true
}

output "ssm_tweet_params" {
  value = var.enable_auto_tweet ? ["/twitter/tweets/morning", "/twitter/tweets/afternoon", "/twitter/tweets/evening"] : []
  description = "Update these SSM parameters with your tweet text (e.g. aws ssm put-parameter --name /twitter/tweets/morning --value 'your tweet' --overwrite)"
}
