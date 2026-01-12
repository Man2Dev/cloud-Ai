##########################
# Input Variables
##########################

variable "telegram_token" {
  description = "Telegram bot token from @BotFather"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.telegram_token) > 0
    error_message = "Telegram token cannot be empty."
  }
}

variable "lab_role_arn" {
  description = "ARN of the pre-existing LabRole in AWS Academy"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:iam::", var.lab_role_arn))
    error_message = "Lab role ARN must be a valid IAM role ARN."
  }
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 14

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention must be a valid CloudWatch retention value."
  }
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 256
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
}