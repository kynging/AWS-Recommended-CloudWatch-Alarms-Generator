import boto3
import copy
import json
import os


def lambda_handler(event, context):
    
    notification_topic = os.environ['NOTIFICATION_TOPIC']
    s3_bucket = os.environ['S3_BUCKET']
    stack_name = 'CloudWatchAlarmsCWAgent'
    
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
    namespace = 'CWAgent'
    response = cw.list_metrics(Namespace=namespace)
    metrics = response['Metrics']
    while 'NextToken' in response.keys():
        response = cw.list_metrics(Namespace=namespace, NextToken=response['NextToken'])
        metrics = metrics + response['Metrics']
    
    metrics = [x for x in metrics if x['MetricName'] in ['disk_used_percent', 'mem_used_percent']]
    
    # generate cloudformation template
    for m in metrics:
        metric_name = m['MetricName']
        dimensions = m['Dimensions']
        instance_id = [x for x in dimensions if x['Name']=='InstanceId'][0]['Value']
        
        if metric_name == 'mem_used_percent':
            if len(dimensions) == 3:
                t = copy.deepcopy(template['Resources']['MemUsedPercent'])
                t['Properties']['AlarmName'] = t['Properties']['AlarmName'] + instance_id
                t['Properties']['Dimensions'] = dimensions
                alarms_template['Resources']['MemUsedPercent'+instance_id[2:]] = t
                print(namespace, metric_name, instance_id)
        elif metric_name == 'disk_used_percent':
            if len(dimensions) == 6:
                device = [x for x in dimensions if x['Name']=='device'][0]['Value']
                fstype = [x for x in dimensions if x['Name']=='fstype'][0]['Value']
                t = copy.deepcopy(template['Resources']['DiskUsedPercent'])
                t['Properties']['AlarmName'] = t['Properties']['AlarmName'] + instance_id + ' ' + device
                t['Properties']['Dimensions'] = dimensions
                alarms_template['Resources']['DiskUsedPercent'+instance_id[2:]+device] = t
                print(namespace, metric_name, instance_id, device)

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
    except Exception as e:
        print(e)

    try:
        cfn.update_stack(StackName=stack_name,
                         TemplateURL=s3_url,
                         Parameters=[{'ParameterKey': 'AlarmNotificationTopic',
                                      'ParameterValue': notification_topic}])
    except Exception as e:
        print(e)
        
    return {
        'statusCode': 200,
        'body': json.dumps('Success!')
    }

