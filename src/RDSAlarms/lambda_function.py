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
    
    logger.info("Starting RDS alarm generation Lambda function")
    
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
    rds = session.client('rds')
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
    
    # list cloudwatch metrics
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
            
            ### RDS metrics can be at the cluster level or the instance level
            if 'DBClusterIdentifier' in [i['Name'] for i in m['Dimensions']]:
                db_cluster_identifier = {i['Name']: i['Value'] for i in m['Dimensions']}['DBClusterIdentifier']
                try:
                    response = rds.describe_db_clusters(DBClusterIdentifier=db_cluster_identifier)
                    response = rds.list_tags_for_resource(ResourceName=response['DBClusters'][0]['DBClusterArn'])
                    tags = {i['Key']:i['Value'] for i in response['TagList']}
                    tags = str(tags)[1:-1].replace('\'', '').replace(', ', '\n')
                except rds.exceptions.DBClusterNotFoundFault:
                    logger.warning(f"DB cluster not found: {db_cluster_identifier} in namespace {namespace}")
                    alarms_skipped += 1
                    continue
                except botocore.exceptions.ClientError as e:
                    logger.error(f"Failed to describe DB cluster {db_cluster_identifier}: {e.response['Error']['Message']}")
                    tags = ''
                    alarms_skipped += 1
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error getting tags for DB cluster {db_cluster_identifier}: {e}", exc_info=True)
                    tags = ''
                    alarms_skipped += 1
                    continue
            elif 'DBInstanceIdentifier' in [i['Name'] for i in m['Dimensions']]:
                db_instance_identifier = {i['Name']: i['Value'] for i in m['Dimensions']}['DBInstanceIdentifier']
                try:
                    response = rds.describe_db_instances(DBInstanceIdentifier=db_instance_identifier)
                    response = rds.list_tags_for_resource(ResourceName=response['DBInstances'][0]['DBInstanceArn'])
                    tags = {i['Key']:i['Value'] for i in response['TagList']}
                    tags = str(tags)[1:-1].replace('\'', '').replace(', ', '\n')
                except rds.exceptions.DBInstanceNotFoundFault:
                    logger.warning(f"DB instance not found: {db_instance_identifier} in namespace {namespace}")
                    alarms_skipped += 1
                    continue
                except botocore.exceptions.ClientError as e:
                    logger.error(f"Failed to describe DB instance {db_instance_identifier}: {e.response['Error']['Message']}")
                    tags = ''
                    alarms_skipped += 1
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error getting tags for DB instance {db_instance_identifier}: {e}", exc_info=True)
                    tags = ''
                    alarms_skipped += 1
                    continue
            else:
                logger.warning(f"Skipping metric {metric_name} - no DBClusterIdentifier or DBInstanceIdentifier dimension found")
                alarms_skipped += 1
                continue
             
            ### you can define your own alarm description format here
            alarm_description = '{}\n'.format(tags)
           
            if 'DBClusterIdentifier' in [i['Name'] for i in m['Dimensions']]:
                ### you can define alarm name here
                alarm_name = '{} {} DBClusterIdentifier={}'.format(namespace, metric_name, db_cluster_identifier)
                ### you can define CloudFormation resource name here
                resource_name = re.sub('[^0-9a-zA-Z]+', '', r+db_cluster_identifier)
            elif 'DBInstanceIdentifier' in [i['Name'] for i in m['Dimensions']]:
                ### you can define alarm name here
                alarm_name = '{} {} DBInstanceIdentifier={}'.format(namespace, metric_name, db_instance_identifier)
                ### you can define CloudFormation resource name here
                resource_name = re.sub('[^0-9a-zA-Z]+', '', r+db_instance_identifier)
            else:
                alarms_skipped += 1
                continue
           
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