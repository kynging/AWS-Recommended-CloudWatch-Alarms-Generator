# AWS-Recommended-CloudWatch-Alarms-Generator

This project looks up available metrics in your AWS accounts and compiles CloudFormation template to automatically create CloudWatch Alarms for AWS recommended alarms. Refer this link to what these alarms are: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html. Some recommended alarms do not have a recommended threshold, therefore I recommend adjusting the threshold values in the template.json file under the alarms Lambda function directory before running the lambda functions. For CWAgent metrics only instance level disk and memory usage alarms are created.

This project uses Lambda function to compile CloudFormation templates for alarms and creates an S3 bucket to store these templates. Lambda functions are by default triggered daily: cron(00 23 * * ? *). All alarms created have a next step action to send notifications to a SNS topic as defined in CloudFormation parameter.

This version of the project currently only supports the following CloudWatch namespace:
- CWAgent
- ContainerInsight
- AWS/EC2
- AWS/ElastiCache
- AWS/RDS