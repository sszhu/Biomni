"""
AWS Bedrock Client with IAM Role Support

This module provides centralized AWS Bedrock client creation and management
using boto3 with IAM role authentication (no bearer tokens required).

The client automatically uses the AWS SDK credential provider chain:
- IAM roles (EC2, ECS, EKS, Lambda, SageMaker, etc.)
- Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)
- AWS profiles (AWS_PROFILE)
- Shared credentials file (~/.aws/credentials)
- Container credentials
- Instance metadata service (IMDS)
"""

import logging
import os
from typing import Any, Dict, Iterator, Optional

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
    
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

logger = logging.getLogger(__name__)


class BedrockClientError(Exception):
    """Base exception for Bedrock client errors."""
    pass


class BedrockAuthenticationError(BedrockClientError):
    """Raised when AWS authentication fails."""
    pass


class BedrockClientManager:
    """
    Manages AWS Bedrock client instances with IAM role authentication.
    
    This class provides a centralized way to create and configure Bedrock
    clients using boto3, with proper error handling and credential validation.
    
    Example:
        manager = BedrockClientManager(region="us-east-1")
        response = manager.invoke_model(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            payload={
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": "Hello"}]
            }
        )
    """
    
    def __init__(
        self,
        region_name: Optional[str] = None,
        profile_name: Optional[str] = None,
        max_retries: int = 5,
        connect_timeout: int = 60,
        read_timeout: int = 300,
    ):
        """
        Initialize Bedrock client manager.
        
        Args:
            region_name: AWS region (defaults to AWS_REGION env var or us-east-1)
            profile_name: AWS profile name (defaults to AWS_PROFILE env var)
            max_retries: Maximum number of retry attempts (default: 5)
            connect_timeout: Connection timeout in seconds (default: 60)
            read_timeout: Read timeout in seconds (default: 300)
            
        Raises:
            BedrockClientError: If boto3 is not installed
            BedrockAuthenticationError: If credentials cannot be resolved
        """
        if not BOTO3_AVAILABLE:
            raise BedrockClientError(
                "boto3 is required for AWS Bedrock support. "
                "Install with: pip install boto3"
            )
        
        # Resolve region
        self.region_name = (
            region_name 
            or os.getenv("AWS_REGION") 
            or os.getenv("AWS_DEFAULT_REGION")
            or "us-east-1"
        )
        
        # Resolve profile (only if explicitly set)
        self.profile_name = profile_name or os.getenv("AWS_PROFILE")
        
        # Create boto3 session
        try:
            if self.profile_name:
                logger.info(f"Creating AWS session with profile: {self.profile_name}")
                self.session = boto3.Session(profile_name=self.profile_name)
            else:
                logger.info("Creating AWS session with default credential chain")
                self.session = boto3.Session()
        except Exception as e:
            raise BedrockAuthenticationError(
                f"Failed to create AWS session: {e}\n"
                "Ensure you have valid AWS credentials configured via:\n"
                "  - IAM role (for EC2/ECS/EKS/Lambda/SageMaker/etc.)\n"
                "  - AWS_PROFILE environment variable\n"
                "  - AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables\n"
                "  - ~/.aws/credentials file"
            ) from e
        
        # Configure boto3 client settings
        self.config = Config(
            retries={"max_attempts": max_retries, "mode": "adaptive"},
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            region_name=self.region_name,
        )
        
        # Create clients
        self._runtime_client = None
        self._bedrock_client = None
        
        # Validate credentials on initialization
        self._validate_credentials()
    
    def _validate_credentials(self) -> None:
        """
        Validate that AWS credentials can be resolved.
        
        Raises:
            BedrockAuthenticationError: If credentials cannot be resolved
        """
        try:
            # Try to get credentials to verify they exist
            credentials = self.session.get_credentials()
            if credentials is None:
                raise BedrockAuthenticationError(
                    "No AWS credentials found. Please configure credentials via:\n"
                    "  - IAM role (recommended for production)\n"
                    "  - AWS_PROFILE environment variable (for local development)\n"
                    "  - AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables\n"
                    "  - ~/.aws/credentials file"
                )
            
            # Optional: verify with STS GetCallerIdentity
            try:
                sts = self.session.client("sts", config=self.config)
                identity = sts.get_caller_identity()
                logger.info(
                    f"AWS credentials validated. Account: {identity['Account']}, "
                    f"ARN: {identity['Arn']}"
                )
            except Exception as e:
                logger.warning(f"Could not verify credentials with STS: {e}")
                # Don't fail here - credentials might still work for Bedrock
                
        except NoCredentialsError as e:
            raise BedrockAuthenticationError(
                "No AWS credentials found. Please configure credentials."
            ) from e
    
    @property
    def runtime_client(self):
        """Get or create the bedrock-runtime client."""
        if self._runtime_client is None:
            try:
                self._runtime_client = self.session.client(
                    "bedrock-runtime",
                    config=self.config,
                )
                logger.info(f"Created bedrock-runtime client in region: {self.region_name}")
            except Exception as e:
                raise BedrockClientError(
                    f"Failed to create bedrock-runtime client: {e}\n"
                    f"Region: {self.region_name}\n"
                    "Ensure the AWS Bedrock service is available in your region."
                ) from e
        return self._runtime_client
    
    @property
    def bedrock_client(self):
        """Get or create the bedrock client (for control plane operations)."""
        if self._bedrock_client is None:
            try:
                self._bedrock_client = self.session.client(
                    "bedrock",
                    config=self.config,
                )
                logger.info(f"Created bedrock client in region: {self.region_name}")
            except Exception as e:
                raise BedrockClientError(
                    f"Failed to create bedrock client: {e}"
                ) from e
        return self._bedrock_client
    
    def invoke_model(
        self,
        model_id: str,
        body: bytes,
        accept: str = "application/json",
        content_type: str = "application/json",
    ) -> Dict[str, Any]:
        """
        Invoke a Bedrock model (non-streaming).
        
        Args:
            model_id: The model ID (e.g., "anthropic.claude-3-sonnet-20240229-v1:0")
            body: The request body as bytes
            accept: The accept header (default: "application/json")
            content_type: The content type header (default: "application/json")
            
        Returns:
            Dict containing the response from Bedrock
            
        Raises:
            BedrockClientError: If the invocation fails
        """
        try:
            response = self.runtime_client.invoke_model(
                modelId=model_id,
                body=body,
                accept=accept,
                contentType=content_type,
            )
            return response
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            
            # Provide helpful error messages
            if error_code == "AccessDeniedException":
                raise BedrockClientError(
                    f"Access denied to model {model_id}. "
                    f"Ensure your IAM role/user has bedrock:InvokeModel permission "
                    f"and the model is enabled in region {self.region_name}.\n"
                    f"Error: {error_message}"
                ) from e
            elif error_code == "ResourceNotFoundException":
                raise BedrockClientError(
                    f"Model {model_id} not found in region {self.region_name}. "
                    f"Verify the model ID and ensure it's available in your region.\n"
                    f"Error: {error_message}"
                ) from e
            elif error_code == "ThrottlingException":
                raise BedrockClientError(
                    f"Request throttled for model {model_id}. "
                    f"Consider implementing exponential backoff or requesting a quota increase.\n"
                    f"Error: {error_message}"
                ) from e
            else:
                raise BedrockClientError(
                    f"Failed to invoke model {model_id}: [{error_code}] {error_message}"
                ) from e
        except (BotoCoreError, Exception) as e:
            raise BedrockClientError(
                f"Unexpected error invoking model {model_id}: {e}"
            ) from e
    
    def invoke_model_with_response_stream(
        self,
        model_id: str,
        body: bytes,
        accept: str = "application/json",
        content_type: str = "application/json",
    ) -> Iterator[Dict[str, Any]]:
        """
        Invoke a Bedrock model with streaming response.
        
        Args:
            model_id: The model ID
            body: The request body as bytes
            accept: The accept header (default: "application/json")
            content_type: The content type header (default: "application/json")
            
        Yields:
            Chunks from the streaming response
            
        Raises:
            BedrockClientError: If the invocation fails
        """
        try:
            response = self.runtime_client.invoke_model_with_response_stream(
                modelId=model_id,
                body=body,
                accept=accept,
                contentType=content_type,
            )
            
            # Yield events from the stream
            for event in response.get("body", []):
                yield event
                
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            
            if error_code == "AccessDeniedException":
                raise BedrockClientError(
                    f"Access denied to model {model_id}. "
                    f"Ensure your IAM role/user has bedrock:InvokeModelWithResponseStream permission.\n"
                    f"Error: {error_message}"
                ) from e
            else:
                raise BedrockClientError(
                    f"Failed to invoke streaming model {model_id}: [{error_code}] {error_message}"
                ) from e
        except (BotoCoreError, Exception) as e:
            raise BedrockClientError(
                f"Unexpected error invoking streaming model {model_id}: {e}"
            ) from e


# Global client manager instance (lazy initialized)
_bedrock_manager: Optional[BedrockClientManager] = None


def get_bedrock_client(
    region_name: Optional[str] = None,
    profile_name: Optional[str] = None,
    max_retries: int = 5,
) -> BedrockClientManager:
    """
    Get or create a global Bedrock client manager instance.
    
    This function provides a convenient way to get a configured Bedrock client
    without managing instances manually.
    
    Args:
        region_name: AWS region (defaults to AWS_REGION env var or us-east-1)
        profile_name: AWS profile name (defaults to AWS_PROFILE env var)
        max_retries: Maximum number of retry attempts (default: 5)
        
    Returns:
        BedrockClientManager instance
    """
    global _bedrock_manager
    
    # Create new manager if not exists or if parameters differ
    if _bedrock_manager is None:
        _bedrock_manager = BedrockClientManager(
            region_name=region_name,
            profile_name=profile_name,
            max_retries=max_retries,
        )
    
    return _bedrock_manager
