export default function PolicyPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-3xl mx-auto bg-white rounded-xl shadow-sm p-6 sm:p-10">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 text-center mb-2">개인정보처리방침</h1>
        <p className="text-center text-gray-500 text-sm mb-10">시행일: 2026년 2월 10일</p>

        <p className="text-gray-600 mb-8 leading-relaxed">
          유니로드(이하 "회사")는 이용자의 개인정보를 중요시하며, 「개인정보 보호법」 등 관련 법령을 준수하고 있습니다. 
          회사는 개인정보처리방침을 통하여 이용자가 제공하는 개인정보가 어떠한 용도와 방식으로 이용되고 있으며, 
          개인정보 보호를 위해 어떠한 조치가 취해지고 있는지 알려드립니다.
        </p>

        <Section title="제1조 (개인정보의 수집 항목 및 수집 방법)">
          <h4 className="font-semibold text-gray-700 mt-4 mb-3">1. 수집하는 개인정보 항목</h4>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm mb-4">
              <thead>
                <tr className="bg-gray-100">
                  <th className="border border-gray-200 px-4 py-3 text-left font-semibold">구분</th>
                  <th className="border border-gray-200 px-4 py-3 text-left font-semibold">수집 항목</th>
                  <th className="border border-gray-200 px-4 py-3 text-left font-semibold">수집 목적</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="border border-gray-200 px-4 py-3">회원가입 시</td>
                  <td className="border border-gray-200 px-4 py-3">이메일, 이름, 프로필 사진(선택)</td>
                  <td className="border border-gray-200 px-4 py-3">회원 식별 및 서비스 제공</td>
                </tr>
                <tr>
                  <td className="border border-gray-200 px-4 py-3">서비스 이용 시</td>
                  <td className="border border-gray-200 px-4 py-3">채팅 내역, 성적 정보(선택), 관심 대학(선택)</td>
                  <td className="border border-gray-200 px-4 py-3">맞춤형 입시 상담 서비스 제공</td>
                </tr>
                <tr>
                  <td className="border border-gray-200 px-4 py-3">자동 수집</td>
                  <td className="border border-gray-200 px-4 py-3">접속 IP, 브라우저 정보, 접속 일시, 서비스 이용 기록</td>
                  <td className="border border-gray-200 px-4 py-3">서비스 개선 및 통계 분석</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h4 className="font-semibold text-gray-700 mt-4 mb-3">2. 개인정보 수집 방법</h4>
          <ul className="list-disc pl-5 space-y-2 text-gray-600">
            <li>회원가입 및 서비스 이용 과정에서 이용자가 직접 입력</li>
            <li>소셜 로그인(Google, Kakao, Naver) 연동 시 제공받는 정보</li>
            <li>서비스 이용 과정에서 자동으로 생성되어 수집되는 정보</li>
          </ul>
        </Section>

        <Section title="제2조 (개인정보의 이용 목적)">
          <p className="text-gray-600 mb-3">회사는 수집한 개인정보를 다음의 목적을 위해 이용합니다.</p>
          <ul className="list-disc pl-5 space-y-2 text-gray-600">
            <li><strong>서비스 제공:</strong> 입시 상담 AI 서비스, 합격 예측, 맞춤형 대학 추천</li>
            <li><strong>회원 관리:</strong> 회원제 서비스 이용에 따른 본인확인, 개인식별, 불량회원의 부정이용 방지</li>
            <li><strong>서비스 개선:</strong> 신규 서비스 개발, 서비스 품질 향상, 이용자 만족도 조사</li>
            <li><strong>마케팅 및 광고:</strong> 이벤트 정보 및 참여기회 제공, 광고성 정보 제공 (동의 시)</li>
          </ul>
        </Section>

        <Section title="제3조 (개인정보의 보유 및 이용 기간)">
          <p className="text-gray-600 mb-4">
            회사는 원칙적으로 개인정보 수집 및 이용목적이 달성된 후에는 해당 정보를 지체 없이 파기합니다. 
            단, 관계법령의 규정에 의하여 보존할 필요가 있는 경우 회사는 아래와 같이 관계법령에서 정한 일정한 기간 동안 회원정보를 보관합니다.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-gray-100">
                  <th className="border border-gray-200 px-4 py-3 text-left font-semibold">보존 항목</th>
                  <th className="border border-gray-200 px-4 py-3 text-left font-semibold">보존 기간</th>
                  <th className="border border-gray-200 px-4 py-3 text-left font-semibold">근거 법령</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="border border-gray-200 px-4 py-3">계약 또는 청약철회 등에 관한 기록</td>
                  <td className="border border-gray-200 px-4 py-3">5년</td>
                  <td className="border border-gray-200 px-4 py-3">전자상거래법</td>
                </tr>
                <tr>
                  <td className="border border-gray-200 px-4 py-3">대금결제 및 재화 등의 공급에 관한 기록</td>
                  <td className="border border-gray-200 px-4 py-3">5년</td>
                  <td className="border border-gray-200 px-4 py-3">전자상거래법</td>
                </tr>
                <tr>
                  <td className="border border-gray-200 px-4 py-3">소비자의 불만 또는 분쟁처리에 관한 기록</td>
                  <td className="border border-gray-200 px-4 py-3">3년</td>
                  <td className="border border-gray-200 px-4 py-3">전자상거래법</td>
                </tr>
                <tr>
                  <td className="border border-gray-200 px-4 py-3">웹사이트 방문기록</td>
                  <td className="border border-gray-200 px-4 py-3">3개월</td>
                  <td className="border border-gray-200 px-4 py-3">통신비밀보호법</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Section>

        <Section title="제4조 (개인정보의 제3자 제공)">
          <p className="text-gray-600 mb-3">회사는 이용자의 개인정보를 원칙적으로 외부에 제공하지 않습니다. 다만, 아래의 경우에는 예외로 합니다.</p>
          <ul className="list-disc pl-5 space-y-2 text-gray-600">
            <li>이용자가 사전에 동의한 경우</li>
            <li>법령의 규정에 의거하거나, 수사 목적으로 법령에 정해진 절차와 방법에 따라 수사기관의 요구가 있는 경우</li>
          </ul>
        </Section>

        <Section title="제5조 (개인정보의 파기 절차 및 방법)">
          <p className="text-gray-600 mb-3">회사는 개인정보 보유기간의 경과, 처리목적 달성 등 개인정보가 불필요하게 되었을 때에는 지체없이 해당 개인정보를 파기합니다.</p>
          <ul className="list-disc pl-5 space-y-2 text-gray-600">
            <li><strong>파기 절차:</strong> 이용자가 입력한 정보는 목적 달성 후 별도의 DB에 옮겨져 내부 방침 및 기타 관련 법령에 따라 일정기간 저장된 후 혹은 즉시 파기됩니다.</li>
            <li><strong>파기 방법:</strong> 전자적 파일 형태의 정보는 기록을 재생할 수 없는 기술적 방법을 사용합니다.</li>
          </ul>
        </Section>

        <Section title="제6조 (이용자의 권리와 그 행사 방법)">
          <p className="text-gray-600 mb-3">이용자는 언제든지 등록되어 있는 자신의 개인정보를 조회하거나 수정할 수 있으며, 회원탈퇴를 통해 개인정보의 삭제를 요청할 수 있습니다.</p>
          <ul className="list-disc pl-5 space-y-2 text-gray-600">
            <li>개인정보 조회/수정: 마이페이지에서 직접 조회/수정</li>
            <li>회원탈퇴: 마이페이지 또는 고객센터를 통해 요청</li>
            <li>개인정보 처리정지 요구: 고객센터를 통해 요청</li>
          </ul>
        </Section>

        <Section title="제7조 (개인정보의 안전성 확보 조치)">
          <p className="text-gray-600 mb-3">회사는 개인정보의 안전성 확보를 위해 다음과 같은 조치를 취하고 있습니다.</p>
          <ul className="list-disc pl-5 space-y-2 text-gray-600">
            <li>개인정보의 암호화</li>
            <li>해킹 등에 대비한 기술적 대책</li>
            <li>개인정보에 대한 접근 제한</li>
            <li>개인정보 취급 직원의 최소화 및 교육</li>
          </ul>
        </Section>

        <Section title="제8조 (개인정보 보호책임자)">
          <p className="text-gray-600 mb-4">
            회사는 개인정보 처리에 관한 업무를 총괄해서 책임지고, 개인정보 처리와 관련한 이용자의 불만처리 및 피해구제 등을 위하여 아래와 같이 개인정보 보호책임자를 지정하고 있습니다.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <tbody>
                <tr>
                  <td className="border border-gray-200 px-4 py-3 bg-gray-100 font-semibold w-1/3">개인정보 보호책임자</td>
                  <td className="border border-gray-200 px-4 py-3">유니로드 운영팀</td>
                </tr>
                <tr>
                  <td className="border border-gray-200 px-4 py-3 bg-gray-100 font-semibold">연락처</td>
                  <td className="border border-gray-200 px-4 py-3">uni2road@gmail.com</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Section>

        <Section title="제9조 (개인정보처리방침의 변경)">
          <p className="text-gray-600">
            이 개인정보처리방침은 시행일로부터 적용되며, 법령 및 방침에 따른 변경내용의 추가, 삭제 및 정정이 있는 경우에는 변경사항의 시행 7일 전부터 공지사항을 통하여 고지할 것입니다.
          </p>
        </Section>

        <div className="mt-12 pt-8 border-t border-gray-200 text-center">
          <a 
            href="/chat" 
            className="inline-block px-6 py-3 bg-blue-500 text-white rounded-lg font-medium hover:bg-blue-600 transition-colors"
          >
            유니로드로 돌아가기
          </a>
          <p className="mt-6 text-gray-400 text-sm">© 2026 유니로드. All rights reserved.</p>
        </div>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="text-lg font-semibold text-gray-800 mb-4 pb-2 border-b-2 border-gray-200">{title}</h2>
      {children}
    </section>
  )
}
