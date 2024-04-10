import boto3
import copy
import json
import os


def lambda_handler(event, context):
    
    notification_topic = os.environ['NOTIFICATION_TOPIC']
    s3_bucket = os.environ['S3_BUCKET']
    stack_name = 'CloudWatchAlarmsEC2'
    
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
    namespace = 'AWS/EC2'
    response = cw.list_metrics(Namespace=namespace)
    metrics = response['Metrics']
    while 'NextToken' in response.keys():
        response = cw.list_metrics(Namespace=namespace, NextToken=response['NextToken'])
        metrics = metrics + response['Metrics']
    
    metrics = [x for x in metrics if x['MetricName'] in ['CPUUtilization', 'StatusCheckFailed', 'StatusCheckFailed_AttachedEBS']]
    
    # generate cloudformation template
    for m in metrics:
        metric_name = m['MetricName']
        dimensions = m['Dimensions']
        if len(dimensions) != 1:
            continue
        elif dimensions[0]['Name'] != 'InstanceId':
            continue
        else:
            instance_id = dimensions[0]['Value']
    
        t = copy.deepcopy(template['Resources'][metric_name.replace('_', '')])
        t['Properties']['AlarmName'] = t['Properties']['AlarmName'] + instance_id
        t['Properties']['Dimensions'] = dimensions
        alarms_template['Resources'][metric_name.replace('_', '')+instance_id[2:]] = t
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
