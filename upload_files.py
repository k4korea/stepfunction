#!/usr/bin/env python3
"""
S3 버킷에 커리큘럼 생성에 필요한 입력 파일을 업로드하는 스크립트
"""

import boto3
import argparse
from datetime import datetime

# AWS 서비스 클라이언트 초기화
s3_client = boto3.client('s3')

# 환경 설정
BUCKET_NAME = 'curriculum-bucket-20250331'
INPUT_PREFIX = 'input/'

def upload_input_files(title, data=None):
    """
    입력 파일 업로드
    
    Args:
        title (str): 커리큘럼 제목
        data (str, optional): 커리큘럼 데이터. 지정하지 않으면 제목에 따라 자동 생성
    
    Returns:
        tuple: (title_key, data_key) - 업로드된 파일의 S3 키
    """
    timestamp = datetime.now().strftime('%Y%m%d')
    
    # 파일명 생성
    title_key = f"{INPUT_PREFIX}title-{title}-{timestamp}.txt"
    data_key = f"{INPUT_PREFIX}data-{title}-{timestamp}.txt"
    
    # 데이터가 지정되지 않은 경우 제목에 따라 자동 생성
    if data is None:
        if "천문학" in title:
            data = """
            태양계, 행성, 별, 은하, 우주론, 천체물리학, 관측 천문학, 천체 역학, 
            천문학 역사, 망원경, 우주 탐사, 블랙홀, 중성자별, 초신성, 
            외계행성, 암흑물질, 암흑에너지, 빅뱅 이론
            """
        elif "미술" in title:
            data = """
            회화, 조각, 건축, 공예, 디자인, 사진, 영상, 설치미술, 
            미술사, 미술이론, 미술비평, 미술교육, 미술심리학, 미술치료, 
            현대미술, 전통미술, 동양미술, 서양미술, 한국미술
            """
        else:
            data = f"{title} 관련 데이터"
    
    # 제목 파일 업로드
    print(f"제목 파일 '{title_key}' 업로드 중...")
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=title_key,
        Body=title.encode('utf-8'),
        ContentType='text/plain; charset=utf-8'
    )
    
    # 데이터 파일 업로드
    print(f"데이터 파일 '{data_key}' 업로드 중...")
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=data_key,
        Body=data.encode('utf-8'),
        ContentType='text/plain; charset=utf-8'
    )
    
    print("파일 업로드 완료")
    return title_key, data_key

def main():
    """명령줄에서 실행할 때의 메인 함수"""
    parser = argparse.ArgumentParser(description='S3 버킷에 커리큘럼 입력 파일 업로드')
    parser.add_argument('--title', '-t', required=True, help='커리큘럼 제목')
    parser.add_argument('--data', '-d', help='커리큘럼 데이터 (지정하지 않으면 제목에 따라 자동 생성)')
    
    args = parser.parse_args()
    
    title_key, data_key = upload_input_files(args.title, args.data)
    print(f"업로드된 파일: {title_key}, {data_key}")

if __name__ == "__main__":
    main() 