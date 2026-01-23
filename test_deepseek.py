import requests
import json

# DeepSeek API 테스트
api_key = "sk-8a322cf1ede64f4aa1046e9b0e71a76d"
base_url = "https://api.deepseek.com/v1/chat/completions"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

data = {
    "model": "deepseek-chat",  # DeepSeek v3
    "messages": [
        {
            "role": "user",
            "content": "안녕하세요! DeepSeek API 연결 테스트입니다. 간단하게 인사해주세요."
        }
    ],
    "temperature": 0.7,
    "max_tokens": 100
}

print("DeepSeek v3 API 호출 중...")
print(f"API Key: {api_key[:20]}...")
print(f"Model: {data['model']}")
print("-" * 50)

try:
    response = requests.post(base_url, headers=headers, json=data, timeout=30)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("\n✅ 연결 성공!")
        print("-" * 50)
        print("응답:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("-" * 50)
        
        if 'choices' in result and len(result['choices']) > 0:
            message = result['choices'][0]['message']['content']
            print(f"\nDeepSeek 응답 메시지:\n{message}")
    else:
        print(f"\n❌ 연결 실패!")
        print(f"에러 내용: {response.text}")
        
except Exception as e:
    print(f"\n❌ 예외 발생: {str(e)}")
