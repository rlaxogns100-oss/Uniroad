import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const TEAM = [
  {
    name: '김태훈',
    role: 'CEO · 대표',
    desc: '제품 전략 · 사용자 문제 정의 · 사업 개발',
    experience: [
      '서울대학교 기계공학부 (21학번)',
      'AI 뉴스 비교 플랫폼 \'한누네\' 공동 창업',
      '에듀테크 플랫폼 창업 및 사업화 자금 1,500만원 유치',
      '서울대학교 벤처 네트워크 SNUSV 회원',
    ],
  },
  {
    name: '김도균',
    role: 'CTO · 기술총괄',
    desc: '멀티에이전트 RAG · 생기부 분석 파이프라인 설계·개발',
    experience: [
      '춘천시 빅데이터 분석 대회 대상 수상',
      '세븐일레븐 × 경희대 산학협력 데이터 프로젝트 수행',
      'Microsoft Agent Hackathon 대상 수상',
    ],
  },
]

const TIMELINE = [
  {
    week: '1주차',
    period: '1.10 ~ 1.17',
    items: ['RAG 기반 상담 아키텍처 설계·구축', '대학별 모집요강 검색 파이프라인 개발'],
  },
  {
    week: '2주차',
    period: '1.17 ~ 1.24',
    items: ['입시 상담 웹 서비스 프로토타입 완성', '초기 사용자 검증 및 반복 개선'],
  },
  {
    week: '3주차',
    period: '1.24 ~ 1.31',
    items: ['대학별 환산점수/입결 데이터 고도화', '공유형 상담 결과 기능 출시'],
  },
  {
    week: '4주차',
    period: '1.31 ~ 2.10',
    items: ['생기부 심층 분석 베타 고도화', '입시 상담 품질 지표 체계화'],
    current: true,
  },
]

function LandingPage() {
  const navigate = useNavigate()
  const [showSecurityFaq, setShowSecurityFaq] = useState(false)

  return (
    <div className="min-h-screen bg-white text-[#141414]">
      {/* ── 헤더 (퍼슬리 스타일 - 투명 / 비디오 위에 떠 있는 형태) ── */}
      <header className="absolute left-0 right-0 top-0 z-20">
        <div className="mx-auto flex max-w-[1100px] items-center justify-between px-6 py-5 sm:px-10 lg:px-16">
          <button onClick={() => navigate('/')} className="flex items-center">
            <img src="/uniroad-logo.png" alt="유니로드" className="h-6 w-auto brightness-0 invert sm:h-7" />
          </button>
          <nav className="hidden items-center gap-8 text-[14px] font-medium text-white/90 md:flex">
            <a href="#features" className="transition hover:text-white">서비스 소개</a>
            <button onClick={() => navigate('/chat')} className="transition hover:text-white">지금 시작하기</button>
            <a href="#trusted" className="transition hover:text-white">API/기업제휴 문의</a>
            <a href="#faq" className="transition hover:text-white">FAQ</a>
          </nav>
        </div>
      </header>

      <main>
        {/* ── 1. 히어로 (비디오 배경 + 폰 목업) ── */}
        <section className="relative min-h-[80vh] overflow-hidden sm:min-h-[88vh]">
          <video
            autoPlay
            loop
            muted
            playsInline
            className="absolute inset-0 h-full w-full object-cover"
          >
            <source src="/hero-bg.mp4" type="video/mp4" />
          </video>
          <div className="absolute inset-0 bg-gradient-to-r from-black/70 via-black/35 to-black/10" />

          <div className="relative z-10 flex min-h-[80vh] flex-col items-center justify-center px-6 pb-20 pt-28 text-center sm:min-h-[88vh] sm:px-8 lg:absolute lg:inset-0 lg:items-start lg:justify-center lg:px-8 lg:pb-16 lg:pt-28 lg:text-left xl:pl-[max(7vw,80px)]">
            <div className="lg:max-w-[55%]">
              <p className="mb-4 text-sm font-bold uppercase tracking-[0.2em] text-[#7cacff] sm:text-base">AI-Powered College Counseling</p>
              <h1 className="text-[44px] font-black leading-[1.08] tracking-[-0.03em] text-white sm:text-[64px] lg:text-[72px]">
                세상에서
                <br />
                가장 정확한
                <br />
                <span className="bg-gradient-to-r from-[#60a5fa] to-[#a78bfa] bg-clip-text text-transparent">입시 전문 AI</span>
              </h1>
              <p className="mt-5 max-w-[480px] text-[16px] font-medium leading-[1.7] text-white/80 sm:text-lg">
                200+ 대학 모집요강·입결 데이터 기반의 실시간 AI 입시 상담
              </p>
              <div className="mt-6 flex items-center justify-center gap-3 lg:justify-start">
                <div className="rounded-xl border border-amber-400/50 bg-amber-500/15 px-5 py-2.5 backdrop-blur-sm">
                  <p className="text-[15px] font-extrabold text-amber-300">2026 수시·정시 반영</p>
                </div>
              </div>
              <button
                onClick={() => navigate('/chat')}
                className="mt-10 w-fit rounded-full bg-gradient-to-b from-[#3b82f6] to-[#1d4ed8] px-10 py-5 text-lg font-bold text-white shadow-[0_4px_14px_rgba(29,78,216,0.4),0_2px_4px_rgba(0,0,0,0.08)] transition hover:from-[#2563eb] hover:to-[#1e40af] hover:shadow-[0_6px_20px_rgba(29,78,216,0.45)] active:shadow-[0_2px_8px_rgba(29,78,216,0.35)]"
              >
                지금 시작하기 →
              </button>
            </div>
            {/* 휴대폰: 작은 창에선 가운데, 큰 창에선 오른쪽 하단 */}
            <img
              src="/hero-phones.png"
              alt="유니로드 앱 화면"
              className="mt-10 h-[320px] w-auto self-center shrink-0 drop-shadow-[0_24px_48px_rgba(0,0,0,0.45)] sm:h-[380px] lg:absolute lg:bottom-0 lg:right-8 lg:mt-0 lg:h-[500px] lg:-translate-y-8 lg:self-auto xl:right-12 xl:h-[620px] xl:-translate-y-12"
            />
          </div>
        </section>

        {/* ── 1.5 문제 정의 + 목표 고객 ── */}
        <section className="bg-white py-24 sm:py-32">
          <div className="mx-auto max-w-[960px] px-6 lg:px-8">
            <div className="text-center">
              <p className="text-[15px] font-bold text-[#2d63f6]">우리가 해결하는 문제</p>
              <h2 className="mt-4 text-[32px] font-extrabold leading-[1.25] tracking-[-0.02em] text-[#0f172a] sm:text-[42px]">
                입시 정보는 넘쳐나는데,
                <br />
                정확한 답은 찾기 어렵습니다
              </h2>
              <p className="mx-auto mt-6 max-w-[680px] text-[16px] font-medium leading-[1.9] text-[#64748b]">
                대학별 모집요강은 해마다 수백 페이지씩 바뀌고, 입결 데이터는 출처마다 다릅니다.
                범용 AI에 물어보면 그럴듯하지만 틀린 답을 자신 있게 말합니다.
                유니로드는 이 문제를 <strong className="font-bold text-[#334155]">대학 공식 자료와 AI 기술</strong>로 해결합니다.
              </p>
            </div>

            <div className="mt-14 grid gap-6 sm:grid-cols-3">
              <div className="rounded-2xl bg-white p-7 text-center shadow-md">
                <span className="text-3xl">🎓</span>
                <p className="mt-3 text-lg font-bold text-[#0f172a]">수험생 · 재수생</p>
                <p className="mt-2 text-[15px] font-medium leading-relaxed text-[#64748b]">
                  복잡한 입결 계산, 지원 전략을 AI에게 물어보고 <strong className="font-bold text-[#334155]">빠르게 답</strong>을 얻으세요
                </p>
              </div>
              <div className="rounded-2xl bg-white p-7 text-center shadow-md">
                <span className="text-3xl">👨‍👩‍👧</span>
                <p className="mt-3 text-lg font-bold text-[#0f172a]">학부모</p>
                <p className="mt-2 text-[15px] font-medium leading-relaxed text-[#64748b]">
                  <strong className="font-bold text-[#334155]">출처가 명확한 데이터 기반</strong>의 상담으로 자녀의 입시를 함께 준비하세요
                </p>
              </div>
              <div className="rounded-2xl bg-white p-7 text-center shadow-md">
                <span className="text-3xl">🏫</span>
                <p className="mt-3 text-lg font-bold text-[#0f172a]">입시 컨설턴트</p>
                <p className="mt-2 text-[15px] font-medium leading-relaxed text-[#64748b]">
                  200+ 대학 데이터 검색과 <strong className="font-bold text-[#334155]">환산점수 자동 계산</strong>으로 상담 효율을 높이세요
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ── 2. 섹션: 공식 자료 기반 ── */}
        <section id="features" className="bg-white py-24 sm:py-32">
          <div className="mx-auto flex max-w-[1100px] flex-col items-center gap-14 px-6 lg:flex-row lg:items-center lg:gap-20 lg:px-8">
            <div className="flex-1 lg:max-w-[48%]">
              <p className="text-[15px] font-bold text-[#2d63f6]">대학 공식 자료 기반의 답변</p>
              <h2 className="mt-4 text-[32px] font-extrabold leading-[1.25] tracking-[-0.02em] text-[#0f172a] sm:text-[42px]">
                수백 개 대학의 모집요강·입결
                <br />
                데이터로 정답을 찾아드려요
              </h2>
              <p className="mt-6 text-[16px] font-medium leading-[1.85] text-[#64748b]">
                대학별 모집요강, 정시 배치표, 입결 자료 등 <strong className="font-bold text-[#334155]">공식 데이터를 AI가 교차 검증</strong>해 정확한 답변을 제공합니다.
                모든 답변에 <strong className="font-bold text-[#334155]">원문 출처</strong>가 함께 제공되어 신뢰할 수 있습니다.
              </p>
              <div className="mt-7 space-y-3.5">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#2d63f6] text-xs text-white">✓</span>
                  <span className="text-[15px] font-medium leading-[1.7] text-[#334155]">200+ 대학 모집요강·입결 데이터 실시간 반영</span>
                </div>
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#2d63f6] text-xs text-white">✓</span>
                  <span className="text-[15px] font-medium leading-[1.7] text-[#334155]">답변마다 원문 출처·근거 자료를 함께 표시</span>
                </div>
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#2d63f6] text-xs text-white">✓</span>
                  <span className="text-[15px] font-medium leading-[1.7] text-[#334155]">일반 AI처럼 지어내지 않고, 공식 자료에서 검색</span>
                </div>
              </div>
              <button
                onClick={() => navigate('/chat')}
                className="mt-10 w-fit rounded-full bg-gradient-to-b from-[#3b82f6] to-[#1d4ed8] px-9 py-4 text-[15px] font-bold text-white shadow-[0_3px_12px_rgba(29,78,216,0.35),0_1px_3px_rgba(0,0,0,0.06)] transition hover:from-[#2563eb] hover:to-[#1e40af] hover:shadow-[0_5px_16px_rgba(29,78,216,0.4)] active:shadow-[0_2px_6px_rgba(29,78,216,0.3)]"
              >
                지금 시작하기 →
              </button>
            </div>
            {/* 오른쪽: 폰 이미지 */}
            <div className="relative flex flex-1 justify-center lg:max-w-[48%]">
              <img
                src="/section2-phone.png"
                alt="유니로드 앱 - 내신 기반 지원 가능성 분석"
                className="w-full max-w-[380px] sm:max-w-[440px]"
              />
            </div>
          </div>
        </section>

        {/* ── 3. 섹션 B: 수험생 상황에 맞춘 답변 ── */}
        <section className="bg-white py-24 sm:py-32">
          <div className="mx-auto flex max-w-[1100px] flex-col gap-14 px-6 lg:flex-row lg:items-center lg:gap-16 lg:px-8">
            <div className="flex-1 lg:max-w-[48%]">
              <p className="text-[15px] font-bold text-[#2d63f6]">수험생의 상황에 맞춘 답변</p>
              <h2 className="mt-4 text-[32px] font-extrabold leading-[1.25] tracking-[-0.02em] text-[#0f172a] sm:text-[42px]">
                AI가 당신의 입시 정보를
                <br />
                기억해요
              </h2>
              <p className="mt-6 text-[16px] font-medium leading-[1.85] text-[#64748b]">
                ChatGPT는 서비스 목적 상 당신의 입시 정보를 기억하지 못해요.
                유니로드는 <strong className="font-bold text-[#334155]">당신의 성적, 지원 희망 대학까지 모두 기억</strong>해서,
                매번 처음부터 설명할 필요 없이 딱 맞춘 답변만 드려요!
              </p>
              <button
                onClick={() => navigate('/chat')}
                className="mt-10 w-fit rounded-full border-2 border-[#2d63f6] bg-white px-9 py-4 text-[15px] font-bold text-[#2d63f6] shadow-[0_2px_8px_rgba(45,99,246,0.15)] transition hover:bg-[#2d63f6] hover:text-white hover:shadow-[0_4px_14px_rgba(45,99,246,0.25)]"
              >
                지금 시작하기
              </button>
            </div>
            <div className="flex-1 lg:max-w-[48%]">
              <div className="space-y-6 rounded-2xl border-0 bg-white p-7 lg:p-9">
                <div className="flex justify-end">
                  <div className="rounded-2xl bg-[#f0fdf4] px-5 py-3 text-[15px] font-medium text-[#1e293b]">
                    내가 지원하려던 대학 합격선이 얼마였지?
                  </div>
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#f3f4f6]">
                    <svg className="h-6 w-6 text-[#9ca3af]" fill="currentColor" viewBox="0 0 24 24"><path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073z" /></svg>
                  </div>
                  <div>
                    <p className="text-[15px] font-bold text-[#374151]">ChatGPT</p>
                    <p className="mt-1 text-[15px] font-medium text-[#dc2626]">죄송합니다. 이전 대화 내용은 기억하지 않아요</p>
                  </div>
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#eef2ff]">
                    <img src="/uniroad-logo.png" alt="" className="h-6 w-6 object-contain mix-blend-multiply" />
                  </div>
                  <div>
                    <p className="text-[15px] font-bold text-[#374151]">유니로드</p>
                    <p className="mt-1 text-[15px] font-medium text-[#059669]">고려대 기계공학부 적정컷 660.84점이었어요!</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── 4. 섹션 D: 생기부·성적표 분석 ── */}
        <section className="bg-white py-24 sm:py-32">
          <div className="mx-auto max-w-[1100px] px-6 lg:px-8">
            <div className="max-w-[620px]">
              <p className="text-[15px] font-bold text-[#2d63f6]">생기부 연동 · 세특 분석</p>
              <h2 className="mt-4 text-[32px] font-extrabold leading-[1.25] tracking-[-0.02em] text-[#0f172a] sm:text-[42px]">
                생기부를 올리면,
                <br />
                AI가 알아서 분석해요
              </h2>
              <p className="mt-6 text-[16px] font-medium leading-[1.85] text-[#64748b]">
                생기부와 성적 데이터를 연동하면, <strong className="font-bold text-[#334155]">세특 적합성 평가</strong>부터
                <strong className="font-bold text-[#334155]">추천 모집단위·지원 전략</strong>까지 한 번에 받아볼 수 있어요.
                복잡한 내용을 쉽게 풀어드립니다.
              </p>
            </div>

            <div className="mt-14 grid gap-10 sm:grid-cols-2">
              <div className="flex flex-col items-center">
                <div className="overflow-hidden rounded-2xl">
                  <img
                    src="/section-sidebar.png"
                    alt="유니로드 사이드바 - 입시 기록 관리"
                    className="w-full max-w-[320px]"
                  />
                </div>
                <div className="mt-5 text-center">
                  <p className="text-[16px] font-bold text-[#0f172a]">간편한 생기부·성적 연동</p>
                  <p className="mt-1 text-[14px] font-medium text-[#64748b]">사이드바에서 클릭 한 번으로 데이터 연동</p>
                </div>
              </div>
              <div className="flex flex-col items-center">
                <div className="overflow-hidden rounded-2xl">
                  <img
                    src="/section-analysis.png"
                    alt="유니로드 세특 분석 결과"
                    className="w-full max-w-[320px]"
                  />
                </div>
                <div className="mt-5 text-center">
                  <p className="text-[16px] font-bold text-[#0f172a]">세특 적합성 + 추천 모집단위</p>
                  <p className="mt-1 text-[14px] font-medium text-[#64748b]">AI가 분석한 결과를 한눈에 확인</p>
                </div>
              </div>
            </div>

            <button
              onClick={() => navigate('/chat')}
              className="mt-12 w-fit rounded-full bg-gradient-to-b from-[#3b82f6] to-[#1d4ed8] px-9 py-4 text-[15px] font-bold text-white shadow-[0_3px_12px_rgba(29,78,216,0.35),0_1px_3px_rgba(0,0,0,0.06)] transition hover:from-[#2563eb] hover:to-[#1e40af] hover:shadow-[0_5px_16px_rgba(29,78,216,0.4)]"
            >
              지금 분석받기 →
            </button>
          </div>
        </section>

        {/* ── 5. 3중 보안/신뢰 ── */}
        <section className="bg-[#eff6ff] py-28 sm:py-36">
          <div className="mx-auto max-w-[1000px] px-6 lg:px-8">
            <div className="flex flex-col items-center text-center">
              <div className="team-avatar-pulse flex h-28 w-28 shrink-0 items-center justify-center rounded-full bg-[#2d63f6] shadow-lg shadow-[#2d63f6]/30 sm:h-32 sm:w-32">
                <svg className="h-12 w-12 text-white sm:h-14 sm:w-14" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
                </svg>
              </div>
              <p className="mt-7 text-[15px] font-extrabold text-[#2d63f6]">3중 보안 원칙</p>
              <h2 className="mt-4 text-[32px] font-extrabold leading-[1.25] tracking-[-0.02em] text-[#0f172a] sm:text-[42px]">
                민감한 입시 정보, 철저한 3중 보안
              </h2>
              <p className="mt-5 max-w-[620px] text-[16px] font-medium leading-[1.85] text-[#475569]">
                <strong className="font-bold text-[#334155]">접근 통제, 안전 저장, 강력한 사용자 통제 권한</strong>이라는 철저한 3중 보안 원칙으로 운영됩니다.
              </p>
            </div>

            <div className="mt-16 grid gap-8 md:grid-cols-3">
              <article className="rounded-2xl bg-white p-8 shadow-md">
                <div className="flex items-center gap-4">
                  <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-[#2d63f6]">
                    <svg className="h-7 w-7 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
                    </svg>
                  </div>
                  <div>
                    <span className="text-xs font-extrabold text-[#2d63f6]">1st</span>
                    <h3 className="text-xl font-extrabold text-[#0f172a]">접근 통제</h3>
                  </div>
                </div>
                <p className="mt-5 text-[15px] font-medium leading-[1.75] text-[#475569]">
                  사용자의 대화·업로드 정보는 개인 식별 정보와 철저히 분리되어 저장되며, 권한 있는 최소한의 인원만이 확인 가능하도록 통제됩니다.
                </p>
              </article>
              <article className="rounded-2xl bg-white p-8 shadow-md">
                <div className="flex items-center gap-4">
                  <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-[#2d63f6]">
                    <svg className="h-7 w-7 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
                    </svg>
                  </div>
                  <div>
                    <span className="text-xs font-extrabold text-[#2d63f6]">2nd</span>
                    <h3 className="text-xl font-extrabold text-[#0f172a]">안전 저장</h3>
                  </div>
                </div>
                <p className="mt-5 text-[15px] font-medium leading-[1.75] text-[#475569]">
                  <strong className="text-[#0f172a]">유니로드</strong>는 모든 전송·저장 과정을 철저한 보안 조치를 통해 관리합니다. 모든 개인정보는 외부에 무단 공개되지 않습니다.
                </p>
              </article>
              <article className="rounded-2xl bg-white p-8 shadow-md">
                <div className="flex items-center gap-4">
                  <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-[#2d63f6]">
                    <svg className="h-7 w-7 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25a3 3 0 0 1 3 3m3 0a6 6 0 0 1-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1 1 21.75 8.25Z" />
                    </svg>
                  </div>
                  <div>
                    <span className="text-xs font-extrabold text-[#2d63f6]">3rd</span>
                    <h3 className="text-xl font-extrabold text-[#0f172a]">강력한 사용자 통제</h3>
                  </div>
                </div>
                <p className="mt-5 text-[15px] font-medium leading-[1.75] text-[#475569]">
                  사용자는 언제든 대화·업로드 기록 삭제를 요청할 수 있습니다. 개인정보 활용 동의 및 범위도 언제든 변경하거나 철회할 수 있습니다.
                </p>
              </article>
            </div>

            <div className="mt-14 flex flex-col items-center gap-4">
              <button
                type="button"
                className="rounded-full border-2 border-[#2d63f6] bg-white px-10 py-4 text-[16px] font-bold text-[#2d63f6] shadow-[0_2px_8px_rgba(45,99,246,0.15)] transition hover:bg-[#2d63f6] hover:text-white hover:shadow-[0_4px_14px_rgba(45,99,246,0.25)]"
                onClick={() => setShowSecurityFaq(true)}
              >
                보안 FAQ 더 보기
              </button>
              <button
                onClick={() => navigate('/chat')}
                className="rounded-full bg-gradient-to-b from-[#3b82f6] to-[#1d4ed8] px-10 py-4 text-[16px] font-bold text-white shadow-[0_3px_12px_rgba(29,78,216,0.35)] transition hover:from-[#2563eb] hover:to-[#1e40af] hover:shadow-[0_5px_16px_rgba(29,78,216,0.4)]"
              >
                지금 시작하기 →
              </button>
            </div>
          </div>
        </section>

        {/* 보안 FAQ 모달 */}
        {showSecurityFaq && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
            onClick={() => setShowSecurityFaq(false)}
            role="dialog"
            aria-modal="true"
            aria-labelledby="security-faq-title"
          >
            <div
              className="relative max-h-[85vh] w-full max-w-[560px] overflow-y-auto rounded-2xl bg-white p-8 shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between">
                <h2 id="security-faq-title" className="text-2xl font-extrabold text-[#111827]">보안 FAQ</h2>
                <button
                  type="button"
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-[#f3f4f6] text-[#6b7280] transition hover:bg-[#e5e7eb]"
                  onClick={() => setShowSecurityFaq(false)}
                  aria-label="닫기"
                >
                  <span className="text-lg font-bold">×</span>
                </button>
              </div>

              <div className="mt-8 space-y-4">
                <div className="rounded-xl bg-[#f6f6f6] p-5">
                  <p className="text-base font-bold text-[#111827]">Q. 내 데이터를 학습하거나 판매하나요?</p>
                  <p className="mt-3 text-[15px] font-medium leading-[1.7] text-[#666666]">
                    유니로드는 절대로 사용자의 동의 없이 개인 정보 및 데이터를 외부에 공유하거나 판매하지 않습니다.
                    AI의 학습에 사용될지 여부는 철저히 사용자가 선택할 수 있습니다.
                    데이터의 활용 범위는 모두 개인정보처리방침에 공개되어 있습니다.
                  </p>
                </div>
                <div className="rounded-xl bg-[#f6f6f6] p-5">
                  <p className="text-base font-bold text-[#111827]">Q. 내 데이터를 삭제할 수 있나요?</p>
                  <p className="mt-3 text-[15px] font-medium leading-[1.7] text-[#666666]">
                    네, 당연하죠. 사용자는 언제든 고객센터 삭제 요청을 통해 본인의 대화·업로드 기록의 삭제를 요청할 수 있습니다.
                  </p>
                </div>
                <div className="rounded-xl bg-[#f6f6f6] p-5">
                  <p className="text-base font-bold text-[#111827]">Q. 운영자가 내 질문을 볼 수 있나요?</p>
                  <p className="mt-3 text-[15px] font-medium leading-[1.7] text-[#666666]">
                    아니요. 서비스 운영 및 고객 CS에 반드시 필요한 경우에만 권한을 가진 최소한의 인원이 확인합니다.
                  </p>
                </div>
              </div>

              <button
                type="button"
                className="mt-8 w-full rounded-full bg-gradient-to-b from-[#3b82f6] to-[#1d4ed8] py-4 text-base font-bold text-white shadow-[0_3px_12px_rgba(29,78,216,0.35)] transition hover:from-[#2563eb] hover:to-[#1e40af] hover:shadow-[0_5px_16px_rgba(29,78,216,0.4)]"
                onClick={() => setShowSecurityFaq(false)}
              >
                닫기
              </button>
            </div>
          </div>
        )}

        {/* ── 7. 팀 소개 ── */}
        <section className="bg-white py-24 sm:py-32">
          <div className="mx-auto max-w-[1000px] px-6 lg:px-8">
            <div className="text-center">
              <p className="text-[15px] font-bold text-[#2d63f6]">팀 소개</p>
              <h2 className="mt-4 text-[32px] font-extrabold leading-[1.25] tracking-[-0.02em] text-[#0f172a] sm:text-[42px]">
                AI 기술과 교육 도메인을 가진 팀,
                <br />
                단 1개월 만에 서비스를 만든 팀
              </h2>
              <p className="mx-auto mt-6 max-w-[640px] text-[16px] font-medium leading-[1.85] text-[#64748b]">
                2026년 1월 10일부터 2월 10일까지, <strong className="font-bold text-[#334155]">단 30일 만에
                아이디어부터 서비스 출시까지</strong> 완성한 팀입니다.
              </p>
            </div>

            <div className="mt-14 grid gap-8 md:grid-cols-2">
              {TEAM.map((member) => (
                <article key={member.name} className="rounded-2xl bg-[#f8fafc] p-7 shadow-md">
                  <div className="flex items-center gap-4">
                    <div className="team-avatar-pulse flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-[#2d63f6] text-xl font-bold text-white">
                      {member.name[0]}
                    </div>
                    <div>
                      <p className="text-xl font-bold text-[#0f172a]">{member.name}</p>
                      <p className="text-[14px] font-semibold text-[#2d63f6]">{member.role}</p>
                    </div>
                  </div>
                  <p className="mt-4 text-[15px] font-bold text-[#334155]">{member.desc}</p>
                  <ul className="mt-4 space-y-2">
                    {member.experience.map((exp) => (
                      <li key={exp} className="flex items-start gap-2 text-[14px] font-bold leading-relaxed text-[#475569]">
                        <span className="mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[#94a3b8]" />
                        {exp}
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ── 8.5 제품 소개 + 개발 단계 ── */}
        <section className="bg-white py-24 sm:py-32">
          <div className="mx-auto max-w-[1000px] px-6 lg:px-8">
            <div className="flex flex-col gap-16 lg:flex-row lg:items-start">
              <div className="flex-1">
                <p className="text-[15px] font-bold text-[#2d63f6]">제품 소개</p>
                <h2 className="mt-4 text-[32px] font-extrabold leading-[1.25] tracking-[-0.02em] text-[#0f172a] sm:text-[40px]">
                  RAG 기반 AI 입시 상담 웹 서비스
                </h2>
                <p className="mt-6 text-[16px] font-medium leading-[1.85] text-[#64748b]">
                  유니로드는 <strong className="font-bold text-[#334155]">200+ 대학의 모집요강·입결 데이터</strong>를 실시간으로 검색하고,
                  수험생의 성적·생기부를 분석해 <strong className="font-bold text-[#334155]">맞춤형 입시 상담</strong>을 제공하는
                  RAG 기반 AI 웹 서비스입니다.
                </p>
                <div className="mt-7 space-y-3.5">
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#2d63f6] text-xs text-white">✓</span>
                    <span className="text-[15px] font-medium leading-[1.7] text-[#334155]">대학별 모집요강·입결 RAG 검색 파이프라인</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#2d63f6] text-xs text-white">✓</span>
                    <span className="text-[15px] font-medium leading-[1.7] text-[#334155]">생기부·세특 심층 분석 및 모집단위 추천</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#2d63f6] text-xs text-white">✓</span>
                    <span className="text-[15px] font-medium leading-[1.7] text-[#334155]">수험생 컨텍스트 기억 기반 개인화 상담</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#2d63f6] text-xs text-white">✓</span>
                    <span className="text-[15px] font-medium leading-[1.7] text-[#334155]">대학별 환산점수 자동 계산 엔진</span>
                  </div>
                </div>
                <div className="mt-8 inline-flex items-center gap-2 rounded-full bg-[#059669]/10 px-5 py-2.5">
                  <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-[#059669]" />
                  <span className="text-[14px] font-bold text-[#059669]">현재: 서비스 운영 중 · 베타 고도화</span>
                </div>
              </div>

              <div className="flex-1 lg:max-w-[400px]">
                <div className="team-avatar-pulse mb-5 rounded-xl bg-[#2d63f6] px-5 py-3 text-center">
                  <p className="text-lg font-black text-white">2026.01.10 → 02.10</p>
                  <p className="text-sm font-extrabold text-white">단 30일간의 개발 타임라인</p>
                </div>
                <div className="space-y-4">
                  {TIMELINE.map((t, i) => (
                    <div key={t.week} className={`rounded-2xl border-2 p-5 ${t.current ? 'border-[#2d63f6] bg-white shadow-lg' : 'border-[#e2e8f0] bg-white'}`}>
                      <div className="flex items-center gap-3">
                        <span className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-black ${t.current ? 'bg-[#2d63f6] text-white' : 'bg-[#e2e8f0] text-[#64748b]'}`}>{i + 1}</span>
                        <div>
                          <p className="text-lg font-black text-[#0f172a]">{t.week}</p>
                          <p className="text-xs font-bold text-[#94a3b8]">{t.period}</p>
                        </div>
                        {t.current && (
                          <span className="ml-auto rounded-full bg-[#2d63f6] px-3 py-1 text-xs font-bold text-white">NOW</span>
                        )}
                      </div>
                      <ul className="mt-3 space-y-1.5">
                        {t.items.map((item) => (
                          <li key={item} className="text-[14px] font-medium leading-relaxed text-[#475569]">• {item}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── 9. 푸터 CTA ── */}
        <section className="bg-white py-20 text-center sm:py-28">
          <div className="mx-auto max-w-[600px] px-6">
            <h2 className="text-[32px] font-extrabold tracking-[-0.02em] text-[#0f172a] sm:text-[42px]">
              지금 바로 시작하기
            </h2>
            <p className="mt-4 text-[16px] font-medium leading-relaxed text-[#64748b]">
              질문 하나로 연결되는 <strong className="font-bold text-[#334155]">AI 입시 상담</strong>, 유니로드를 경험해 보세요.
            </p>
            <div className="mt-9 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
              <button
                onClick={() => navigate('/chat')}
                className="rounded-full bg-gradient-to-b from-[#3b82f6] to-[#1d4ed8] px-10 py-4 text-[16px] font-bold text-white shadow-[0_3px_12px_rgba(29,78,216,0.35)] transition hover:from-[#2563eb] hover:to-[#1e40af] hover:shadow-[0_5px_16px_rgba(29,78,216,0.4)]"
              >
                지금 시작하기
              </button>
              <a
                href="mailto:uni2road@gmail.com"
                className="rounded-full border-2 border-[#2d63f6] bg-white px-9 py-4 text-[16px] font-semibold text-[#2d63f6] transition hover:bg-[#eff6ff]"
              >
                제휴/문의
              </a>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

export default LandingPage
