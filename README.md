# stepfunction



# 람다 함수 테스트 json

{
  "bucket": "curriculum-bucket-20250331",
  "titleKey": "input/title-A-20250331.txt",
  "dataKey": "input/data-A-20250331.txt"
}




aws s3 cp ./data/title-미술-20250401.txt s3://curriculum-bucket-20250331/input/title-미술-20250401.txt
aws s3 cp ./data/data-미술-20250401.txt s3://curriculum-bucket-20250331/input/data-미술-20250401.txt

aws s3 cp ./data/title-천문학-20250401.txt s3://curriculum-bucket-20250331/input/title-천문학-20250401.txt
aws s3 cp ./data/data-천문학-20250401.txt s3://curriculum-bucket-20250331/input/data-천문학-20250401.txt



{
  "bucket": "curriculum-bucket-20250331",
  "titleKey": "input/title-미술-20250401.txt",
  "dataKey": "input/data-미술-20250401.txt"
}



# 프롬프트 



# 1. 각 주제별로 섹션을 나누고 하위 섹션으로 세분화
# 2. 각 섹션에 소요 시간 포함
# 3. 학습 목표와 핵심 내용 포함
# 4. 실습 활동 제안
# 5. 평가 방법 제시

###### 프롬프트 가, 나 의 차이처럼 세세히 적용하면 커리큘럼의 퀄리티가 높아짐. 
##### 데이터를 거꾸로 패턴을 찾아서 커리큘럼을 만들어 보자. 양이많다면 
가. 간단한 방식
1. 주제 소개 
2. 교수진 소개
3. 교수별 대표
4. 교수별 컬럼 
5. 평가 방식 (학생들의 성취도를 평가하는 방법)

나. 상세한 방식
다음 형식으로 커리큘럼을 작성해주세요:

1. 주제 소개 (주제에 대한 간략한 설명)
2. 교수진 소개 (이 주제를 가르칠 가상의 교수 3명의 이름, 전공, 경력 등)
3. 교수별 대표 강의 (각 교수가 담당할 주요 강의 내용)
4. 교수별 주요 컬럼 (각 교수가 작성한 주요 컬럼이나 연구 내용)
5. 평가 방식 (학생들의 성취도를 평가하는 방법)



간단히 쿼리 테스트

python simplified_curriculum_workflow.py --title "프로그래밍" --data "Python, Java, C++, 알고리즘, 자료구조"

# chatgpt 와 다른점
1. 프롬프트의 형식을 저장하고 재사용 가능
2. 외부 서비스로 확장이 가능
3. 자동화 형식을 도입가능

# 추가 작업 
1. 토큰 4000 이상 처리 
2. opensearch rag 연동 추가 
3. 거꾸로 데이터의 패턴을 찾아서 커리큘럼및 프로프트의 퀄리티 높이기 
4. 수정된 람다 펑션만 배포되게
5. pdf,word 형식의 입출력
6. sns , email 배포 및 트리거 추가 