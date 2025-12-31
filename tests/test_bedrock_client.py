"""
Unit tests for AWS Bedrock client with IAM role support.

These tests use botocore.stub.Stubber to mock boto3 clients without making
actual AWS API calls.
"""

import json
import os
from unittest.mock import Mock, patch

import pytest

# Skip all tests if boto3 is not installed
pytest.importorskip("boto3")
pytest.importorskip("botocore")

from botocore.stub import Stubber

from biomni.bedrock_client import (
    BedrockAuthenticationError,
    BedrockClientError,
    BedrockClientManager,
    get_bedrock_client,
)


class TestBedrockClientManager:
    """Test suite for BedrockClientManager."""

    def test_init_with_default_region(self):
        """Test client initialization with default region."""
        with patch.dict(os.environ, {}, clear=True):
            manager = BedrockClientManager()
            assert manager.region_name == "us-east-1"

    def test_init_with_env_region(self):
        """Test client initialization with AWS_REGION environment variable."""
        with patch.dict(os.environ, {"AWS_REGION": "us-west-2"}):
            manager = BedrockClientManager()
            assert manager.region_name == "us-west-2"

    def test_init_with_aws_default_region(self):
        """Test client initialization with AWS_DEFAULT_REGION environment variable."""
        with patch.dict(os.environ, {"AWS_DEFAULT_REGION": "eu-west-1"}):
            manager = BedrockClientManager()
            assert manager.region_name == "eu-west-1"

    def test_init_with_explicit_region(self):
        """Test client initialization with explicit region parameter."""
        manager = BedrockClientManager(region_name="ap-southeast-1")
        assert manager.region_name == "ap-southeast-1"

    def test_init_with_profile(self):
        """Test client initialization with AWS profile."""
        with patch.dict(os.environ, {"AWS_PROFILE": "test-profile"}):
            manager = BedrockClientManager()
            assert manager.profile_name == "test-profile"

    def test_init_with_explicit_profile(self):
        """Test client initialization with explicit profile parameter."""
        manager = BedrockClientManager(profile_name="my-profile")
        assert manager.profile_name == "my-profile"

    def test_credentials_validation_no_credentials(self):
        """Test that initialization fails when no credentials are available."""
        # Mock session with no credentials
        with patch("biomni.bedrock_client.boto3.Session") as mock_session_class:
            mock_session = Mock()
            mock_session.get_credentials.return_value = None
            mock_session_class.return_value = mock_session

            with pytest.raises(BedrockAuthenticationError) as exc_info:
                BedrockClientManager()

            assert "No AWS credentials found" in str(exc_info.value)
            assert "IAM role" in str(exc_info.value)

    def test_runtime_client_property(self):
        """Test that runtime_client property creates client lazily."""
        manager = BedrockClientManager()

        # Client should not be created yet
        assert manager._runtime_client is None

        # Access property to create client
        with patch.object(manager.session, "client") as mock_client:
            _ = manager.runtime_client
            mock_client.assert_called_once_with("bedrock-runtime", config=manager.config)

    def test_bedrock_client_property(self):
        """Test that bedrock_client property creates client lazily."""
        manager = BedrockClientManager()

        # Client should not be created yet
        assert manager._bedrock_client is None

        # Access property to create client
        with patch.object(manager.session, "client") as mock_client:
            _ = manager.bedrock_client
            mock_client.assert_called_once_with("bedrock", config=manager.config)

    def test_invoke_model_success(self):
        """Test successful model invocation."""
        manager = BedrockClientManager()

        # Create stubber for runtime client
        client_stub = Stubber(manager.runtime_client)

        # Set up expected request and response
        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        request_body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": "Hello"}],
            }
        )
        response_body = json.dumps(
            {
                "content": [{"type": "text", "text": "Hi there!"}],
                "stop_reason": "end_turn",
            }
        )

        expected_params = {
            "modelId": model_id,
            "body": request_body.encode(),
            "accept": "application/json",
            "contentType": "application/json",
        }
        response = {
            "body": Mock(read=lambda: response_body.encode()),
            "contentType": "application/json",
            "ResponseMetadata": {"HTTPStatusCode": 200},
        }

        client_stub.add_response("invoke_model", response, expected_params)

        # Invoke model
        with client_stub:
            result = manager.invoke_model(
                model_id=model_id,
                body=request_body.encode(),
            )

            assert result["contentType"] == "application/json"
            assert result["ResponseMetadata"]["HTTPStatusCode"] == 200

    def test_invoke_model_access_denied(self):
        """Test model invocation with access denied error."""
        manager = BedrockClientManager()
        client_stub = Stubber(manager.runtime_client)

        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        request_body = b'{"test": "data"}'

        # Simulate AccessDeniedException
        client_stub.add_client_error(
            "invoke_model",
            service_error_code="AccessDeniedException",
            service_message="User is not authorized to perform: bedrock:InvokeModel",
            expected_params={
                "modelId": model_id,
                "body": request_body,
                "accept": "application/json",
                "contentType": "application/json",
            },
        )

        with client_stub:
            with pytest.raises(BedrockClientError) as exc_info:
                manager.invoke_model(model_id=model_id, body=request_body)

            assert "Access denied" in str(exc_info.value)
            assert "bedrock:InvokeModel" in str(exc_info.value)

    def test_invoke_model_resource_not_found(self):
        """Test model invocation with model not found error."""
        manager = BedrockClientManager()
        client_stub = Stubber(manager.runtime_client)

        model_id = "invalid.model-id"
        request_body = b'{"test": "data"}'

        # Simulate ResourceNotFoundException
        client_stub.add_client_error(
            "invoke_model",
            service_error_code="ResourceNotFoundException",
            service_message="Model not found",
            expected_params={
                "modelId": model_id,
                "body": request_body,
                "accept": "application/json",
                "contentType": "application/json",
            },
        )

        with client_stub:
            with pytest.raises(BedrockClientError) as exc_info:
                manager.invoke_model(model_id=model_id, body=request_body)

            assert "not found" in str(exc_info.value)
            assert model_id in str(exc_info.value)

    def test_invoke_model_throttling(self):
        """Test model invocation with throttling error."""
        manager = BedrockClientManager()
        client_stub = Stubber(manager.runtime_client)

        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        request_body = b'{"test": "data"}'

        # Simulate ThrottlingException
        client_stub.add_client_error(
            "invoke_model",
            service_error_code="ThrottlingException",
            service_message="Rate exceeded",
            expected_params={
                "modelId": model_id,
                "body": request_body,
                "accept": "application/json",
                "contentType": "application/json",
            },
        )

        with client_stub:
            with pytest.raises(BedrockClientError) as exc_info:
                manager.invoke_model(model_id=model_id, body=request_body)

            assert "throttled" in str(exc_info.value).lower()

    def test_invoke_model_with_response_stream_success(self):
        """Test successful streaming model invocation."""
        manager = BedrockClientManager()
        client_stub = Stubber(manager.runtime_client)

        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        request_body = b'{"test": "data"}'

        # Simulate streaming response
        mock_event_stream = [
            {"chunk": {"bytes": b'{"text": "Hello"}'}},
            {"chunk": {"bytes": b'{"text": " World"}'}},
        ]

        response = {
            "body": iter(mock_event_stream),
            "contentType": "application/json",
            "ResponseMetadata": {"HTTPStatusCode": 200},
        }

        client_stub.add_response(
            "invoke_model_with_response_stream",
            response,
            expected_params={
                "modelId": model_id,
                "body": request_body,
                "accept": "application/json",
                "contentType": "application/json",
            },
        )

        with client_stub:
            events = list(
                manager.invoke_model_with_response_stream(
                    model_id=model_id,
                    body=request_body,
                )
            )

            assert len(events) == 2
            assert events[0]["chunk"]["bytes"] == b'{"text": "Hello"}'

    def test_invoke_model_with_response_stream_access_denied(self):
        """Test streaming invocation with access denied error."""
        manager = BedrockClientManager()
        client_stub = Stubber(manager.runtime_client)

        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        request_body = b'{"test": "data"}'

        client_stub.add_client_error(
            "invoke_model_with_response_stream",
            service_error_code="AccessDeniedException",
            service_message="Not authorized for streaming",
            expected_params={
                "modelId": model_id,
                "body": request_body,
                "accept": "application/json",
                "contentType": "application/json",
            },
        )

        with client_stub:
            with pytest.raises(BedrockClientError) as exc_info:
                list(
                    manager.invoke_model_with_response_stream(
                        model_id=model_id,
                        body=request_body,
                    )
                )

            assert "Access denied" in str(exc_info.value)
            assert "InvokeModelWithResponseStream" in str(exc_info.value)


class TestGetBedrockClient:
    """Test suite for get_bedrock_client factory function."""

    def test_get_bedrock_client_creates_instance(self):
        """Test that get_bedrock_client returns a BedrockClientManager instance."""
        client = get_bedrock_client()
        assert isinstance(client, BedrockClientManager)

    def test_get_bedrock_client_with_region(self):
        """Test that get_bedrock_client respects region parameter."""
        client = get_bedrock_client(region_name="eu-central-1")
        assert client.region_name == "eu-central-1"

    def test_get_bedrock_client_with_profile(self):
        """Test that get_bedrock_client respects profile parameter."""
        client = get_bedrock_client(profile_name="test-profile")
        assert client.profile_name == "test-profile"


class TestBedrockClientIntegration:
    """
    Integration tests that require AWS credentials.
    
    These tests are skipped by default. Set RUN_BEDROCK_INTEGRATION=1 to run them.
    """

    @pytest.mark.skipif(
        os.getenv("RUN_BEDROCK_INTEGRATION") != "1",
        reason="Integration tests disabled. Set RUN_BEDROCK_INTEGRATION=1 to enable.",
    )
    def test_real_bedrock_invoke_model(self):
        """Test actual Bedrock model invocation (requires AWS credentials and model access)."""
        manager = BedrockClientManager()

        model_id = "anthropic.claude-3-haiku-20240307-v1:0"
        request_body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Say hello in 3 words"}],
            }
        )

        response = manager.invoke_model(
            model_id=model_id,
            body=request_body.encode(),
        )

        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
        assert "body" in response

        # Parse response body
        response_body = json.loads(response["body"].read())
        assert "content" in response_body
        assert len(response_body["content"]) > 0

    @pytest.mark.skipif(
        os.getenv("RUN_BEDROCK_INTEGRATION") != "1",
        reason="Integration tests disabled. Set RUN_BEDROCK_INTEGRATION=1 to enable.",
    )
    def test_real_credentials_validation(self):
        """Test that credentials validation works with real AWS credentials."""
        # This should not raise if credentials are properly configured
        manager = BedrockClientManager()

        # Verify we can access the runtime client
        assert manager.runtime_client is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
