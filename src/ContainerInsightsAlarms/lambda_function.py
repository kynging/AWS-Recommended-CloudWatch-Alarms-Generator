import boto3
import copy
import json
import os
import re


def lambda_handler(event, context):
    
    notification_topic = os.environ['NOTIFICATION_TOPIC']
    s3_bucket = os.environ['S3_BUCKET']
    stack_name = 'CloudWatchAlarmsContainerInsights'
    
    session = boto3.session.Session()
    cw = session.client('cloudwatch')
    cfn = session.client('cloudformation')
    s3 = session.client('s3')
    
    # open base template
    with open('template.json') as f:
        template = json.loads(f.read())
    f.close()
    alarms_template = {'AWSTemplateFormatVersion': template['AWSTemplateFormatVersion'],
                       'Parameters': template['Parameters'],
                       'Resources': {}}
    
    # list cloudwatch metrics
    namespace = 'ContainerInsights'
    response = cw.list_metrics(Namespace=namespace)
    metrics = response['Metrics']
    while 'NextToken' in response.keys():
        response = cw.list_metrics(Namespace=namespace, NextToken=response['NextToken'])
        metrics = metrics + response['Metrics']
    
    metrics = [x for x in metrics if x['MetricName'] in ['node_cpu_utilization', 'node_filesystem_utilization', 'node_memory_utilization']]
    
    # generate cloudformation template
    for m in metrics:
        metric_name = m['MetricName']
        dimensions = m['Dimensions']
        if len(dimensions) != 3:
            continue
        else:
            instance_id = [x for x in dimensions if x['Name']=='InstanceId'][0]['Value']
    
        if metric_name == 'node_cpu_utilization':
            t = copy.deepcopy(template['Resources']['NodeCPUUtilization'])
            t['Properties']['AlarmName'] = t['Properties']['AlarmName'] + instance_id
            t['Properties']['Dimensions'] = dimensions
            resource_name = re.sub('[^0-9a-zA-Z]+', '', 'NodeCPUUtilization'+instance_id)
            alarms_template['Resources'][resource_name] = t
        if metric_name == 'node_filesystem_utilization':
            t = copy.deepcopy(template['Resources']['NodeFilesystemUtilization'])
            t['Properties']['AlarmName'] = t['Properties']['AlarmName'] + instance_id
            t['Properties']['Dimensions'] = dimensions
            resource_name = re.sub('[^0-9a-zA-Z]+', '', 'NodeFilesystemUtilization'+instance_id)
            alarms_template['Resources'][resource_name] = t
        if metric_name == 'node_memory_utilization':
            t = copy.deepcopy(template['Resources']['NodeMemoryUtilization'])
            t['Properties']['AlarmName'] = t['Properties']['AlarmName'] + instance_id
            t['Properties']['Dimensions'] = dimensions
            resource_name = re.sub('[^0-9a-zA-Z]+', '', 'NodeMemoryUtilization'+instance_id)
            alarms_template['Resources'][resource_name] = t
        print(namespace, metric_name, instance_id)
    
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
        cfn.create_stack(StackName=stack_name,
                         TemplateURL=s3_url,
                         Parameters=[{'ParameterKey': 'AlarmNotificationTopic',
                                      'ParameterValue': notification_topic}])
        return {
            'statusCode': 200,
            'body': json.dumps('Successfully initiated new stack creation')
        }
    except Exception as e:
        print(e)

    try:
        cfn.update_stack(StackName=stack_name,
                         TemplateURL=s3_url,
                         Parameters=[{'ParameterKey': 'AlarmNotificationTopic',
                                      'ParameterValue': notification_topic}])
        return {
            'statusCode': 200,
            'body': json.dumps('Successfully initiated stack update')
        }
    except Exception as e:
        print(e)
        
    return {
        'statusCode': 400,
        'body': json.dumps('Lambda function ran with error')
    }