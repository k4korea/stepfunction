import boto3
import json
import os
import uuid
from datetime import datetime

# AWS 서비스 클라이언트 초기화
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-agent-runtime')
sfn_client = boto3.client('stepfunctions')

# 환경 설정
BUCKET_NAME = 'curriculum-bucket-20250331'
INPUT_PREFIX = 'input/'
OUTPUT_PREFIX = 'curriculum/'
BEDROCK_MODEL_ID = 'anthropic.claude-3-sonnet-20240229-v1:0'
KNOWLEDGE_BASE_ID = 'your-knowledge-base-id'  # 여기에 실제 KB ID를 입력

def create_step_function():
    """Step Function 워크플로우 생성"""
    
    # Step Function 정의 - S3 저장 단계 추가
    definition = {
        "Comment": "커리큘럼 생성 및 S3 저장 워크플로우",
        "StartAt": "GenerateCurriculum",
        "States": {
            "GenerateCurriculum": {
                "Type": "Pass",
                "Result": {
                    "curriculum": "# 인공지능 기초 교육 커리큘럼 (2일)\n\n## 1일차: 인공지능 개요 및 머신러닝 기초\n\n### 오전 세션 (9:00 - 12:00)\n- 인공지능의 정의와 역사\n- 머신러닝의 기본 개념\n- 지도학습, 비지도학습, 강화학습 소개\n\n### 오후 세션 (13:00 - 17:00)\n- 머신러닝 알고리즘 실습\n- 데이터 전처리 및 특성 공학\n- 모델 평가 및 검증 방법\n\n## 2일차: 딥러닝과 자연어 처리\n\n### 오전 세션 (9:00 - 12:00)\n- 딥러닝 기초 및 신경망 구조\n- CNN, RNN 등 주요 아키텍처 소개\n- 딥러닝 프레임워크 소개\n\n### 오후 세션 (13:00 - 17:00)\n- 자연어 처리 기본 개념\n- 텍스트 전처리 및 임베딩\n- 트랜스포머 모델과 최신 NLP 기술 동향"
                },
                "ResultPath": "$.result",
                "Next": "SaveCurriculum"
            },
            "SaveCurriculum": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": "${SaveCurriculumLambdaArn}",
                    "Payload": {
                        "bucket": BUCKET_NAME,
                        "curriculum.$": "$.result.curriculum",
                        "titleKey.$": "$.titleKey"
                    }
                },
                "End": True
            }
        }
    }
    
    # Lambda 함수 생성 또는 ARN 가져오기
    lambda_client = boto3.client('lambda')
    
    # SaveCurriculum Lambda 함수 코드
    save_curriculum_code = """
import boto3
import json
from datetime import datetime

def lambda_handler(event, context):
    bucket = event['bucket']
    curriculum = event['curriculum']
    title_key = event.get('titleKey', 'default-title')
    
    # 파일명 생성
    file_prefix = title_key.split('/')[-1].split('.')[0].replace('title-', '')
    output_key = f"curriculum/curriculum-{file_prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
    
    # S3에 커리큘럼 저장
    s3_client = boto3.client('s3')
    s3_client.put_object(
        Bucket=bucket,
        Key=output_key,
        Body=curriculum,
        ContentType='text/plain'
    )
    
    return {
        'bucket': bucket,
        'outputKey': output_key,
        'status': 'success'
    }
"""
    
    # Lambda 함수 생성 또는 기존 함수 사용
    save_curriculum_function_name = 'save-curriculum'
    
    try:
        # 기존 Lambda 함수 확인
        lambda_client.get_function(FunctionName=save_curriculum_function_name)
        print(f"Lambda 함수 '{save_curriculum_function_name}'이(가) 이미 존재합니다.")
    except lambda_client.exceptions.ResourceNotFoundException:
        # Lambda 함수 생성
        print(f"Lambda 함수 '{save_curriculum_function_name}'을(를) 생성합니다...")
        
        # Lambda 실행 역할 생성 또는 가져오기
        iam_client = boto3.client('iam')
        lambda_role_name = 'LambdaExecutionRole'
        
        try:
            lambda_role = iam_client.get_role(RoleName=lambda_role_name)
            lambda_role_arn = lambda_role['Role']['Arn']
        except iam_client.exceptions.NoSuchEntityException:
            # 역할 생성
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole"
                    }
                ]
            }
            
            lambda_role = iam_client.create_role(
                RoleName=lambda_role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description='Lambda 함수 실행 역할'
            )
            
            # S3 접근 정책 연결
            iam_client.attach_role_policy(
                RoleName=lambda_role_name,
                PolicyArn='arn:aws:iam::aws:policy/AmazonS3FullAccess'
            )
            
            lambda_role_arn = lambda_role['Role']['Arn']
            
            # 역할 권한이 전파될 시간을 주기 위해 잠시 대기
            import time
            time.sleep(10)
        
        # Lambda 함수 생성
        with open('/tmp/lambda_function.zip', 'wb') as f:
            import io
            import zipfile
            
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as zf:
                zf.writestr('lambda_function.py', save_curriculum_code)
            
            buffer.seek(0)
            f.write(buffer.read())
        
        with open('/tmp/lambda_function.zip', 'rb') as f:
            lambda_client.create_function(
                FunctionName=save_curriculum_function_name,
                Runtime='python3.9',
                Role=lambda_role_arn,
                Handler='lambda_function.lambda_handler',
                Code={'ZipFile': f.read()},
                Description='커리큘럼을 S3에 저장하는 Lambda 함수',
                Timeout=30
            )
    
    # Lambda 함수 ARN 가져오기
    lambda_response = lambda_client.get_function(FunctionName=save_curriculum_function_name)
    save_curriculum_lambda_arn = lambda_response['Configuration']['FunctionArn']
    
    # Step Function 정의에 Lambda ARN 설정
    definition_str = json.dumps(definition)
    definition_str = definition_str.replace('${SaveCurriculumLambdaArn}', save_curriculum_lambda_arn)
    
    # Step Function 생성
    response = sfn_client.create_state_machine(
        name=f'CurriculumGenerator-WithS3-{uuid.uuid4()}',
        definition=definition_str,
        roleArn='arn:aws:iam::211125752707:role/BedrockKnowledgeBaseRole',
        type='STANDARD'
    )
    
    return response['stateMachineArn']

def create_lambda_functions():
    """워크플로우에 필요한 Lambda 함수 생성"""
    
    # 여기서는 Lambda 함수 생성 코드를 생략하고 ARN만 반환합니다.
    # 실제 구현에서는 boto3를 사용하여 Lambda 함수를 생성해야 합니다.
    
    return {
        'fetch_s3_data_arn': 'arn:aws:lambda:region:account-id:function:fetch-s3-data',
        'generate_curriculum_arn': 'arn:aws:lambda:region:account-id:function:generate-curriculum-kb',
        'save_curriculum_arn': 'arn:aws:lambda:region:account-id:function:save-curriculum'
    }

def lambda_fetch_s3_data():
    """S3에서 데이터를 가져오는 Lambda 함수 코드"""
    
    def handler(event, context):
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
    
    return handler

def lambda_generate_curriculum_with_kb():
    """Bedrock Knowledge Base를 사용하여 커리큘럼을 생성하는 Lambda 함수 코드"""
    
    def handler(event, context):
        knowledge_base_id = event['knowledgeBaseId']
        title = event['title']
        data = event['data']
        bucket = event['bucket']
        title_key = event['titleKey']
        
        # 검색 쿼리 구성 (제목과 데이터를 결합)
        retrieval_query = f"주제: {title}\n\n참고 데이터: {data}\n\n이 주제와 데이터를 바탕으로 체계적인 교육 커리큘럼을 생성해주세요."
        
        # Bedrock Knowledge Base를 사용하여 RAG 수행
        bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')
        response = bedrock_agent_runtime.retrieve_and_generate(
            knowledgeBaseId=knowledge_base_id,
            retrievalQuery=retrieval_query,
            generationConfiguration={
                "modelId": BEDROCK_MODEL_ID,
                "promptTemplate": "당신은 교육 커리큘럼 전문가입니다. 제공된 주제와 데이터를 바탕으로 체계적인 커리큘럼을 생성해주세요.\n\n{retrievalResults}\n\n주제: {title}\n\n참고 데이터: {data}"
            }
        )
        
        # 생성된 커리큘럼 추출
        curriculum = response['output']['text']
        
        return {
            'bucket': bucket,
            'titleKey': title_key,
            'curriculum': curriculum
        }
    
    return handler

def lambda_save_curriculum():
    """생성된 커리큘럼을 S3에 저장하는 Lambda 함수 코드"""
    
    def handler(event, context):
        bucket = event['bucket']
        curriculum = event['curriculum']
        title_key = event['titleKey']
        
        # 파일명 생성 (원본 제목 파일에서 파생)
        file_prefix = title_key.split('/')[-1].split('.')[0].replace('title-', '')
        output_key = f"{OUTPUT_PREFIX}curriculum-{file_prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
        
        # S3에 커리큘럼 저장
        s3_client.put_object(
            Bucket=bucket,
            Key=output_key,
            Body=curriculum,
            ContentType='text/plain'
        )
        
        return {
            'bucket': bucket,
            'outputKey': output_key,
            'status': 'success'
        }
    
    return handler

def execute_workflow(title_key, data_key, state_machine_arn):
    """워크플로우 실행"""
    
    # Step Function 실행
    execution_input = {
        'bucket': BUCKET_NAME,
        'titleKey': title_key,
        'dataKey': data_key
    }
    
    response = sfn_client.start_execution(
        stateMachineArn=state_machine_arn,
        name=f'Execution-{uuid.uuid4()}',
        input=json.dumps(execution_input)
    )
    
    execution_arn = response['executionArn']
    
    # 실행 완료 대기
    import time
    print("Step Function 실행 완료 대기 중...")
    
    while True:
        execution = sfn_client.describe_execution(executionArn=execution_arn)
        status = execution['status']
        
        if status == 'SUCCEEDED':
            print("Step Function 실행 완료!")
            
            # 결과 가져오기
            output = json.loads(execution['output'])
            curriculum = output.get('result', {}).get('curriculum', '')
            
            # S3에 저장
            file_prefix = title_key.split('/')[-1].split('.')[0].replace('title-', '')
            output_key = f"{OUTPUT_PREFIX}curriculum-{file_prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
            
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=output_key,
                Body=curriculum,
                ContentType='text/plain'
            )
            
            print(f"커리큘럼이 S3에 저장되었습니다: s3://{BUCKET_NAME}/{output_key}")
            break
        elif status in ['FAILED', 'TIMED_OUT', 'ABORTED']:
            print(f"Step Function 실행 실패: {status}")
            break
        
        print(f"현재 상태: {status}. 5초 후 다시 확인...")
        time.sleep(5)
    
    return execution_arn

def save_to_s3(curriculum, title_key):
    """커리큘럼을 S3에 저장"""
    
    # 파일명 생성
    file_prefix = title_key.split('/')[-1].split('.')[0].replace('title-', '')
    output_key = f"{OUTPUT_PREFIX}curriculum-{file_prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
    
    # S3에 저장
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=output_key,
        Body=curriculum,
        ContentType='text/plain'
    )
    
    return output_key

def main():
    """메인 함수"""
    
    # Step Function 생성 후 ARN 사용
    state_machine_arn = create_step_function()
    print(f"생성된 Step Function ARN: {state_machine_arn}")
    
    # 워크플로우 실행 예시
    title_key = f"{INPUT_PREFIX}title-A-20250331.txt"
    data_key = f"{INPUT_PREFIX}data-A-20250331.txt"
    execution_arn = execute_workflow(title_key, data_key, state_machine_arn)
    print(f"실행된 워크플로우 ARN: {execution_arn}")
    
    # 실행 결과 가져오기
    execution = sfn_client.describe_execution(executionArn=execution_arn)
    if execution['status'] == 'SUCCEEDED':
        output = json.loads(execution['output'])
        curriculum = output.get('curriculum', '')
        
        # S3에 저장
        output_key = save_to_s3(curriculum, title_key)
        print(f"커리큘럼이 S3에 저장되었습니다: s3://{BUCKET_NAME}/{output_key}")

if __name__ == "__main__":
    main() 