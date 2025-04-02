import boto3
import json

# AWS 서비스 클라이언트 초기화
bedrock_runtime = boto3.client('bedrock-runtime')
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')

def lambda_handler(event, context):
    """Bedrock을 사용하여 커리큘럼을 생성하는 Lambda 함수"""
    
    title = event['title']
    data = event['data']
    bucket = event['bucket']
    title_key = event['titleKey']
    model_id = event.get('modelId', 'anthropic.claude-3-sonnet-20240229-v1:0')
    
    # Knowledge Base ID가 있는지 확인
    knowledge_base_id = event.get('knowledgeBaseId')
    
    try:
        if knowledge_base_id:
            # Knowledge Base가 있으면 RAG 사용
            print(f"Knowledge Base ID {knowledge_base_id}를 사용하여 RAG 수행")
            curriculum = generate_with_kb(knowledge_base_id, title, data, model_id)
        else:
            # Knowledge Base가 없으면 일반 Bedrock 호출
            print("Knowledge Base 없이 Bedrock 직접 호출")
            curriculum = generate_without_kb(title, data, model_id)
        
        return {
            'bucket': bucket,
            'titleKey': title_key,
            'curriculum': curriculum
        }
    except Exception as e:
        print(f"Error generating curriculum: {str(e)}")
        # 오류 발생 시 기본 응답 반환
        return {
            'bucket': bucket,
            'titleKey': title_key,
            'curriculum': f"# 커리큘럼 생성 중 오류가 발생했습니다\n\n오류 메시지: {str(e)}\n\n## 기본 커리큘럼\n\n1. 소개\n2. 기본 개념\n3. 심화 학습\n4. 실습\n5. 평가",
            'error': str(e)
        }

def generate_with_kb(knowledge_base_id, title, data, model_id):
    """Knowledge Base를 사용하여 RAG로 커리큘럼 생성"""
    
    # 검색 쿼리 구성 (제목과 데이터를 결합)
    retrieval_query = f"주제: {title}\n\n참고 데이터: {data}\n\n이 주제와 데이터를 바탕으로 체계적인 교육 커리큘럼을 생성해주세요."
    
    # Bedrock Knowledge Base를 사용하여 RAG 수행
    response = bedrock_agent_runtime.retrieve_and_generate(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery=retrieval_query,
        generationConfiguration={
            "modelId": model_id,
            "promptTemplate": "당신은 교육 커리큘럼 전문가입니다. 제공된 주제와 데이터를 바탕으로 체계적인 커리큘럼을 생성해주세요.\n\n{retrievalResults}\n\n주제: {title}\n\n참고 데이터: {data}"
        }
    )
    
    # 생성된 커리큘럼 추출
    return response['output']['text']

def generate_without_kb(title, data, model_id):
    """일반 Bedrock 모델을 사용하여 커리큘럼 생성"""
    
    # 사용 가능한 모델 확인 및 선택
    try:
        # 사용 가능한 모델 목록 가져오기
        bedrock = boto3.client('bedrock')
        models = bedrock.list_foundation_models()
        available_models = [model['modelId'] for model in models['modelSummaries']]
        
        print(f"사용 가능한 모델: {available_models}")
        
        # 지정된 모델이 사용 가능한지 확인
        if model_id not in available_models:
            print(f"지정된 모델 '{model_id}'을(를) 사용할 수 없습니다. 대체 모델을 사용합니다.")
            
            # 사용 가능한 모델 중 하나 선택
            if available_models:
                model_id = available_models[0]
                print(f"대체 모델로 '{model_id}'을(를) 사용합니다.")
            else:
                raise Exception("사용 가능한 모델이 없습니다.")
    except Exception as e:
        print(f"모델 목록 가져오기 실패: {str(e)}")
        # 기본 모델 사용 (Amazon Titan Text)
        model_id = 'amazon.titan-text-express-v1'
        print(f"기본 모델 '{model_id}'을(를) 사용합니다.")
    
    # 프롬프트 구성
    prompt = f"""당신은 교육 커리큘럼 전문가입니다. 제공된 주제와 데이터를 바탕으로 체계적인 커리큘럼을 생성해주세요.

주제: {title}

참고 데이터: {data}

다음 형식으로 커리큘럼을 작성해주세요:

1. 주제 소개 (주제에 대한 간략한 설명)
2. 교수진 소개 (이 주제를 가르칠 가상의 교수 3명의 이름, 전공, 경력 등)
3. 교수별 대표 강의 (각 교수가 담당할 주요 강의 내용)
4. 교수별 주요 컬럼 (각 교수가 작성한 주요 컬럼이나 연구 내용)
5. 평가 방식 (학생들의 성취도를 평가하는 방법)

체계적이고 교육적으로 가치 있는 커리큘럼을 작성해주세요."""
    print(f"prompt 교슈내용: {prompt}")
    try:
        # 모델 ID에 따라 요청 형식 조정
        if 'claude' in model_id.lower():
            # Claude 모델용 요청
            response = bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4000,
                    "temperature": 0.6,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )
            
            # 응답 파싱
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']
        
        elif 'titan' in model_id.lower():
            # Titan 모델용 요청
            response = bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps({
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": 4000,
                        "temperature": 0.6,
                        "topP": 0.9
                    }
                })
            )
            
            # 응답 파싱
            response_body = json.loads(response['body'].read())
            return response_body['results'][0]['outputText']
        
        else:
            # 기타 모델용 기본 요청
            response = bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps({
                    "prompt": prompt,
                    "max_tokens": 4000,
                    "temperature": 0.7
                })
            )
            
            # 응답 파싱 (모델에 따라 다를 수 있음)
            response_body = json.loads(response['body'].read())
            if 'completion' in response_body:
                return response_body['completion']
            elif 'generated_text' in response_body:
                return response_body['generated_text']
            else:
                return str(response_body)  # 응답 구조를 알 수 없는 경우
    
    except Exception as e:
        print(f"모델 호출 중 오류 발생: {str(e)}")
        # 오류 발생 시 기본 커리큘럼 반환
        return f"""# 기본 커리큘럼

오류로 인해 자동 생성된 기본 커리큘럼입니다. 오류: {str(e)}""" 