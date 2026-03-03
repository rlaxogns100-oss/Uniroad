export type GuideUserType = 'student' | 'graduate'
export type GuideMethodId = 'kakao' | 'naver' | 'gov24'

export interface GuideStep {
  title: string
  description: string
  image?: string
  warning?: string
}

export interface GuideSection {
  title: string
  summary?: string
  steps: GuideStep[]
}

export interface GuideMethod {
  id: GuideMethodId
  label: string
  short: string
  links?: Array<{ label: string; href: string }>
  sections: GuideSection[]
}

export const guideUserTypeTabs: Array<{ id: GuideUserType; label: string }> = [
  { id: 'student', label: '재학생' },
  { id: 'graduate', label: '졸업생' },
]

const APP_LINKS = {
  gov24Android: 'https://play.google.com/store/apps/details?id=kr.go.minwon.m&hl=ko&gl=US',
  gov24Ios: 'https://apps.apple.com/kr/app/%EC%A0%95%EB%B6%8024-%EA%B5%AC-%EB%AF%BC%EC%9B%9024/id586454505',
}

const toStep = (title: string, description: string, image?: string, warning?: string): GuideStep => ({
  title,
  description,
  image,
  warning,
})

const uploadStepsDefault = [
  toStep(
    '저장 방식 선택',
    '발급된 화면에서 저장하기를 누르고 비밀번호 설정 없이 저장하기를 선택하세요.',
    '/guide/student_pdfguide_step1.png'
  ),
  toStep(
    '휴대폰에 파일 저장',
    'iOS는 파일에 저장, 안드로이드는 내 파일 앱에 자동 저장됩니다.',
    '/guide/student_pdfguide_step2.png'
  ),
  toStep(
    '파일 업로드',
    '생활기록부 연동 페이지에서 업로드 버튼으로 저장한 파일을 등록하면 완료됩니다.'
  ),
]

export const getStudentGuideMethods = (userType: GuideUserType): GuideMethod[] => {
  const isGraduate = userType === 'graduate'
  const graduateSchoolText = isGraduate ? '졸업한 중학교명' : '학교명'
  const naverIssueText = isGraduate
    ? '학교생활기록부(초중고)를 선택하고 졸업한 중학교를 입력하면 발급됩니다.'
    : '학교생활기록부(초중고)를 선택하면 학교생활기록부가 발급됩니다.'

  return [
    {
      id: 'kakao',
      label: '카카오톡 앱',
      short: '재학생/졸업생',
      sections: [
        {
          title: '1단계. 학교생활기록부 발급하기',
          summary: '카카오톡 지갑 > 발견 > 학교생활기록부(초중고) 순서로 진행합니다.',
          steps: [
            toStep(
              '카카오톡에서 지갑 메뉴 선택',
              '카카오톡 더보기에서 지갑을 누른 뒤, 발견 메뉴로 이동하세요.',
              '/guide/student_kakaoguide_step1.png'
            ),
            toStep(
              '학교생활기록부(초중고) 선택',
              '전자증명서 목록에서 학교생활기록부(초중고)를 선택하세요.',
              '/guide/student_kakaoguide_step2.png'
            ),
            toStep(
              '신청내용 입력',
              `${isGraduate ? '졸업한 중학교' : '출신 고등학교'} 정보를 입력하고 인증 후 신청하기를 누르세요.`,
              '/guide/student_kakaoguide_step3.png'
            ),
          ],
        },
        {
          title: '2단계. 파일로 업로드하기',
          summary: '문서열람번호 방식은 제외하고, 파일 저장 후 업로드만 사용합니다.',
          steps: uploadStepsDefault,
        },
      ],
    },
    {
      id: 'naver',
      label: '네이버 앱',
      short: '재학생/졸업생',
      sections: [
        {
          title: '1단계. 학교생활기록부 발급하기',
          steps: [
            toStep(
              '더보기 탭 진입',
              '네이버 모바일 앱을 열고 더보기 탭으로 이동하세요.',
              '/guide/student_naverguide_step1.png'
            ),
            toStep(
              '전자증명서 선택',
              '메뉴에서 전자증명서를 선택하세요.',
              '/guide/student_naverguide_step2.png'
            ),
            toStep(
              '학교생활기록부(초중고) 발급',
              naverIssueText,
              '/guide/student_naverguide_step3.png'
            ),
          ],
        },
        {
          title: '2단계. 파일로 업로드하기',
          summary: '문서열람번호 방식은 제외하고, 저장된 파일 업로드만 사용합니다.',
          steps: [
            toStep(
              '저장 방식 선택',
              '발급 화면에서 저장을 누른 후 바로 저장을 선택하세요.',
              '/guide/student_pdfnaverguide_step1.png'
            ),
            uploadStepsDefault[1],
            uploadStepsDefault[2],
          ],
        },
      ],
    },
    {
      id: 'gov24',
      label: '정부24 앱',
      short: '재학생/졸업생',
      links: [
        { label: '정부24 Android', href: APP_LINKS.gov24Android },
        { label: '정부24 iOS', href: APP_LINKS.gov24Ios },
      ],
      sections: [
        {
          title: '1단계. 학교생활기록부 발급하기',
          steps: [
            toStep(
              '정부24 앱 다운로드',
              '정부24 앱 설치 후 로그인합니다.',
              '/guide/student_govguide_step1.png'
            ),
            toStep(
              '학교생활기록부(초중고) 검색',
              '민원 검색에서 학교생활기록부(초중고)를 찾고 발급하기를 선택하세요.',
              '/guide/student_govguide_step2.png'
            ),
            toStep(
              '신청내용 입력',
              `${graduateSchoolText}, 주민번호(비공개), 수령방법(전자문서지갑) 선택 후 신청하기를 누르세요.`,
              isGraduate ? '/guide/student_govguide_step3_middle_school.png' : '/guide/student_govguide_step3.png'
            ),
          ],
        },
        {
          title: '2단계. 파일로 업로드하기',
          summary: '문서열람번호 방식은 제외하고 파일 업로드만 사용합니다.',
          steps: uploadStepsDefault,
        },
      ],
    },
  ]
}
