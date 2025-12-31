#!/usr/bin/env python3
"""
Verification script for Bedrock IAM role migration.

This script checks that all the changes have been properly implemented
without requiring full dependency installation.
"""

import os
import sys
from pathlib import Path


def check_file_exists(filepath, description):
    """Check if a file exists."""
    if Path(filepath).exists():
        print(f"✓ {description}: {filepath}")
        return True
    else:
        print(f"✗ MISSING: {description}: {filepath}")
        return False


def check_file_contains(filepath, search_text, description, should_not_contain=False):
    """Check if a file contains (or doesn't contain) specific text."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            found = search_text in content
            
            if should_not_contain:
                if not found:
                    print(f"✓ {description}")
                    return True
                else:
                    print(f"✗ FAIL: {description} (found unexpected text)")
                    return False
            else:
                if found:
                    print(f"✓ {description}")
                    return True
                else:
                    print(f"✗ FAIL: {description} (text not found)")
                    return False
    except FileNotFoundError:
        print(f"✗ File not found: {filepath}")
        return False
    except Exception as e:
        print(f"✗ Error reading {filepath}: {e}")
        return False


def main():
    """Run all verification checks."""
    print("=" * 70)
    print("Biomni AWS Bedrock IAM Role Migration Verification")
    print("=" * 70)
    print()
    
    checks_passed = 0
    checks_failed = 0
    
    # Check new files created
    print("1. Checking new files created...")
    print("-" * 70)
    new_files = [
        ("biomni/bedrock_client.py", "Bedrock client manager"),
        ("docs/bedrock_setup.md", "Bedrock setup documentation"),
        ("tests/__init__.py", "Tests package"),
        ("tests/test_bedrock_client.py", "Bedrock client tests"),
        ("tests/test_llm_bedrock.py", "LLM Bedrock integration tests"),
        ("tests/README.md", "Testing documentation"),
        ("requirements-test.txt", "Test requirements"),
        ("pytest.ini", "Pytest configuration"),
        ("BEDROCK_MIGRATION.md", "Migration documentation"),
    ]
    
    for filepath, description in new_files:
        if check_file_exists(filepath, description):
            checks_passed += 1
        else:
            checks_failed += 1
    print()
    
    # Check modifications in existing files
    print("2. Checking AWS_BEARER_TOKEN_BEDROCK removed from docs...")
    print("-" * 70)
    files_to_check = [
        ("README.md", "README.md should not reference AWS_BEARER_TOKEN_BEDROCK"),
        (".env.example", ".env.example should not reference AWS_BEARER_TOKEN_BEDROCK"),
        ("docs/configuration.md", "configuration.md should not reference AWS_BEARER_TOKEN_BEDROCK"),
    ]
    
    for filepath, description in files_to_check:
        if check_file_contains(filepath, "AWS_BEARER_TOKEN_BEDROCK", description, should_not_contain=True):
            checks_passed += 1
        else:
            checks_failed += 1
    print()
    
    # Check IAM role mentions added
    print("3. Checking IAM role documentation added...")
    print("-" * 70)
    iam_checks = [
        ("README.md", "IAM role", "README mentions IAM role"),
        ("README.md", "AWS_PROFILE", "README mentions AWS_PROFILE"),
        ("docs/bedrock_setup.md", "bedrock:InvokeModel", "Bedrock setup has IAM policy"),
        (".env.example", "AWS_PROFILE", ".env.example mentions AWS_PROFILE"),
    ]
    
    for filepath, search_text, description in iam_checks:
        if check_file_contains(filepath, search_text, description):
            checks_passed += 1
        else:
            checks_failed += 1
    print()
    
    # Check config.py updates
    print("4. Checking config.py updates...")
    print("-" * 70)
    config_checks = [
        ("biomni/config.py", "aws_region", "config.py has aws_region field"),
        ("biomni/config.py", "aws_profile", "config.py has aws_profile field"),
        ("biomni/config.py", "bedrock_max_retries", "config.py has bedrock_max_retries field"),
        ("biomni/config.py", "AWS_REGION", "config.py reads AWS_REGION env var"),
    ]
    
    for filepath, search_text, description in config_checks:
        if check_file_contains(filepath, search_text, description):
            checks_passed += 1
        else:
            checks_failed += 1
    print()
    
    # Check llm.py updates
    print("5. Checking llm.py updates...")
    print("-" * 70)
    llm_checks = [
        ("biomni/llm.py", "credentials_profile_name", "llm.py uses credentials_profile_name"),
        ("biomni/llm.py", "AWS_DEFAULT_REGION", "llm.py supports AWS_DEFAULT_REGION"),
        ("biomni/llm.py", "IAM role", "llm.py has IAM role error message"),
    ]
    
    for filepath, search_text, description in llm_checks:
        if check_file_contains(filepath, search_text, description):
            checks_passed += 1
        else:
            checks_failed += 1
    print()
    
    # Check bedrock_client.py content
    print("6. Checking bedrock_client.py implementation...")
    print("-" * 70)
    bedrock_checks = [
        ("biomni/bedrock_client.py", "BedrockClientManager", "bedrock_client.py has BedrockClientManager"),
        ("biomni/bedrock_client.py", "get_bedrock_client", "bedrock_client.py has get_bedrock_client"),
        ("biomni/bedrock_client.py", "invoke_model", "bedrock_client.py has invoke_model"),
        ("biomni/bedrock_client.py", "invoke_model_with_response_stream", "bedrock_client.py supports streaming"),
        ("biomni/bedrock_client.py", "IAM role", "bedrock_client.py mentions IAM role"),
    ]
    
    for filepath, search_text, description in bedrock_checks:
        if check_file_contains(filepath, search_text, description):
            checks_passed += 1
        else:
            checks_failed += 1
    print()
    
    # Summary
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"Checks passed: {checks_passed}")
    print(f"Checks failed: {checks_failed}")
    print()
    
    if checks_failed == 0:
        print("✓ ALL CHECKS PASSED! Migration completed successfully.")
        return 0
    else:
        print(f"✗ {checks_failed} checks failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
