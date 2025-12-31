"""
Unit tests for LLM integration with Bedrock.

Tests the get_llm function with Bedrock source to ensure IAM role
authentication works correctly.
"""

import os
from unittest.mock import Mock, patch

import pytest

# Skip if langchain_aws is not installed
langchain_aws = pytest.importorskip("langchain_aws")

from biomni.llm import get_llm


class TestBedrockLLMIntegration:
    """Test suite for Bedrock LLM integration."""

    def test_get_llm_bedrock_auto_detect(self):
        """Test that Bedrock is auto-detected from model name."""
        with patch.dict(os.environ, {"AWS_REGION": "us-east-1"}):
            with patch("biomni.llm.ChatBedrock") as mock_bedrock:
                mock_instance = Mock()
                mock_bedrock.return_value = mock_instance

                llm = get_llm(
                    model="anthropic.claude-3-sonnet-20240229-v1:0",
                    temperature=0.5,
                )

                # Verify ChatBedrock was called
                mock_bedrock.assert_called_once()
                call_kwargs = mock_bedrock.call_args[1]

                assert call_kwargs["model"] == "anthropic.claude-3-sonnet-20240229-v1:0"
                assert call_kwargs["temperature"] == 0.5
                assert call_kwargs["region_name"] == "us-east-1"
                assert call_kwargs.get("credentials_profile_name") is None

    def test_get_llm_bedrock_explicit_source(self):
        """Test Bedrock with explicit source parameter."""
        with patch.dict(os.environ, {"AWS_REGION": "us-west-2"}):
            with patch("biomni.llm.ChatBedrock") as mock_bedrock:
                mock_instance = Mock()
                mock_bedrock.return_value = mock_instance

                llm = get_llm(
                    model="my-custom-model",
                    source="Bedrock",
                    temperature=0.7,
                )

                mock_bedrock.assert_called_once()
                call_kwargs = mock_bedrock.call_args[1]

                assert call_kwargs["model"] == "my-custom-model"
                assert call_kwargs["region_name"] == "us-west-2"

    def test_get_llm_bedrock_with_profile(self):
        """Test Bedrock with AWS_PROFILE for local development."""
        with patch.dict(os.environ, {"AWS_REGION": "eu-west-1", "AWS_PROFILE": "dev-profile"}):
            with patch("biomni.llm.ChatBedrock") as mock_bedrock:
                mock_instance = Mock()
                mock_bedrock.return_value = mock_instance

                llm = get_llm(
                    model="anthropic.claude-3-haiku-20240307-v1:0",
                    source="Bedrock",
                )

                mock_bedrock.assert_called_once()
                call_kwargs = mock_bedrock.call_args[1]

                assert call_kwargs["region_name"] == "eu-west-1"
                assert call_kwargs["credentials_profile_name"] == "dev-profile"

    def test_get_llm_bedrock_default_region(self):
        """Test that Bedrock defaults to us-east-1 if no region specified."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("biomni.llm.ChatBedrock") as mock_bedrock:
                mock_instance = Mock()
                mock_bedrock.return_value = mock_instance

                llm = get_llm(
                    model="meta.llama3-70b-instruct-v1:0",
                    source="Bedrock",
                )

                mock_bedrock.assert_called_once()
                call_kwargs = mock_bedrock.call_args[1]

                assert call_kwargs["region_name"] == "us-east-1"

    def test_get_llm_bedrock_with_stop_sequences(self):
        """Test Bedrock with stop sequences."""
        with patch.dict(os.environ, {"AWS_REGION": "us-east-1"}):
            with patch("biomni.llm.ChatBedrock") as mock_bedrock:
                mock_instance = Mock()
                mock_bedrock.return_value = mock_instance

                stop_sequences = ["STOP", "END"]
                llm = get_llm(
                    model="anthropic.claude-3-sonnet-20240229-v1:0",
                    source="Bedrock",
                    stop_sequences=stop_sequences,
                )

                mock_bedrock.assert_called_once()
                call_kwargs = mock_bedrock.call_args[1]

                assert call_kwargs["stop_sequences"] == stop_sequences

    def test_get_llm_bedrock_error_handling(self):
        """Test that helpful error message is provided on initialization failure."""
        with patch.dict(os.environ, {"AWS_REGION": "us-east-1"}):
            with patch("biomni.llm.ChatBedrock") as mock_bedrock:
                # Simulate initialization error
                mock_bedrock.side_effect = Exception("NoCredentialsError")

                with pytest.raises(RuntimeError) as exc_info:
                    get_llm(
                        model="anthropic.claude-3-sonnet-20240229-v1:0",
                        source="Bedrock",
                    )

                error_msg = str(exc_info.value)
                assert "Failed to initialize Bedrock client" in error_msg
                assert "IAM role" in error_msg
                assert "AWS_PROFILE" in error_msg
                assert "bedrock:InvokeModel" in error_msg

    def test_get_llm_bedrock_aws_default_region(self):
        """Test that AWS_DEFAULT_REGION is respected if AWS_REGION is not set."""
        with patch.dict(os.environ, {"AWS_DEFAULT_REGION": "ap-southeast-1"}):
            with patch("biomni.llm.ChatBedrock") as mock_bedrock:
                mock_instance = Mock()
                mock_bedrock.return_value = mock_instance

                llm = get_llm(
                    model="amazon.titan-text-premier-v1:0",
                    source="Bedrock",
                )

                mock_bedrock.assert_called_once()
                call_kwargs = mock_bedrock.call_args[1]

                assert call_kwargs["region_name"] == "ap-southeast-1"

    def test_get_llm_bedrock_model_auto_detection(self):
        """Test auto-detection of various Bedrock model prefixes."""
        bedrock_models = [
            "anthropic.claude-3-opus-20240229-v1:0",
            "amazon.titan-text-express-v1",
            "meta.llama3-8b-instruct-v1:0",
            "mistral.mixtral-8x7b-instruct-v0:1",
            "cohere.command-text-v14",
            "ai21.j2-ultra-v1",
        ]

        with patch.dict(os.environ, {"AWS_REGION": "us-east-1"}):
            for model in bedrock_models:
                with patch("biomni.llm.ChatBedrock") as mock_bedrock:
                    mock_instance = Mock()
                    mock_bedrock.return_value = mock_instance

                    # Should auto-detect as Bedrock (no explicit source)
                    llm = get_llm(model=model)

                    mock_bedrock.assert_called_once()
                    call_kwargs = mock_bedrock.call_args[1]
                    assert call_kwargs["model"] == model

    def test_get_llm_bedrock_with_config(self):
        """Test Bedrock initialization with BiomniConfig."""
        from biomni.config import BiomniConfig

        config = BiomniConfig(
            llm="anthropic.claude-3-sonnet-20240229-v1:0",
            temperature=0.3,
            source="Bedrock",
        )

        with patch.dict(os.environ, {"AWS_REGION": "us-east-1"}):
            with patch("biomni.llm.ChatBedrock") as mock_bedrock:
                mock_instance = Mock()
                mock_bedrock.return_value = mock_instance

                llm = get_llm(config=config)

                mock_bedrock.assert_called_once()
                call_kwargs = mock_bedrock.call_args[1]

                assert call_kwargs["model"] == "anthropic.claude-3-sonnet-20240229-v1:0"
                assert call_kwargs["temperature"] == 0.3


class TestBedrockLLMIntegrationReal:
    """
    Integration tests with real Bedrock API calls.
    
    Set RUN_BEDROCK_INTEGRATION=1 to enable these tests.
    """

    @pytest.mark.skipif(
        os.getenv("RUN_BEDROCK_INTEGRATION") != "1",
        reason="Integration tests disabled. Set RUN_BEDROCK_INTEGRATION=1 to enable.",
    )
    def test_real_bedrock_llm_invoke(self):
        """Test actual Bedrock LLM invocation with IAM role."""
        with patch.dict(os.environ, {"AWS_REGION": "us-east-1", "LLM_SOURCE": "Bedrock"}):
            llm = get_llm(
                model="anthropic.claude-3-haiku-20240307-v1:0",
                temperature=0.5,
            )

            # Simple test invocation
            response = llm.invoke("Say 'test successful' and nothing else")

            # Verify we got a response
            assert response is not None
            assert hasattr(response, "content")
            assert len(response.content) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
