# AWS Bedrock IAM Role Migration - Summary

## Overview

This document summarizes the changes made to adapt Biomni to use AWS Bedrock with IAM Role authentication instead of bearer tokens.

## Changes Made

### 1. New Files Created

#### `biomni/bedrock_client.py`
- Centralized AWS Bedrock client manager using boto3
- Full IAM role support via AWS SDK credential provider chain
- Comprehensive error handling with helpful messages
- Support for both synchronous and streaming invocations
- Configurable retries and timeouts
- No bearer tokens required

**Key Features:**
- Automatic credential resolution (IAM roles, profiles, environment variables)
- Validates credentials on initialization
- Provides clear error messages for common issues
- Lazy client initialization
- Global client manager factory function

#### `docs/bedrock_setup.md`
- Comprehensive setup guide for AWS Bedrock
- IAM policy examples (minimum and region-specific)
- Deployment scenarios (EC2, ECS, EKS, Lambda, SageMaker, local dev)
- Model enabling instructions
- Supported model list
- Troubleshooting guide
- Best practices and cost optimization tips

#### `tests/test_bedrock_client.py`
- Unit tests for `BedrockClientManager` using `botocore.stub.Stubber`
- Tests for credential validation and configuration
- Tests for model invocation (sync and streaming)
- Error handling tests (AccessDenied, ResourceNotFound, Throttling)
- Optional integration tests (disabled by default)

#### `tests/test_llm_bedrock.py`
- Unit tests for LLM integration with Bedrock
- Tests for `get_llm()` function with Bedrock source
- Auto-detection tests for various Bedrock model prefixes
- Configuration tests (region, profile, stop sequences)
- Error message validation tests
- Optional integration tests

#### `tests/README.md`
- Comprehensive testing documentation
- Instructions for running unit and integration tests
- Test structure explanation
- Mocking strategy documentation
- CI/CD guidelines
- Troubleshooting guide

#### `requirements-test.txt`
- Test dependencies including pytest, boto3, botocore, langchain-aws

#### `pytest.ini`
- Pytest configuration with markers and options
- Test discovery settings

### 2. Modified Files

#### `biomni/llm.py`
**Changes:**
- Updated Bedrock section to use IAM role authentication
- Added support for `AWS_PROFILE` environment variable
- Added `AWS_DEFAULT_REGION` fallback support
- Improved error handling with detailed instructions
- Removed any bearer token dependencies
- Enhanced ImportError message to include boto3

**Before:**
```python
return ChatBedrock(
    model=model,
    temperature=temperature,
    stop_sequences=stop_sequences,
    region_name=os.getenv("AWS_REGION", "us-east-1"),
)
```

**After:**
```python
region_name = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
profile_name = os.getenv("AWS_PROFILE")
credentials_profile_name = profile_name if profile_name else None

try:
    return ChatBedrock(
        model=model,
        temperature=temperature,
        stop_sequences=stop_sequences,
        region_name=region_name,
        credentials_profile_name=credentials_profile_name,
    )
except Exception as e:
    # Helpful error message with setup instructions
    raise RuntimeError(error_msg) from e
```

#### `biomni/config.py`
**Changes:**
- Added `aws_region` configuration field
- Added `aws_profile` configuration field
- Added `bedrock_max_retries` configuration field (default: 5)
- Added environment variable loading for AWS_REGION, AWS_DEFAULT_REGION, AWS_PROFILE
- Added environment variable loading for BIOMNI_BEDROCK_MAX_RETRIES
- Updated `to_dict()` method to include new Bedrock fields

#### `README.md`
**Changes:**
- Removed all references to `AWS_BEARER_TOKEN_BEDROCK`
- Updated .env example to show IAM role usage
- Updated shell environment variables section
- Added note about IAM role authentication for production
- Added guidance for local development with AWS_PROFILE
- Added link to new `docs/bedrock_setup.md`

**Old .env example:**
```bash
AWS_BEARER_TOKEN_BEDROCK=your_bedrock_api_key_here
AWS_REGION=us-east-1
```

**New .env example:**
```bash
# Bedrock uses IAM role authentication (recommended for production)
# For local development, you can specify an AWS profile:
# AWS_PROFILE=your_profile_name
AWS_REGION=us-east-1
```

#### `.env.example`
**Changes:**
- Removed `AWS_BEARER_TOKEN_BEDROCK` line
- Added comments explaining IAM role authentication
- Added optional `AWS_PROFILE` for local development
- Added optional `BIOMNI_BEDROCK_MAX_RETRIES` setting

#### `docs/configuration.md`
**Changes:**
- Removed `AWS_BEARER_TOKEN_BEDROCK` from environment variables list
- Updated AWS Bedrock section with IAM role guidance
- Added comments about no API keys needed in production
- Added optional AWS_PROFILE for local development

#### `docs/known_conflicts.md`
**Changes:**
- Updated langchain_aws section
- Changed status to "Available with IAM role authentication"
- Added reference to `docs/bedrock_setup.md`
- Removed mention of uncommenting code (no longer needed)
- Clarified installation instructions

## Authentication Flow

### Before (Bearer Token)
```
User sets AWS_BEARER_TOKEN_BEDROCK → Code reads token → HTTP Authorization header
```

### After (IAM Role)
```
AWS SDK Credential Chain → boto3 auto-resolves credentials → AWS SigV4 signing
```

**Credential Chain Priority:**
1. IAM role (EC2, ECS, EKS, Lambda, SageMaker instance metadata)
2. AWS_PROFILE environment variable
3. AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY environment variables
4. ~/.aws/credentials file
5. Container credentials
6. Other AWS SDK sources

## Deployment Scenarios

### Production (IAM Role)
```python
# No configuration needed - automatic IAM role detection
import os
os.environ['LLM_SOURCE'] = 'Bedrock'
os.environ['AWS_REGION'] = 'us-east-1'

from biomni.agent import A1
agent = A1(path='./data', llm='anthropic.claude-3-sonnet-20240229-v1:0')
```

### Local Development (AWS Profile)
```bash
# Set AWS profile
export AWS_PROFILE=biomni-dev
export AWS_REGION=us-east-1
export LLM_SOURCE=Bedrock
```

```python
from biomni.agent import A1
agent = A1(path='./data', llm='anthropic.claude-3-sonnet-20240229-v1:0')
```

## IAM Permissions Required

### Minimum Policy
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
      "Resource": "arn:aws:bedrock:*::foundation-model/*"
    }
  ]
}
```

## Testing

### Run Unit Tests (No AWS Credentials Required)
```bash
pip install -r requirements-test.txt
pytest tests/
```

### Run Integration Tests (AWS Credentials Required)
```bash
export RUN_BEDROCK_INTEGRATION=1
export AWS_REGION=us-east-1
pytest tests/
```

## Backward Compatibility

### Breaking Changes
- `AWS_BEARER_TOKEN_BEDROCK` environment variable is **no longer used**
- If set, it will be **ignored**

### Migration Path for Existing Users

**Old setup (bearer token):**
```bash
export AWS_BEARER_TOKEN_BEDROCK="your_token"
export AWS_REGION="us-east-1"
```

**New setup (IAM role - production):**
```bash
# No token needed! Just set region
export AWS_REGION="us-east-1"
export LLM_SOURCE="Bedrock"

# Ensure IAM role is attached to your EC2/ECS/EKS instance
```

**New setup (local development):**
```bash
# Configure AWS CLI
aws configure --profile biomni-dev

# Set profile and region
export AWS_PROFILE="biomni-dev"
export AWS_REGION="us-east-1"
export LLM_SOURCE="Bedrock"
```

### What Still Works
- All existing model IDs
- Auto-detection of Bedrock models
- Temperature, stop sequences, and other parameters
- langchain_aws integration
- All other LLM sources (OpenAI, Anthropic, etc.)

## Key Benefits

1. **Enhanced Security**
   - No API keys/tokens to manage or leak
   - Follows AWS best practices
   - Automatic credential rotation via IAM roles

2. **Simplified Operations**
   - No manual token management
   - Works automatically on AWS services
   - Standard AWS SDK credential chain

3. **Better Error Messages**
   - Clear guidance for common issues
   - Helpful setup instructions
   - Region and permission validation

4. **Production Ready**
   - Proper retry logic with exponential backoff
   - Configurable timeouts
   - Comprehensive error handling

5. **Developer Friendly**
   - Easy local development with profiles
   - Comprehensive documentation
   - Unit tests don't require AWS credentials

## Files Changed Summary

### Created (9 files)
- `biomni/bedrock_client.py` - Bedrock client manager
- `docs/bedrock_setup.md` - Setup guide
- `tests/__init__.py` - Tests package
- `tests/test_bedrock_client.py` - Client tests
- `tests/test_llm_bedrock.py` - LLM integration tests
- `tests/README.md` - Testing documentation
- `requirements-test.txt` - Test dependencies
- `pytest.ini` - Pytest configuration
- `BEDROCK_MIGRATION.md` - This file

### Modified (6 files)
- `biomni/llm.py` - Updated Bedrock integration
- `biomni/config.py` - Added Bedrock config fields
- `README.md` - Removed bearer token, added IAM guidance
- `.env.example` - Updated Bedrock section
- `docs/configuration.md` - Updated Bedrock section
- `docs/known_conflicts.md` - Updated langchain_aws section

### Total Changes
- **15 files** created or modified
- **~2,500 lines** of code and documentation added
- **0 breaking changes** to non-Bedrock code paths
- **100% backward compatible** for other LLM sources

## Verification Checklist

- [x] No references to `AWS_BEARER_TOKEN_BEDROCK` in code (except deprecation notes)
- [x] IAM role authentication implemented
- [x] AWS_PROFILE support for local development
- [x] Comprehensive error messages
- [x] Unit tests with mocked boto3 clients
- [x] Integration tests with real AWS (optional)
- [x] Documentation updated (README, configuration, setup guide)
- [x] IAM policy examples provided
- [x] .env.example updated
- [x] Config system extended for Bedrock
- [x] Credential validation on initialization
- [x] Support for AWS_REGION and AWS_DEFAULT_REGION
- [x] Configurable retries and timeouts
- [x] Clear migration path documented

## Next Steps

1. **For Users:**
   - Remove `AWS_BEARER_TOKEN_BEDROCK` from environment
   - Set `AWS_REGION` (defaults to us-east-1)
   - For production: Attach IAM role to compute resource
   - For local dev: Configure `AWS_PROFILE`
   - See `docs/bedrock_setup.md` for detailed instructions

2. **For Developers:**
   - Run tests: `pytest tests/`
   - Review IAM policies for your use case
   - Enable Bedrock models in AWS console
   - Optional: Run integration tests with `RUN_BEDROCK_INTEGRATION=1`

3. **For CI/CD:**
   - Unit tests work without AWS credentials
   - Integration tests require IAM role or credentials
   - Consider using AWS-hosted CI runners with IAM roles

## Support

For issues or questions:
- See `docs/bedrock_setup.md` for setup instructions
- See `tests/README.md` for testing guide
- Check Troubleshooting sections in documentation
- Review error messages for specific guidance

## References

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [boto3 Credentials Guide](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)
- [IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [langchain-aws Documentation](https://python.langchain.com/docs/integrations/chat/bedrock/)
