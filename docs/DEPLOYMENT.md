# Deployment and Usage Guide

This guide provides comprehensive instructions for deploying and operating the AWS Recommended CloudWatch Alarms Generator.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation Methods](#installation-methods)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Prerequisites

### Required Tools

1. **AWS CLI** (version 2.x or higher)
   ```bash
   # Install AWS CLI
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
   unzip awscliv2.zip
   sudo ./aws/install
   
   # Verify installation
   aws --version
   ```

2. **AWS SAM CLI** (version 1.100.0 or higher)
   ```bash
   # Install SAM CLI
   pip install aws-sam-cli
   
   # Verify installation
   sam --version
   ```

3. **Python** (version 3.12 or higher)
   ```bash
   python3.12 --version
   ```

### AWS Account Setup

1. **AWS Account**: Active AWS account with appropriate permissions
2. **IAM Permissions**: Administrator access or specific permissions:
   - CloudFormation: Full access
   - Lambda: Full access
   - IAM: Create roles and policies
   - S3: Create and manage buckets
   - CloudWatch: Full access
   - EventBridge: Create and manage rules
   - SNS: (Optional) Topic management

3. **AWS CLI Configuration**:
   ```bash
   aws configure
   # Enter your AWS Access Key ID
   # Enter your AWS Secret Access Key
   # Enter default region (e.g., us-east-1)
   # Enter default output format (json)
   ```

## Installation Methods

### Method 1: AWS Serverless Application Repository (Recommended)

This is the easiest method for end-users who want to deploy the application without cloning the repository.

1. **Navigate to AWS SAR**:
   - Go to AWS Console → Serverless Application Repository
   - Check "Show apps that create custom IAM roles or resource policies"
   - Search for: `aws-recommended-cloudwatch-alarms-generator`

2. **Deploy Application**:
   - Click on the application
   - Configure parameters (see [Configuration](#configuration))
   - Click "Deploy"

3. **Wait for Deployment**:
   - Monitor CloudFormation stack creation
   - Typically takes 2-3 minutes

### Method 2: SAM CLI Deployment (For Developers)

Use this method for development, testing, or customization.

1. **Clone Repository**:
   ```bash
   git clone https://github.com/kynging/AWS-Recommended-CloudWatch-Alarms-Generator.git
   cd AWS-Recommended-CloudWatch-Alarms-Generator
   ```

2. **Build Application**:
   ```bash
   sam build
   ```

3. **Deploy Application**:
   ```bash
   # Interactive deployment (first time)
   sam deploy --guided
   
   # Follow prompts:
   # Stack Name: aws-cloudwatch-alarms-generator
   # AWS Region: us-east-1 (or your preferred region)
   # Parameter AlarmNotificationTopic: (leave empty or enter SNS ARN)
   # Parameter EventBridgeScheduleCron: cron(00 23 * * ? *)
   # Confirm changes before deploy: Y
   # Allow SAM CLI IAM role creation: Y
   # Disable rollback: N
   # Save arguments to configuration file: Y
   ```

4. **Subsequent Deployments**:
   ```bash
   sam deploy
   ```

### Method 3: CloudFormation Console

1. **Download Template**:
   - Download `template.yaml` from the repository
   - Download Lambda function source code

2. **Package Application**:
   ```bash
   sam package \
     --output-template-file packaged.yaml \
     --s3-bucket your-deployment-bucket
   ```

3. **Deploy via Console**:
   - Go to CloudFormation Console
   - Create Stack → Upload template file
   - Select `packaged.yaml`
   - Configure parameters
   - Create stack

## Deployment

### Quick Start Deployment

```bash
# Clone repository
git clone https://github.com/kynging/AWS-Recommended-CloudWatch-Alarms-Generator.git
cd AWS-Recommended-CloudWatch-Alarms-Generator

# Build and deploy
sam build && sam deploy --guided
```

### Environment-Specific Deployments

#### Development Environment

```bash
sam build
sam deploy --config-env dev \
  --parameter-overrides \
    AlarmNotificationTopic="" \
    EventBridgeScheduleCron="cron(0 12 * * ? *)" \
    EC2Alarms="Enabled" \
    RDSAlarms="Disabled"
```

#### Staging Environment

```bash
sam build
sam deploy --config-env staging \
  --parameter-overrides \
    AlarmNotificationTopic="arn:aws:sns:us-east-1:123456789012:staging-alarms" \
    EventBridgeScheduleCron="cron(00 23 * * ? *)"
```

#### Production Environment

```bash
sam build
sam deploy --config-env prod \
  --parameter-overrides \
    AlarmNotificationTopic="arn:aws:sns:us-east-1:123456789012:prod-alarms" \
    EventBridgeScheduleCron="cron(00 23 * * ? *)"
```

### Multi-Region Deployment

Deploy to multiple regions for comprehensive monitoring:

```bash
# US East 1
sam deploy --region us-east-1 --config-env prod-us-east-1

# US West 2
sam deploy --region us-west-2 --config-env prod-us-west-2

# EU West 1
sam deploy --region eu-west-1 --config-env prod-eu-west-1

# AP Southeast 1
sam deploy --region ap-southeast-1 --config-env prod-ap-southeast-1
```

## Configuration

### CloudFormation Parameters

#### AlarmNotificationTopic (Optional)

**Description**: SNS topic ARN to receive alarm notifications

**Format**: `arn:aws:sns:REGION:ACCOUNT_ID:TOPIC_NAME`

**Examples**:
```bash
# No notifications (default)
AlarmNotificationTopic=""

# Single topic
AlarmNotificationTopic="arn:aws:sns:us-east-1:123456789012:cloudwatch-alarms"

# Different topics per environment
# Development
AlarmNotificationTopic="arn:aws:sns:us-east-1:123456789012:dev-alarms"

# Production
AlarmNotificationTopic="arn:aws:sns:us-east-1:123456789012:prod-critical-alarms"
```

#### EventBridgeScheduleCron

**Description**: Schedule for automatic alarm generation

**Format**: `cron(Minutes Hours Day-of-month Month Day-of-week Year)`

**Examples**:
```bash
# Daily at 11 PM UTC (default)
EventBridgeScheduleCron="cron(00 23 * * ? *)"

# Every 6 hours
EventBridgeScheduleCron="cron(0 */6 * * ? *)"

# Business hours only (9 AM weekdays)
EventBridgeScheduleCron="cron(0 9 ? * MON-FRI *)"

# First day of each month
EventBridgeScheduleCron="cron(0 0 1 * ? *)"
```

#### Service-Specific Alarms (Enable/Disable)

```bash
# Enable all services (default)
ContainerInsightsAlarms="Enabled"
CWAgentAlarms="Enabled"
EC2Alarms="Enabled"
ElastiCacheAlarms="Enabled"
RDSAlarms="Enabled"

# Disable specific services
EC2Alarms="Disabled"
ElastiCacheAlarms="Disabled"
```

### Complete Configuration Example

```bash
sam deploy \
  --stack-name aws-cloudwatch-alarms-generator \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    AlarmNotificationTopic="arn:aws:sns:us-east-1:123456789012:prod-alarms" \
    EventBridgeScheduleCron="cron(00 23 * * ? *)" \
    ContainerInsightsAlarms="Enabled" \
    CWAgentAlarms="Enabled" \
    EC2Alarms="Enabled" \
    ElastiCacheAlarms="Enabled" \
    RDSAlarms="Enabled" \
  --region us-east-1 \
  --no-fail-on-empty-changeset
```

## Usage Examples

### First-Time Setup

After deployment, manually invoke Lambda functions to create initial alarms:

```bash
# Get function names
aws cloudformation describe-stacks \
  --stack-name aws-cloudwatch-alarms-generator \
  --query 'Stacks[0].Outputs[?OutputKey==`FunctionName`].OutputValue' \
  --output text

# Invoke EC2 alarms function
aws lambda invoke \
  --function-name EC2AlarmsFunction \
  --invocation-type RequestResponse \
  --log-type Tail \
  response.json

# Invoke RDS alarms function
aws lambda invoke \
  --function-name RDSAlarmsFunction \
  --invocation-type RequestResponse \
  response.json

# View response
cat response.json
```

### Verify Alarm Creation

```bash
# List all CloudWatch alarms
aws cloudwatch describe-alarms \
  --query 'MetricAlarms[*].[AlarmName,StateValue,MetricName]' \
  --output table

# List alarms for specific namespace
aws cloudwatch describe-alarms \
  --alarm-name-prefix "EC2-" \
  --query 'MetricAlarms[*].[AlarmName,StateValue,Threshold]' \
  --output table

# Get alarm details
aws cloudwatch describe-alarms \
  --alarm-names "EC2-CPUUtilization-i-1234567890abcdef0" \
  --output json
```

### Monitor Lambda Execution

```bash
# View Lambda logs
aws logs tail /aws/lambda/EC2AlarmsFunction --follow

# Get recent invocations
aws lambda list-functions \
  --query 'Functions[?starts_with(FunctionName, `EC2Alarms`)].FunctionName' \
  --output text | xargs -I {} aws lambda get-function --function-name {}

# View CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=EC2AlarmsFunction \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

### Update Alarm Configuration

To modify alarm thresholds or add new alarms, update the Lambda function code:

```bash
# Edit alarm template
vim src/EC2Alarms/template.json

# Rebuild and redeploy
sam build
sam deploy

# Manually invoke to update alarms
aws lambda invoke \
  --function-name EC2AlarmsFunction \
  --invocation-type RequestResponse \
  response.json
```

### SNS Notification Setup

#### Create SNS Topic

```bash
# Create topic
aws sns create-topic --name cloudwatch-alarms

# Subscribe email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:cloudwatch-alarms \
  --protocol email \
  --notification-endpoint your-email@example.com

# Confirm subscription (check email)
```

#### Update Stack with SNS Topic

```bash
sam deploy \
  --parameter-overrides \
    AlarmNotificationTopic="arn:aws:sns:us-east-1:123456789012:cloudwatch-alarms"
```

### Testing Alarms

#### Simulate CPU Load (EC2)

```bash
# SSH to EC2 instance
ssh -i your-key.pem ec2-user@instance-ip

# Generate CPU load
yes > /dev/null &
yes > /dev/null &

# Monitor alarm state
aws cloudwatch describe-alarms \
  --alarm-names "EC2-CPUUtilization-i-1234567890abcdef0" \
  --query 'MetricAlarms[0].StateValue'

# Stop load
killall yes
```

#### Check Alarm History

```bash
aws cloudwatch describe-alarm-history \
  --alarm-name "EC2-CPUUtilization-i-1234567890abcdef0" \
  --max-records 10 \
  --output table
```

## Troubleshooting

### Common Issues

#### 1. Lambda Function Errors

**Problem**: Lambda execution fails

**Solution**:
```bash
# Check Lambda logs
aws logs tail /aws/lambda/EC2AlarmsFunction --follow

# Check IAM permissions
aws iam get-role-policy \
  --role-name AlarmsGeneratorLambdaExecutionRole-us-east-1 \
  --policy-name AlarmsGeneratorPolicy

# Verify environment variables
aws lambda get-function-configuration \
  --function-name EC2AlarmsFunction \
  --query 'Environment.Variables'
```

#### 2. No Alarms Created

**Problem**: Lambda runs but no alarms appear

**Solution**:
```bash
# Check if resources exist
aws ec2 describe-instances --query 'Reservations[*].Instances[*].[InstanceId,State.Name]'

# Check CloudWatch metrics
aws cloudwatch list-metrics --namespace AWS/EC2

# Verify CloudFormation stack
aws cloudformation describe-stacks \
  --stack-name CloudWatchAlarmsEC2 \
  --query 'Stacks[0].StackStatus'
```

#### 3. CloudFormation Stack Failures

**Problem**: Stack creation/update fails

**Solution**:
```bash
# Get stack events
aws cloudformation describe-stack-events \
  --stack-name CloudWatchAlarmsEC2 \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'

# Check S3 template
aws s3 ls s3://cloudwatch-alarms-generator-ACCOUNT-REGION/

# View template
aws s3 cp s3://cloudwatch-alarms-generator-ACCOUNT-REGION/ec2-alarms.json -
```

#### 4. Permission Errors

**Problem**: Access denied errors

**Solution**:
```bash
# Verify IAM role
aws iam get-role --role-name AlarmsGeneratorLambdaExecutionRole-us-east-1

# Check trust relationship
aws iam get-role \
  --role-name AlarmsGeneratorLambdaExecutionRole-us-east-1 \
  --query 'Role.AssumeRolePolicyDocument'

# List attached policies
aws iam list-attached-role-policies \
  --role-name AlarmsGeneratorLambdaExecutionRole-us-east-1
```

### Debug Mode

Enable detailed logging:

```bash
# Update Lambda environment variable
aws lambda update-function-configuration \
  --function-name EC2AlarmsFunction \
  --environment Variables="{LOG_LEVEL=DEBUG,NOTIFICATION_TOPIC=arn:aws:sns:us-east-1:123456789012:alarms,S3_BUCKET=cloudwatch-alarms-generator-123456789012-us-east-1,STACK_NAME=CloudWatchAlarmsEC2,NAMESPACE=AWS/EC2}"

# Invoke and check logs
aws lambda invoke --function-name EC2AlarmsFunction response.json
aws logs tail /aws/lambda/EC2AlarmsFunction --follow
```

## Best Practices

### 1. Alarm Threshold Tuning

- Start with default thresholds
- Monitor alarm state changes for 2-4 weeks
- Adjust thresholds based on actual usage patterns
- Document threshold changes

### 2. SNS Topic Organization

```bash
# Separate topics by severity
aws sns create-topic --name cloudwatch-alarms-critical
aws sns create-topic --name cloudwatch-alarms-warning
aws sns create-topic --name cloudwatch-alarms-info

# Different topics per environment
aws sns create-topic --name dev-cloudwatch-alarms
aws sns create-topic --name staging-cloudwatch-alarms
aws sns create-topic --name prod-cloudwatch-alarms
```

### 3. Multi-Account Strategy

Deploy using AWS Organizations and StackSets:

```bash
# Create StackSet
aws cloudformation create-stack-set \
  --stack-set-name cloudwatch-alarms-generator \
  --template-body file://template.yaml \
  --parameters ParameterKey=AlarmNotificationTopic,ParameterValue="" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM

# Deploy to multiple accounts
aws cloudformation create-stack-instances \
  --stack-set-name cloudwatch-alarms-generator \
  --accounts 123456789012 210987654321 \
  --regions us-east-1 us-west-2
```

### 4. Cost Optimization

```bash
# Disable alarms for non-production
sam deploy --parameter-overrides \
  EC2Alarms="Disabled" \
  RDSAlarms="Disabled"

# Adjust schedule frequency
EventBridgeScheduleCron="cron(0 0 * * ? *)"  # Once daily

# Use composite alarms
aws cloudwatch put-composite-alarm \
  --alarm-name high-priority-alarms \
  --alarm-rule "ALARM(EC2-CPUUtilization-*) OR ALARM(RDS-CPUUtilization-*)"
```

### 5. Monitoring and Alerting

Create alarms for the alarm generator itself:

```bash
# Lambda error alarm
aws cloudwatch put-metric-alarm \
  --alarm-name lambda-errors-alarm-generator \
  --alarm-description "Alert when Lambda functions fail" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1

# S3 bucket alarm
aws cloudwatch put-metric-alarm \
  --alarm-name s3-errors-alarm-generator \
  --metric-name 4xxErrors \
  --namespace AWS/S3 \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1
```

### 6. Backup and Recovery

```bash
# Export alarm configurations
aws cloudwatch describe-alarms > alarms-backup.json

# Enable S3 versioning
aws s3api put-bucket-versioning \
  --bucket cloudwatch-alarms-generator-ACCOUNT-REGION \
  --versioning-configuration Status=Enabled

# Backup CloudFormation templates
aws s3 sync s3://cloudwatch-alarms-generator-ACCOUNT-REGION/ ./backup/
```

## Advanced Usage

### Custom Alarm Templates

Modify alarm templates in Lambda function code:

```python
# src/EC2Alarms/template.json
{
  "AlarmName": "EC2-CustomMetric-{InstanceId}",
  "MetricName": "CustomMetric",
  "Namespace": "AWS/EC2",
  "Threshold": 75,
  "ComparisonOperator": "GreaterThanThreshold",
  "EvaluationPeriods": 2,
  "Period": 300,
  "Statistic": "Average"
}
```

### Integration with Other Services

#### EventBridge Rules

```bash
# Trigger Lambda on resource creation
aws events put-rule \
  --name trigger-alarm-creation \
  --event-pattern '{"source":["aws.ec2"],"detail-type":["EC2 Instance State-change Notification"],"detail":{"state":["running"]}}'

aws events put-targets \
  --rule trigger-alarm-creation \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:123456789012:function:EC2AlarmsFunction"
```

#### CloudWatch Dashboards

```bash
# Create dashboard with alarms
aws cloudwatch put-dashboard \
  --dashboard-name alarm-generator-dashboard \
  --dashboard-body file://dashboard.json
```

## Additional Resources

- [GitHub Repository](https://github.com/kynging/AWS-Recommended-CloudWatch-Alarms-Generator)
- [AWS CloudWatch Documentation](https://docs.aws.amazon.com/cloudwatch/)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [Best Practice Alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html)

## Support

- **Issues**: [GitHub Issues](https://github.com/kynging/AWS-Recommended-CloudWatch-Alarms-Generator/issues)
- **Discussions**: [GitHub Discussions](https://github.com/kynging/AWS-Recommended-CloudWatch-Alarms-Generator/discussions)
- **Contributing**: See [CONTRIBUTING.md](../CONTRIBUTING.md)
