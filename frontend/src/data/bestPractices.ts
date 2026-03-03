/** 전공 계열 (입학사정관 관점) */
export type MajorCategory =
  | '인문 사회 교육 계열'
  | '자연 공학 IT 계열'
  | '의학 생명 환경 계열'

/** 4단계 필승구조 단계 키 */
export type StepKey = '계기' | '심화' | '역량' | '변화'

/** 4단계 하이라이트용 — content 내 해당 문장(quote)이 어떤 단계인지 */
export type StepHighlight = { step: StepKey; quote: string }

export type BestPracticeType = {
  category: MajorCategory
  major: string
  subject: string
  book: string
  content: string
  keyPoint: string
  /** 4단계(계기/심화/역량/변화) 구간 하이라이트. content에서 quote 문자열 위치로 표시 */
  stepHighlights?: StepHighlight[]
}

/** 키(Key)값은 컴포넌트에서 호출할 때 사용할 ID입니다. */
export const BEST_PRACTICES: Record<string, BestPracticeType> = {
  // =========================================================
  // 1. 인문/사회/교육 계열
  // =========================================================
  management: {
    category: '인문 사회 교육 계열',
    major: '경영·경제학과',
    subject: '수학 I (지수/로그함수)',
    book: '부의 시나리오(오건영)',
    content:
      '수업 시간 지수함수와 로그함수를 학습하며 복리 계산의 원리를 이해함. 이후 『부의 시나리오(오건영)』를 읽으며 금리 변동이 시장 경제에 미치는 영향에 호기심을 가짐. 이를 바탕으로 인플레이션율에 따른 실질 구매력의 지수함수적 감소를 수식화하여 보고서를 작성함.',
    keyPoint:
      '경제 현상을 수학적 모델(지수함수)로 연결하고, 보고서라는 구체적 산출물을 제시하여 데이터 문해력을 증명함.',
  },
  sociology: {
    category: '인문 사회 교육 계열',
    major: '정치·외교·사회학과',
    subject: '사회문화 (사회 불평등)',
    book: '정의란 무엇인가(마이클 샌델)',
    content:
      '사회 불평등 현상 학습 중 디지털 격차가 정보 불평등으로 이어지는 현상에 주목함. 『정의란 무엇인가(마이클 샌델)』를 읽고 능력주의의 한계와 공동체적 정의에 대해 고민함. 이후 노년층의 키오스크 이용률 실태 조사를 직접 수행하고, 이를 해결하기 위한 지자체 정책의 실효성을 비판적으로 분석하여 정책 대안을 제시함.',
    keyPoint:
      '사회 현상(디지털 격차)을 철학적 사유와 연결하고, 직접 설문조사를 수행하여 해결책까지 제안하는 완결성.',
  },
  /** 심화영어 I — 서울대 정치외교학과 합격 생기부 예시 (Soft Power) */
  politicalEnglish: {
    category: '인문 사회 교육 계열',
    major: '정치·외교·사회학과',
    subject: '심화영어 I',
    book: 'Academic Essay, CNN·Times 등 영자 신문',
    content:
      "6단원 'Different Perspectives'를 학습하며 개인의 관점과 가치관의 형성에는 소속집단의 문화와 관습이 영향을 미침을 이해하고, 평소 국제정치에 관심이 많은 학생으로서 현대 글로벌 사회에서 국력을 증강시키기 위해서는 국제적으로 우호적인 이미지를 형성하는 것이 중요할 것이라고 예상함. 가설의 확인을 위해 academic essay를 읽고 최근 군사력, 경제력, 자원 등 'Hard Power (경성권력)'과 대비되는 개념으로서 'Soft Power (연성권력)'이 실제로 학계에서 더욱 강조되고 있음을 알게 됨. 이를 기반으로 'CNN', 'Times' 등 영자 신문 사이트에서 한국과 관련된 기사와 독자 반응을 스크랩하여 미국사회에서 한국이 갖는 이미지를 파악하고자 했으며 그 과정에서 K-POP, K-드라마 등 한국문화콘텐츠의 흥행으로 미국언론에서 한국문화를 긍정적으로 인식한다는 것을 알게 됨. 스크랩한 내용을 예시로 포함하여 'The Growth of South Korean Soft Power'라는 보고서를 작성하고 유창한 영어로 발표함. 'Soft Power'는 국력을 결정하는 데 무력만큼이나 중요한 요소임을 깨닫고 한국의 'Soft Power' 증강은 'Hard Power' 차원의 한계를 극복하는 전략이 될 수 있다고 제안함.",
    keyPoint:
      '국제정치 현상에 대한 비판적 이해를 바탕으로 학술적 연구(Soft Power 분석)와 영어 보고서 작성을 통해 탐구 역량과 심화된 지적 호기심을 증명하고, 전략적 대안을 제시함.',
    stepHighlights: [
      {
        step: '계기',
        quote:
          "6단원 'Different Perspectives'를 학습하며 개인의 관점과 가치관의 형성에는 소속집단의 문화와 관습이 영향을 미침을 이해하고, 평소 국제정치에 관심이 많은 학생으로서 현대 글로벌 사회에서 국력을 증강시키기 위해서는 국제적으로 우호적인 이미지를 형성하는 것이 중요할 것이라고 예상함.",
      },
      {
        step: '심화',
        quote:
          "가설의 확인을 위해 academic essay를 읽고 최근 군사력, 경제력, 자원 등 'Hard Power (경성권력)'과 대비되는 개념으로서 'Soft Power (연성권력)'이 실제로 학계에서 더욱 강조되고 있음을 알게 됨. 이를 기반으로 'CNN', 'Times' 등 영자 신문 사이트에서 한국과 관련된 기사와 독자 반응을 스크랩하여 미국사회에서 한국이 갖는 이미지를 파악하고자 했으며 그 과정에서 K-POP, K-드라마 등 한국문화콘텐츠의 흥행으로 미국언론에서 한국문화를 긍정적으로 인식한다는 것을 알게 됨.",
      },
      {
        step: '역량',
        quote:
          "스크랩한 내용을 예시로 포함하여 'The Growth of South Korean Soft Power'라는 보고서를 작성하고 유창한 영어로 발표함.",
      },
      {
        step: '변화',
        quote:
          "'Soft Power'는 국력을 결정하는 데 무력만큼이나 중요한 요소임을 깨닫고 한국의 'Soft Power' 증강은 'Hard Power' 차원의 한계를 극복하는 전략이 될 수 있다고 제안함.",
      },
    ],
  },
  education: {
    category: '인문 사회 교육 계열',
    major: '교육·교대',
    subject: '국어 (매체 비판적 읽기)',
    book: '언어의 온도(이기주)',
    content:
      '매체 비판적 읽기 단원에서 청소년 언어 파괴 현상을 접함. 『언어의 온도(이기주)』를 읽으며 언어가 인간관계와 정서 발달에 미치는 영향을 성찰함. 이를 교육적 관점으로 풀어내어 비속어 사용이 자아 존중감에 미치는 영향 설문조사를 실시하고, 올바른 언어 습관 형성을 위한 에듀테크 활용 수업 지도안을 직접 설계함.',
    keyPoint:
      "단순한 문제 인식을 넘어 '수업 지도안'이라는 예비 교사로서의 실무적 역량을 보여주는 산출물 제작.",
  },

  // =========================================================
  // 2. 자연/공학/IT 계열
  // =========================================================
  cs: {
    category: '자연 공학 IT 계열',
    major: '컴퓨터공학·IT',
    subject: '정보 (알고리즘)',
    book: '알고리즘, 인생을 계산하다',
    content:
      '수업 중 정렬 알고리즘의 원리를 배우고, 『알고리즘, 인생을 계산하다』를 읽으며 알고리즘의 효율성이 실생활의 결정 구조에 미치는 영향을 학습함. 이를 응용하여 데이터 양에 따른 처리 속도 차이를 파이썬 코딩으로 구현하여 시각화함. 시행착오 과정에서 발생한 런타임 에러를 디버깅하며 공학적 끈기를 보여줌.',
    keyPoint:
      "구체적인 언어(파이썬) 사용과 '런타임 에러 디버깅'이라는 시행착오 과정(Problem Solving)이 핵심.",
  },
  engineering: {
    category: '자연 공학 IT 계열',
    major: '기계·전자공학',
    subject: '물리 (전자기 유도)',
    book: '도구와 기계의 원리',
    content:
      '전자기 유도 원리를 학습하고 무선 충전 기술의 효율성에 의문을 가짐. 『도구와 기계의 원리』를 통해 기계 메커니즘을 파악함. 이후 아두이노와 코일을 활용해 거리 및 각도에 따른 전력 전송 효율 실험을 설계함. 전압 손실 문제를 옴의 법칙을 적용하여 저항값을 재계산함으로써 해결하는 등 문제 해결 역량을 입증함.',
    keyPoint:
      '이론(옴의 법칙)을 실제 실험(아두이노)에 적용하여 문제를 해결한 엔지니어링 역량 부각.',
  },
  chemistry: {
    category: '자연 공학 IT 계열',
    major: '화학·신소재공학',
    subject: '화학 (화학 결합)',
    book: '세상은 온통 화학이다',
    content:
      '화학 결합 단원에서 탄소 동소체에 매료됨. 『세상은 온통 화학이다』를 읽고 그래핀의 상용화 난제를 조사함. 나노 소재의 특성을 화학적 공유 결합 관점에서 분석하고, 이를 대체할 수 있는 차세대 신소재의 가능성을 화학적 평형 이론과 결합하여 보고서로 정리함.',
    keyPoint:
      '교과 개념(공유 결합, 화학 평형)을 심화된 소재(그래핀, 신소재)와 논리적으로 연결함.',
  },

  // =========================================================
  // 3. 의학/생명/환경 계열
  // =========================================================
  medical: {
    category: '의학 생명 환경 계열',
    major: '의예·생명과학',
    subject: '생명과학 (유전)',
    book: '제3의 과학 혁명, 유전자 편집',
    content:
      '유전 단원에서 유전자 편집 기술의 가능성을 접함. 『제3의 과학 혁명, 유전자 편집』을 읽고 크리스퍼 가위의 메커니즘과 오프타겟 효과의 위험성을 탐구함. 이후 유전자 치료의 윤리적 가이드라인에 대한 토론 입론서를 작성하여, 과학적 발전과 생명 윤리가 양립해야 함을 논리적으로 설득함.',
    keyPoint:
      "최신 기술(크리스퍼)의 원리 이해뿐만 아니라 '윤리적 고찰'을 통해 균형 잡힌 의료인 자질을 보여줌.",
  },
  pharmacy: {
    category: '의학 생명 환경 계열',
    major: '약학·화학',
    subject: '화학 (산과 염기)',
    book: '약은 어떻게 작용하는가',
    content:
      '산과 염기 수업 중 약물의 체내 흡수율과 pH 농도의 상관관계에 호기심을 가짐. 『약은 어떻게 작용하는가』를 읽고 약물이 수용체와 결합하는 화학적 원리를 학습함. 완충 용액의 원리를 활용해 약물이 서서히 방출되는 서방형 제제의 기전을 실험적으로 증명하고 약학적 기초 지식에 대한 탐구 의지를 드러냄.',
    keyPoint:
      "단순 호기심을 넘어 '서방형 제제 실험'이라는 구체적 탐구로 연결한 실행력이 돋보임.",
  },
  environment: {
    category: '의학 생명 환경 계열',
    major: '환경·지구과학',
    subject: '지구과학 (대기와 해양)',
    book: '6도의 멸종',
    content:
      '대기와 해양의 상호작용 단원에서 기후 변화에 주목함. 『6도의 멸종』을 읽고 기온 상승에 따른 해류 변화 시나리오를 분석함. 탄소 포집 기술(CCS)의 지질학적 저장 가능성을 조사하며, 지속 가능한 에너지 전환 정책에 대한 자신의 견해를 학술적으로 서술함.',
    keyPoint:
      '거시적 현상(기후 변화)을 기술적 대안(CCS)과 정책적 견해로 구체화하여 학술적 깊이를 증명함.',
  },
}

const CATEGORY_ORDER: MajorCategory[] = [
  '인문 사회 교육 계열',
  '자연 공학 IT 계열',
  '의학 생명 환경 계열',
]

/** 전공 계열에 해당하는 S등급 사례 목록 반환 (첫 번째는 대표 사례) */
export function getPracticesForCategory(category: MajorCategory | string): BestPracticeType[] {
  return Object.values(BEST_PRACTICES).filter((p) => p.category === category)
}

/** 해당 계열의 대표 사례 1건 반환 (카드에 노출용) */
export function getRepresentativePractice(category: MajorCategory | string): BestPracticeType | null {
  const list = getPracticesForCategory(category)
  return list.length > 0 ? list[0] : null
}

/**
 * 희망 전공 없이 보여줄 기본 추천 사례.
 * 심화영어 I / 정치외교(Soft Power) 사례 — 서울대 합격 생기부 예시.
 */
export function getDefaultPractice(): BestPracticeType {
  return BEST_PRACTICES.politicalEnglish
}

/**
 * 희망 전공 텍스트에서 전공 계열 추론 (키워드 매칭).
 * 매칭 실패 시 null 반환.
 */
export function getMajorCategoryFromHopeMajor(hopeMajor: string): MajorCategory | null {
  const t = hopeMajor.trim().toLowerCase()
  if (!t) return null
  // 의학·약학·생명·환경
  if (
    /의(예|과)|약학|생명|환경|지구과학|간호|수의|한의|치의|의료|보건|바이오/.test(t)
  )
    return '의학 생명 환경 계열'
  // 자연·공학·IT
  if (
    /컴퓨터|공학|기계|전자|전기|화학|물리|수학|IT|소프트웨어|정보통신|신소재|건축|항공/.test(t)
  )
    return '자연 공학 IT 계열'
  // 인문·사회·교육
  if (
    /경영|경제|사회|정치|외교|교육|국어|영어|사학|철학|심리|언론|문헌|교대/.test(t)
  )
    return '인문 사회 교육 계열'
  return null
}

export { CATEGORY_ORDER }
