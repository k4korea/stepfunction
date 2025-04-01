import boto3
import json
import time
import uuid


# 이것도 class로 만들어줘 
# create_bedrock_knowledge_base_role 을 만들고 
# create_opensearch_collection 을 만들고 


# IAM 클라이언트 초기화
iam_client = boto3.client('iam')

class BedrockResourceManager:
    """
    AWS Bedrock 및 OpenSearch 리소스를 관리하는 클래스
    
    Attributes:
        iam_client: AWS IAM 클라이언트
        aoss_client: AWS OpenSearch Serverless 클라이언트
        bedrock_client: AWS Bedrock 클라이언트
        s3_bucket_name: S3 버킷 이름
    """
    
    def __init__(self, s3_bucket_name='curriculum-bucket-20250331'):
        """
        BedrockResourceManager 초기화
        
        Args:
            s3_bucket_name (str): S3 버킷 이름
        """
        self.iam_client = boto3.client('iam')
        self.aoss_client = boto3.client('opensearchserverless')
        self.bedrock_client = boto3.client('bedrock')
        self.s3_bucket_name = s3_bucket_name
    
    def create_bedrock_knowledge_base_role(self, role_name='BedrockKnowledgeBaseRole'):
        """
        Bedrock Knowledge Base용 IAM 역할 생성
        
        Args:
            role_name (str): 생성할 역할 이름
            
        Returns:
            str: 생성된 역할의 ARN
        """
        # 역할이 이미 존재하는지 확인
        try:
            response = self.iam_client.get_role(RoleName=role_name)
            print(f"Role '{role_name}' already exists.")
            return response['Role']['Arn']
        except self.iam_client.exceptions.NoSuchEntityException:
            print(f"Creating role '{role_name}'...")
        
        # 신뢰 정책 (Trust Policy) 정의
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "bedrock.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        # 역할 생성
        response = self.iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='Role for Bedrock Knowledge Base to access S3 and OpenSearch Serverless'
        )
        
        role_arn = response['Role']['Arn']
        print(f"Role '{role_name}' has been created. ARN: {role_arn}")
        
        # S3 접근 정책 생성 및 연결
        s3_policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:ListBucket"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{self.s3_bucket_name}",
                        f"arn:aws:s3:::{self.s3_bucket_name}/*"
                    ]
                }
            ]
        }
        
        s3_policy_name = f"{role_name}-S3Access"
        s3_policy_arn = self._create_or_get_policy(s3_policy_name, s3_policy_document, 
                                                 'S3 access permissions for Bedrock Knowledge Base')
        
        # OpenSearch Serverless 접근 정책 생성 및 연결
        opensearch_policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "aoss:APIAccessAll",
                        "aoss:BatchGetCollection",
                        "aoss:CreateCollection",
                        "aoss:CreateSecurityPolicy",
                        "aoss:GetSecurityPolicy",
                        "aoss:ListCollections",
                        "aoss:UpdateCollection"
                    ],
                    "Resource": "*"
                }
            ]
        }
        
        opensearch_policy_name = f"{role_name}-OpenSearchAccess"
        opensearch_policy_arn = self._create_or_get_policy(opensearch_policy_name, opensearch_policy_document,
                                                         'OpenSearch Serverless access permissions for Bedrock Knowledge Base')
        
        # Bedrock 모델 접근 정책 생성 및 연결
        bedrock_policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:GetFoundationModel"
                    ],
                    "Resource": "*"
                }
            ]
        }
        
        bedrock_policy_name = f"{role_name}-BedrockAccess"
        bedrock_policy_arn = self._create_or_get_policy(bedrock_policy_name, bedrock_policy_document,
                                                      'Bedrock model access permissions for Bedrock Knowledge Base')
        
        # 정책을 역할에 연결
        self._attach_policy_to_role(role_name, s3_policy_arn)
        self._attach_policy_to_role(role_name, opensearch_policy_arn)
        self._attach_policy_to_role(role_name, bedrock_policy_arn)
        
        print(f"All policies have been attached to role '{role_name}'.")
        
        # 역할 권한이 전파될 시간을 주기 위해 잠시 대기
        print("Waiting 10 seconds for IAM role permissions to propagate...")
        time.sleep(10)
        
        return role_arn
    
    def _create_or_get_policy(self, policy_name, policy_document, description):
        """
        IAM 정책을 생성하거나 기존 정책 가져오기
        
        Args:
            policy_name (str): 정책 이름
            policy_document (dict): 정책 문서
            description (str): 정책 설명
            
        Returns:
            str: 정책 ARN
        """
        try:
            policy_response = self.iam_client.create_policy(
                PolicyName=policy_name,
                PolicyDocument=json.dumps(policy_document),
                Description=description
            )
            policy_arn = policy_response['Policy']['Arn']
            print(f"Policy '{policy_name}' has been created. ARN: {policy_arn}")
        except self.iam_client.exceptions.EntityAlreadyExistsException:
            account_id = boto3.client('sts').get_caller_identity()['Account']
            policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
            print(f"Policy '{policy_name}' already exists. ARN: {policy_arn}")
        
        return policy_arn
    
    def _attach_policy_to_role(self, role_name, policy_arn):
        """
        정책을 역할에 연결
        
        Args:
            role_name (str): 역할 이름
            policy_arn (str): 정책 ARN
        """
        try:
            # 이미 연결되어 있는지 확인
            attached_policies = self.iam_client.list_attached_role_policies(RoleName=role_name)
            for policy in attached_policies['AttachedPolicies']:
                if policy['PolicyArn'] == policy_arn:
                    print(f"Policy '{policy_arn}' is already attached to role '{role_name}'.")
                    return
            
            # 정책 연결
            self.iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn=policy_arn
            )
            print(f"Policy '{policy_arn}' has been attached to role '{role_name}'.")
        except Exception as e:
            print(f"Error attaching policy to role: {str(e)}")
    
    def create_opensearch_collection(self, collection_name='bedrock-kb-collection'):
        """
        OpenSearch Serverless 컬렉션 생성
        
        Args:
            collection_name (str): 컬렉션 이름
            
        Returns:
            str: 컬렉션 ARN
        """
        # 컬렉션이 이미 존재하는지 확인
        try:
            collections = self.aoss_client.list_collections()['collectionSummaries']
            for collection in collections:
                if collection['name'] == collection_name:
                    print(f"OpenSearch 컬렉션 '{collection_name}'이(가) 이미 존재합니다.")
                    return collection['arn']
        except Exception as e:
            print(f"컬렉션 확인 중 오류 발생: {str(e)}")
        
        print(f"OpenSearch 컬렉션 '{collection_name}'을(를) 생성합니다...")
        
        # 보안 정책 생성 (네트워크 정책)
        network_policy_name = f"{collection_name}-network-policy"
        network_policy = [  # 배열 형식으로 변경
            {
                "Description": "Network policy for Bedrock Knowledge Base",
                "Name": network_policy_name,
                "Policy": json.dumps([  # 내부 정책도 배열 형식으로 변경
                    {
                        "Description": "Allow public access to collection",
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [
                                    f"collection/{collection_name}"
                                ]
                            },
                            {
                                "ResourceType": "dashboard",
                                "Resource": [
                                    f"collection/{collection_name}"
                                ]
                            }
                        ],
                        "AllowFromPublic": True
                    }
                ]),
                "Type": "network"
            }
        ]
        
        try:
            # 네트워크 정책 생성
            print(f"OpenSearch 네트워크 정책 '{network_policy_name}' 생성 중...")
            self.aoss_client.create_security_policy(
                name=network_policy_name,
                policy=json.dumps(network_policy[0]["Policy"]),  # 배열의 첫 번째 요소에서 정책 추출
                type="network",
                description="Network policy for Bedrock Knowledge Base"
            )
            print(f"OpenSearch 네트워크 정책 '{network_policy_name}' 생성 완료")
        except self.aoss_client.exceptions.ConflictException:
            print(f"OpenSearch 네트워크 정책 '{network_policy_name}'이(가) 이미 존재합니다.")
        except Exception as e:
            print(f"보안 정책 생성 중 오류 발생: {str(e)}")
            raise
        
        # 데이터 액세스 정책 생성
        access_policy_name = f"{collection_name}-access-policy"
        access_policy = [  # 배열 형식으로 변경
            {
                "Description": "Access policy for Bedrock Knowledge Base",
                "Name": access_policy_name,
                "Policy": json.dumps([  # 내부 정책도 배열 형식으로 변경
                    {
                        "Description": "Allow full access to collection",
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [
                                    f"collection/{collection_name}"
                                ],
                                "Permission": [
                                    "aoss:CreateCollectionItems",
                                    "aoss:DeleteCollectionItems",
                                    "aoss:UpdateCollectionItems",
                                    "aoss:DescribeCollectionItems"
                                ]
                            },
                            {
                                "ResourceType": "index",
                                "Resource": [
                                    f"index/{collection_name}/*"
                                ],
                                "Permission": [
                                    "aoss:CreateIndex",
                                    "aoss:DeleteIndex",
                                    "aoss:UpdateIndex",
                                    "aoss:DescribeIndex",
                                    "aoss:ReadDocument",
                                    "aoss:WriteDocument"
                                ]
                            }
                        ],
                        "Principal": [
                            "*"
                        ]
                    }
                ]),
                "Type": "data"
            }
        ]
        
        try:
            # 데이터 액세스 정책 생성
            print(f"OpenSearch 데이터 액세스 정책 '{access_policy_name}' 생성 중...")
            self.aoss_client.create_security_policy(
                name=access_policy_name,
                policy=json.dumps(access_policy[0]["Policy"]),  # 배열의 첫 번째 요소에서 정책 추출
                type="data",
                description="Data access policy for Bedrock Knowledge Base"
            )
            print(f"OpenSearch 데이터 액세스 정책 '{access_policy_name}' 생성 완료")
        except self.aoss_client.exceptions.ConflictException:
            print(f"OpenSearch 데이터 액세스 정책 '{access_policy_name}'이(가) 이미 존재합니다.")
        except Exception as e:
            print(f"보안 정책 생성 중 오류 발생: {str(e)}")
            raise
        
        # 컬렉션 생성
        try:
            response = self.aoss_client.create_collection(
                name=collection_name,
                type='VECTORSEARCH'
            )
            
            collection_id = response['createCollectionDetail']['id']
            collection_arn = response['createCollectionDetail']['arn']
            
            print(f"OpenSearch 컬렉션 '{collection_name}'이(가) 생성 중입니다.")
            print(f"컬렉션 ID: {collection_id}")
            print(f"컬렉션 ARN: {collection_arn}")
            
            # 컬렉션 생성 완료 대기
            print("컬렉션이 활성화될 때까지 대기 중...")
            
            while True:
                collection_status = self.aoss_client.batch_get_collection(
                    names=[collection_name]
                )['collectionDetails'][0]['status']
                
                if collection_status == 'ACTIVE':
                    print(f"컬렉션 '{collection_name}'이(가) 활성화되었습니다.")
                    break
                elif collection_status in ['FAILED', 'DELETING', 'DELETED']:
                    print(f"컬렉션 생성 실패: {collection_status}")
                    raise Exception(f"컬렉션 생성 실패: {collection_status}")
                
                print(f"현재 상태: {collection_status}. 10초 후 다시 확인...")
                time.sleep(10)
            
            return collection_arn
            
        except Exception as e:
            print(f"컬렉션 생성 중 오류 발생: {str(e)}")
            raise
    
    def _create_security_policy(self, policy_name, collection_name, policy_type):
        """
        OpenSearch Serverless 보안 정책 생성
        
        Args:
            policy_name (str): 정책 이름
            collection_name (str): 컬렉션 이름
            policy_type (str): 정책 유형 ('network' 또는 'encryption' 또는 'access')
        """
        try:
            # 정책 이름 길이 제한 (32자 이하)
            if len(policy_name) > 32:
                # 이름 축약 (예: bedrock-kb-collection-network-policy -> bkb-net-policy)
                if policy_type == 'network':
                    policy_name = f"bkb-net-policy-{uuid.uuid4().hex[:8]}"
                elif policy_type == 'encryption':
                    policy_name = f"bkb-enc-policy-{uuid.uuid4().hex[:8]}"
                else:  # access
                    policy_name = f"bkb-acc-policy-{uuid.uuid4().hex[:8]}"
                
                print(f"정책 이름이 너무 깁니다. 축약된 이름으로 변경: {policy_name}")
            
            if policy_type == 'network':
                # 네트워크 정책 생성
                self.aoss_client.create_security_policy(
                    name=policy_name,
                    policy=json.dumps({
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{collection_name}"]
                            }
                        ],
                        "AWSOwnedKey": True
                    }),
                    type='network'
                )
                print(f"네트워크 보안 정책 '{policy_name}'이(가) 생성되었습니다.")
                
            elif policy_type == 'encryption':
                # 암호화 정책 생성
                self.aoss_client.create_security_policy(
                    name=policy_name,
                    policy=json.dumps({
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{collection_name}"]
                            }
                        ],
                        "AWSOwnedKey": True
                    }),
                    type='encryption'
                )
                print(f"암호화 보안 정책 '{policy_name}'이(가) 생성되었습니다.")
                
            else:  # access
                # 액세스 정책 생성
                self.aoss_client.create_security_policy(
                    name=policy_name,
                    policy=json.dumps({
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{collection_name}"],
                                "Permission": [
                                    "aoss:CreateCollectionItems",
                                    "aoss:DeleteCollectionItems",
                                    "aoss:UpdateCollectionItems",
                                    "aoss:DescribeCollectionItems"
                                ]
                            },
                            {
                                "ResourceType": "index",
                                "Resource": [f"index/{collection_name}/*"],
                                "Permission": [
                                    "aoss:CreateIndex",
                                    "aoss:DeleteIndex",
                                    "aoss:UpdateIndex",
                                    "aoss:DescribeIndex",
                                    "aoss:ReadDocument",
                                    "aoss:WriteDocument"
                                ]
                            }
                        ],
                        "Principal": ["*"]
                    }),
                    type='data'
                )
                print(f"액세스 보안 정책 '{policy_name}'이(가) 생성되었습니다.")
                
        except self.aoss_client.exceptions.ConflictException:
            print(f"보안 정책 '{policy_name}'이(가) 이미 존재합니다.")
        except Exception as e:
            print(f"보안 정책 생성 중 오류 발생: {str(e)}")
            raise
    
    def _wait_for_collection_active(self, collection_id, max_attempts=30, delay=10):
        """
        컬렉션이 활성화될 때까지 대기
        
        Args:
            collection_id (str): 컬렉션 ID
            max_attempts (int): 최대 시도 횟수
            delay (int): 시도 간 대기 시간(초)
            
        Returns:
            bool: 컬렉션이 활성화되었는지 여부
        """
        for attempt in range(max_attempts):
            try:
                response = self.aoss_client.batch_get_collection(ids=[collection_id])
                status = response['collectionDetails'][0]['status']
                
                if status == 'ACTIVE':
                    print(f"Collection is now active after {attempt + 1} attempts.")
                    return True
                
                print(f"Collection status: {status}. Waiting {delay} seconds... (Attempt {attempt + 1}/{max_attempts})")
                time.sleep(delay)
                
            except Exception as e:
                print(f"Error checking collection status: {str(e)}")
                time.sleep(delay)
        
        print(f"Collection did not become active after {max_attempts} attempts.")
        return False
    
    def create_knowledge_base(self, kb_name, collection_arn, role_arn, s3_data_source=None):
        """
        Bedrock Knowledge Base 생성
        
        Args:
            kb_name (str): Knowledge Base 이름
            collection_arn (str): OpenSearch 컬렉션 ARN
            role_arn (str): IAM 역할 ARN
            s3_data_source (dict, optional): S3 데이터 소스 설정
            
        Returns:
            str: Knowledge Base ID
        """
        # Knowledge Base가 이미 존재하는지 확인
        try:
            knowledge_bases = self.bedrock_client.list_knowledge_bases()['knowledgeBases']
            for kb in knowledge_bases:
                if kb['name'] == kb_name:
                    print(f"Knowledge Base '{kb_name}' already exists.")
                    return kb['knowledgeBaseId']
        except Exception as e:
            print(f"Error checking knowledge bases: {str(e)}")
        
        print(f"Creating Knowledge Base '{kb_name}'...")
        
        # Knowledge Base 생성
        try:
            kb_params = {
                'name': kb_name,
                'roleArn': role_arn,
                'knowledgeBaseConfiguration': {
                    'type': 'VECTOR',
                    'vectorKnowledgeBaseConfiguration': {
                        'embeddingModelArn': 'arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1'
                    }
                },
                'storageConfiguration': {
                    'type': 'OPENSEARCH_SERVERLESS',
                    'opensearchServerlessConfiguration': {
                        'collectionArn': collection_arn,
                        'vectorIndexName': 'bedrock-kb-index',
                        'fieldMapping': {
                            'vectorField': 'bedrock-kb-vector',
                            'textField': 'bedrock-kb-text',
                            'metadataField': 'bedrock-kb-metadata'
                        }
                    }
                }
            }
            
            # S3 데이터 소스 추가 (선택 사항)
            if s3_data_source:
                kb_params['dataSource'] = {
                    'type': 'S3',
                    's3Configuration': s3_data_source
                }
            
            response = self.bedrock_client.create_knowledge_base(**kb_params)
            
            kb_id = response['knowledgeBase']['knowledgeBaseId']
            print(f"Knowledge Base '{kb_name}' is being created.")
            print(f"Knowledge Base ID: {kb_id}")
            
            return kb_id
            
        except Exception as e:
            print(f"Error creating Knowledge Base: {str(e)}")
            return None


# curriculum_workflow.py에서 사용할 함수들
def create_bedrock_resources(bucket_name='curriculum-bucket-20250331'):
    """
    curriculum_workflow.py에서 사용할 Bedrock 리소스 생성 함수
    
    Args:
        bucket_name (str): S3 버킷 이름
        
    Returns:
        dict: 생성된 리소스 정보
    """
    manager = BedrockResourceManager(bucket_name)
    
    # 1. IAM 역할 생성
    role_arn = manager.create_bedrock_knowledge_base_role()
    
    # 2. OpenSearch 컬렉션 생성
    collection_arn = manager.create_opensearch_collection()
    
    # 3. Knowledge Base 생성
    kb_id = manager.create_knowledge_base(
        kb_name='curriculum-knowledge-base',
        collection_arn=collection_arn,
        role_arn=role_arn,
        s3_data_source={
            'bucketArn': f"arn:aws:s3:::{bucket_name}",
            'inclusionPrefixes': ['input/']
        }
    )
    
    return {
        'role_arn': role_arn,
        'collection_arn': collection_arn,
        'knowledge_base_id': kb_id
    }

def get_knowledge_base_id(kb_name='curriculum-knowledge-base'):
    """
    Knowledge Base ID 가져오기
    
    Args:
        kb_name (str): Knowledge Base 이름
        
    Returns:
        str: Knowledge Base ID
    """
    bedrock_client = boto3.client('bedrock')
    
    try:
        knowledge_bases = bedrock_client.list_knowledge_bases()['knowledgeBases']
        for kb in knowledge_bases:
            if kb['name'] == kb_name:
                return kb['knowledgeBaseId']
    except Exception as e:
        print(f"Error getting Knowledge Base ID: {str(e)}")
    
    return None

def create_bedrock_role_functions():
    """
    curriculum_workflow.py에서 호출할 함수
    Bedrock 역할, OpenSearch 컬렉션, Knowledge Base 생성
    
    Returns:
        str: Knowledge Base ID
    """
    resources = create_bedrock_resources()
    return resources['knowledge_base_id']


# 명령줄에서 직접 실행할 때 사용하는 함수들
def create_bedrock_knowledge_base_role(s3_bucket_name='curriculum-bucket-20250331'):
    """
    Bedrock Knowledge Base용 IAM 역할 생성 (유틸리티 함수)
    
    Args:
        s3_bucket_name (str): S3 버킷 이름
        
    Returns:
        str: 생성된 역할의 ARN
    """
    manager = BedrockResourceManager(s3_bucket_name)
    return manager.create_bedrock_knowledge_base_role()

def create_opensearch_collection(collection_name='bedrock-kb-collection'):
    """
    OpenSearch Serverless 컬렉션 생성 (유틸리티 함수)
    
    Args:
        collection_name (str): 컬렉션 이름
        
    Returns:
        str: 컬렉션 ARN
    """
    manager = BedrockResourceManager()
    return manager.create_opensearch_collection(collection_name)

def create_step_function_role(role_name='StepFunctionExecutionRole'):
    """
    Step Function 실행 역할 생성
    
    Args:
        role_name (str): 생성할 역할 이름
        
    Returns:
        str: 생성된 역할의 ARN
    """
    iam_client = boto3.client('iam')
    
    # 역할이 이미 존재하는지 확인
    try:
        response = iam_client.get_role(RoleName=role_name)
        print(f"Step Function 역할 '{role_name}'이(가) 이미 존재합니다.")
        return response['Role']['Arn']
    except iam_client.exceptions.NoSuchEntityException:
        print(f"Step Function 역할 '{role_name}'을(를) 생성합니다...")
    
    # 신뢰 정책 (Trust Policy) 정의 - states.amazonaws.com 서비스 추가
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "states.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    # 역할 생성
    response = iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description='Role for Step Functions to invoke Lambda functions'
    )
    
    role_arn = response['Role']['Arn']
    print(f"Step Function 역할 '{role_name}'이(가) 생성되었습니다. ARN: {role_arn}")
    
    # Lambda 호출 권한 정책 생성 및 연결
    lambda_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "lambda:InvokeFunction"
                ],
                "Resource": "*"
            }
        ]
    }
    
    lambda_policy_name = f"{role_name}-LambdaInvoke"
    
    try:
        policy_response = iam_client.create_policy(
            PolicyName=lambda_policy_name,
            PolicyDocument=json.dumps(lambda_policy_document),
            Description='Lambda invoke permissions for Step Functions'
        )
        lambda_policy_arn = policy_response['Policy']['Arn']
        print(f"정책 '{lambda_policy_name}'이(가) 생성되었습니다. ARN: {lambda_policy_arn}")
    except iam_client.exceptions.EntityAlreadyExistsException:
        account_id = boto3.client('sts').get_caller_identity()['Account']
        lambda_policy_arn = f"arn:aws:iam::{account_id}:policy/{lambda_policy_name}"
        print(f"정책 '{lambda_policy_name}'이(가) 이미 존재합니다. ARN: {lambda_policy_arn}")
    
    # 정책을 역할에 연결
    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn=lambda_policy_arn
    )
    
    # CloudWatch Logs 접근 정책 연결
    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn='arn:aws:iam::aws:policy/CloudWatchLogsFullAccess'
    )
    
    print(f"모든 정책이 역할 '{role_name}'에 연결되었습니다.")
    
    # 역할 권한이 전파될 시간을 주기 위해 잠시 대기
    print("IAM 역할 권한이 전파될 때까지 10초 대기 중...")
    time.sleep(10)
    
    return role_arn

def main():
    """메인 함수 - 명령줄에서 직접 실행할 때 사용"""
    
    # 명령줄 인자 처리
    import argparse
    parser = argparse.ArgumentParser(description='Bedrock Knowledge Base 리소스 관리')
    parser.add_argument('--create-role', action='store_true', help='Bedrock Knowledge Base 역할 생성')
    parser.add_argument('--create-collection', action='store_true', help='OpenSearch 컬렉션 생성')
    parser.add_argument('--create-kb', action='store_true', help='Knowledge Base 생성')
    parser.add_argument('--create-all', action='store_true', help='모든 리소스 생성')
    parser.add_argument('--bucket', default='curriculum-bucket-20250331', help='S3 버킷 이름')
    parser.add_argument('--collection-name', default='bedrock-kb-collection', help='OpenSearch 컬렉션 이름')
    parser.add_argument('--kb-name', default='curriculum-knowledge-base', help='Knowledge Base 이름')
    parser.add_argument('--get-kb-id', action='store_true', help='Knowledge Base ID 가져오기')
    
    args = parser.parse_args()
    
    if args.create_all:
        resources = create_bedrock_resources(args.bucket)
        print("\n=== 생성된 리소스 정보 ===")
        print(f"IAM 역할 ARN: {resources['role_arn']}")
        print(f"OpenSearch 컬렉션 ARN: {resources['collection_arn']}")
        print(f"Knowledge Base ID: {resources['knowledge_base_id']}")
        return
    
    if args.get_kb_id:
        kb_id = get_knowledge_base_id(args.kb_name)
        if kb_id:
            print(f"Knowledge Base ID: {kb_id}")
        else:
            print(f"Knowledge Base '{args.kb_name}'을(를) 찾을 수 없습니다.")
        return
    
    manager = BedrockResourceManager(args.bucket)
    
    if args.create_role:
        role_arn = manager.create_bedrock_knowledge_base_role()
        print(f"Created role ARN: {role_arn}")
    
    if args.create_collection:
        collection_arn = manager.create_opensearch_collection(args.collection_name)
        print(f"Created collection ARN: {collection_arn}")
    
    if args.create_kb:
        # 먼저 역할과 컬렉션 생성
        role_arn = manager.create_bedrock_knowledge_base_role()
        collection_arn = manager.create_opensearch_collection(args.collection_name)
        
        # Knowledge Base 생성
        kb_id = manager.create_knowledge_base(
            kb_name=args.kb_name,
            collection_arn=collection_arn,
            role_arn=role_arn,
            s3_data_source={
                'bucketArn': f"arn:aws:s3:::{args.bucket}",
                'inclusionPrefixes': ['input/']
            }
        )
        print(f"Created Knowledge Base ID: {kb_id}")
    
    # 아무 옵션도 지정하지 않은 경우 도움말 표시
    if not (args.create_role or args.create_collection or args.create_kb or args.create_all or args.get_kb_id):
        parser.print_help()

def create_opensearch_security_policy(opensearch_client, name, policy_type, policy_content, description):
    """
    OpenSearch 보안 정책 생성
    
    Args:
        opensearch_client: OpenSearch 클라이언트
        name (str): 정책 이름
        policy_type (str): 정책 유형 ('network' 또는 'data')
        policy_content (list): 정책 내용 (배열 형식)
        description (str): 정책 설명
        
    Returns:
        bool: 정책 생성 성공 여부
    """
    try:
        # 정책이 이미 존재하는지 확인
        try:
            policies = opensearch_client.list_security_policies(type=policy_type)
            for policy in policies.get('securityPolicySummaries', []):
                if policy['name'] == name:
                    print(f"OpenSearch {policy_type} 정책 '{name}'이(가) 이미 존재합니다.")
                    return True
        except Exception as e:
            print(f"보안 정책 확인 중 오류 발생: {str(e)}")
        
        # 정책 생성
        print(f"OpenSearch {policy_type} 정책 '{name}' 생성 중...")
        
        # 정책 내용이 배열 형식인지 확인
        if not isinstance(policy_content, list):
            policy_content = [policy_content]
        
        opensearch_client.create_security_policy(
            name=name,
            policy=json.dumps(policy_content),  # 배열 형식으로 직렬화
            type=policy_type,
            description=description
        )
        
        print(f"OpenSearch {policy_type} 정책 '{name}' 생성 완료")
        return True
        
    except opensearch_client.exceptions.ConflictException:
        print(f"OpenSearch {policy_type} 정책 '{name}'이(가) 이미 존재합니다.")
        return True
    except Exception as e:
        print(f"{policy_type} 정책 생성 중 오류 발생: {str(e)}")
        print(f"정책 내용: {json.dumps(policy_content, indent=2)}")
        return False

if __name__ == "__main__":
    main() 