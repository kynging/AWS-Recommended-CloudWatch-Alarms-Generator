# AWS-Recommended-CloudWatch-Alarms-Generator

This project looks up available metrics in your AWS accounts and compiles CloudFormation template to automatically create CloudWatch Alarms for AWS recommended alarms. Refer this link to what these alarms are: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html. Some recommended alarms do not have a recommended threshold, therefore I recommend adjusting the threshold values in the template.json file under the alarms Lambda function directory before running the lambda functions. For CWAgent metrics only instance level disk and memory usage alarms are created. 

This solution is not a complete replacement for Application Insight, which is a managed observability feature that can manage CloudWatch Alarms for you. However, you may find this solution to offer more space for customization.

To deploy this solution, search "aws-recommended-cloudwatch-alarms-generator" in AWS Serverless Application Repository (make sure you check the "Show apps that create custom IAM roles or resource policies" option when searching).

This version of the project currently only supports the following CloudWatch namespace:
- AWS/EC2
- AWS/ElastiCache (only supports Redis OSS cluster for now)
- AWS/RDS
- ContainerInsight
- CWAgent

Each lambda function in the project contains a template.json file that specifies the alarm template. The lambda function will copy/paste the alarm template and fill in some additional info to the CloudFormation template and submit the CloudFormation template to create actual alarms. 

After first creation please run the Lambda functions manually to create alamrs. Otherwise Lambda functions are by default triggered daily: cron(00 23 * * ? *) to do so. 

When CloudWatch alarm state is changed, you have the options of 1) set a forward action to SNS; 2) use EventBridge rule to detect state change and trigger next step. Since version 1.06, you can specify the SNS topic parameter to an empty string "" to choose not to set forward action to SNS.


## Major Changes since 1.0.8
- We no longer use fixed resource names, so you can now add custom metrics to the alarm template,  as long as the metric name you specify matches the metric name returned from CloudWatch.
- You can also specify multiple alarms with the same metric name prefix, with different thresholds and specifications. For example, you can create 2 CPUUtilization alarms with different thresholds.
- Lambda functions will now call respective describe service APIs and put more information into alarm description. If the specific resource is not found, the alarm creation will be skipped.
- Moved all varible declaration to read from environment variables instead of hard coded.
- If you want to change the content of alarm name and description you still need to modify the Lambda function code.
- Added some error handling for boto3 API calls.

## Default Alarms types and specification
| Namespace         | Metric Name                      | Dimensions                      | Threshold     |
|-------------------|----------------------------------|---------------------------------|---------------|
| AWS/EC2           | CPUUtilization                   | InstanceId                      | 80            |
| AWS/EC2           | StatusCheckFailed                | InstanceId                      | 1             |
| AWS/EC2           | StatusCheckFailed_AttachedEBS    | InstanceId                      | 1             |
| AWS/ElastiCache   | CPUUtilization                   | CacheClusterId,CacheNodeId      | 90            |
| AWS/ElastiCache   | CurrConnections                  | CacheClusterId,CacheNodeId      | 1000          |
| AWS/ElastiCache   | DatabaseMemoryUsagePercentage    | CacheClusterId                  | 80            |
| AWS/ElastiCache   | EngineCPUUtilization             | CacheClusterId                  | 90            |
| AWS/ElastiCache   | ReplicationLag                   | CacheClusterId                  | 1             |
| AWS/RDS           | CPUUtilization                   | DBInstanceIdentifier            | 90            |
| AWS/RDS           | DatabaseConnections              | DBInstanceIdentifier            | 1000          |
| AWS/RDS           | EBSByteBalance%                  | DBInstanceIdentifier            | 10            |
| AWS/RDS           | EBSIOBalance%                    | DBInstanceIdentifier            | 10            |
| AWS/RDS           | FreeableMemory                   | DBInstanceIdentifier            | 1073741824    |
| AWS/RDS           | FreeLocalStorage                 | DBInstanceIdentifier            | 1073741824    |
| AWS/RDS           | FreeStorageSpace                 | DBInstanceIdentifier            | 1073741824    |
| AWS/RDS           | MaximumUsedTransactionIDs        | DBInstanceIdentifier            | 1000000000    |
| AWS/RDS           | ReadLatency                      | DBInstanceIdentifier            | 1             |
| AWS/RDS           | ReplicaLag                       | Role,DBInstanceIdentifier       | 60            |
| AWS/RDS           | WriteLatency                     | DBInstanceIdentifier            | 1             |
| AWS/RDS           | DBLoad                           | DBInstanceIdentifier            | 100           |
| AWS/RDS           | AuroraVolumeBytesLeftTotal       | DBInstanceIdentifier            | 1099511627776 |
| AWS/RDS           | AuroraBinlogReplicaLag           | Role,DBInstanceIdentifier       | -1            |
| AWS/RDS           | BlockedTransactions              | DBInstanceIdentifier            | 0             |
| AWS/RDS           | BufferCacheHitRatio              | DBInstanceIdentifier            | 80            |
| AWS/RDS           | EngineUptime                     | Role,DBInstanceIdentifier       | 0             |
| AWS/RDS           | RollbackSegmentHistoryListLength | DBInstanceIdentifier            | 1000000       |
| AWS/RDS           | StorageNetworkThroughput         | Role,DBClusterIdentifier        | 1073741824    |
| ContainerInsights | node_cpu_utilization             | InstanceId,NodeName,ClusterName | 80            |
| ContainerInsights | node_filesystem_utilization      | InstanceId,NodeName,ClusterName | 80            |
| ContainerInsights | node_memory_utilization          | InstanceId,NodeName,ClusterName | 80            |
| CWAgent           | mem_used_percent                 | InstanceId,ImageId,InstanceType | 90            |
| CWAgent           | disk_used_percent                | path                            | 80            |
