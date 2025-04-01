import boto3
import json

def test_bedrock_prompt():
    # AWS 서비스 클라이언트 초기화
    bedrock_runtime = boto3.client('bedrock-runtime')
    
    # 테스트할 제목과 데이터
    title = "천문학"
    data = "태양계, 행성, 별, 은하, 우주론, 천체물리학, 관측 천문학, 천체 역학"
    
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

반드시 가상의 교수 정보를 포함하여 체계적이고 교육적으로 가치 있는 커리큘럼을 작성해주세요.
각 교수는 {title} 분야의 전문가여야 합니다."""
    
    # Claude 모델 호출
    try:
        response = bedrock_runtime.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
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
        result = response_body['content'][0]['text']
        
        # 결과 출력
        print("=== 모델 응답 ===")
        print(result)
        
        # 교수 정보가 포함되어 있는지 확인
        if "교수" in result and "전공" in result:
            print("\n✅ 교수 정보가 포함되어 있습니다.")
        else:
            print("\n❌ 교수 정보가 포함되어 있지 않습니다.")
        
        return result
    
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        return None

if __name__ == "__main__":
    test_bedrock_prompt() 