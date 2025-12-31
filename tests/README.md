# Biomni Tests

This directory contains tests for Biomni, including unit tests and integration tests for AWS Bedrock support.

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

### Run All Unit Tests

```bash
pytest tests/
```

### Run Specific Test Files

```bash
# Test Bedrock client
pytest tests/test_bedrock_client.py

# Test LLM integration
pytest tests/test_llm_bedrock.py
```

### Run with Coverage

```bash
pytest tests/ --cov=biomni --cov-report=html --cov-report=term-missing
```

## Integration Tests

Integration tests require actual AWS credentials and access to Bedrock models. They are disabled by default.

### Prerequisites for Integration Tests

1. **AWS Credentials**: Configure via IAM role, AWS profile, or environment variables
2. **Bedrock Access**: Ensure models are enabled in your AWS account
3. **Permissions**: Your IAM role/user needs `bedrock:InvokeModel` permission

### Run Integration Tests

```bash
# Enable integration tests
export RUN_BEDROCK_INTEGRATION=1

# Run all tests including integration tests
pytest tests/

# Run only integration tests
pytest tests/ -m integration
```

### Integration Test Configuration

```bash
# Set AWS region for integration tests
export AWS_REGION=us-east-1

# Optional: Use specific AWS profile
export AWS_PROFILE=your-profile-name

# Run tests
RUN_BEDROCK_INTEGRATION=1 pytest tests/
```

## Test Structure

### Unit Tests (No AWS API Calls)

- **test_bedrock_client.py**: Tests for `BedrockClientManager`
  - Uses `botocore.stub.Stubber` to mock AWS API calls
  - Tests credential validation
  - Tests error handling
  - Tests client configuration

- **test_llm_bedrock.py**: Tests for LLM integration
  - Tests `get_llm()` function with Bedrock source
  - Tests auto-detection of Bedrock models
  - Tests region and profile configuration
  - Tests error messages

### Integration Tests (Require AWS Credentials)

- **TestBedrockClientIntegration**: Real Bedrock API calls
  - Tests actual model invocation
  - Tests credentials validation
  - Requires: `RUN_BEDROCK_INTEGRATION=1`

- **TestBedrockLLMIntegrationReal**: Real LLM invocations
  - Tests end-to-end LLM usage
  - Requires: `RUN_BEDROCK_INTEGRATION=1`

## Mocking Strategy

Unit tests use `botocore.stub.Stubber` to mock boto3 clients without making actual AWS API calls:

```python
from botocore.stub import Stubber

# Create stubber for client
client_stub = Stubber(client)

# Add expected request and response
client_stub.add_response('invoke_model', expected_response, expected_params)

# Run test within stubber context
with client_stub:
    result = client.invoke_model(...)
```

## Test Markers

Tests are organized with pytest markers:

- `@pytest.mark.unit`: Unit tests (fast, no external dependencies)
- `@pytest.mark.integration`: Integration tests (slow, require AWS)
- `@pytest.mark.slow`: Slow running tests

Run specific markers:

```bash
# Run only unit tests
pytest tests/ -m unit

# Run only integration tests
pytest tests/ -m integration

# Skip slow tests
pytest tests/ -m "not slow"
```

## Continuous Integration

For CI/CD pipelines, run only unit tests by default:

```bash
# CI pipeline - unit tests only
pytest tests/ -m "not integration"
```

To enable integration tests in CI, set environment variables and ensure AWS credentials are available via:
- IAM roles (for AWS-hosted CI runners)
- GitHub Secrets (for GitHub Actions)
- Environment variables in CI configuration

## Debugging Tests

### Verbose Output

```bash
pytest tests/ -v -s
```

### Run Specific Test

```bash
pytest tests/test_bedrock_client.py::TestBedrockClientManager::test_init_with_default_region
```

### Drop into Debugger on Failure

```bash
pytest tests/ --pdb
```

### Show Local Variables on Failure

```bash
pytest tests/ -l
```

## Writing New Tests

### Unit Test Template

```python
import pytest
from unittest.mock import Mock, patch
from botocore.stub import Stubber

def test_my_feature():
    """Test description."""
    # Setup
    manager = BedrockClientManager()
    client_stub = Stubber(manager.runtime_client)
    
    # Add expected API call
    client_stub.add_response('invoke_model', expected_response, expected_params)
    
    # Run test
    with client_stub:
        result = manager.invoke_model(...)
    
    # Assert
    assert result['key'] == 'expected_value'
```

### Integration Test Template

```python
@pytest.mark.skipif(
    os.getenv("RUN_BEDROCK_INTEGRATION") != "1",
    reason="Integration tests disabled"
)
def test_real_bedrock_call():
    """Test with real AWS API call."""
    manager = BedrockClientManager()
    response = manager.invoke_model(model_id="...", body=b"...")
    assert response['ResponseMetadata']['HTTPStatusCode'] == 200
```

## Troubleshooting

### ImportError: No module named 'boto3'

```bash
pip install boto3 botocore
```

### Tests Fail with "No credentials found"

This is expected for unit tests if mocking isn't set up correctly. Unit tests should not require real AWS credentials.

For integration tests, configure AWS credentials:
```bash
aws configure
# OR
export AWS_PROFILE=your-profile
```

### Integration Tests Fail with AccessDeniedException

Ensure your IAM role/user has these permissions:
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream"
  ],
  "Resource": "arn:aws:bedrock:*::foundation-model/*"
}
```

Also verify that Bedrock models are enabled in your AWS account via the Bedrock console.

## Contributing

When adding new features:
1. Write unit tests first (TDD approach)
2. Use mocking for external dependencies
3. Add integration tests for critical paths
4. Update this README if adding new test patterns
5. Ensure all unit tests pass without AWS credentials
6. Mark integration tests with appropriate skipif decorators
