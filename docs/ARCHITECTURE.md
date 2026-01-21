# Architecture Documentation

## System Architecture Overview

The AWS Recommended CloudWatch Alarms Generator is a serverless application that automatically creates and manages CloudWatch alarms based on AWS best practices.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AWS Account / Region                              │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      EventBridge (Scheduler)                        │ │
│  │                   Cron: 00 23 * * ? * (Daily)                       │ │
│  └─────────────┬──────────────┬──────────────┬──────────────┬─────────┘ │
│                │              │              │              │            │
│                │              │              │              │            │
│         ┌──────▼──────┐┌──────▼──────┐┌──────▼──────┐┌──────▼──────┐   │
│         │   Lambda    ││   Lambda    ││   Lambda    ││   Lambda    │   │
│         │ EC2 Alarms  ││ RDS Alarms  ││ElastiCache  ││ Container   │   │
│         │  Function   ││  Function   ││   Alarms    ││  Insights   │   │
│         │             ││             ││  Function   ││  Function   │   │
│         │ Python 3.12 ││ Python 3.12 ││ Python 3.12 ││ Python 3.12 │   │
│         └──────┬──────┘└──────┬──────┘└──────┬──────┘└──────┬──────┘   │
│                │              │              │              │            │
│                └──────────────┴──────────────┴──────────────┘            │
│                                      │                                   │
│                                      │                                   │
│         ┌────────────────────────────▼────────────────────────────┐     │
│         │              IAM Execution Role                          │     │
│         │   - CloudWatch: ListMetrics, PutMetricAlarm             │     │
│         │   - CloudFormation: Create/Update Stacks                │     │
│         │   - EC2/RDS/ElastiCache: Describe Resources             │     │
│         │   - S3: GetObject, PutObject                            │     │
│         │   - CloudWatch Logs: Write Logs                         │     │
│         └────────────────────────────┬────────────────────────────┘     │
│                                      │                                   │
│              ┌───────────────────────┼───────────────────────┐           │
│              │                       │                       │           │
│      ┌───────▼────────┐   ┌─────────▼─────────┐   ┌─────────▼────────┐ │
│      │  CloudWatch    │   │   CloudFormation  │   │      S3 Bucket   │ │
│      │    Metrics     │   │      Stacks       │   │ (CFN Templates)  │ │
│      │                │   │                   │   │                  │ │
│      │ - AWS/EC2      │   │ CloudWatchAlarms* │   │ cloudwatch-      │ │
│      │ - AWS/RDS      │   │  (5 Stacks)       │   │ alarms-generator │ │
│      │ - AWS/ElastiC..│   │                   │   │ -<account>-      │ │
│      │ - ContainerI.. │   │                   │   │ <region>         │ │
│      │ - CWAgent      │   │                   │   │                  │ │
│      └────────────────┘   └─────────┬─────────┘   └──────────────────┘ │
│                                     │                                   │
│                           ┌─────────▼──────────┐                        │
│                           │  CloudWatch Alarms │                        │
│                           │                    │                        │
│                           │ - CPUUtilization   │                        │
│                           │ - StatusCheckFailed│                        │
│                           │ - DatabaseConns    │                        │
│                           │ - Memory Usage     │                        │
│                           │ - Disk Usage       │                        │
│                           │ - And more...      │                        │
│                           └─────────┬──────────┘                        │
│                                     │                                   │
│                                     │ (Alarm State Change)              │
│                                     │                                   │
│                           ┌─────────▼──────────┐                        │
│                           │   SNS Topic        │                        │
│                           │  (Optional)        │                        │
│                           │  Notifications     │                        │
│                           └────────────────────┘                        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. EventBridge Scheduler

**Purpose**: Triggers Lambda functions on a scheduled basis

**Configuration**:
- Default Schedule: `cron(00 23 * * ? *)` (Daily at 11 PM UTC)
- Configurable via CloudFormation parameter
- Each Lambda function has its own EventBridge rule

**Flow**:
1. EventBridge evaluates cron expression
2. Triggers corresponding Lambda function
3. Lambda function executes alarm generation logic

### 2. Lambda Functions

The application consists of five Lambda functions, one for each supported namespace:

#### EC2 Alarms Function
- **Runtime**: Python 3.12
- **Memory**: 256 MB
- **Timeout**: 60 seconds
- **Namespace**: AWS/EC2
- **Metrics Monitored**:
  - CPUUtilization
  - StatusCheckFailed
  - StatusCheckFailed_AttachedEBS

#### RDS Alarms Function
- **Runtime**: Python 3.12
- **Memory**: 256 MB
- **Timeout**: 60 seconds
- **Namespace**: AWS/RDS
- **Metrics Monitored**:
  - CPUUtilization
  - DatabaseConnections
  - FreeableMemory
  - FreeStorageSpace
  - ReadLatency / WriteLatency
  - And more...

#### ElastiCache Alarms Function
- **Runtime**: Python 3.12
- **Memory**: 256 MB
- **Timeout**: 60 seconds
- **Namespace**: AWS/ElastiCache
- **Metrics Monitored**:
  - CPUUtilization
  - EngineCPUUtilization
  - DatabaseMemoryUsagePercentage
  - CurrConnections
  - ReplicationLag

#### Container Insights Alarms Function
- **Runtime**: Python 3.12
- **Memory**: 256 MB
- **Timeout**: 60 seconds
- **Namespace**: ContainerInsights
- **Metrics Monitored**:
  - node_cpu_utilization
  - node_memory_utilization
  - node_filesystem_utilization

#### CW Agent Alarms Function
- **Runtime**: Python 3.12
- **Memory**: 256 MB
- **Timeout**: 60 seconds
- **Namespace**: CWAgent
- **Metrics Monitored**:
  - mem_used_percent
  - disk_used_percent

### 3. IAM Execution Role

**Permissions**:
- **CloudWatch**:
  - `ListMetrics`: Discover available metrics
  - `PutMetricAlarm`: Create/update alarms
  - `DeleteAlarms`: Remove outdated alarms

- **CloudFormation**:
  - `ListStacks`: Check existing stacks
  - `DescribeStacks`: Get stack details
  - `CreateStack`: Create new alarm stacks
  - `UpdateStack`: Update existing stacks

- **Service-Specific**:
  - `ec2:DescribeInstances`: Get EC2 instance details
  - `rds:DescribeDBInstances`: Get RDS instance details
  - `rds:DescribeDBClusters`: Get RDS cluster details
  - `elasticache:DescribeCacheClusters`: Get ElastiCache details
  - `rds:ListTagsForResource`: Get resource tags
  - `elasticache:ListTagsForResource`: Get resource tags

- **S3**:
  - `GetObject`: Read CloudFormation templates
  - `PutObject`: Write CloudFormation templates

- **CloudWatch Logs**:
  - `CreateLogGroup`: Create log groups
  - `CreateLogStream`: Create log streams
  - `PutLogEvents`: Write logs

### 4. S3 Bucket

**Purpose**: Store CloudFormation templates for alarm creation

**Configuration**:
- **Naming**: `cloudwatch-alarms-generator-<account-id>-<region>`
- **Encryption**: AWS KMS (aws/s3)
- **Public Access**: Blocked
- **Bucket Policy**: Enforce TLS/SSL

**Contents**:
- Generated CloudFormation templates for each service
- One template per namespace
- Updated on each Lambda execution

### 5. CloudFormation Stacks

**Stack Names**:
- `CloudWatchAlarmsEC2`
- `CloudWatchAlarmsRDS`
- `CloudWatchAlarmsElastiCache`
- `CloudWatchAlarmsContainerInsights`
- `CloudWatchAlarmsCWAgent`

**Stack Purpose**:
- Manage CloudWatch alarms as infrastructure as code
- Enable version control of alarm configurations
- Support rollback capabilities
- Provide consistent alarm management

### 6. CloudWatch Alarms

**Naming Convention**: `<Namespace>-<MetricName>-<ResourceID>`

**Configuration**:
- **Evaluation Period**: Varies by metric
- **Datapoints to Alarm**: Varies by metric
- **Statistic**: Average, Maximum, or Minimum
- **Comparison Operator**: GreaterThanThreshold or LessThanThreshold
- **Actions**: SNS notification (optional)

### 7. SNS Topic (Optional)

**Purpose**: Send notifications when alarm state changes

**Configuration**:
- Configurable via CloudFormation parameter
- Can be left empty to disable notifications
- Supports email, SMS, Lambda, and other endpoints

## Execution Flow

### Initialization Flow

```
┌─────────────────────┐
│  Deploy SAM Stack   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Create Resources   │
│  - IAM Role         │
│  - S3 Bucket        │
│  - Lambda Functions │
│  - EventBridge Rules│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  First Execution    │
│  (Manual Invoke)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Alarms Created     │
└─────────────────────┘
```

### Daily Execution Flow

```
┌─────────────────────┐
│  EventBridge Timer  │
│  Triggers Lambda    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Lambda Function    │
│  Execution Starts   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  List Available     │
│  CloudWatch Metrics │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Describe Resources │
│  (EC2, RDS, etc.)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Generate CFN       │
│  Template           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Upload Template    │
│  to S3 Bucket       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Create/Update      │
│  CloudFormation     │
│  Stack              │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  CloudWatch Alarms  │
│  Created/Updated    │
└─────────────────────┘
```

## Alarm Generation Logic

### Step 1: Metric Discovery
```python
# List all available metrics for the namespace
metrics = cloudwatch.list_metrics(Namespace='AWS/EC2')
```

### Step 2: Resource Discovery
```python
# Get detailed information about resources
instances = ec2.describe_instances()
```

### Step 3: Template Generation
```python
# Load alarm template
with open('template.json', 'r') as f:
    alarm_template = json.load(f)

# Generate alarms for each resource
for resource in resources:
    alarm = copy.deepcopy(alarm_template)
    alarm['AlarmName'] = f"{namespace}-{metric}-{resource_id}"
    alarm['Dimensions'] = [{'Name': 'InstanceId', 'Value': resource_id}]
    alarms.append(alarm)
```

### Step 4: CloudFormation Submission
```python
# Create CloudFormation template
cfn_template = {
    'Resources': {
        f'Alarm{i}': alarm for i, alarm in enumerate(alarms)
    }
}

# Upload to S3
s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(cfn_template))

# Create or update stack
cloudformation.create_stack(
    StackName=stack_name,
    TemplateURL=template_url,
    Capabilities=['CAPABILITY_IAM']
)
```

## Scalability Considerations

### Lambda Concurrency
- Each Lambda function runs independently
- No concurrent execution limits set by default
- Scales automatically with AWS resources

### CloudFormation Limits
- Maximum 500 resources per stack
- If limit is exceeded, additional stacks are created
- Stack naming: `CloudWatchAlarmsEC2-1`, `CloudWatchAlarmsEC2-2`, etc.

### Performance Optimization
- CloudFormation templates cached in S3
- Only changed alarms trigger stack updates
- Parallel processing of multiple namespaces

## High Availability

### Multi-Region Support
- Deploy stack in each region independently
- Regional S3 buckets for template storage
- Regional CloudWatch alarms

### Fault Tolerance
- Lambda automatic retry on failure
- CloudFormation rollback on stack errors
- EventBridge guaranteed delivery

## Security Architecture

### Encryption
- S3 bucket encrypted with AWS KMS (aws/s3)
- Lambda environment variables encrypted
- TLS/SSL enforced for all API calls

### IAM Best Practices
- Least privilege principle
- Service-specific permissions
- Resource-level restrictions where possible

### Network Security
- Lambda runs in AWS-managed VPC
- No internet access required
- All API calls via AWS endpoints

## Monitoring and Observability

### CloudWatch Logs
- Each Lambda function has dedicated log group
- Log retention: Configurable (default: indefinite)
- Log group naming: `/aws/lambda/<function-name>`

### Metrics
- Lambda invocations
- Lambda errors
- Lambda duration
- CloudFormation stack events

### Alarms
- Lambda error rate
- Lambda throttling
- CloudFormation stack failures

## Cost Optimization

### Lambda Costs
- Pay per invocation
- 256 MB memory allocation
- 60-second timeout
- Estimated: ~$0.01 per day for typical deployment

### S3 Costs
- Minimal storage (KB range)
- Infrequent access pattern
- Estimated: <$0.01 per month

### CloudFormation
- No additional cost
- API calls covered by AWS API limits

### CloudWatch Alarms
- Standard alarm pricing applies
- ~$0.10 per alarm per month
- Cost depends on number of resources

## Disaster Recovery

### Backup Strategy
- CloudFormation templates stored in S3
- S3 versioning enabled
- CloudFormation stack templates preserved

### Recovery Procedures
1. Restore SAM stack from template.yaml
2. Re-execute Lambda functions manually
3. CloudFormation stacks recreated automatically

## Future Architecture Enhancements

### Planned Features
1. Support for additional AWS services
2. Custom alarm threshold configuration
3. Multi-account alarm management
4. Alarm grouping and tagging
5. Dashboard generation
6. Cost analysis integration

### Architectural Improvements
1. DynamoDB for state management
2. Step Functions for orchestration
3. API Gateway for manual triggers
4. SQS for reliable message processing
5. X-Ray for distributed tracing

## References

- [AWS CloudWatch Best Practices](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [CloudFormation Best Practices](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html)
