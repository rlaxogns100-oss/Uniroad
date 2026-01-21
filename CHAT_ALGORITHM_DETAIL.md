    # 🤖 UniZ 대화 알고리즘 - 완전 상세 가이드

    **Agent 기반 Function Calling 시스템**

    ---

    ## 📋 목차

    1. [전체 플로우 개요](#전체-플로우-개요)
    2. [Phase 1: 사용자 입력 → API 전송](#phase-1-사용자-입력--api-전송)
    3. [Phase 2: API 라우터 처리](#phase-2-api-라우터-처리)
    4. [Phase 3: 에이전트 대화 처리 (핵심)](#phase-3-에이전트-대화-처리-핵심)
    5. [Phase 4: 문서 검색 실행](#phase-4-문서-검색-실행)
    6. [Phase 5: 응답 반환](#phase-5-응답-반환)
    7. [데이터 구조](#데이터-구조)

    ---

    ## 🎯 전체 플로우 개요

    ```
    사용자 입력
        ↓
    [Frontend] ChatPage.tsx::handleSend()
        ↓
    [Frontend] client.ts::sendMessage()
        ↓ POST /api/chat/
    [Backend] chat.py::chat()
        ↓
    [Backend] agent_service.py::chat()
        ↓
        ┌─────────────────────┐
        │ Gemini Function Call│
        │   (최대 5번 루프)   │
        └─────────────────────┘
        ↓
        ├─ [일반 대화] → 텍스트 응답
        │
        └─ [검색 필요] → search_documents() 호출
                ↓
            1. 해시태그 기반 문서 필터링
            2. Gemini로 요약본 분석
            3. 전체 문서 로드
            4. Gemini Lite로 정보 추출
            5. Function Response 반환
                ↓
            다시 Gemini에게 전달
                ↓
            최종 답변 생성
        ↓
    사용자에게 응답 표시
    ```

    ---

    ## Phase 1: 사용자 입력 → API 전송

    ### 📍 위치: `frontend/src/pages/ChatPage.tsx`

    #### 1.1 사용자가 메시지 입력 후 전송 버튼 클릭

    ```typescript
    // 함수: ChatPage::handleSend()
    const handleSend = async () => {
    if (!input.trim() || isLoading) return

    // 1. 사용자 메시지 객체 생성
    const userMessage: Message = {
        id: Date.now().toString(),
        text: input,
        isUser: true,
    }

    // 2. 화면에 즉시 표시
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
        // 3. API 호출
        const response: ChatResponse = await sendMessage(input, sessionId)
        // ...
    }
    }
    ```

    **호출 체인:**
    - `handleSend()` → `sendMessage(input, sessionId)`

    ---

    ### 📍 위치: `frontend/src/api/client.ts`

    #### 1.2 API 클라이언트에서 HTTP 요청 전송

    ```typescript
    // 함수: sendMessage()
    export async function sendMessage(
    message: string,
    sessionId: string = 'default'
    ): Promise<ChatResponse> {
    const response = await axios.post<ChatResponse>('/api/chat/', {
        message,
        session_id: sessionId
    })
    return response.data
    }
    ```

    **HTTP 요청:**
    ```http
    POST /api/chat/
    Content-Type: application/json

    {
    "message": "서울대 2028 정시 알려줘",
    "session_id": "session-1234567890"
    }
    ```

    ---

    ## Phase 2: API 라우터 처리

    ### 📍 위치: `backend/routers/chat.py`

    #### 2.1 FastAPI 엔드포인트 진입

    ```python
    # 함수: chat()
    @router.post("/", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        """에이전트 기반 채팅 메시지 처리"""
        
        # 1. 세션 ID 가져오기
        session_id = request.session_id
        
        # 2. 대화 히스토리 가져오기 (인메모리 저장소)
        if session_id not in conversation_sessions:
            conversation_sessions[session_id] = []
        
        history = conversation_sessions[session_id]
        
        # 3. 에이전트 서비스 호출 ⭐ 핵심!
        result = await agent_service.chat(
            user_message=request.message,
            history=history
        )
        
        # 4. 히스토리 업데이트
        history.append({"role": "user", "parts": [request.message]})
        history.append({"role": "model", "parts": [result["response"]]})
        
        # 5. 최근 10턴만 유지 (메모리 절약)
        if len(history) > 20:
            conversation_sessions[session_id] = history[-20:]
        
        # 6. 채팅 로그 DB 저장
        await supabase_service.insert_chat_log(
            request.message,
            result["response"],
            is_fact_mode=result["used_search"]
        )
        
        # 7. 응답 반환
        return ChatResponse(
            response=result["response"],
            sources=result["sources"],
            source_urls=result.get("source_urls", [])
        )
    ```

    **호출 체인:**
    - `chat()` → `agent_service.chat(user_message, history)`
    - `chat()` → `supabase_service.insert_chat_log()`

    ---

    ## Phase 3: 에이전트 대화 처리 (핵심)

    ### 📍 위치: `backend/services/agent_service.py`

    #### 3.1 에이전트 대화 시작

    ```python
    # 클래스: AgentService
    # 함수: chat()
    @staticmethod
    async def chat(user_message: str, history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        에이전트 기반 대화 처리
        """
        
        # 1. 대화 히스토리 구성
        if history is None:
            history = []
        
        # 현재 요청용 messages (function call 내역 포함)
        messages = history.copy() + [{"role": "user", "parts": [user_message]}]
        
        # 2. 초기화
        sources = []
        source_urls = []
        used_search = False
        
        # 3. Tool 사용 대화 루프 (최대 5번)
        for turn in range(5):
            print(f"{'~'*80}")
            print(f"턴 {turn + 1}")
            print(f"{'~'*80}")
            
            # 4. Gemini 호출 (tools 포함) ⭐
            response = await gemini_service.chat_with_tools(
                messages=messages,
                tools=[AgentService.SEARCH_TOOL],
                system_instruction=AgentService.SYSTEM_INSTRUCTION
            )
            
            # 5. 응답 타입 확인
            if response["type"] == "text":
                # ✅ 최종 답변 (검색 없이 바로 답변)
                return {
                    "response": response["content"],
                    "sources": sources,
                    "source_urls": source_urls,
                    "used_search": used_search
                }
            
            elif response["type"] == "function_call":
                # 🔧 Function Call 발생 (문서 검색 필요)
                fc = response["function_call"]
                func_name = fc["name"]
                func_args = fc["args"]
                
                if func_name == "search_documents":
                    # 6. 문서 검색 실행 ⭐
                    search_result = await AgentService.search_documents(func_args["query"])
                    used_search = True
                    
                    if search_result["found"]:
                        sources.extend(search_result["sources"])
                        source_urls.extend(search_result.get("source_urls", []))
                        
                        # 7. Gemini Lite로 정보 추출 ⭐
                        extracted_info = await gemini_service.extract_info_from_documents(
                            query=func_args["query"],
                            documents=search_result['content'],
                            system_instruction="당신은 문서에서 핵심 정보를 정확하게 추출하는 전문가입니다."
                        )
                        
                        result_text = f"검색 결과:\n\n{extracted_info}"
                    else:
                        result_text = "관련 문서를 찾지 못했습니다. 일반적인 지식으로 답변해주세요."
                    
                    # 8. Function Response 생성 (Gemini SDK 형식)
                    from google.ai.generativelanguage_v1beta.types import content as glm_content
                    
                    # Function Call을 대화에 추가
                    messages.append({
                        "role": "model",
                        "parts": [response["raw_response"].candidates[0].content.parts[0]]
                    })
                    
                    # Function Response 추가
                    function_response = glm_content.Part(
                        function_response=glm_content.FunctionResponse(
                            name=func_name,
                            response={"result": result_text}
                        )
                    )
                    
                    messages.append({
                        "role": "user",
                        "parts": [function_response]
                    })
                    
                    # 9. 다음 턴으로 (Gemini가 이제 추출된 정보로 답변 생성)
                    continue
        
        # 최대 턴 초과 (보통 여기까지 안 옴)
        return {
            "response": "죄송합니다. 답변 생성 중 문제가 발생했습니다. 다시 질문해주세요.",
            "sources": sources,
            "source_urls": source_urls,
            "used_search": used_search
        }
    ```

    **호출 체인:**
    - `agent_service.chat()` → `gemini_service.chat_with_tools()`
    - `agent_service.chat()` → `AgentService.search_documents()` (조건부)
    - `agent_service.chat()` → `gemini_service.extract_info_from_documents()` (조건부)

    ---

    #### 3.2 Gemini Function Calling

    ### 📍 위치: `backend/services/gemini_service.py`

    ```python
    # 클래스: GeminiService
    # 함수: chat_with_tools()
    async def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[FunctionDeclaration],
        system_instruction: str = ""
    ) -> Dict[str, Any]:
        """Tool을 사용한 Gemini 대화"""
        
        # 1. Tool 래핑
        tool_wrapper = Tool(function_declarations=tools)
        
        # 2. 모델 생성 (시스템 인스트럭션 포함)
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        
        model = genai.GenerativeModel(
            GEMINI_FLASH_MODEL,  # "gemini-2.0-flash-exp"
            tools=[tool_wrapper],
            system_instruction=system_instruction if system_instruction else None,
            generation_config=generation_config
        )
        
        # 3. 대화 세션 시작
        chat = model.start_chat(history=messages[:-1] if len(messages) > 1 else [])
        
        # 4. 마지막 메시지 전송
        last_message = messages[-1]["parts"][0]
        
        request_options = genai.types.RequestOptions(
            retry=None,
            timeout=30.0
        )
        
        response = chat.send_message(last_message, request_options=request_options)
        
        # 5. 응답 파싱 (빈 응답 체크)
        if not response.candidates or len(response.candidates) == 0:
            logger.warning("Gemini 응답에 candidates가 없습니다")
            return {
                "type": "text",
                "content": "죄송합니다. AI가 응답을 생성하지 못했습니다. 다시 시도해주세요.",
                "raw_response": response
            }
        
        candidate = response.candidates[0]
        
        # finish_reason 확인
        finish_reason = getattr(candidate, 'finish_reason', None)
        logger.info(f"Gemini finish_reason: {finish_reason}")
        
        if not candidate.content or not candidate.content.parts or len(candidate.content.parts) == 0:
            # SAFETY 필터 체크
            if finish_reason and 'SAFETY' in str(finish_reason):
                return {
                    "type": "text",
                    "content": "죄송합니다. 해당 질문에 대한 답변을 생성할 수 없습니다. 다른 방식으로 질문해주세요.",
                    "raw_response": response
                }
            
            return {
                "type": "text",
                "content": "죄송합니다. AI가 응답을 생성하지 못했습니다. 다시 시도해주세요.",
                "raw_response": response
            }
        
        # 6. Function Call vs Text 구분
        first_part = candidate.content.parts[0]
        
        if hasattr(first_part, 'function_call') and first_part.function_call and first_part.function_call.name:
            # 🔧 Function Call 반환
            fc = first_part.function_call
            return {
                "type": "function_call",
                "function_call": {
                    "name": fc.name,
                    "args": dict(fc.args)
                },
                "raw_response": response
            }
        else:
            # 💬 일반 텍스트 응답
            return {
                "type": "text",
                "content": response.text.strip(),
                "raw_response": response
            }
    ```

    **반환 예시:**

    **케이스 1: 일반 대화 (검색 불필요)**
    ```python
    {
        "type": "text",
        "content": "서울대를 목표로 하시는군요! 정말 멋진 목표예요. 혹시 수시와 정시 중 어느 전형이 더 궁금하신가요?",
        "raw_response": <Response 객체>
    }
    ```

    **케이스 2: Function Call (검색 필요)**
    ```python
    {
        "type": "function_call",
        "function_call": {
            "name": "search_documents",
            "args": {
                "query": "서울대 2028 정시 교과평가"
            }
        },
        "raw_response": <Response 객체>
    }
    ```

    ---

    ## Phase 4: 문서 검색 실행

    ### 📍 위치: `backend/services/agent_service.py`

    #### 4.1 search_documents 도구 실행

    ```python
    # 클래스: AgentService
    # 함수: search_documents() - 정적 메서드
    @staticmethod
    async def search_documents(query: str) -> Dict[str, Any]:
        """
        문서 검색 도구 실행
        
        Returns:
            {
                "found": bool,
                "content": str,
                "sources": List[str],
                "source_urls": List[str]
            }
        """
        
        try:
            client = supabase_service.get_client()
            
            # ============================================================
            # 1단계: documents_metadata에서 관련 문서 찾기
            # ============================================================
            print(f"   📋 [1단계] 질문 분석 중...")
            
            metadata_response = client.table('documents_metadata').select('*').execute()
            
            if not metadata_response.data:
                return {"found": False, "content": "", "sources": [], "source_urls": []}
            
            # 1-1. 질문에서 필수 조건 추출 (연도, 대학명)
            query_lower = query.lower()
            import re
            
            required_year = None
            required_univ = None
            
            # 연도 추출 (필수)
            year_match = re.search(r'(2024|2025|2026|2027|2028)', query)
            if year_match:
                required_year = f'#{year_match.group()}'
                print(f"   ✓ [필수] 연도 감지: {required_year}")
            
            # 대학명 추출 (필수)
            universities = ['서울대', '연세대', '고려대', ...]
            for univ in universities:
                if univ in query:
                    required_univ = f'#{univ}'
                    print(f"   ✓ [필수] 대학명 감지: {required_univ}")
                    break
            
            # 선택 조건: 문서 성격, 전형 구분
            optional_hashtags = []
            
            if any(word in query for word in ['요강', '모집', '전형']):
                optional_hashtags.append('#모집요강')
            elif any(word in query for word in ['입결', '경쟁률', '커트', '합격선']):
                optional_hashtags.append('#입결통계')
            
            if '수시' in query:
                optional_hashtags.append('#수시')
            if '정시' in query:
                optional_hashtags.append('#정시')
            
            # ============================================================
            # 2단계: 해시태그 매칭으로 문서 필터링
            # ============================================================
            print(f"\n   📋 [2단계] 문서 검색 중...")
            
            relevant_docs = []
            
            for doc in metadata_response.data:
                doc_hashtags = doc.get('hashtags', []) or []
                
                # ⚠️ 필수 조건 체크
                if required_year and required_year not in doc_hashtags:
                    continue  # 연도 불일치 → 제외
                
                if required_univ and required_univ not in doc_hashtags:
                    continue  # 대학 불일치 → 제외
                
                # 점수 계산
                score = 0
                matched_info = []
                
                if required_year and required_year in doc_hashtags:
                    score += 20
                    matched_info.append(f"연도 일치: {required_year}")
                
                if required_univ and required_univ in doc_hashtags:
                    score += 20
                    matched_info.append(f"대학 일치: {required_univ}")
                
                # 선택 조건 매칭
                if doc_hashtags and optional_hashtags:
                    matching_optional = set(doc_hashtags) & set(optional_hashtags)
                    if matching_optional:
                        score += len(matching_optional) * 5
                
                if score > 0:
                    print(f"   • {doc.get('title')} (점수: {score})")
                    relevant_docs.append((score, doc))
            
            # 점수 순으로 정렬
            relevant_docs.sort(key=lambda x: x[0], reverse=True)
            relevant_docs = [doc for score, doc in relevant_docs]
            
            if not relevant_docs:
                print("   ❌ 관련 문서 없음")
                return {"found": False, "content": "", "sources": [], "source_urls": []}
            
            print(f"\n   ✅ 해시태그 매칭: {len(relevant_docs)}개 문서 후보")
            
            # ============================================================
            # 3단계: 요약본(목차) 기반 2차 필터링 (Gemini)
            # ============================================================
            print(f"\n   📋 [3단계] 요약본 기반 문서 선별 중...")
            
            # 후보 문서들의 요약본 목록 생성
            docs_summary_list = []
            for idx, doc in enumerate(relevant_docs[:10], 1):
                title = doc.get('title', '제목 없음')
                summary = doc.get('summary', '요약 없음')
                hashtags = doc.get('hashtags', [])
                docs_summary_list.append(
                    f"{idx}. 제목: {title}\n   해시태그: {', '.join(hashtags)}\n   요약: {summary[:500]}"
                )
            
            docs_summary_text = "\n\n".join(docs_summary_list)
            
            # Gemini로 요약본 기반 문서 선별
            filter_prompt = f"""다음 문서들의 요약본(목차)을 읽고, 사용자 질문에 답변하는데 필요한 정보가 있는 문서만 선택하세요.

    사용자 질문: "{query}"

    문서 목록:
    {docs_summary_text}

    **선택 기준:**
    1. 질문에 답변하는데 필요한 구체적인 정보가 포함된 문서만 선택
    2. 관련 없는 문서는 제외
    3. 최대 3개까지만 선택

    **답변 형식:**
    관련 문서가 있으면: 번호만 쉼표로 구분 (예: 1, 3)
    관련 문서가 없으면: 없음"""
            
            try:
                filter_result = await gemini_service.generate(
                    filter_prompt,
                    "당신은 문서 필터링 전문가입니다."
                )
                
                if not filter_result.strip():
                    # 빈 응답 → fallback
                    selected_docs = relevant_docs[:3]
                elif "없음" in filter_result.lower():
                    return {"found": False, "content": "", "sources": [], "source_urls": []}
                else:
                    # 번호 추출
                    import re
                    selected_indices = [int(n.strip())-1 for n in re.findall(r'\d+', filter_result)]
                    selected_docs = [relevant_docs[i] for i in selected_indices if i < len(relevant_docs)]
                    
                    if not selected_docs:
                        selected_docs = relevant_docs[:3]
            
            except Exception as e:
                print(f"   ⚠️ Gemini 요약본 분석 실패: {e}")
                selected_docs = relevant_docs[:3]
            
            # ============================================================
            # 4단계: 선별된 문서의 전체 청크 가져오기
            # ============================================================
            print(f"\n   📋 [4단계] 문서 내용 로드 중...")
            
            full_content = ""
            sources = []
            source_urls = []
            
            for idx, doc in enumerate(selected_docs, 1):
                filename = doc['file_name']
                title = doc['title']
                file_url = doc.get('file_url') or ''
                
                sources.append(title)
                source_urls.append(file_url)
                
                print(f"   [{idx}] 📄 {title}")
                
                # 해당 문서의 모든 청크 가져오기
                chunks_response = client.table('policy_documents')\
                    .select('content, metadata')\
                    .eq('metadata->>fileName', filename)\
                    .execute()
                
                if chunks_response.data:
                    # 청크 순서대로 정렬
                    sorted_chunks = sorted(
                        chunks_response.data,
                        key=lambda x: x.get('metadata', {}).get('chunkIndex', 0)
                    )
                    
                    print(f"       청크 수: {len(sorted_chunks)}개")
                    
                    full_content += f"\n\n{'='*60}\n"
                    full_content += f"📄 {title}\n"
                    full_content += f"{'='*60}\n\n"
                    
                    for chunk in sorted_chunks:
                        full_content += chunk['content']
                        full_content += "\n\n"
            
            print(f"\n   📊 로드된 문서 내용:")
            print(f"       선별된 문서 수: {len(selected_docs)}개")
            print(f"       총 길이: {len(full_content):,}자")
            
            return {
                "found": True,
                "content": full_content,
                "sources": sources,
                "source_urls": source_urls
            }
        
        except Exception as e:
            print(f"   ❌ 검색 오류: {e}")
            return {"found": False, "content": "", "sources": [], "source_urls": []}
    ```

    **호출 체인:**
    - `search_documents()` → `supabase_service.get_client()` (DB 접속)
    - `search_documents()` → `client.table('documents_metadata').select('*').execute()` (메타데이터 조회)
    - `search_documents()` → `gemini_service.generate()` (요약본 분석)
    - `search_documents()` → `client.table('policy_documents').select().eq().execute()` (청크 조회)

    ---

    #### 4.2 Gemini Lite로 정보 추출

    ### 📍 위치: `backend/services/gemini_service.py`

    ```python
    # 클래스: GeminiService
    # 함수: extract_info_from_documents()
    async def extract_info_from_documents(
        self,
        query: str,
        documents: str,
        system_instruction: str = ""
    ) -> str:
        """
        Lite 모델로 대용량 문서에서 정보 추출 (빠른 처리)
        """
        
        prompt = f"""다음 문서에서 '{query}'에 대한 핵심 정보를 추출해주세요.

    문서:
    {documents}

    요구사항:
    - 질문과 관련된 정보만 정확하게 추출
    - 불필요한 내용은 제외
    - 원문의 표현을 최대한 유지
    - 간결하게 정리 (1000자 이내)

    추출된 정보:"""
        
        if system_instruction:
            full_prompt = f"{system_instruction}\n\n{prompt}"
        else:
            full_prompt = prompt
        
        request_options = genai.types.RequestOptions(
            retry=None,
            timeout=30.0
        )
        
        # Lite 모델로 빠르게 처리
        response = self.lite_model.generate_content(full_prompt, request_options=request_options)
        return response.text.strip()
    ```

    **사용 모델:**
    - `gemini-2.0-flash-thinking-exp-01-21` (Lite 모델)
    - 대용량 문서 처리에 최적화
    - 빠른 응답 속도

    ---

    ## Phase 5: 응답 반환

    ### 5.1 에이전트에서 최종 답변 생성

    Phase 3의 루프에서 정보 추출 후, `messages`에 Function Response를 추가하고 다시 Gemini를 호출합니다.

    ```python
    # agent_service.py::chat() 내부

    # Function Response가 messages에 추가된 상태
    messages = [
        {"role": "user", "parts": ["서울대 2028 정시 알려줘"]},
        {"role": "model", "parts": [<function_call object>]},  # Function Call
        {"role": "user", "parts": [<function_response object>]}  # Function Response (추출된 정보)
    ]

    # 다음 턴으로 돌아가서 다시 Gemini 호출
    response = await gemini_service.chat_with_tools(...)

    # 이번엔 type이 "text"로 반환됨
    if response["type"] == "text":
        return {
            "response": response["content"],  # 최종 답변 (cite 태그 포함)
            "sources": sources,  # ["2028학년도 대입 기본사항", ...]
            "source_urls": source_urls,  # ["https://...", ...]
            "used_search": True
        }
    ```

    ---

    ### 5.2 API 라우터에서 응답 반환

    ```python
    # routers/chat.py::chat()

    result = await agent_service.chat(...)  # Phase 3의 결과

    return ChatResponse(
        response=result["response"],
        sources=result["sources"],
        source_urls=result.get("source_urls", [])
    )
    ```

    **HTTP 응답:**
    ```json
    {
    "response": "네, 중요한 변화가 있어요. <cite>2028학년도부터 서울대 정시에서는 학생부 교과평가가 40% 반영됩니다</cite>. 다른 변경사항도 궁금하신가요?",
    "sources": ["2028학년도 대입 기본사항"],
    "source_urls": ["https://supabase.co/storage/.../abc123.pdf"],
    "debug_logs": []
    }
    ```

    ---

    ### 5.3 프론트엔드에서 응답 표시

    ```typescript
    // ChatPage.tsx::handleSend() 내부

    const response: ChatResponse = await sendMessage(input, sessionId)

    const botMessage: Message = {
    id: (Date.now() + 1).toString(),
    text: response.response,
    isUser: false,
    sources: response.sources,
    source_urls: response.source_urls,
    }

    setMessages((prev) => [...prev, botMessage])
    ```

    ---

    ## 📊 데이터 구조

    ### Message 구조 (Gemini SDK)

    ```python
    # Gemini에게 전달되는 messages 형식
    [
        {
            "role": "user",
            "parts": ["사용자 메시지"]
        },
        {
            "role": "model",
            "parts": ["AI 응답"]
        },
        {
            "role": "user",
            "parts": ["다음 사용자 메시지"]
        }
    ]
    ```

    ### Function Declaration (Tool 정의)

    ```python
    # agent_service.py::SEARCH_TOOL
    SEARCH_TOOL = FunctionDeclaration(
        name="search_documents",
        description=(
            "대학 입시 관련 공식 문서를 검색합니다. "
            "구체적인 수치, 날짜, 규정, 전형 방법 등 정확한 정보가 필요할 때 사용하세요. "
            "일반적인 위로나 격려는 검색 없이 답변하세요."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색할 키워드 (예: '2028학년도 서울대 정시 교과평가')"
                }
            },
            "required": ["query"]
        }
    )
    ```

    ### System Instruction

    ```python
    SYSTEM_INSTRUCTION = """당신은 친근하고 따뜻한 대학 입시 전문 상담사입니다.

    🚫 절대 금지 사항:
    1. 마크다운 문법 사용 금지
    2. 한 번에 많은 정보를 쏟아내지 마세요
    3. 막연한 질문에 바로 검색하지 마세요

    ⚠️ 검색 타이밍 판단:
    막연한 질문: "서울대 가고싶어" → 검색 X, 구체화 유도
    구체적인 질문: "서울대 2028 정시 변경사항" → 검색 O

    ✅ 출처 표시 (<cite> 태그):
    - 검색으로 찾은 내용만 <cite>로 감싸기
    - 출처 개수와 <cite> 개수 정확히 일치
    - 일반 조언/격려는 <cite> 사용 금지

    예시:
    "<cite>2028학년도부터 서울대 정시에서는 학생부 교과평가가 40% 반영됩니다</cite>."
    """
    ```

    ---

    ## 🔄 전체 함수 호출 체인 요약

    ```
    1. ChatPage.tsx::handleSend()
        ↓
    2. client.ts::sendMessage()
        ↓ HTTP POST /api/chat/
    3. chat.py::chat()
        ↓
    4. agent_service.py::chat()
        ↓
    5. gemini_service.py::chat_with_tools()
        ↓
        ├─ [일반 대화] → 6a. response["type"] == "text" → 끝
        │
        └─ [검색 필요] → 6b. response["type"] == "function_call"
                ↓
            7. agent_service.py::search_documents()
                ↓
                ├─ 8a. supabase_service.get_client()
                ├─ 8b. client.table('documents_metadata').select().execute()
                ├─ 8c. gemini_service.generate() (요약본 분석)
                └─ 8d. client.table('policy_documents').select().execute()
                ↓
            9. gemini_service.py::extract_info_from_documents()
                ↓
            10. Function Response 생성 → messages에 추가
                ↓
            11. 다시 gemini_service.py::chat_with_tools() 호출
                ↓
            12. response["type"] == "text" (최종 답변)
                ↓
    13. chat.py::chat() → ChatResponse 반환
        ↓
    14. client.ts::sendMessage() → response 받음
        ↓
    15. ChatPage.tsx::handleSend() → 화면에 표시
    ```

    ---

    ## 🎯 핵심 알고리즘 특징

    ### 1. **Agent 기반 대화**
    - LLM이 스스로 판단하여 검색 여부 결정
    - 막연한 질문 → 구체화 유도 (검색 X)
    - 구체적인 질문 → 문서 검색 (검색 O)

    ### 2. **6단계 검색 알고리즘**
    1. 질문 분석 (연도, 대학명, 전형 등 추출)
    2. 해시태그 기반 문서 필터링 (필수 조건 체크)
    3. Gemini로 요약본 분석 (2차 필터링)
    4. 전체 문서 로드 (선별된 문서의 모든 청크)
    5. Gemini Lite로 정보 추출 (빠른 처리)
    6. Function Response 반환

    ### 3. **Function Calling 루프**
    - 최대 5번 반복
    - Function Call → Function Response → 다시 LLM 호출
    - 자연스러운 대화 흐름 유지

    ### 4. **출처 표시**
    - `<cite>` 태그로 검색된 정보 마킹
    - 프론트엔드에서 파란색 배경으로 표시
    - 다운로드 URL 제공

    ---

    ## 📌 주요 설정값

    | 항목 | 값 | 설명 |
    |------|-----|------|
    | **Gemini 모델 (대화)** | `gemini-2.0-flash-exp` | Function Calling 지원 |
    | **Gemini 모델 (문서)** | `gemini-2.0-flash-thinking-exp-01-21` | 빠른 정보 추출 |
    | **Temperature** | 0.7 | 적절한 창의성 |
    | **Max Output Tokens** | 2048 | 충분한 답변 길이 |
    | **최대 루프** | 5턴 | Function Call 반복 제한 |
    | **히스토리 유지** | 최근 10턴 (20개 메시지) | 메모리 절약 |
    | **타임아웃** | 30초 | API 호출 제한 |

    ---

    이 문서는 UniZ 프로젝트의 대화 알고리즘을 **함수 호출 수준**까지 완전히 분석한 가이드입니다. 각 단계에서 어떤 함수가 호출되고, 어떤 데이터가 전달되는지 정확하게 추적할 수 있습니다.
