"""
Common utilities module for CloudWatch Alarms Generator Lambda functions.
Provides shared functionality for template processing, S3 operations, and CloudFormation stack management.
"""

import boto3
import botocore
import json

# Constants
URL_EXPIRATION_SECONDS = 3600  # S3 pre-signed URL expiration time (1 hour)
EC2_RUNNING_STATE_CODE = 16    # AWS EC2 instance state code for "running"


def load_template(template_path='template.json'):
    """
    Load and parse the CloudFormation template from a JSON file.
    
    Args:
        template_path: Path to the template JSON file
        
    Returns:
        dict: Parsed JSON template
    """
    with open(template_path) as f:
        template = json.loads(f.read())
    return template


def build_metric_name_mapping(template):
    """
    Build a mapping of metric names to CloudFormation resource names.
    
    Args:
        template: CloudFormation template dictionary
        
    Returns:
        dict: Mapping of metric names to list of resource names
    """
    metric_name_mapping = {}
    for resource_name in template['Resources']:
        metric_name = template['Resources'][resource_name]['Properties']['MetricName']
        if metric_name not in metric_name_mapping:
            metric_name_mapping[metric_name] = []
        metric_name_mapping[metric_name].append(resource_name)
    return metric_name_mapping


def initialize_alarms_template(template):
    """
    Initialize an empty CloudFormation alarms template.
    
    Args:
        template: Base CloudFormation template dictionary
        
    Returns:
        dict: Initialized alarms template with empty Resources
    """
    return {
        'AWSTemplateFormatVersion': template['AWSTemplateFormatVersion'],
        'Resources': {}
    }


def list_all_metrics(cw_client, namespace):
    """
    List all CloudWatch metrics for a given namespace, handling pagination.
    
    Args:
        cw_client: Boto3 CloudWatch client
        namespace: AWS CloudWatch namespace
        
    Returns:
        list: All metrics in the namespace
    """
    response = cw_client.list_metrics(Namespace=namespace)
    metrics = response['Metrics']
    while 'NextToken' in response:
        response = cw_client.list_metrics(Namespace=namespace, NextToken=response['NextToken'])
        metrics = metrics + response['Metrics']
    return metrics


def upload_template_to_s3(s3_client, s3_bucket, stack_name, alarms_template):
    """
    Upload CloudFormation template to S3 and generate a pre-signed URL.
    
    Args:
        s3_client: Boto3 S3 client
        s3_bucket: S3 bucket name
        stack_name: CloudFormation stack name
        alarms_template: CloudFormation template dictionary
        
    Returns:
        str: Pre-signed S3 URL for the template
        
    Raises:
        ValueError: If the template is empty (no resources)
    """
    # Validate template is not empty
    if not alarms_template['Resources']:
        raise ValueError("Template has no resources - skipping S3 upload")
    
    # Upload template to S3 (size limit 460800 bytes)
    s3_client.put_object(
        Bucket=s3_bucket,
        Key=stack_name + '.json',
        Body=json.dumps(alarms_template)
    )
    
    # Generate pre-signed URL with extended expiration to prevent CloudFormation timeout
    s3_url = s3_client.generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': s3_bucket,
            'Key': stack_name + '.json'
        },
        ExpiresIn=URL_EXPIRATION_SECONDS
    )
    
    return s3_url


def submit_cloudformation_stack(cfn_client, stack_name, s3_url):
    """
    Submit CloudFormation stack creation or update.
    
    Args:
        cfn_client: Boto3 CloudFormation client
        stack_name: CloudFormation stack name
        s3_url: S3 URL of the template
        
    Returns:
        dict: Response dictionary with statusCode and body
    """
    # Try to create stack
    try:
        cfn_client.create_stack(StackName=stack_name, TemplateURL=s3_url)
        return {
            'statusCode': 200,
            'body': json.dumps('Successfully initiated new stack creation')
        }
    except cfn_client.exceptions.AlreadyExistsException:
        pass
    except Exception as e:
        print(e)
    
    # Try to update stack
    try:
        cfn_client.update_stack(StackName=stack_name, TemplateURL=s3_url)
        return {
            'statusCode': 200,
            'body': json.dumps('Successfully initiated stack update')
        }
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Message'] == 'No updates are to be performed.':
            print('*** No updates are to be performed. ***')
            return {
                'statusCode': 200,
                'body': json.dumps('No updates are to be performed')
            }
        else:
            print(e)
    except Exception as e:
        print(e)
    
    return {
        'statusCode': 400,
        'body': json.dumps('Lambda function ran with error')
    }


def fetch_ec2_tags(ec2_client, instance_id):
    """
    Fetch tags for an EC2 instance.
    
    Args:
        ec2_client: Boto3 EC2 client
        instance_id: EC2 instance ID
        
    Returns:
        tuple: (tags_string, private_ip, is_running)
            - tags_string: Formatted tags as string
            - private_ip: Private IP address
            - is_running: Boolean indicating if instance is running
        None if instance not found or error occurs
    """
    try:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
    except Exception as e:
        print(e)
        return None
    
    if len(response['Reservations']) == 0:
        return None
    
    instance = response['Reservations'][0]['Instances'][0]
    
    # Check if instance is running
    if instance['State']['Code'] != EC2_RUNNING_STATE_CODE:
        print(f"Instance {instance_id} is not running: {instance['State']['Name']}")
        return None
    
    # Extract tags
    if 'Tags' in instance:
        tags = {i['Key']: i['Value'] for i in instance['Tags']}
        tags_string = str(tags)[1:-1].replace('\'', '').replace(', ', '\n')
    else:
        tags_string = ''
    
    private_ip = instance['PrivateIpAddress']
    
    return (tags_string, private_ip, True)
