import boto3
import json
import os
import uuid
import time
from datetime import datetime
from lambda_functions.lambda_make import create_lambda_function, LambdaFunctionManager, add_bedrock_permissions_to_role
from create_bedrock_role import create_bedrock_role_functions, get_knowledge_base_id, create_step_function_role

# AWS 서비스 클라이언트 초기화
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-agent-runtime')
sfn_client = boto3.client('stepfunctions')

# 환경 설정
BUCKET_NAME = 'curriculum-bucket-20250331'
INPUT_PREFIX = 'input/'
OUTPUT_PREFIX = 'curriculum/'
BEDROCK_MODEL_ID = 'amazon.titan-text-express-v1'  # 기본 모델을 Titan으로 변경
STEP_FUNCTION_ROLE_ARN = None  # 역할 ARN을 저장할 변수

def create_bedrock_resources():
    """Bedrock Knowledge Base 리소스 생성"""
    
    try:
        # 기존 Knowledge Base ID 확인
        kb_id = get_knowledge_base_id('curriculum-knowledge-base')
        
        if kb_id:
            print(f"기존 Knowledge Base ID: {kb_id}")
        else:
            # Knowledge Base가 없으면 생성 시도
            print("Knowledge Base를 생성합니다...")
            try:
                kb_id = create_bedrock_role_functions()
                print(f"새로 생성된 Knowledge Base ID: {kb_id}")
            except Exception as kb_err:
                print(f"Knowledge Base 생성 실패: {str(kb_err)}")
                print("Knowledge Base 없이 계속 진행합니다.")
                kb_id = None
        
        return kb_id
    except Exception as e:
        print(f"Bedrock 리소스 확인 중 오류 발생: {str(e)}")
        print("Knowledge Base 없이 계속 진행합니다.")
        return None

def create_lambda_functions():
    """필요한 모든 Lambda 함수 생성"""
    
    # Lambda 실행 역할에 Bedrock 권한 추가
    print("Lambda 실행 역할에 Bedrock 권한 추가 중...")
    add_bedrock_permissions_to_role()
    
    # 필요한 Lambda 함수 목록
    lambda_list = {
        'fetch-s3-data': os.path.join(os.path.dirname(__file__), 'lambda_functions/fetch_s3_data.py'),
        'generate-curriculum-kb': os.path.join(os.path.dirname(__file__), 'lambda_functions/generate_curriculum_kb.py'),
        'save-curriculum': os.path.join(os.path.dirname(__file__), 'lambda_functions/save_curriculum.py'),
    }
    
    # Lambda 함수 생성 또는 업데이트
    manager = LambdaFunctionManager()
    lambda_arns = manager.create_or_update_functions(lambda_list)
    
    print("Lambda 함수 생성/업데이트 완료:")
    for name, arn in lambda_arns.items():
        print(f"  {name}: {arn}")
    
    return lambda_arns

def create_step_function(title_key=None, knowledge_base_id=None):
    """Step Function 워크플로우 생성"""
    
    global STEP_FUNCTION_ROLE_ARN
    
    # Step Function 실행 역할 생성 또는 가져오기
    if not STEP_FUNCTION_ROLE_ARN:
        STEP_FUNCTION_ROLE_ARN = create_step_function_role()
    
    # Lambda 함수 ARN 가져오기
    lambda_arns = create_lambda_functions()
    
    # Knowledge Base ID 확인
    if not knowledge_base_id:
        knowledge_base_id = create_bedrock_resources()
    
    # Step Function 정의 - 전체 워크플로우
    definition = {
        "Comment": "커리큘럼 생성 및 S3 저장 워크플로우",
        "StartAt": "FetchS3Data",
        "States": {
            "FetchS3Data": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": lambda_arns['fetch-s3-data'],
                    "Payload": {
                        "bucket": BUCKET_NAME,
                        "titleKey.$": "$.titleKey",
                        "dataKey.$": "$.dataKey"
                    }
                },
                "ResultPath": "$.fetchResult",
                "Next": "GenerateCurriculum"
            },
            "GenerateCurriculum": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": lambda_arns['generate-curriculum-kb'],
                    "Payload": {
                        "bucket": BUCKET_NAME,
                        "titleKey.$": "$.titleKey",
                        "title.$": "$.fetchResult.Payload.title",
                        "data.$": "$.fetchResult.Payload.data",
                        "modelId": BEDROCK_MODEL_ID
                    }
                },
                "ResultPath": "$.generateResult",
                "Next": "SaveCurriculum"
            },
            "SaveCurriculum": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": lambda_arns['save-curriculum'],
                    "Payload": {
                        "bucket": BUCKET_NAME,
                        "curriculum.$": "$.generateResult.Payload.curriculum",
                        "titleKey.$": "$.titleKey"
                    }
                },
                "ResultPath": "$.saveResult",
                "End": True
            }
        }
    }
    
    # Knowledge Base ID가 있으면 추가
    if knowledge_base_id:
        definition["States"]["GenerateCurriculum"]["Parameters"]["Payload"]["knowledgeBaseId"] = knowledge_base_id
    
    # Step Function 이름 생성
    if title_key:
        # title_key에서 파일명 추출 (예: input/title-A-20250331.txt -> A-20250331)
        file_name = os.path.basename(title_key)
        prefix = file_name.split('.')[0]
        if prefix.startswith('title-'):
            prefix = prefix[6:]  # 'title-' 제거
        state_machine_name = f'CurriculumGenerator-{prefix}'
    else:
        # 기본 이름 사용
        state_machine_name = f'CurriculumGenerator-{uuid.uuid4()}'
    
    # 기존 Step Function 확인
    try:
        # 이름으로 Step Function 찾기
        existing_state_machines = sfn_client.list_state_machines()
        for machine in existing_state_machines['stateMachines']:
            if machine['name'] == state_machine_name:
                # 기존 Step Function 업데이트
                print(f"기존 Step Function '{state_machine_name}' 업데이트 중...")
                response = sfn_client.update_state_machine(
                    stateMachineArn=machine['stateMachineArn'],
                    definition=json.dumps(definition),
                    roleArn=STEP_FUNCTION_ROLE_ARN  # 새 역할 ARN 사용
                )
                return machine['stateMachineArn']
    except Exception as e:
        print(f"Step Function 확인 중 오류 발생: {str(e)}")
    
    # 새 Step Function 생성
    print(f"새 Step Function '{state_machine_name}' 생성 중...")
    response = sfn_client.create_state_machine(
        name=state_machine_name,
        definition=json.dumps(definition),
        roleArn=STEP_FUNCTION_ROLE_ARN,  # 새 역할 ARN 사용
        type='STANDARD'
    )
    
    return response['stateMachineArn']

def execute_workflow(title_key, data_key, state_machine_arn):
    """워크플로우 실행"""
    
    # Step Function 실행
    execution_input = {
        'bucket': BUCKET_NAME,
        'titleKey': title_key,
        'dataKey': data_key
    }
    
    # 실행 이름 생성 (title_key에서 파생)
    file_name = os.path.basename(title_key)
    prefix = file_name.split('.')[0]
    if prefix.startswith('title-'):
        prefix = prefix[6:]  # 'title-' 제거
    
    execution_name = f'Execution-{prefix}-{datetime.now().strftime("%Y%m%d%H%M%S")}'
    
    response = sfn_client.start_execution(
        stateMachineArn=state_machine_arn,
        name=execution_name,
        input=json.dumps(execution_input)
    )
    
    execution_arn = response['executionArn']
    print(f"Step Function 실행 시작: {execution_name}")
    print(f"실행 ARN: {execution_arn}")
    
    # 실행 완료 대기
    print("Step Function 실행 완료 대기 중...")
    
    while True:
        execution = sfn_client.describe_execution(executionArn=execution_arn)
        status = execution['status']
        
        if status == 'SUCCEEDED':
            print("Step Function 실행 완료!")
            output = json.loads(execution['output'])
            save_result = output.get('saveResult', {}).get('Payload', {})
            output_key = save_result.get('outputKey', '')
            
            if output_key:
                print(f"커리큘럼이 S3에 저장되었습니다: s3://{BUCKET_NAME}/{output_key}")
                
                # 저장된 파일 내용 출력 (선택 사항)
                try:
                    s3_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=output_key)
                    curriculum_content = s3_response['Body'].read().decode('utf-8')
                    print("\n=== 생성된 커리큘럼 ===")
                    print(curriculum_content[:500] + "..." if len(curriculum_content) > 500 else curriculum_content)
                    print("=== 커리큘럼 끝 ===\n")
                except Exception as e:
                    print(f"저장된 파일 읽기 실패: {str(e)}")
            else:
                print("저장된 파일 정보를 찾을 수 없습니다.")
            
            break
        elif status in ['FAILED', 'TIMED_OUT', 'ABORTED']:
            print(f"Step Function 실행 실패: {status}")
            if 'error' in execution and 'cause' in execution:
                print(f"오류: {execution['error']}")
                print(f"원인: {execution['cause']}")
            break
        
        print(f"현재 상태: {status}. 5초 후 다시 확인...")
        time.sleep(5)
    
    return execution_arn

def main():
    """메인 함수"""
    
    print("=== 커리큘럼 생성 워크플로우 시작 ===")
    
    try:
        # 기본값 초기화
        title_key = f"{INPUT_PREFIX}title-천문학-20250401.txt"
        data_key = f"{INPUT_PREFIX}data-천문학-20250401.txt"
        knowledge_base_id = None
        state_machine_arn = None
        
        bInit = True
        
        if bInit:
            # 1. Bedrock Knowledge Base 리소스 생성
            print("\n1. Bedrock Knowledge Base 리소스 생성 중...")
            knowledge_base_id = create_bedrock_resources()
            if knowledge_base_id:
                print(f"Knowledge Base ID: {knowledge_base_id}")
            else:
                print("Knowledge Base 없이 계속 진행합니다.")
            
            # 2. 입력 파일 경로 설정
            print("\n2. 입력 파일 경로 설정...")
            print(f"제목 파일: {title_key}")
            print(f"데이터 파일: {data_key}")
            
            # 3. Step Function 생성
            print("\n3. Step Function 워크플로우 생성 중...")
            state_machine_arn = create_step_function(title_key, knowledge_base_id)
            print(f"Step Function ARN: {state_machine_arn}")
        else:
            # 기존 Step Function 찾기
            # 수동입력 실행
            state_machine_arn = "arn:aws:states:us-west-2:211125752707:stateMachine:CurriculumGenerator-미술-20250401" #  수동입력
        
        # 4. 워크플로우 실행
        print("\n4. 워크플로우 실행 중...")
        execution_arn = execute_workflow(title_key, data_key, state_machine_arn)
        print(f"실행 완료. 실행 ARN: {execution_arn}")
        
        print("\n=== 커리큘럼 생성 워크플로우 완료 ===")
    
    except Exception as e:
        print(f"\n오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n=== 커리큘럼 생성 워크플로우 실패 ===")

if __name__ == "__main__":
    main() 