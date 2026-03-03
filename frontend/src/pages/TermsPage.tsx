function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="text-lg font-bold text-gray-900 border-b border-gray-200 pb-2 mb-4">{title}</h2>
      <div className="text-gray-600 leading-relaxed space-y-2">{children}</div>
    </section>
  )
}

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-3xl mx-auto bg-white rounded-xl shadow-sm p-6 sm:p-10">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 text-center mb-2">서비스 이용약관</h1>
        <p className="text-center text-gray-500 text-sm mb-10">시행일: 2026년 2월 25일</p>

        <p className="text-gray-600 mb-8 leading-relaxed">
          본 약관은 김태훈(이하 "회사")이 운영하는 유니로드(uni2road.com, 이하 "서비스")의 이용과 관련하여
          회사와 회원 간의 권리·의무 및 책임사항을 규정함을 목적으로 합니다.
        </p>

        <Section title="제1조 (목적)">
          <p>
            본 약관은 회사가 제공하는 유니로드 및 관련 제반 서비스의 이용 조건 및 절차, 회사와 회원 간의
            권리·의무 및 책임사항, 기타 필요한 사항을 규정함을 목적으로 합니다.
          </p>
        </Section>

        <Section title="제2조 (용어의 정의)">
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              <strong>"서비스"</strong>란 PC·모바일 등 각종 유무선 장치를 통해 회원이 이용할 수 있는
              대학 입시 정보 제공, AI 기반 합격 가능성 진단, 환산점수 계산, 생활기록부 분석 등
              유니로드의 모든 온라인 서비스를 의미합니다.
            </li>
            <li>
              <strong>"회원"</strong>이란 본 약관에 동의하고 회사와 이용계약을 체결하여 서비스를 이용하는
              자를 의미합니다.
            </li>
            <li>
              <strong>"유료서비스"</strong>란 회사가 유료로 제공하는 AI 입시 진단, Pro 플랜 구독 등
              각종 온라인 디지털 콘텐츠 및 제반 서비스를 의미합니다.
            </li>
            <li>
              <strong>"콘텐츠"</strong>란 회사가 서비스 내에서 제공하는 AI 답변, 분석 리포트, 입시 정보 등
              디지털 형태의 모든 정보를 의미합니다.
            </li>
          </ol>
        </Section>

        <Section title="제3조 (서비스의 제공 및 변경)">
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              회사는 회원에게 대학별 모집요강 조회, 환산점수 계산, 과거 입시결과 조회, 정시 합격 가능성
              진단, 생활기록부 분석 등의 서비스를 제공합니다.
            </li>
            <li>
              회사는 서비스의 내용·이용방법·이용시간에 변경이 있을 경우, 변경 전 7일 이상 서비스 초기화면
              또는 공지사항에 게시합니다. 단, 긴급한 변경의 경우 사후에 공지할 수 있습니다.
            </li>
            <li>
              회사는 서비스 운영 또는 기술상 필요에 따라 제공하는 서비스를 변경할 수 있으며, 이에 대해
              관련 법령에 특별한 규정이 없는 한 회원에게 별도의 보상을 하지 않습니다.
            </li>
          </ol>
        </Section>

        <Section title="제4조 (이용요금의 결제)">
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              유료서비스의 이용요금 및 결제 방식은 회사가 서비스 내에 별도로 고지한 바에 따릅니다.
            </li>
            <li>
              회사는 토스페이먼츠 등 전자결제 대행사를 통해 신용카드, 계좌이체 등의 결제 수단을 제공합니다.
            </li>
            <li>
              결제와 관련하여 회원이 입력한 정보 및 그에 따른 책임과 불이익은 전적으로 회원이 부담합니다.
            </li>
            <li>
              정기결제(구독) 서비스의 경우, 회원이 해지하지 않는 한 매 결제 주기마다 자동으로 결제됩니다.
            </li>
          </ol>
        </Section>

        <Section title="제5조 (청약철회 및 환불)">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4 text-sm text-blue-800">
            본 조항은 「전자상거래 등에서의 소비자보호에 관한 법률」 제17조에 근거합니다.
          </div>
          <ol className="list-decimal pl-5 space-y-3">
            <li>
              회사와 유료서비스 이용계약을 체결한 회원은 구매일 또는 유료서비스 이용가능일로부터
              <strong> 7일 이내</strong>에 청약철회를 할 수 있습니다.
            </li>
            <li>
              다음 각 호의 경우에는 청약철회가 제한될 수 있습니다.
              <ul className="list-disc pl-5 mt-2 space-y-1">
                <li>
                  회원이 AI 입시 진단, 분석 리포트 등 디지털 콘텐츠를 이미 열람하였거나 서비스를 사용한 경우
                  (「전자상거래 등에서의 소비자보호에 관한 법률」 제17조 제2항 제5호에 따른
                  디지털 콘텐츠 제공이 개시된 경우)
                </li>
                <li>
                  회사의 귀책사유 없이 회원의 단순 변심으로 인한 경우로서 이미 서비스가 제공된 경우
                </li>
                <li>
                  구독 서비스에서 이미 해당 월의 서비스 이용이 개시된 경우
                </li>
              </ul>
            </li>
            <li>
              청약철회가 가능한 경우, 회사는 철회 의사 확인 후 <strong>3영업일 이내</strong>에
              결제수단과 동일한 방법으로 환불을 진행합니다.
            </li>
            <li>
              환불 및 청약철회 문의: <strong>rlaxogns100@snu.ac.kr</strong>
            </li>
          </ol>
        </Section>

        <Section title="제6조 (회사의 면책)">
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4 text-sm text-yellow-800">
            유니로드가 제공하는 모든 입시 정보 및 AI 진단 결과는 참고용 예측 데이터입니다.
          </div>
          <ol className="list-decimal pl-5 space-y-3">
            <li>
              회사가 제공하는 모든 입시 정보 및 AI 기반 진단 결과는 <strong>참고용 예측 데이터</strong>이며,
              실제 대학의 합격 또는 불합격을 보장하지 않습니다.
            </li>
            <li>
              회원은 회사가 제공하는 정보를 바탕으로 본인의 독자적인 판단과 책임하에 대학 지원 등의
              최종 결정을 내려야 하며, 회사는 회원의 입시 결과(불합격 등)에 대해 어떠한 법적 책임도
              지지 않습니다.
            </li>
            <li>
              회사는 천재지변, 전쟁, 폭동, 화재, 통신 장애 또는 이에 준하는 불가항력으로 인해 서비스를
              제공할 수 없는 경우 서비스 제공에 관한 책임이 면제됩니다.
            </li>
            <li>
              회사는 회원의 귀책사유로 인한 서비스 이용 장애에 대해 책임을 지지 않습니다.
            </li>
            <li>
              서비스 내 제공되는 대학별 입시 데이터는 각 대학의 공식 발표 자료를 기반으로 하나,
              정보의 정확성·완전성을 보증하지 않으며 실제 지원 전 반드시 해당 대학의 공식 모집요강을
              직접 확인하시기 바랍니다.
            </li>
          </ol>
        </Section>

        <Section title="제7조 (회원의 의무)">
          <ol className="list-decimal pl-5 space-y-2">
            <li>회원은 본 약관 및 관계 법령을 준수하여야 합니다.</li>
            <li>회원은 서비스를 이용하여 다음 각 호의 행위를 하여서는 안 됩니다.
              <ul className="list-disc pl-5 mt-2 space-y-1">
                <li>타인의 정보를 도용하는 행위</li>
                <li>회사가 제공하는 콘텐츠를 무단으로 복제·배포·상업적으로 이용하는 행위</li>
                <li>서비스의 정상적인 운영을 방해하는 행위</li>
                <li>기타 관계 법령에 위반되는 행위</li>
              </ul>
            </li>
          </ol>
        </Section>

        <Section title="제8조 (분쟁 해결)">
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              서비스 이용과 관련하여 회사와 회원 간에 분쟁이 발생한 경우, 회사는 분쟁 해결을 위해
              성실히 협의합니다.
            </li>
            <li>
              분쟁이 원만히 해결되지 않을 경우, 관련 법령에 따라 관할 법원에 소를 제기할 수 있습니다.
            </li>
          </ol>
        </Section>

        <Section title="제9조 (기타)">
          <ol className="list-decimal pl-5 space-y-2">
            <li>
              본 약관에서 정하지 아니한 사항이나 해석에 대해서는 「전자상거래 등에서의 소비자보호에 관한
              법률」, 「약관의 규제에 관한 법률」 등 관련 법령 및 상관례에 따릅니다.
            </li>
            <li>
              본 약관은 2026년 2월 25일부터 시행됩니다.
            </li>
          </ol>
        </Section>

        <div className="mt-10 pt-6 border-t border-gray-200 text-sm text-gray-500 space-y-1">
          <p><strong>상호명:</strong> 제로타이핑</p>
          <p><strong>대표자:</strong> 김태훈</p>
          <p><strong>사업자등록번호:</strong> 140-29-01759</p>
          <p><strong>주소:</strong> 경기도 용인시 수지구 현암로125번길 11, 723동 704호</p>
          <p><strong>고객센터:</strong> rlaxogns100@snu.ac.kr</p>
        </div>
      </div>
    </div>
  )
}
