import boto3
import botocore
import copy
import json
import os
import re


def lambda_handler(event, context):
    
    notification_topic = os.environ['NOTIFICATION_TOPIC']
    notification_enabled = (notification_topic!='')
    s3_bucket = os.environ['S3_BUCKET']
    stack_name = os.environ['STACK_NAME']
    namespace = os.environ['NAMESPACE']
    
    session = boto3.session.Session()
    cw = session.client('cloudwatch')
    cfn = session.client('cloudformation')
    rds = session.client('rds')
    s3 = session.client('s3')
    
    # open base template
    with open('template.json') as f:
        template = json.loads(f.read())
    f.close()
    metric_name_mapping = {}
    for i in template['Resources']:
        if template['Resources'][i]['Properties']['MetricName'] not in metric_name_mapping:
            metric_name_mapping[template['Resources'][i]['Properties']['MetricName']] = []
        metric_name_mapping[template['Resources'][i]['Properties']['MetricName']].append(i)
            
    alarms_template = {'AWSTemplateFormatVersion': template['AWSTemplateFormatVersion'],
                       # 'Parameters': template['Parameters'],
                       'Resources': {}}
    
    # list cloudwatch metrics
    response = cw.list_metrics(Namespace=namespace)
    metrics = response['Metrics']
    while 'NextToken' in response.keys():
        response = cw.list_metrics(Namespace=namespace, NextToken=response['NextToken'])
        metrics = metrics + response['Metrics']

    # generate cloudformation template
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
                print(namespace, metric_name, 'dimensions', sorted([i['Name'] for i in dimensions]), 'don\'t match template requirement', sorted([i['Name'] for i in template['Resources'][r]['Properties']['Dimensions']]))
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
                    print(namespace, db_cluster_identifier, 'DB cluster not found')
                    continue
                except Exception as e:
                    tags = ''
                    print(e)
                    continue
            elif 'DBInstanceIdentifier' in [i['Name'] for i in m['Dimensions']]:
                db_instance_identifier = {i['Name']: i['Value'] for i in m['Dimensions']}['DBInstanceIdentifier']
                try:
                    response = rds.describe_db_instances(DBInstanceIdentifier=db_instance_identifier)
                    response = rds.list_tags_for_resource(ResourceName=response['DBInstances'][0]['DBInstanceArn'])
                    tags = {i['Key']:i['Value'] for i in response['TagList']}
                    tags = str(tags)[1:-1].replace('\'', '').replace(', ', '\n')
                except rds.exceptions.DBInstanceNotFoundFault:
                    print(namespace, db_instance_identifier, 'DB instance not found')
                    continue
                except Exception as e:
                    tags = ''
                    print(e)
                    continue
            else:
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
            print(alarm_name, 'OK')
    
    # put template into s3 (size limit 460800 bytes)
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

    # submit cloudformation template
    try:
        cfn.create_stack(StackName=stack_name, TemplateURL=s3_url)
        return {
            'statusCode': 200,
            'body': json.dumps('Successfully initiated new stack creation')
        }
    except cfn.exceptions.AlreadyExistsException:
        pass
    except Exception as e:
        print(e)

    try:
        cfn.update_stack(StackName=stack_name, TemplateURL=s3_url)
        return {
            'statusCode': 200,
            'body': json.dumps('Successfully initiated stack update')
        }
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Message'] == 'No updates are to be performed.':
            print('*** No updates are to be performed. ***')
            return {
                'statusCode': 200,
                'body': json.dumps('Successfully initiated stack update')
            }
        else:
            print(e)
    except Exception as e:
        print(e)

    return {
        'statusCode': 400,
        'body': json.dumps('Lambda function ran with error')
    }