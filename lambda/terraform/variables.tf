variable "aws_profile" {
  description = "AWS CLI profile (e.g. vikash-own)"
  type        = string
  default     = "vikash-own"
}

variable "region" {
  description = "AWS region (SES and Lambda must be in this region)"
  type        = string
  default     = "us-east-1"
}

variable "reminder_email" {
  description = "Email address to receive the daily reminder (must be verified in SES)"
  type        = string
}

variable "from_email" {
  description = "SES verified sender email (e.g. same as reminder_email in sandbox)"
  type        = string
}

variable "schedule_cron" {
  description = "EventBridge schedule expression. Default: 7 PM IST (13:30 UTC)"
  type        = string
  default     = "cron(30 13 * * ? *)"
}

variable "function_name" {
  description = "Lambda function name (email reminder)"
  type        = string
  default     = "twitter-daily-reminder"
}

# Twitter API (OAuth 1.0a) – for auto-posting. Get from X Developer Portal: Consumer Key, Consumer Secret, Access Token (Read and Write), Access Token Secret.
variable "twitter_consumer_key" {
  description = "Twitter API Consumer Key (API Key)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "twitter_consumer_secret" {
  description = "Twitter API Consumer Secret (API Key Secret)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "twitter_access_token" {
  description = "Twitter Access Token (Read and Write)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "twitter_access_token_secret" {
  description = "Twitter Access Token Secret"
  type        = string
  default     = ""
  sensitive   = true
}

variable "enable_auto_tweet" {
  description = "Create Lambda + EventBridge to post tweets at 8a/1p/6p IST from SSM"
  type        = bool
  default     = false
}

variable "post_tweet_function_name" {
  description = "Lambda function name for posting tweets"
  type        = string
  default     = "twitter-post-tweet"
}
