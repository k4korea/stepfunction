import boto3
import json

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """S3에서 데이터를 가져오는 Lambda 함수"""
    
    bucket = event['bucket']
    title_key = event['titleKey']
    data_key = event['dataKey']
    
    # S3에서 제목 파일 읽기
    title_response = s3_client.get_object(Bucket=bucket, Key=title_key)
    title_content = title_response['Body'].read().decode('utf-8')
    
    # S3에서 데이터 파일 읽기
    data_response = s3_client.get_object(Bucket=bucket, Key=data_key)
    data_content = data_response['Body'].read().decode('utf-8')
    
    return {
        'bucket': bucket,
        'titleKey': title_key,
        'dataKey': data_key,
        'title': title_content,
        'data': data_content
    } 