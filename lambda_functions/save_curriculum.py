import boto3
import json
import os
from datetime import datetime

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """커리큘럼을 S3에 저장하는 Lambda 함수"""
    
    bucket = event['bucket']
    curriculum = event['curriculum']
    title_key = event.get('titleKey', 'default-title')
    
    # 출력 파일 이름 생성
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # title_key에서 파일명 추출 (예: input/title-A-20250331.txt -> A-20250331)
    if title_key:
        file_name = os.path.basename(title_key)
        prefix = file_name.split('.')[0]
        if prefix.startswith('title-'):
            prefix = prefix[6:]  # 'title-' 제거
    else:
        prefix = 'curriculum'
    
    output_key = f"curriculum/{prefix}-{timestamp}.txt"
    
    # UTF-8로 명시적 인코딩하여 S3에 저장
    s3_client.put_object(
        Bucket=bucket,
        Key=output_key,
        Body=curriculum.encode('utf-8'),  # UTF-8로 명시적 인코딩
        ContentType='text/plain; charset=utf-8'  # 콘텐츠 타입에 문자셋 지정
    )
    
    print(f"커리큘럼이 S3에 저장되었습니다: s3://{bucket}/{output_key}")
    
    return {
        'statusCode': 200,
        'bucket': bucket,
        'outputKey': output_key,
        'message': f"커리큘럼이 S3에 저장되었습니다: {output_key}"
    } 