import boto3
import copy
import json
import os
import re

# Import common utilities from Lambda Layer
from common import (
    load_template,
    build_metric_name_mapping,
    initialize_alarms_template,
    list_all_metrics,
    upload_template_to_s3,
    submit_cloudformation_stack,
    fetch_ec2_tags
)


def lambda_handler(event, context):
    
    notification_topic = os.environ['NOTIFICATION_TOPIC']
    notification_enabled = (notification_topic != '')
    s3_bucket = os.environ['S3_BUCKET']
    stack_name = os.environ['STACK_NAME']
    namespace = os.environ['NAMESPACE']
    
    session = boto3.session.Session()
    cw = session.client('cloudwatch')
    cfn = session.client('cloudformation')
    ec2 = session.client('ec2')
    s3 = session.client('s3')
    
    # Load base template and build metric mapping
    template = load_template('template.json')
    metric_name_mapping = build_metric_name_mapping(template)
    alarms_template = initialize_alarms_template(template)

    # List all CloudWatch metrics
    metrics = list_all_metrics(cw, namespace)
    
    # Generate CloudFormation template
    for m in metrics:
        # Check metric name
        metric_name = m['MetricName']
        if metric_name not in metric_name_mapping.keys():
            continue
        
        dimensions = m['Dimensions']
        # Iterate every resource for this metric name
        resources = metric_name_mapping[metric_name]
        for r in resources:
            # Check if dimensions exact match
            if not sorted([i['Name'] for i in dimensions]) == sorted([i['Name'] for i in template['Resources'][r]['Properties']['Dimensions']]):
                print(namespace, metric_name, 'dimensions', sorted([i['Name'] for i in dimensions]), 'don\'t match template requirement', sorted([i['Name'] for i in template['Resources'][r]['Properties']['Dimensions']]))
                continue
            
            instance_id = [x for x in dimensions if x['Name'] == 'InstanceId'][0]['Value']
            
            # Fetch EC2 instance information and tags
            ec2_info = fetch_ec2_tags(ec2, instance_id)
            if ec2_info is None:
                continue
            
            tags, private_ip, is_running = ec2_info
            
            # Define alarm description with tags and private IP
            alarm_description = '{}\nPrivate IP: {}\n'.format(tags, private_ip)
            # Define alarm name
            alarm_name = '{} {} InstanceId={}'.format(namespace, metric_name, instance_id)
            # Define CloudFormation resource name
            resource_name = re.sub('[^0-9a-zA-Z]+', '', r + instance_id)
            
            # Special check for disk used percent to filter out temporary filesystems
            if metric_name == 'disk_used_percent':
                device = [x for x in dimensions if x['Name'] == 'device'][0]['Value']
                # Skip temporary filesystems
                if device == 'tmpfs' or device == 'devtmpfs':
                    continue
                fstype = [x for x in dimensions if x['Name'] == 'fstype'][0]['Value']
                # Only monitor xfs filesystems
                if fstype != 'xfs':
                    continue
                alarm_name += ' devise={}'.format(device)
                resource_name += device
                
            # Copy CloudFormation template from template
            t = copy.deepcopy(template['Resources'][r])
            # Set alarm name
            t['Properties']['AlarmName'] = alarm_name
            # Set alarm description
            t['Properties']['AlarmDescription'] = alarm_description
            # Set dimensions value
            t['Properties']['Dimensions'] = dimensions
            # Set notification
            if notification_enabled:
                t['Properties']['ActionsEnabled'] = True
                t['Properties']['AlarmActions'] = [notification_topic]
            else:
                t['Properties']['ActionsEnabled'] = False
                t['Properties']['AlarmActions'] = []
            # Generate final template
            alarms_template['Resources'][resource_name] = t
            print(alarm_name, 'OK')

    # Upload template to S3 and submit CloudFormation stack
    try:
        s3_url = upload_template_to_s3(s3, s3_bucket, stack_name, alarms_template)
        return submit_cloudformation_stack(cfn, stack_name, s3_url)
    except ValueError as e:
        # Empty template - no alarms to create
        print(str(e))
        return {
            'statusCode': 200,
            'body': json.dumps('No alarms match criteria - skipped template upload')
        }
    except Exception as e:
        print(e)
        return {
            'statusCode': 400,
            'body': json.dumps('Lambda function ran with error')
        }
