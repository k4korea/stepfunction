#!/usr/bin/env python3
"""
커리큘럼 생성 워크플로우 설정 및 실행 스크립트

이 스크립트는 다음 작업을 수행합니다:
1. 필요한 AWS 리소스 생성 (S3 버킷, IAM 역할, Lambda 함수 등)
2. 샘플 입력 파일 업로드
3. 워크플로우 실행
"""

import os
import sys
import boto3
import json
import time
import argparse
from datetime import datetime

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 필요한 모듈 가져오기
from lambda_functions.lambda_make import LambdaFunctionManager, add_bedrock_permissions_to_role
from create_bedrock_role import create_bedrock_role_functions, create_step_function_role
from curriculum_workflow import create_step_function, execute_workflow

# AWS 서비스 클라이언트 초기화
s3_client = boto3.client('s3')

# 환경 설정
BUCKET_NAME = 'curriculum-bucket-20250331'
INPUT_PREFIX = 'input/'
OUTPUT_PREFIX = 'curriculum/'
BEDROCK_MODEL_ID = 'amazon.titan-text-express-v1'

def setup_s3_bucket():
    """S3 버킷 생성 및 설정"""
    try:
        # 버킷이 이미 존재하는지 확인
        s3_client.head_bucket(Bucket=BUCKET_NAME)
        print(f"S3 버킷 '{BUCKET_NAME}'이(가) 이미 존재합니다.")
    except Exception:
        # 버킷 생성
        print(f"S3 버킷 '{BUCKET_NAME}' 생성 중...")
        s3_client.create_bucket(
            Bucket=BUCKET_NAME,
            CreateBucketConfiguration={'LocationConstraint': 'us-west-2'}
        )
        print(f"S3 버킷 '{BUCKET_NAME}' 생성 완료")
    
    return BUCKET_NAME

def upload_sample_files(title, data):
    """샘플 입력 파일 업로드"""
    timestamp = datetime.now().strftime('%Y%m%d')
    
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

def setup_and_run(title, data, skip_setup=False):
    """설정 및 실행"""
    print("=== 커리큘럼 생성 워크플로우 설정 및 실행 시작 ===")
    
    try:
        # 1. 초기 설정
        if not skip_setup:
            print("\n1. 초기 설정 중...")
            
            # S3 버킷 설정
            setup_s3_bucket()
            
            # Lambda 실행 역할에 Bedrock 권한 추가
            print("Lambda 실행 역할에 Bedrock 권한 추가 중...")
            add_bedrock_permissions_to_role()
            
            # Step Function 실행 역할 생성
            print("Step Function 실행 역할 생성 중...")
            create_step_function_role()
            
            print("초기 설정 완료")
        
        # 2. 샘플 파일 업로드
        print("\n2. 샘플 파일 업로드 중...")
        title_key, data_key = upload_sample_files(title, data)
        
        # 3. Step Function 생성
        print("\n3. Step Function 워크플로우 생성 중...")
        state_machine_arn = create_step_function(title_key)
        print(f"Step Function ARN: {state_machine_arn}")
        
        # 4. 워크플로우 실행
        print("\n4. 워크플로우 실행 중...")
        execution_arn = execute_workflow(title_key, data_key, state_machine_arn)
        print(f"실행 완료. 실행 ARN: {execution_arn}")
        
        print("\n=== 커리큘럼 생성 워크플로우 설정 및 실행 완료 ===")
        
        return execution_arn
    
    except Exception as e:
        print(f"\n오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n=== 커리큘럼 생성 워크플로우 설정 및 실행 실패 ===")
        return None

def main():
    """명령줄에서 실행할 때의 메인 함수"""
    parser = argparse.ArgumentParser(description='커리큘럼 생성 워크플로우 설정 및 실행')
    parser.add_argument('--title', '-t', default='인공지능', help='커리큘럼 제목')
    parser.add_argument('--data', '-d', default='머신러닝, 딥러닝, 자연어처리, 컴퓨터비전', help='커리큘럼 데이터')
    parser.add_argument('--skip-setup', '-s', action='store_true', help='초기 설정 건너뛰기')
    
    args = parser.parse_args()
    
    setup_and_run(args.title, args.data, args.skip_setup)

if __name__ == "__main__":
    main() 