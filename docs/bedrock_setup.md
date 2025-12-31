# AWS Bedrock Setup Guide

This guide explains how to configure Biomni to use Amazon Bedrock with IAM role authentication.

## Overview

Biomni supports Amazon Bedrock models using **IAM role-based authentication** through the AWS SDK credential provider chain. This means:

- ✅ No API keys or bearer tokens required
- ✅ Automatic credential resolution on AWS services (EC2, ECS, EKS, Lambda, SageMaker, etc.)
- ✅ Secure, AWS-native authentication
- ✅ Easy local development with AWS profiles

## Prerequisites

1. **boto3 and langchain-aws packages**:
   ```bash
   pip install boto3 langchain-aws
   ```

2. **AWS credentials** configured via one of:
   - IAM role attached to your compute resource (recommended for production)
   - AWS profile in `~/.aws/credentials` (for local development)
   - Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)

3. **Bedrock model access** enabled in your AWS account/region

## Configuration

### 1. Set Environment Variables

Create a `.env` file or set environment variables:

```bash
# Required: Specify Bedrock as the LLM source
LLM_SOURCE=Bedrock

# Required: AWS region where Bedrock is available
AWS_REGION=us-east-1

# Optional: For local development with AWS CLI profiles
# AWS_PROFILE=your_profile_name

# Optional: Bedrock-specific settings
# BIOMNI_BEDROCK_MAX_RETRIES=5
```

### 2. Specify a Bedrock Model

When initializing the agent, specify a Bedrock model ID:

```python
from biomni.agent import A1

# Anthropic Claude on Bedrock
agent = A1(
    path='./data',
    llm='anthropic.claude-3-sonnet-20240229-v1:0'
)

# Amazon Titan
agent = A1(
    path='./data',
    llm='amazon.titan-text-premier-v1:0'
)

# Meta Llama
agent = A1(
    path='./data',
    llm='meta.llama3-70b-instruct-v1:0'
)
```

## IAM Permissions

### Minimum Required Policy

Your IAM role or user must have the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/*"
      ]
    }
  ]
}
```

### Region-Specific Policy

To restrict access to specific models or regions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-*",
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-*"
      ]
    }
  ]
}
```

## Deployment Scenarios

### Running on EC2

1. Create an IAM role with Bedrock permissions (see above)
2. Attach the role to your EC2 instance
3. No additional configuration needed - credentials are automatically available via IMDS

```python
# No AWS credentials needed - automatically uses instance role
from biomni.agent import A1
import os

os.environ['LLM_SOURCE'] = 'Bedrock'
os.environ['AWS_REGION'] = 'us-east-1'

agent = A1(path='./data', llm='anthropic.claude-3-sonnet-20240229-v1:0')
agent.go("Design a CRISPR screen for T cell exhaustion")
```

### Running on ECS/EKS

1. Create an IAM role with Bedrock permissions
2. Configure your task definition (ECS) or service account (EKS) to use the role
3. Deploy your container - credentials are automatically injected

### Running on Lambda

1. Create a Lambda execution role with Bedrock permissions
2. Deploy your function
3. Credentials are automatically available

### Running on SageMaker

1. Create a SageMaker execution role with Bedrock permissions
2. Attach to your notebook instance or training job
3. Credentials are automatically available

### Local Development

For local development, use AWS CLI profiles:

1. Configure AWS CLI:
   ```bash
   aws configure --profile biomni-dev
   ```

2. Set environment variable:
   ```bash
   export AWS_PROFILE=biomni-dev
   export AWS_REGION=us-east-1
   export LLM_SOURCE=Bedrock
   ```

3. Or set in `.env`:
   ```bash
   AWS_PROFILE=biomni-dev
   AWS_REGION=us-east-1
   LLM_SOURCE=Bedrock
   ```

## Enabling Bedrock Models

Before using Bedrock models, you must enable them in your AWS account:

1. Open the [Amazon Bedrock console](https://console.aws.amazon.com/bedrock/)
2. Navigate to "Model access" in the left sidebar
3. Click "Manage model access"
4. Select the models you want to use (e.g., Claude 3, Titan, Llama)
5. Click "Request model access" (some models require approval)

## Supported Bedrock Models

Biomni automatically detects Bedrock models by their ID prefix. Common models:

### Anthropic Claude
- `anthropic.claude-3-opus-20240229-v1:0`
- `anthropic.claude-3-sonnet-20240229-v1:0`
- `anthropic.claude-3-haiku-20240307-v1:0`
- `anthropic.claude-3-5-sonnet-20240620-v1:0`

### Amazon Titan
- `amazon.titan-text-premier-v1:0`
- `amazon.titan-text-express-v1`
- `amazon.titan-embed-text-v1`

### Meta Llama
- `meta.llama3-70b-instruct-v1:0`
- `meta.llama3-8b-instruct-v1:0`

### Mistral AI
- `mistral.mistral-7b-instruct-v0:2`
- `mistral.mixtral-8x7b-instruct-v0:1`

### Cohere
- `cohere.command-text-v14`
- `cohere.command-light-text-v14`

### AI21 Labs
- `ai21.j2-ultra-v1`
- `ai21.j2-mid-v1`

## Troubleshooting

### Error: "No AWS credentials found"

**Cause**: AWS credentials are not configured or accessible.

**Solutions**:
- For EC2/ECS/EKS: Ensure IAM role is attached to the resource
- For local dev: Set `AWS_PROFILE` or configure `aws configure`
- Verify credentials: `aws sts get-caller-identity`

### Error: "AccessDeniedException"

**Cause**: IAM role/user lacks required permissions.

**Solutions**:
- Add `bedrock:InvokeModel` permission to IAM policy
- Verify model access is enabled in Bedrock console
- Check if model is available in your region

### Error: "ResourceNotFoundException"

**Cause**: Model ID is incorrect or not available in your region.

**Solutions**:
- Verify model ID spelling
- Check model availability in your region
- Enable model access in Bedrock console

### Error: "ThrottlingException"

**Cause**: Too many requests or quota limits reached.

**Solutions**:
- Implement exponential backoff
- Request quota increase via AWS Support
- Use different model with higher quota

## Best Practices

1. **Use IAM roles** instead of access keys for production deployments
2. **Enable only necessary models** to minimize security surface
3. **Set appropriate timeouts** for long-running tasks:
   ```python
   config = BiomniConfig(timeout_seconds=1200)
   agent = A1(config=config)
   ```
4. **Monitor costs** - Bedrock charges per token. Use CloudWatch and AWS Cost Explorer
5. **Implement retry logic** - The SDK handles automatic retries, but you can adjust:
   ```bash
   BIOMNI_BEDROCK_MAX_RETRIES=5
   ```
6. **Use specific model versions** for reproducibility
7. **Test in development** with AWS profiles before deploying

## Region Availability

Amazon Bedrock is available in select regions. As of December 2024:

- US East (N. Virginia) - `us-east-1` ✅ Recommended
- US West (Oregon) - `us-west-2`
- Asia Pacific (Singapore) - `ap-southeast-1`
- Asia Pacific (Tokyo) - `ap-northeast-1`
- Europe (Frankfurt) - `eu-central-1`
- Europe (Ireland) - `eu-west-1`

Check the [AWS Bedrock documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html#bedrock-regions) for the latest region availability.

## Cost Optimization

- Use smaller models (e.g., Claude Haiku) for simpler tasks
- Enable caching for repeated queries (when available)
- Set appropriate token limits
- Monitor usage with CloudWatch metrics
- Use AWS Budgets to set spending alerts

## Additional Resources

- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
- [IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [boto3 Credentials Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)
