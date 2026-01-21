import boto3
import botocore
import copy
import json
import logging
import os
import re

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    # Configure structured logging format
    for handler in logger.handlers:
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
        ))
    
    logger.info("Starting EC2 alarm generation Lambda function")
    
    try:
        notification_topic = os.environ['NOTIFICATION_TOPIC']
        notification_enabled = (notification_topic != '')
        s3_bucket = os.environ['S3_BUCKET']
        stack_name = os.environ['STACK_NAME']
        namespace = os.environ['NAMESPACE']
        
        logger.info(f"Configuration loaded - Namespace: {namespace}, Stack: {stack_name}, "
                   f"Notifications: {'enabled' if notification_enabled else 'disabled'}")
    except KeyError as e:
        logger.error(f"Missing required environment variable: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Missing required environment variable: {e}')
        }
    
    session = boto3.session.Session()
    cw = session.client('cloudwatch')
    cfn = session.client('cloudformation')
    ec2 = session.client('ec2')
    s3 = session.client('s3')
    
    # open base template
    try:
        logger.info("Loading alarm template configuration")
        with open('template.json') as f:
            template = json.loads(f.read())
        f.close()
        
        metric_name_mapping = {}
        for i in template['Resources']:
            if template['Resources'][i]['Properties']['MetricName'] not in metric_name_mapping:
                metric_name_mapping[template['Resources'][i]['Properties']['MetricName']] = []
            metric_name_mapping[template['Resources'][i]['Properties']['MetricName']].append(i)
        
        logger.info(f"Template loaded successfully with {len(template['Resources'])} alarm definitions")
    except FileNotFoundError:
        logger.error("Template file 'template.json' not found")
        return {
            'statusCode': 500,
            'body': json.dumps('Template file not found')
        }
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse template.json: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Invalid template JSON: {e}')
        }
            
    alarms_template = {'AWSTemplateFormatVersion': template['AWSTemplateFormatVersion'],
                       # 'Parameters': template['Parameters'],
                       'Resources': {}}
                  
    # list and filter cloudwatch metrics
    try:
        logger.info(f"Fetching CloudWatch metrics from namespace: {namespace}")
        response = cw.list_metrics(Namespace=namespace)
        metrics = response['Metrics']
        while 'NextToken' in response.keys():
            response = cw.list_metrics(Namespace=namespace, NextToken=response['NextToken'])
            metrics = metrics + response['Metrics']
        logger.info(f"Retrieved {len(metrics)} metrics from CloudWatch")
    except Exception as e:
        logger.error(f"Failed to retrieve CloudWatch metrics from namespace '{namespace}': {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps(f'Failed to retrieve metrics: {str(e)}')
        }
    
    # generate cloudformation template
    logger.info("Generating CloudFormation alarms template")
    alarms_created = 0
    alarms_skipped = 0
    
    for m in metrics:
        ## check metric name
        metric_name = m['MetricName']
        if metric_name not in metric_name_mapping.keys():
            continue
        
        dimensions = m['Dimensions']
    
        ## iterate every resource for this metric name
        resources = metric_name_mapping[metric_name]
        for r in resources:
            ### check if dimensions exact match
            if not sorted([i['Name'] for i in dimensions]) == sorted([i['Name'] for i in template['Resources'][r]['Properties']['Dimensions']]):
                logger.warning(f"Dimension mismatch for {namespace} {metric_name}: "
                             f"metric dimensions {sorted([i['Name'] for i in dimensions])} "
                             f"don't match template requirement {sorted([i['Name'] for i in template['Resources'][r]['Properties']['Dimensions']])}")
                alarms_skipped += 1
                continue
            
            instance_id = [x for x in dimensions if x['Name']=='InstanceId'][0]['Value']
            try:
                response = ec2.describe_instances(InstanceIds=[instance_id])
            except botocore.exceptions.ClientError as e:
                logger.error(f"Failed to describe EC2 instance {instance_id}: {e.response['Error']['Message']}")
                alarms_skipped += 1
                continue
            except Exception as e:
                logger.error(f"Unexpected error describing EC2 instance {instance_id}: {e}", exc_info=True)
                alarms_skipped += 1
                continue
            if len(response['Reservations']) == 0:
                logger.warning(f"No reservations found for instance {instance_id}")
                alarms_skipped += 1
                continue
            
            ### check if instance is still running
            instance_state = response['Reservations'][0]['Instances'][0]['State']
            if instance_state['Code'] != 16:
                logger.info(f"Skipping instance {instance_id} - state: {instance_state['Name']} (code: {instance_state['Code']})")
                alarms_skipped += 1
                continue
            
            if 'Tags' in response['Reservations'][0]['Instances'][0]:
                tags = {i['Key']:i['Value'] for i in response['Reservations'][0]['Instances'][0]['Tags']}
                tags = str(tags)[1:-1].replace('\'', '').replace(', ', '\n')
            else:
                tags = ''
                
            ### you can define your own alarm description format here
            alarm_description = '{}\nPrivate IP: {}\n'.format(tags, response['Reservations'][0]['Instances'][0]['PrivateIpAddress'])
            ### you can define alarm name here
            alarm_name = '{} {} InstanceId={}'.format(namespace, metric_name, instance_id)
            ### you can define CloudFormation resource name here
            resource_name = re.sub('[^0-9a-zA-Z]+', '', r+instance_id)
                
            ### copy CloudFormation template from template
            t = copy.deepcopy(template['Resources'][r])
            ### set alarm name
            t['Properties']['AlarmName'] = alarm_name
            ### set dimensions value
            t['Properties']['Dimensions'] = dimensions
            ### set notification
            if notification_enabled:
                t['Properties']['ActionsEnabled'] = True
                t['Properties']['AlarmActions'] = [notification_topic]
            else:
                t['Properties']['ActionsEnabled'] = False
                t['Properties']['AlarmActions'] = []
            ### generate final template
            alarms_template['Resources'][resource_name] = t
            logger.info(f"Created alarm definition: {alarm_name}")
            alarms_created += 1
    
    logger.info(f"Alarm generation complete - Created: {alarms_created}, Skipped: {alarms_skipped}")
    
    # put template into s3 (size limit 460800 bytes)
    try:
        logger.info(f"Uploading CloudFormation template to S3: s3://{s3_bucket}/{stack_name}.json")
        s3.put_object(
            Bucket=s3_bucket, 
            Key=stack_name+'.json',
            Body=json.dumps(alarms_template)
        )
        s3_url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': s3_bucket,
                'Key': stack_name+'.json'
            },
            ExpiresIn=60
        )
        logger.info(f"Template uploaded successfully to S3")
    except Exception as e:
        logger.error(f"Failed to upload template to S3 bucket '{s3_bucket}': {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps(f'Failed to upload template to S3: {str(e)}')
        }
    
    # submit cloudformation template
    try:
        logger.info(f"Attempting to create new CloudFormation stack: {stack_name}")
        cfn.create_stack(StackName=stack_name, TemplateURL=s3_url)
        logger.info(f"Successfully initiated new stack creation for {stack_name}")
        return {
            'statusCode': 200,
            'body': json.dumps('Successfully initiated new stack creation')
        }
    except cfn.exceptions.AlreadyExistsException:
        logger.info(f"Stack {stack_name} already exists, attempting update instead")
        pass
    except botocore.exceptions.ClientError as e:
        logger.error(f"CloudFormation create stack failed for {stack_name}: {e.response['Error']['Message']}")
    except Exception as e:
        logger.error(f"Unexpected error creating stack {stack_name}: {e}", exc_info=True)

    try:
        logger.info(f"Attempting to update CloudFormation stack: {stack_name}")
        cfn.update_stack(StackName=stack_name, TemplateURL=s3_url)
        logger.info(f"Successfully initiated stack update for {stack_name}")
        return {
            'statusCode': 200,
            'body': json.dumps('Successfully initiated stack update')
        }
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Message'] == 'No updates are to be performed.':
            logger.info(f"No updates needed for stack {stack_name} - already up to date")
            return {
                'statusCode': 200,
                'body': json.dumps('Successfully initiated stack update')
            }
        else:
            logger.error(f"CloudFormation update stack failed for {stack_name}: {e.response['Error']['Message']}")
    except Exception as e:
        logger.error(f"Unexpected error updating stack {stack_name}: {e}", exc_info=True)

    logger.error(f"Lambda function completed with errors for stack {stack_name}")
    return {
        'statusCode': 400,
        'body': json.dumps('Lambda function ran with error')
    }
