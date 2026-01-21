# Contributing to AWS Recommended CloudWatch Alarms Generator

Thank you for your interest in contributing to the AWS Recommended CloudWatch Alarms Generator! This document provides guidelines and instructions for contributing to this project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment Setup](#development-environment-setup)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors.

## Getting Started

### Prerequisites

- Python 3.12 or higher
- AWS SAM CLI
- AWS CLI configured with appropriate credentials
- Git
- A GitHub account

### Finding Issues to Work On

- Check the [Issues](https://github.com/kynging/AWS-Recommended-CloudWatch-Alarms-Generator/issues) page
- Look for issues labeled `good first issue` or `help wanted`
- Comment on the issue to express your interest before starting work

## Development Environment Setup

1. **Fork and Clone the Repository**

   ```bash
   # Fork the repository on GitHub, then clone your fork
   git clone https://github.com/YOUR-USERNAME/AWS-Recommended-CloudWatch-Alarms-Generator.git
   cd AWS-Recommended-CloudWatch-Alarms-Generator
   ```

2. **Set Up Python Virtual Environment**

   ```bash
   # Create virtual environment
   python3.12 -m venv venv
   
   # Activate virtual environment
   # On Linux/macOS:
   source venv/bin/activate
   # On Windows:
   venv\Scripts\activate
   ```

3. **Install Dependencies**

   ```bash
   # Install development dependencies
   pip install --upgrade pip
   pip install -r requirements-dev.txt
   ```

4. **Install Pre-commit Hooks**

   ```bash
   pre-commit install
   ```

5. **Verify SAM CLI Installation**

   ```bash
   sam --version
   ```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/` - New features
- `bugfix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions or modifications

### 2. Make Your Changes

- Follow the [Coding Standards](#coding-standards)
- Write or update tests as needed
- Update documentation if you're changing functionality

### 3. Run Tests Locally

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_lambda_functions.py

# Run with coverage
pytest --cov=src --cov-report=html

# Run linting
black src/ tests/
isort src/ tests/
flake8 src/ tests/
```

### 4. Validate SAM Template

```bash
# Validate template syntax
sam validate --lint

# Build the application
sam build

# Test locally (if applicable)
sam local invoke EC2AlarmsFunction
```

### 5. Commit Your Changes

```bash
git add .
git commit -m "feat: add support for new alarm type"
```

**Commit Message Format:**

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Test additions or changes
- `chore:` - Maintenance tasks

Examples:
```
feat: add SNS notification support for ElastiCache alarms
fix: correct threshold value for RDS CPU utilization
docs: update deployment instructions in README
test: add unit tests for EC2 alarms function
```

## Coding Standards

### Python Style Guide

We follow PEP 8 with some modifications:

- **Line Length**: Maximum 100 characters
- **Formatting**: Use Black for code formatting
- **Import Sorting**: Use isort with Black profile
- **Linting**: Code must pass flake8 checks

### Code Organization

```python
# Standard library imports
import json
import os
import re

# Third-party imports
import boto3
import botocore

# Local imports
from src.utils import helper_function
```

### Naming Conventions

- **Functions**: `lowercase_with_underscores`
- **Variables**: `lowercase_with_underscores`
- **Constants**: `UPPERCASE_WITH_UNDERSCORES`
- **Classes**: `PascalCase`
- **Private methods**: `_leading_underscore`

### Documentation

Add docstrings to all functions and classes:

```python
def create_alarm(resource_id: str, metric_name: str, threshold: float) -> dict:
    """
    Create a CloudWatch alarm for the specified resource.
    
    Args:
        resource_id: The AWS resource identifier
        metric_name: The CloudWatch metric name
        threshold: The alarm threshold value
    
    Returns:
        dict: CloudFormation alarm resource definition
    
    Raises:
        ValueError: If resource_id is invalid
    """
    # Implementation
```

### Error Handling

Always handle exceptions appropriately:

```python
try:
    response = client.describe_instances()
except botocore.exceptions.ClientError as e:
    print(f"Error describing instances: {e}")
    raise
```

## Testing Guidelines

### Test Structure

- Place unit tests in `tests/unit/`
- Use descriptive test names: `test_<function>_<scenario>_<expected_result>`
- Use pytest fixtures for common setup

### Writing Tests

```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_cloudwatch_client():
    """Create a mock CloudWatch client."""
    return Mock()

def test_create_alarm_with_valid_input(mock_cloudwatch_client):
    """Test alarm creation with valid input parameters."""
    # Arrange
    resource_id = "i-1234567890abcdef0"
    
    # Act
    result = create_alarm(resource_id, "CPUUtilization", 80.0)
    
    # Assert
    assert result["AlarmName"] == f"EC2-CPUUtilization-{resource_id}"
    assert result["Threshold"] == 80.0
```

### Test Coverage

- Aim for at least 80% code coverage
- All new features must include tests
- Bug fixes should include regression tests

### Running Tests

```bash
# Run all tests
pytest

# Run with markers
pytest -m unit          # Run only unit tests
pytest -m integration   # Run only integration tests

# Run specific test
pytest tests/unit/test_lambda_functions.py::TestEC2AlarmsFunction::test_create_alarm

# Generate coverage report
pytest --cov=src --cov-report=html
```

## Submitting Changes

### Pull Request Process

1. **Update Documentation**
   - Update README.md if needed
   - Add or update docstrings
   - Update CHANGELOG.md (if applicable)

2. **Ensure All Tests Pass**
   ```bash
   pytest
   sam validate
   sam build
   ```

3. **Push to Your Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

4. **Create Pull Request**
   - Go to the original repository on GitHub
   - Click "New Pull Request"
   - Select your fork and branch
   - Fill out the PR template with:
     - Description of changes
     - Related issue number
     - Testing performed
     - Screenshots (if applicable)

5. **Address Review Comments**
   - Respond to all review comments
   - Make requested changes
   - Push updates to the same branch

### Pull Request Guidelines

- **Title**: Clear and descriptive (e.g., "Add support for Aurora Serverless alarms")
- **Description**: 
  - What changes were made
  - Why these changes were necessary
  - How to test the changes
  - Link to related issues
- **Size**: Keep PRs focused and reasonably sized
- **Tests**: Include appropriate test coverage
- **Documentation**: Update relevant documentation

### PR Checklist

Before submitting, ensure:

- [ ] Code follows the project's coding standards
- [ ] All tests pass locally
- [ ] New tests have been added for new functionality
- [ ] Documentation has been updated
- [ ] Commit messages follow conventional commits format
- [ ] Pre-commit hooks pass
- [ ] SAM template validates successfully
- [ ] No secrets or credentials are committed

## Development Tips

### Local Testing with SAM

```bash
# Build the application
sam build

# Invoke a function locally
sam local invoke EC2AlarmsFunction --event events/test-event.json

# Start API locally (if applicable)
sam local start-api
```

### Debugging

```bash
# Run with debug logging
pytest -v -s

# Use Python debugger
import ipdb; ipdb.set_trace()
```

### Environment Variables for Testing

Create a `.env.test` file for local testing:

```bash
NOTIFICATION_TOPIC=arn:aws:sns:us-east-1:123456789012:test-topic
S3_BUCKET=test-bucket
STACK_NAME=TestStack
NAMESPACE=AWS/EC2
```

## Release Process

Releases are managed by project maintainers:

1. Update version in `template.yaml` (SemanticVersion)
2. Update CHANGELOG.md
3. Create a release branch: `release/vX.Y.Z`
4. Commit with message: `release: vX.Y.Z`
5. Create and push tag: `git tag vX.Y.Z && git push --tags`
6. Merge to main branch
7. GitHub Actions will automatically deploy to production and publish to SAR

## Getting Help

- **Questions**: Open a [Discussion](https://github.com/kynging/AWS-Recommended-CloudWatch-Alarms-Generator/discussions)
- **Bugs**: Open an [Issue](https://github.com/kynging/AWS-Recommended-CloudWatch-Alarms-Generator/issues)
- **Documentation**: Check the [README](README.md) and [Wiki](https://github.com/kynging/AWS-Recommended-CloudWatch-Alarms-Generator/wiki)

## Additional Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [CloudWatch Alarms Best Practices](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html)
- [Python Best Practices](https://docs.python-guide.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)

Thank you for contributing! 🎉
