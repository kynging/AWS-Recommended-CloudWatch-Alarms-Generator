import boto3
import copy
import json
import os
import re


def lambda_handler(event, context):
    
    notification_topic = os.environ['NOTIFICATION_TOPIC']
    s3_bucket = os.environ['S3_BUCKET']
    stack_name = 'CloudWatchAlarmsRDS'
    
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
    namespace = 'AWS/RDS'
    response = cw.list_metrics(Namespace=namespace)
    metrics = response['Metrics']
    while 'NextToken' in response.keys():
        response = cw.list_metrics(Namespace=namespace, NextToken=response['NextToken'])
        metrics = metrics + response['Metrics']
        
    metrics = [x for x in metrics if x['MetricName'] in ['CPUUtilization', 'DatabaseConnections', 'EBSByteBalance%',
                                                         'EBSIOBalance%', 'FreeableMemory', 'FreeLocalStorage',
                                                         'FreeStorageSpace', 'MaximumUsedTransactionIDs', 'ReadLatency',
                                                         'ReplicaLag', 'WriteLatency', 'DBLoad', 'AuroraVolumeBytesLeftTotal',
                                                         'AuroraBinlogReplicaLag', 'BlockedTransactions', 'BufferCacheHitRatio',
                                                         'EngineUptime', 'RollbackSegmentHistoryListLength', 'StorageNetworkThroughput']]

    # generate cloudformation template
    for m in metrics:
        metric_name = m['MetricName']
        dimensions = m['Dimensions']
        if len(dimensions) == 2:
            role = {i['Name']: i['Value'] for i in m['Dimensions']}['Role']
            db_cluster_identifier = {i['Name']: i['Value'] for i in m['Dimensions']}['DBClusterIdentifier']
            t = copy.deepcopy(template['Resources'][metric_name.replace('%', '')])
            t['Properties']['AlarmName'] = t['Properties']['AlarmName'] + role + ' DBClusterIdentifier=' + db_cluster_identifier
            t['Properties']['Dimensions'] = dimensions
            resource_name = re.sub('[^0-9a-zA-Z]+', '', metric_name + db_cluster_identifier)
            alarms_template['Resources'][resource_name] = t
            print(namespace, metric_name, role, db_cluster_identifier)
        elif len(dimensions) == 1:
            if dimensions[0]['Name'] == 'DBInstanceIdentifier':
                db_instance_identifier = dimensions[0]['Value']
                t = copy.deepcopy(template['Resources'][metric_name.replace('%', '')])
                t['Properties']['AlarmName'] = t['Properties']['AlarmName'] + db_instance_identifier
                t['Properties']['Dimensions'] = dimensions
                resource_name = re.sub('[^0-9a-zA-Z]+', '', metric_name + db_instance_identifier)
                alarms_template['Resources'][resource_name] = t
                print(namespace, metric_name, db_instance_identifier)
            elif dimensions[0]['Name'] == 'DBClusterIdentifier':
                db_cluster_identifier = dimensions[0]['Value']
                t = copy.deepcopy(template['Resources'][metric_name.replace('%', '')])
                t['Properties']['AlarmName'] = t['Properties']['AlarmName'] + db_cluster_identifier
                t['Properties']['Dimensions'] = dimensions
                resource_name = re.sub('[^0-9a-zA-Z]+', '', metric_name + db_cluster_identifier)
                alarms_template['Resources'][resource_name] = t
                print(namespace, metric_name, db_cluster_identifier)
    
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
