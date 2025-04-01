#!/usr/bin/env python3
"""
간소화된 커리큘럼 생성 워크플로우

이 스크립트는 기존 Step Function을 사용하여 커리큘럼 생성 워크플로우를 실행합니다.
복잡한 설정 과정 없이 제목과 데이터만 입력하면 됩니다.
"""

import os
import sys
import boto3
import json
import time
import argparse
from datetime import datetime

# AWS 서비스 클라이언트 초기화
s3_client = boto3.client('s3')
sfn_client = boto3.client('stepfunctions')

# 환경 설정
BUCKET_NAME = 'curriculum-bucket-20250331'
INPUT_PREFIX = 'input/'
OUTPUT_PREFIX = 'curriculum/'
DEFAULT_STATE_MACHINE_ARN = "arn:aws:states:us-west-2:211125752707:stateMachine:CurriculumGenerator-미술-20250401"

def upload_input_files(title, data):
    """입력 파일 업로드"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # 파일명 생성
    title_key = f"{INPUT_PREFIX}title-{title}-{timestamp}.txt"
    data_key = f"{INPUT_PREFIX}data-{title}-{timestamp}.txt"
    
    # 파일 업로드
    print(f"제목 파일 '{title_key}' 업로드 중...")
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=title_key,
        Body=title.encode('utf-8'),
        ContentType='text/plain; charset=utf-8'
    )
    
    print(f"데이터 파일 '{data_key}' 업로드 중...")
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=data_key,
        Body=data.encode('utf-8'),
        ContentType='text/plain; charset=utf-8'
    )
    
    return title_key, data_key

def execute_workflow(title_key, data_key, state_machine_arn=DEFAULT_STATE_MACHINE_ARN):
    """워크플로우 실행"""
    # 실행 이름 생성
    execution_name = f"Execution-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # 입력 데이터 구성
    input_data = {
        "titleKey": title_key,
        "dataKey": data_key,
        "bucket": BUCKET_NAME
    }
    
    # Step Function 실행
    print(f"Step Function '{state_machine_arn}' 실행 중...")
    response = sfn_client.start_execution(
        stateMachineArn=state_machine_arn,
        name=execution_name,
        input=json.dumps(input_data)
    )
    
    execution_arn = response['executionArn']
    print(f"실행 ARN: {execution_arn}")
    
    # 실행 상태 확인
    print("실행 상태 확인 중...")
    while True:
        execution = sfn_client.describe_execution(executionArn=execution_arn)
        status = execution['status']
        
        print(f"현재 상태: {status}")
        
        if status in ['SUCCEEDED', 'FAILED', 'TIMED_OUT', 'ABORTED']:
            break
        
        time.sleep(5)
    
    # 실행 결과 확인
    if status == 'SUCCEEDED':
        print("워크플로우 실행 성공!")
        
        # 출력 확인
        output = json.loads(execution['output'])
        if 'saveResult' in output and 'Payload' in output['saveResult']:
            result = output['saveResult']['Payload']
            if 'outputKey' in result:
                output_key = result['outputKey']
                print(f"생성된 커리큘럼: s3://{BUCKET_NAME}/{output_key}")
                
                # 커리큘럼 내용 가져오기
                try:
                    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=output_key)
                    curriculum = response['Body'].read().decode('utf-8')
                    print("\n=== 생성된 커리큘럼 ===\n")
                    print(curriculum)
                except Exception as e:
                    print(f"커리큘럼 내용 가져오기 실패: {str(e)}")
    else:
        print(f"워크플로우 실행 실패: {status}")
        if 'error' in execution:
            print(f"오류: {execution['error']}")
        if 'cause' in execution:
            print(f"원인: {execution['cause']}")
    
    return execution_arn

def run_workflow(title, data, state_machine_arn=DEFAULT_STATE_MACHINE_ARN):
    """워크플로우 실행"""
    print("=== 간소화된 커리큘럼 생성 워크플로우 시작 ===")
    
    try:
        # 1. 입력 파일 업로드
        print("\n1. 입력 파일 업로드 중...")
        title_key, data_key = upload_input_files(title, data)
        
        # 2. 워크플로우 실행
        print("\n2. 워크플로우 실행 중...")
        execution_arn = execute_workflow(title_key, data_key, state_machine_arn)
        
        print("\n=== 간소화된 커리큘럼 생성 워크플로우 완료 ===")
        
        return execution_arn
    
    except Exception as e:
        print(f"\n오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n=== 간소화된 커리큘럼 생성 워크플로우 실패 ===")
        return None

def main():
    """명령줄에서 실행할 때의 메인 함수"""
    parser = argparse.ArgumentParser(description='간소화된 커리큘럼 생성 워크플로우')
    parser.add_argument('--title', '-t', required=True, help='커리큘럼 제목')
    parser.add_argument('--data', '-d', required=True, help='커리큘럼 데이터')
    parser.add_argument('--state-machine', '-s', default=DEFAULT_STATE_MACHINE_ARN, help='Step Function ARN')
    
    args = parser.parse_args()
    
    run_workflow(args.title, args.data, args.state_machine)

if __name__ == "__main__":
    main() 