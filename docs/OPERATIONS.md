# Operations Guide

This guide covers day-to-day operations, maintenance, and monitoring of the AWS Recommended CloudWatch Alarms Generator.

## Table of Contents

- [Daily Operations](#daily-operations)
- [Monitoring](#monitoring)
- [Maintenance](#maintenance)
- [Incident Response](#incident-response)
- [Performance Tuning](#performance-tuning)
- [Upgrades](#upgrades)

## Daily Operations

### Health Checks

Run these checks daily to ensure the system is operating correctly:

```bash
#!/bin/bash
# health-check.sh

# Check Lambda function status
echo "Checking Lambda functions..."
for func in EC2AlarmsFunction RDSAlarmsFunction ElastiCacheAlarmsFunction ContainerInsightsAlarmsFunction CWAgentAlarmsFunction; do
  status=$(aws lambda get-function --function-name $func 2>&1)
  if [ $? -eq 0 ]; then
    echo "✓ $func is active"
  else
    echo "✗ $func has issues"
  fi
done

# Check CloudFormation stacks
echo -e "\nChecking CloudFormation stacks..."
for stack in CloudWatchAlarmsEC2 CloudWatchAlarmsRDS CloudWatchAlarmsElastiCache CloudWatchAlarmsContainerInsights CloudWatchAlarmsCWAgent; do
  status=$(aws cloudformation describe-stacks --stack-name $stack --query 'Stacks[0].StackStatus' --output text 2>&1)
  if [[ $status == *"COMPLETE"* ]]; then
    echo "✓ $stack: $status"
  else
    echo "✗ $stack: $status"
  fi
done

# Check S3 bucket
echo -e "\nChecking S3 bucket..."
aws s3 ls s3://cloudwatch-alarms-generator-$(aws sts get-caller-identity --query Account --output text)-$(aws configure get region) >/dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "✓ S3 bucket is accessible"
else
  echo "✗ S3 bucket has issues"
fi

# Check recent Lambda executions
echo -e "\nChecking recent Lambda executions..."
for func in EC2AlarmsFunction RDSAlarmsFunction; do
  errors=$(aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Errors \
    --dimensions Name=FunctionName,Value=$func \
    --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 86400 \
    --statistics Sum \
    --query 'Datapoints[0].Sum' \
    --output text)
  
  if [ "$errors" == "0.0" ] || [ "$errors" == "None" ]; then
    echo "✓ $func: No errors in last 24h"
  else
    echo "⚠ $func: $errors errors in last 24h"
  fi
done
```

### Viewing Logs

```bash
# View today's logs for all functions
aws logs tail /aws/lambda/EC2AlarmsFunction --since 1d

# Follow logs in real-time
aws logs tail /aws/lambda/RDSAlarmsFunction --follow

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/EC2AlarmsFunction \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '1 day ago' +%s)000

# Export logs for analysis
aws logs create-export-task \
  --log-group-name /aws/lambda/EC2AlarmsFunction \
  --from $(date -u -d '7 days ago' +%s)000 \
  --to $(date -u +%s)000 \
  --destination logs-archive-bucket \
  --destination-prefix lambda-logs/
```

## Monitoring

### Key Metrics to Monitor

#### Lambda Function Metrics

```bash
# Invocation count
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=EC2AlarmsFunction \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Sum

# Error rate
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=EC2AlarmsFunction \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Sum

# Duration (performance)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=EC2AlarmsFunction \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Average,Maximum

# Throttles
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Throttles \
  --dimensions Name=FunctionName,Value=EC2AlarmsFunction \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Sum
```

#### Alarm Statistics

```bash
# Count alarms by state
aws cloudwatch describe-alarms \
  --query 'MetricAlarms[*].StateValue' | \
  jq -r '.[]' | sort | uniq -c

# List alarms in ALARM state
aws cloudwatch describe-alarms \
  --state-value ALARM \
  --query 'MetricAlarms[*].[AlarmName,StateReason]' \
  --output table

# Alarm state changes in last 24h
aws cloudwatch describe-alarm-history \
  --start-date $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%S) \
  --history-item-type StateUpdate \
  --max-records 100 \
  --query 'AlarmHistoryItems[*].[AlarmName,HistoryItemType,HistorySummary]' \
  --output table
```

### Setting Up Operational Alarms

Create alarms to monitor the alarm generator itself:

```bash
# Lambda error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name AlarmGenerator-HighErrorRate \
  --alarm-description "Alert when Lambda error rate exceeds threshold" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 3600 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=FunctionName,Value=EC2AlarmsFunction

# Lambda duration alarm
aws cloudwatch put-metric-alarm \
  --alarm-name AlarmGenerator-LongDuration \
  --alarm-description "Alert when Lambda execution takes too long" \
  --metric-name Duration \
  --namespace AWS/Lambda \
  --statistic Maximum \
  --period 300 \
  --threshold 45000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=FunctionName,Value=EC2AlarmsFunction

# CloudFormation stack failure alarm
aws cloudwatch put-metric-alarm \
  --alarm-name AlarmGenerator-StackFailure \
  --alarm-description "Alert on CloudFormation stack failures" \
  --metric-name StackUpdateFailure \
  --namespace AWS/CloudFormation \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1
```

### CloudWatch Dashboard

Create a dashboard for operational visibility:

```bash
cat > dashboard.json << 'EOF'
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          [ "AWS/Lambda", "Invocations", { "stat": "Sum" } ],
          [ ".", "Errors", { "stat": "Sum" } ],
          [ ".", "Throttles", { "stat": "Sum" } ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "us-east-1",
        "title": "Lambda Invocations",
        "period": 300
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          [ "AWS/Lambda", "Duration", { "stat": "Average" } ],
          [ "...", { "stat": "Maximum" } ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "us-east-1",
        "title": "Lambda Duration",
        "period": 300,
        "yAxis": {
          "left": {
            "label": "Milliseconds"
          }
        }
      }
    },
    {
      "type": "log",
      "properties": {
        "query": "SOURCE '/aws/lambda/EC2AlarmsFunction'\n| fields @timestamp, @message\n| filter @message like /ERROR/\n| sort @timestamp desc\n| limit 20",
        "region": "us-east-1",
        "title": "Recent Errors",
        "stacked": false
      }
    }
  ]
}
EOF

aws cloudwatch put-dashboard \
  --dashboard-name AlarmGeneratorOperations \
  --dashboard-body file://dashboard.json
```

## Maintenance

### Regular Maintenance Tasks

#### Weekly Tasks

```bash
#!/bin/bash
# weekly-maintenance.sh

echo "=== Weekly Maintenance ==="

# 1. Review alarm states
echo "Reviewing alarm states..."
aws cloudwatch describe-alarms --state-value ALARM --output table

# 2. Check for stale alarms (resources that no longer exist)
echo -e "\nChecking for stale alarms..."
# List all EC2 alarms
ec2_alarms=$(aws cloudwatch describe-alarms --alarm-name-prefix "EC2-" --query 'MetricAlarms[*].AlarmName' --output text)
# List all EC2 instances
ec2_instances=$(aws ec2 describe-instances --query 'Reservations[*].Instances[*].InstanceId' --output text)

# 3. Review Lambda execution metrics
echo -e "\nLambda execution summary (last 7 days)..."
for func in EC2AlarmsFunction RDSAlarmsFunction; do
  echo "Function: $func"
  aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value=$func \
    --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 604800 \
    --statistics Sum \
    --query 'Datapoints[0].Sum'
done

# 4. Check S3 bucket size
echo -e "\nS3 bucket usage..."
aws s3 ls s3://cloudwatch-alarms-generator-$(aws sts get-caller-identity --query Account --output text)-$(aws configure get region) --recursive --summarize | tail -2

# 5. Review costs
echo -e "\nEstimated costs (last 7 days)..."
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --filter file://<(echo '{
    "Dimensions": {
      "Key": "SERVICE",
      "Values": ["AWS Lambda", "Amazon CloudWatch", "AWS CloudFormation"]
    }
  }')
```

#### Monthly Tasks

```bash
#!/bin/bash
# monthly-maintenance.sh

echo "=== Monthly Maintenance ==="

# 1. Archive old logs
echo "Archiving old logs..."
for log_group in /aws/lambda/EC2AlarmsFunction /aws/lambda/RDSAlarmsFunction; do
  aws logs create-export-task \
    --log-group-name $log_group \
    --from $(date -u -d '60 days ago' +%s)000 \
    --to $(date -u -d '30 days ago' +%s)000 \
    --destination logs-archive-bucket \
    --destination-prefix monthly-archive/$(date +%Y-%m)/
done

# 2. Review and update alarm thresholds
echo -e "\nReviewing alarm thresholds..."
# Generate report of alarms that frequently change state
aws cloudwatch describe-alarm-history \
  --start-date $(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%S) \
  --history-item-type StateUpdate \
  --max-records 1000 \
  --output json | \
  jq -r '.AlarmHistoryItems | group_by(.AlarmName) | .[] | {alarm: .[0].AlarmName, count: length}' | \
  jq -s 'sort_by(.count) | reverse | .[:10]'

# 3. Clean up old CloudFormation templates from S3
echo -e "\nCleaning up old S3 objects..."
aws s3 ls s3://cloudwatch-alarms-generator-$(aws sts get-caller-identity --query Account --output text)-$(aws configure get region)/ | \
  awk '{if ($1 < "'$(date -d '90 days ago' +%Y-%m-%d)'") print $4}' | \
  xargs -I {} aws s3 rm s3://cloudwatch-alarms-generator-$(aws sts get-caller-identity --query Account --output text)-$(aws configure get region)/{}

# 4. Update documentation
echo -e "\nGenerating documentation..."
echo "Last updated: $(date)" > maintenance-report.txt
echo "Total alarms: $(aws cloudwatch describe-alarms --query 'length(MetricAlarms)')" >> maintenance-report.txt
echo "Alarms in OK state: $(aws cloudwatch describe-alarms --state-value OK --query 'length(MetricAlarms)')" >> maintenance-report.txt
echo "Alarms in ALARM state: $(aws cloudwatch describe-alarms --state-value ALARM --query 'length(MetricAlarms)')" >> maintenance-report.txt
```

### Backup Procedures

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="./backups/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

echo "Creating backup in $BACKUP_DIR..."

# 1. Backup CloudFormation template
echo "Backing up SAM template..."
cp template.yaml $BACKUP_DIR/

# 2. Backup samconfig
echo "Backing up SAM config..."
cp samconfig.toml $BACKUP_DIR/

# 3. Export all alarms
echo "Exporting alarms..."
aws cloudwatch describe-alarms > $BACKUP_DIR/alarms.json

# 4. Export CloudFormation stacks
echo "Exporting CloudFormation stacks..."
for stack in CloudWatchAlarmsEC2 CloudWatchAlarmsRDS CloudWatchAlarmsElastiCache; do
  aws cloudformation get-template --stack-name $stack > $BACKUP_DIR/$stack.json 2>/dev/null
done

# 5. Backup S3 templates
echo "Backing up S3 templates..."
aws s3 sync s3://cloudwatch-alarms-generator-$(aws sts get-caller-identity --query Account --output text)-$(aws configure get region)/ $BACKUP_DIR/s3-backup/

# 6. Export Lambda configurations
echo "Exporting Lambda configurations..."
for func in EC2AlarmsFunction RDSAlarmsFunction ElastiCacheAlarmsFunction; do
  aws lambda get-function --function-name $func > $BACKUP_DIR/$func-config.json 2>/dev/null
done

echo "Backup completed: $BACKUP_DIR"

# Compress backup
tar -czf $BACKUP_DIR.tar.gz -C ./backups $(date +%Y%m%d)
echo "Compressed backup: $BACKUP_DIR.tar.gz"
```

### Restore Procedures

```bash
#!/bin/bash
# restore.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup-file.tar.gz>"
  exit 1
fi

echo "Restoring from $BACKUP_FILE..."

# Extract backup
tar -xzf $BACKUP_FILE -C ./restore-temp/
BACKUP_DIR="./restore-temp/$(basename $BACKUP_FILE .tar.gz)"

# Deploy SAM application
echo "Deploying SAM application..."
sam deploy --template-file $BACKUP_DIR/template.yaml --config-file $BACKUP_DIR/samconfig.toml

# Wait for deployment
echo "Waiting for stack to be ready..."
aws cloudformation wait stack-create-complete --stack-name aws-cloudwatch-alarms-generator

# Restore alarms by invoking Lambda functions
echo "Triggering alarm recreation..."
aws lambda invoke --function-name EC2AlarmsFunction response.json
aws lambda invoke --function-name RDSAlarmsFunction response.json

echo "Restore completed"
```

## Incident Response

### Lambda Function Failures

#### Symptom: Function timing out

```bash
# Increase timeout
aws lambda update-function-configuration \
  --function-name EC2AlarmsFunction \
  --timeout 120

# Increase memory (also increases CPU)
aws lambda update-function-configuration \
  --function-name EC2AlarmsFunction \
  --memory-size 512
```

#### Symptom: Permission errors

```bash
# Check IAM role
aws lambda get-function-configuration \
  --function-name EC2AlarmsFunction \
  --query 'Role'

# Verify permissions
aws iam simulate-principal-policy \
  --policy-source-arn $(aws lambda get-function-configuration --function-name EC2AlarmsFunction --query 'Role' --output text) \
  --action-names cloudwatch:PutMetricAlarm cloudformation:CreateStack \
  --resource-arns "*"
```

### CloudFormation Stack Issues

#### Symptom: Stack stuck in UPDATE_ROLLBACK_FAILED

```bash
# Continue rollback
aws cloudformation continue-update-rollback \
  --stack-name CloudWatchAlarmsEC2

# If that fails, delete and recreate
aws cloudformation delete-stack --stack-name CloudWatchAlarmsEC2
aws lambda invoke --function-name EC2AlarmsFunction response.json
```

#### Symptom: Stack limit exceeded

```bash
# Check resource count
aws cloudformation describe-stack-resources \
  --stack-name CloudWatchAlarmsEC2 \
  --query 'length(StackResources)'

# If > 500, need to split into multiple stacks (modify Lambda code)
```

### S3 Bucket Issues

#### Symptom: Access denied

```bash
# Check bucket policy
aws s3api get-bucket-policy \
  --bucket cloudwatch-alarms-generator-ACCOUNT-REGION

# Verify encryption
aws s3api get-bucket-encryption \
  --bucket cloudwatch-alarms-generator-ACCOUNT-REGION
```

## Performance Tuning

### Lambda Optimization

```bash
# Enable X-Ray tracing
aws lambda update-function-configuration \
  --function-name EC2AlarmsFunction \
  --tracing-config Mode=Active

# Use provisioned concurrency for predictable performance
aws lambda put-provisioned-concurrency-config \
  --function-name EC2AlarmsFunction \
  --provisioned-concurrent-executions 2 \
  --qualifier $LATEST
```

### Cost Optimization

```bash
# Reduce schedule frequency
sam deploy --parameter-overrides \
  EventBridgeScheduleCron="cron(0 0 * * ? *)"  # Once daily instead of hourly

# Disable unused alarm types
sam deploy --parameter-overrides \
  ContainerInsightsAlarms="Disabled" \
  CWAgentAlarms="Disabled"

# Use reserved concurrency to control costs
aws lambda put-function-concurrency \
  --function-name EC2AlarmsFunction \
  --reserved-concurrent-executions 2
```

## Upgrades

### Upgrade Process

```bash
#!/bin/bash
# upgrade.sh

echo "=== Upgrading Alarm Generator ==="

# 1. Backup current state
echo "Creating backup..."
./backup.sh

# 2. Pull latest code
echo "Pulling latest code..."
git pull origin main

# 3. Review changes
echo "Reviewing changes..."
git log --oneline -10

# 4. Build new version
echo "Building application..."
sam build

# 5. Deploy with changeset preview
echo "Creating changeset..."
sam deploy --no-execute-changeset

# 6. Review changeset
echo "Please review the changeset in CloudFormation console"
read -p "Proceed with deployment? (yes/no): " confirm

if [ "$confirm" == "yes" ]; then
  # 7. Deploy
  echo "Deploying..."
  sam deploy
  
  # 8. Verify deployment
  echo "Verifying deployment..."
  ./health-check.sh
  
  echo "Upgrade completed successfully"
else
  echo "Upgrade cancelled"
fi
```

### Rollback Procedure

```bash
#!/bin/bash
# rollback.sh

echo "=== Rolling Back Alarm Generator ==="

# Get previous stack version
PREVIOUS_TEMPLATE=$(aws cloudformation list-stack-resources \
  --stack-name aws-cloudwatch-alarms-generator \
  --query 'StackResourceSummaries[?ResourceType==`AWS::CloudFormation::Stack`].PhysicalResourceId' \
  --output text)

# Initiate rollback
aws cloudformation update-stack \
  --stack-name aws-cloudwatch-alarms-generator \
  --use-previous-template

# Wait for rollback to complete
aws cloudformation wait stack-update-complete \
  --stack-name aws-cloudwatch-alarms-generator

echo "Rollback completed"
```

## Additional Resources

- [Architecture Documentation](ARCHITECTURE.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [CloudWatch Alarms Best Practices](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html)
