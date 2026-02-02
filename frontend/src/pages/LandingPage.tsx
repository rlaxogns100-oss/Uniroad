import { useNavigate } from 'react-router-dom'

function LandingPage() {
  const navigate = useNavigate()

  const handleStartClick = () => {
    navigate('/chat')
  }

  return (
    <div className="bg-white">
      {/* 메인 배너 섹션 */}
      <div className="relative w-full m-0 p-0">
        <img 
          src="/landing/4.png" 
          alt="UniRoad 메인 배너" 
          className="w-full h-auto block object-cover"
        />
        
        <div className="absolute bottom-[8%] left-0 w-full flex justify-center px-4">
          <button
            onClick={handleStartClick}
            className="
              w-full max-w-sm py-3.5
              text-white text-lg font-bold text-center tracking-wide
              bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500
              rounded-full
              shadow-2xl backdrop-blur-sm
              transition-all duration-300 hover:scale-105 hover:shadow-indigo-500/50
            "
          >
            지금 질문하러 가기 ✨
          </button>
        </div>
      </div>

      {/* 신뢰도 섹션 */}
      <section className="w-full py-24 bg-white">
        <div className="max-w-6xl mx-auto px-6 grid grid-cols-1 md:grid-cols-2 gap-20 items-center">
          
          <div className="text-left">
            <span className="block text-emerald-500 font-bold mb-4 tracking-wide text-sm md:text-base">
              공식 입시요강 기반의 답변
            </span>
            
            <h2 className="text-4xl md:text-5xl font-extrabold text-gray-900 leading-tight mb-6 tracking-tight">
              유니로드는<br />
              거짓말 하지 않아요
            </h2>
            
            <p className="text-gray-500 text-lg leading-relaxed mb-8 tracking-tight">
              ChatGPT는 37.1%의 확률*로 잘못된 답변을 지어내요.<br />
              물어볼 때마다 말이 달라지기도 하죠.
            </p>
            
            <div className="bg-yellow-50 rounded-xl p-6 flex items-start gap-4">
              <span className="text-2xl mt-1">👉</span>
              <div className="text-gray-700 text-base leading-relaxed tracking-tight">
                하지만 유니로드는 <span className="font-bold text-gray-900">대학별 최신 모집요강</span>만을 근거로 삼기 때문에, 거짓말 하지 않고 신뢰도 높은 답변을 제공해요. 물론 말이 달라질 걱정도 없죠!
              </div>
            </div>

            <p className="text-gray-400 text-xs mt-4 pl-1">
              *25년 OpenAI 공식 발표자료 기준
            </p>
          </div>

          <div className="w-full flex justify-center md:justify-end">
            <img 
              src="/landing/2p.png" 
              alt="서비스 예시 화면" 
              className="w-full h-auto object-contain"
            />
          </div>

        </div>
      </section>

      {/* 질문 예시 섹션 */}
      <section className="w-full py-24 bg-gray-50"> 
        <div className="max-w-4xl mx-auto px-6 text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-extrabold text-gray-900 mb-6 tracking-tight">
            무엇이든 물어보세요
          </h2>
          <p className="text-gray-600 text-lg md:text-xl leading-relaxed tracking-tight break-keep">
            입시요강, 작년 입결, 교육과정, 내 성적으로는 어디 갈 수 있지?<br className="hidden md:block" />
            복잡한 입시 고민들, 이제 5초만에 정확하게 확인하세요.
          </p>
        </div>

        <div className="max-w-6xl mx-auto px-6">
          <img 
            src="/landing/3p.png" 
            alt="다양한 질문 예시" 
            className="w-full h-auto block object-cover"
          />
        </div>
      </section>

      {/* CTA 섹션 */}
      <section className="w-full pt-32 pb-10 bg-white">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <span className="block text-teal-600 font-bold mb-5 tracking-wide text-sm md:text-base">
            무제한 무료
          </span>

          <h2 className="text-3xl md:text-5xl font-extrabold text-gray-900 leading-tight mb-8 tracking-tight break-keep">
            유니로드는<br className="md:hidden" />
            무료로 무제한 이용할 수 있어요
          </h2>

          <p className="text-gray-600 text-lg md:text-xl leading-relaxed tracking-tight break-keep mb-10">
            명문대 선배들이 수험생 여러분을 위해 직접 만들었습니다.<br className="hidden md:block" />
            공부하며 생기는 질문들, 고민들 언제든 부담 없이 물어보세요.
          </p>

          <div className="mb-4">
            <button
              onClick={handleStartClick}
              className="inline-block px-10 py-4 bg-teal-500 text-white font-bold text-xl rounded-full shadow-lg hover:bg-teal-600 transition-all transform hover:-translate-y-1 hover:shadow-xl"
            >
              무료로 이용하기
            </button>
          </div>
        </div>
      </section>

      {/* 로고 섹션 */}
      <div className="w-full pb-10 flex justify-center bg-white">
        <img 
          src="/landing/로고.png" 
          alt="UniRoad Logo" 
          className="h-16 w-auto object-contain opacity-90"
        />
      </div>
    </div>
  )
}

export default LandingPage
