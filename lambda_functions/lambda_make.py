import boto3
import json
import os
import time
import argparse
import zipfile
import io

# class로 만들어줘 
# 인자값은 function_name, source_file
# lambda role name은 LambdaExecutionRole로 고정 하고 만들는 함수

class LambdaFunctionManager:
    """
    Lambda 함수를 생성하고 관리하는 클래스
    
    Attributes:
        lambda_client: AWS Lambda 클라이언트
        iam_client: AWS IAM 클라이언트
        lambda_role_name: Lambda 함수 실행 역할 이름
    """
    
    def __init__(self, lambda_role_name='LambdaExecutionRole'):
        """
        LambdaFunctionManager 초기화
        
        Args:
            lambda_role_name (str): Lambda 함수 실행 역할 이름
        """
        self.lambda_client = boto3.client('lambda')
        self.iam_client = boto3.client('iam')
        self.lambda_role_name = lambda_role_name
    
    def create_or_update_function(self, function_name, source_file=None, max_retries=5):
        """
        Lambda 함수를 생성하거나 업데이트
        
        Args:
            function_name (str): 생성할 Lambda 함수 이름
            source_file (str, optional): Lambda 함수 소스 코드 파일 경로
            max_retries (int): 최대 재시도 횟수
        
        Returns:
            str: 생성된 Lambda 함수의 ARN
        """
        # 소스 파일 경로 결정
        if source_file is None:
            source_file = os.path.join(os.path.dirname(__file__), f"{function_name}.py")
        
        # 소스 파일 존재 확인
        if not os.path.exists(source_file):
            raise FileNotFoundError(f"소스 파일을 찾을 수 없습니다: {source_file}")
        
        # 소스 코드 읽기
        with open(source_file, 'r') as f:
            lambda_code = f.read()
        
        print(f"Lambda 함수 '{function_name}' 생성/업데이트 중...")
        
        # 이미 존재하는 함수인지 확인
        try:
            lambda_response = self.lambda_client.get_function(FunctionName=function_name)
            print(f"Lambda 함수 '{function_name}'이(가) 이미 존재합니다.")
            print(f"함수 ARN: {lambda_response['Configuration']['FunctionArn']}")
            
            # 함수 코드 업데이트
            print(f"Lambda 함수 '{function_name}' 코드 업데이트 중...")
            
            # 소스 코드를 ZIP 파일로 압축
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr('lambda_function.py', lambda_code)
            
            zip_buffer.seek(0)
            
            # 함수 코드 업데이트
            self.lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=zip_buffer.read()
            )
            
            # 함수가 업데이트될 때까지 대기
            print(f"Lambda 함수 '{function_name}' 코드 업데이트 완료. 상태 확인 중...")
            self._wait_for_function_update(function_name)
            
            # 함수 구성 업데이트 (타임아웃 증가) - 재시도 로직 추가
            for attempt in range(max_retries):
                try:
                    self.lambda_client.update_function_configuration(
                        FunctionName=function_name,
                        Timeout=300,  # 타임아웃을 5분(300초)으로 설정
                        MemorySize=512  # 메모리 크기를 512MB로 설정
                    )
                    print(f"Lambda 함수 '{function_name}' 구성 업데이트 완료")
                    break
                except self.lambda_client.exceptions.ResourceConflictException as e:
                    if attempt < max_retries - 1:
                        wait_time = 5 * (attempt + 1)  # 점진적으로 대기 시간 증가
                        print(f"업데이트 충돌 발생. {wait_time}초 후 재시도 ({attempt+1}/{max_retries})...")
                        time.sleep(wait_time)
                    else:
                        print(f"최대 재시도 횟수 초과. 구성 업데이트를 건너뜁니다.")
                        print(f"오류: {str(e)}")
            
            # 함수가 업데이트될 때까지 대기
            self._wait_for_function_update(function_name)
            
            print(f"Lambda 함수 '{function_name}' 업데이트 완료")
            
            return lambda_response['Configuration']['FunctionArn']
        
        except self.lambda_client.exceptions.ResourceNotFoundException:
            # 함수가 존재하지 않으면 새로 생성
            print(f"Lambda 함수 '{function_name}'이(가) 존재하지 않습니다. 새로 생성합니다.")
            
            # Lambda 실행 역할 가져오기
            lambda_role_arn = self._get_or_create_role()
            
            # 소스 코드를 ZIP 파일로 압축
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr('lambda_function.py', lambda_code)
            
            zip_buffer.seek(0)
            
            # 함수 생성
            response = self.lambda_client.create_function(
                FunctionName=function_name,
                Runtime='python3.9',
                Role=lambda_role_arn,
                Handler='lambda_function.lambda_handler',
                Code={
                    'ZipFile': zip_buffer.read()
                },
                Description=f'Lambda function for {function_name}',
                Timeout=300,  # 타임아웃을 5분(300초)으로 설정
                MemorySize=512  # 메모리 크기를 512MB로 설정
            )
            
            # 함수가 활성화될 때까지 대기
            self._wait_for_function_active(function_name)
            
            print(f"Lambda 함수 '{function_name}' 생성 완료")
            print(f"함수 ARN: {response['FunctionArn']}")
            
            return response['FunctionArn']
    
    def _get_or_create_role(self):
        """
        Lambda 함수 실행 역할을 가져오거나 생성
        
        Returns:
            str: 역할 ARN
        """
        try:
            lambda_role = self.iam_client.get_role(RoleName=self.lambda_role_name)
            lambda_role_arn = lambda_role['Role']['Arn']
            print(f"기존 IAM 역할 '{self.lambda_role_name}'을(를) 사용합니다.")
            return lambda_role_arn
        except self.iam_client.exceptions.NoSuchEntityException:
            # 역할 생성
            return create_lambda_role(self.lambda_role_name)
    
    def create_or_update_functions(self, lambda_list):
        """
        여러 Lambda 함수를 한 번에 생성하거나 업데이트
        
        Args:
            lambda_list (dict): 함수 이름과 소스 파일 경로를 매핑한 딕셔너리
                               예: {'save-curriculum': 'save_curriculum.py'}
        
        Returns:
            dict: 함수 이름과 ARN을 매핑한 딕셔너리
        """
        result = {}
        
        for function_name, source_file in lambda_list.items():
            try:
                print(f"\n=== Lambda 함수 '{function_name}' 처리 시작 ===")
                arn = self.create_or_update_function(function_name, source_file)
                result[function_name] = arn
                print(f"=== Lambda 함수 '{function_name}' 처리 완료 ===\n")
                
                # 다음 함수 처리 전에 잠시 대기
                time.sleep(3)
                
            except Exception as e:
                print(f"함수 '{function_name}' 생성/업데이트 중 오류 발생: {str(e)}")
                import traceback
                traceback.print_exc()
        
        return result

    def _wait_for_function_update(self, function_name, max_wait_time=60, check_interval=5):
        """
        Lambda 함수 업데이트가 완료될 때까지 대기
        
        Args:
            function_name (str): Lambda 함수 이름
            max_wait_time (int): 최대 대기 시간(초)
            check_interval (int): 상태 확인 간격(초)
        """
        print(f"Lambda 함수 '{function_name}' 업데이트 완료 대기 중...")
        start_time = time.time()
        
        while True:
            try:
                response = self.lambda_client.get_function(FunctionName=function_name)
                state = response['Configuration']['State']
                last_update = response['Configuration'].get('LastUpdateStatus', 'Successful')
                
                if state == 'Active' and last_update in ['Successful', None]:
                    print(f"Lambda 함수 '{function_name}' 상태: {state}, 업데이트 상태: {last_update}")
                    return
                
                print(f"Lambda 함수 '{function_name}' 상태: {state}, 업데이트 상태: {last_update}")
                
                # 최대 대기 시간 초과 확인
                if time.time() - start_time > max_wait_time:
                    print(f"최대 대기 시간({max_wait_time}초)이 초과되었습니다. 계속 진행합니다.")
                    return
                
                time.sleep(check_interval)
            
            except Exception as e:
                print(f"함수 상태 확인 중 오류 발생: {str(e)}")
                return

    def _wait_for_function_active(self, function_name, max_wait_time=60, check_interval=5):
        """
        Lambda 함수가 활성화될 때까지 대기
        
        Args:
            function_name (str): Lambda 함수 이름
            max_wait_time (int): 최대 대기 시간(초)
            check_interval (int): 상태 확인 간격(초)
        """
        print(f"Lambda 함수 '{function_name}' 활성화 대기 중...")
        start_time = time.time()
        
        while True:
            try:
                response = self.lambda_client.get_function(FunctionName=function_name)
                state = response['Configuration']['State']
                
                if state == 'Active':
                    print(f"Lambda 함수 '{function_name}' 상태: {state}")
                    return
                
                print(f"Lambda 함수 '{function_name}' 상태: {state}")
                
                # 최대 대기 시간 초과 확인
                if time.time() - start_time > max_wait_time:
                    print(f"최대 대기 시간({max_wait_time}초)이 초과되었습니다. 계속 진행합니다.")
                    return
                
                time.sleep(check_interval)
            
            except Exception as e:
                print(f"함수 상태 확인 중 오류 발생: {str(e)}")
                return

def create_lambda_role(role_name='LambdaExecutionRole', additional_policies=None):
    """
    Lambda 함수 실행 역할 생성
    
    Args:
        role_name (str): 생성할 역할 이름
        additional_policies (list, optional): 추가로 연결할 정책 ARN 목록
        
    Returns:
        str: 생성된 역할의 ARN
    """
    iam_client = boto3.client('iam')
    
    # 역할이 이미 존재하는지 확인
    try:
        lambda_role = iam_client.get_role(RoleName=role_name)
        lambda_role_arn = lambda_role['Role']['Arn']
        print(f"IAM role '{role_name}' already exists.")
        
        # Bedrock 권한 추가 (이미 있는 역할에도 추가)
        add_bedrock_permissions_to_role(role_name)
        
        return lambda_role_arn
    except iam_client.exceptions.NoSuchEntityException:
        # 역할이 존재하지 않으면 새로 생성
        try:
            # 신뢰 정책 (Trust Policy) 정의
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "lambda.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }
            
            # 역할 생성
            lambda_role = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description='Execution role for Lambda functions'
            )
            
            lambda_role_arn = lambda_role['Role']['Arn']
            print(f"IAM role '{role_name}' has been created.")
            
            # 기본 정책 연결
            try:
                # S3 접근 정책
                iam_client.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn='arn:aws:iam::aws:policy/AmazonS3FullAccess'
                )
                print("Attached S3FullAccess policy")
                
                # CloudWatch Logs 접근 정책
                iam_client.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
                )
                print("Attached LambdaBasicExecutionRole policy")
                
                # Bedrock 접근 정책 추가
                add_bedrock_permissions_to_role(role_name)
                print("Attached Bedrock access policy")
                
                # 추가 정책 연결
                if additional_policies:
                    for policy_arn in additional_policies:
                        iam_client.attach_role_policy(
                            RoleName=role_name,
                            PolicyArn=policy_arn
                        )
                        print(f"Attached additional policy: {policy_arn}")
                
                # 역할 권한이 전파될 시간을 주기 위해 잠시 대기
                print("IAM role permissions are propagating. Waiting for 10 seconds...")
                time.sleep(10)
                
                print(f"Role ARN: {lambda_role_arn}")
                return lambda_role_arn
                
            except Exception as e:
                print(f"Error attaching policies to role: {str(e)}")
                # 정책 연결 실패 시 역할 삭제 시도
                try:
                    iam_client.delete_role(RoleName=role_name)
                    print(f"Deleted role '{role_name}' due to policy attachment failure")
                except Exception as del_err:
                    print(f"Failed to delete role: {str(del_err)}")
                raise
        
        except Exception as e:
            print(f"Error creating IAM role: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

def get_lambda_role(role_name='LambdaExecutionRole'):
    """
    Lambda 함수 실행 역할 정보 가져오기
    
    Args:
        role_name (str): 역할 이름
    
    Returns:
        dict: 역할 정보
    """
    iam_client = boto3.client('iam')
    
    try:
        lambda_role = iam_client.get_role(RoleName=role_name)
        print(f"IAM 역할 '{role_name}' 정보:")
        print(f"  ARN: {lambda_role['Role']['Arn']}")
        print(f"  생성일: {lambda_role['Role']['CreateDate']}")
        
        # 연결된 정책 목록 가져오기
        attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)
        print(f"  연결된 정책:")
        for policy in attached_policies['AttachedPolicies']:
            print(f"    - {policy['PolicyName']} ({policy['PolicyArn']})")
        
        return lambda_role['Role']
    
    except iam_client.exceptions.NoSuchEntityException:
        print(f"IAM 역할 '{role_name}'을(를) 찾을 수 없습니다.")
        return None

# 기존 함수를 클래스 메서드를 호출하도록 수정
def create_lambda_function(function_name, source_file=None):
    """
    Lambda 함수를 생성하는 유틸리티 함수
    
    Args:
        function_name (str): 생성할 Lambda 함수 이름
        source_file (str, optional): Lambda 함수 소스 코드 파일 경로.
                                    지정하지 않으면 function_name.py 파일을 사용
    
    Returns:
        str: 생성된 Lambda 함수의 ARN
    """
    manager = LambdaFunctionManager()
    return manager.create_or_update_function(function_name, source_file)

def add_bedrock_permissions_to_role(role_name='LambdaExecutionRole'):
    """Lambda 실행 역할에 Bedrock 권한 추가"""
    try:
        # IAM 클라이언트 생성
        iam_client = boto3.client('iam')
        
        # Bedrock 권한 정책 문서
        bedrock_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:*",
                        "bedrock-runtime:*",
                        "bedrock-agent-runtime:*"
                    ],
                    "Resource": "*"
                }
            ]
        }
        
        # 인라인 정책 추가
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName='bedrock-full-access-policy',
            PolicyDocument=json.dumps(bedrock_policy)
        )
        
        print(f"Bedrock 권한이 '{role_name}' 역할에 추가되었습니다.")
        return True
        
    except Exception as e:
        print(f"Bedrock 권한 추가 중 오류 발생: {str(e)}")
        return False

def main():
    """
    명령줄에서 실행할 때의 메인 함수
    
    여러 Lambda 함수를 한 번에 생성하거나 업데이트
    """
    parser = argparse.ArgumentParser(description='Lambda 함수 생성 유틸리티')
    parser.add_argument('--all', action='store_true', help='모든 Lambda 함수 생성/업데이트')
    parser.add_argument('--function', '-f', help='생성할 Lambda 함수 이름')
    parser.add_argument('--source', '-s', help='Lambda 함수 소스 코드 파일 경로 (기본값: function_name.py)')
    parser.add_argument('--create-role', action='store_true', help='Lambda 실행 역할 생성')
    parser.add_argument('--role-name', default='LambdaExecutionRole', help='Lambda 실행 역할 이름 (기본값: LambdaExecutionRole)')
    parser.add_argument('--get-role', action='store_true', help='Lambda 실행 역할 정보 가져오기')
    
    args = parser.parse_args()
    
    if args.create_role:
        # Lambda 실행 역할 생성
        create_lambda_role(args.role_name)
        return
    
    if args.get_role:
        # Lambda 실행 역할 정보 가져오기
        get_lambda_role(args.role_name)
        return
    
    manager = LambdaFunctionManager(args.role_name)
    
    if args.all:
        # 모든 Lambda 함수 생성/업데이트
        lambda_list = {
            'save-curriculum': os.path.join(os.path.dirname(__file__), 'save_curriculum.py'),
            # 필요한 다른 함수들 추가
        }
        
        result = manager.create_or_update_functions(lambda_list)
        print("생성/업데이트된 Lambda 함수 ARN:")
        for name, arn in result.items():
            print(f"  {name}: {arn}")
    
    elif args.function:
        # 단일 Lambda 함수 생성/업데이트
        try:
            function_arn = manager.create_or_update_function(args.function, args.source)
            print(f"Lambda 함수 ARN: {function_arn}")
        except Exception as e:
            print(f"오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 