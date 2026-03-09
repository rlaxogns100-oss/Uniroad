function SchoolRecordOneTimeReportPage() {
  return (
    <div className="min-h-screen bg-gray-100 py-6">
      <div className="mx-auto max-w-[800px] border border-gray-200 bg-white shadow-md" style={{ minHeight: '1130px', position: 'relative' }}>
        {/* UNIROAD 워터마크 */}
        <div className="pointer-events-none absolute right-8 top-10 select-none" style={{ fontSize: '60px', fontWeight: 900, letterSpacing: '6px', color: 'rgba(0,0,0,0.04)' }}>
          UNIROAD
        </div>

        <div className="px-10 pb-6 pt-8">

          {/* Part 01 뱃지 */}
          <div className="mb-4">
            <span
              className="inline-block rounded-full px-4 py-1.5 text-xs font-bold text-white"
              style={{ backgroundColor: '#5B9BD5' }}
            >
              Part 01 학생 유형 요약
            </span>
          </div>

          {/* 제목 + 생성 시각 */}
          <h1 className="mb-1 text-xl font-extrabold text-gray-900" style={{ letterSpacing: '-0.02em' }}>
            김유니학생의 학교생활기록부 심층 분석
          </h1>
          <p className="mb-6 text-xs text-gray-400">생성 시각: 2026. 3. 8. 오후 1:55:50</p>

          {/* ===== 구분선 1 (고정) ===== */}
          <hr className="border-gray-200" style={{ marginBottom: '20px' }} />

          {/* ── 핵심 역량 입체 분석 ── */}
          <h3 className="mb-3 text-base font-extrabold text-gray-900">
            교과 성적 흐름과 6대 핵심 지표
          </h3>

          {/* 차트 영역 - 꽉 차게 */}
          <div className="flex items-center" style={{ height: '265px', marginBottom: '14px', gap: '12px' }}>
            {/* 라인 차트 */}
            <div className="h-full" style={{ flex: '1 1 0' }}>
              <svg viewBox="0 0 440 282" preserveAspectRatio="none" className="h-full w-full">
                <rect x="30" y="20" width="400" height="270" fill="#F7F9FB" rx="4" />
                {[0,1,2,3].map(i => (
                  <line key={i} x1="30" y1={48 + i * 65} x2="430" y2={48 + i * 65} stroke="#E5E8EB" strokeWidth="0.6" strokeDasharray="3 3" />
                ))}
                {['1','2','3','4'].map((label, i) => (
                  <text key={i} x="22" y={56 + i * 65} textAnchor="end" fontSize="10" fill="#B0B8C1">{label}</text>
                ))}
                {(() => {
                  const xs = [60, 130, 200, 270, 340, 410]
                  const gy = (g: number) => 48 + (g - 1) * 65
                  const subjects = [
                    { name: '국어', grades: [1,1,2,1,1,1], color: '#F97316' },
                    { name: '수학', grades: [4,2,3,2,1,1], color: '#EF4444' },
                    { name: '영어', grades: [1,1,1,2,null,null] as (number|null)[], color: '#22C55E' },
                    { name: '사회', grades: [1,1,1,1,1,1], color: '#A855F7' },
                    { name: '과학', grades: [3,2,null,null,null,null] as (number|null)[], color: '#EAB308' },
                  ]
                  const avgAll = [2.4, 1.8, 2.1, 1.7, 1.3, 1.2]
                  const avgMain = [2.0, 1.4, 1.75, 1.5, 1.0, 1.0]
                  return (
                    <>
                      {subjects.map(sub => {
                        const valid = sub.grades.map((g, i) => g !== null ? [xs[i], gy(g)] : null).filter(Boolean) as number[][]
                        if (valid.length < 2) return null
                        return (
                          <g key={sub.name}>
                            <polyline fill="none" stroke={sub.color} strokeWidth="0.8" strokeLinejoin="round" strokeLinecap="round" opacity="0.25"
                              points={valid.map(p => p.join(',')).join(' ')} />
                            {valid.map(([cx,cy], i) => (
                              <circle key={i} cx={cx} cy={cy} r="1.5" fill={sub.color} opacity="0.3" />
                            ))}
                            <text x={valid[valid.length-1][0] + 5} y={valid[valid.length-1][1] + 3} fontSize="7" fill={sub.color} fontWeight="600" opacity="0.4">{sub.name}</text>
                          </g>
                        )
                      })}
                      <polyline fill="none" stroke="#2E5C8A" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round"
                        points={avgAll.map((g,i) => `${xs[i]},${gy(g)}`).join(' ')} />
                      <polyline fill="none" stroke="#A8D0E0" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round"
                        points={avgMain.map((g,i) => `${xs[i]},${gy(g)}`).join(' ')} />
                      {avgAll.map((g,i) => <circle key={`a${i}`} cx={xs[i]} cy={gy(g)} r="3" fill="#2E5C8A" />)}
                      {avgMain.map((g,i) => <circle key={`b${i}`} cx={xs[i]} cy={gy(g)} r="3" fill="#A8D0E0" />)}
                    </>
                  )
                })()}
                {/* 범례 - 그래프 안 우측 상단 */}
                <line x1="310" y1="35" x2="320" y2="35" stroke="#2E5C8A" strokeWidth="2.5" />
                <text x="324" y="38" fontSize="8" fill="#6B7280">전교과</text>
                <line x1="358" y1="35" x2="368" y2="35" stroke="#A8D0E0" strokeWidth="2.5" />
                <text x="372" y="38" fontSize="8" fill="#6B7280">국영수사과</text>
                {/* 세로 점선 + x축 라벨 */}
                {[60,130,200,270,340,410].map((x, i) => (
                  <g key={`vl${i}`}>
                    <line x1={x} y1={48} x2={x} y2={243} stroke="#E5E8EB" strokeWidth="0.6" strokeDasharray="3 3" />
                    <text x={x} y="270" textAnchor="middle" fontSize="9" fill="#B0B8C1">{['1-1','1-2','2-1','2-2','3-1','3-2'][i]}</text>
                  </g>
                ))}
              </svg>
            </div>

            {/* 레이더 차트 - 컨테이너만 줄이고 육각형 크기 유지 */}
            <div className="h-full" style={{ width: '200px', flexShrink: 0, overflow: 'hidden' }}>
              <svg viewBox="5 20 290 265" preserveAspectRatio="xMidYMid meet" className="h-full w-full">
                {[1, 0.75, 0.5, 0.25].map((s, idx) => {
                  const cx = 150, cy = 142
                  const r = 100 * s
                  const pts = Array.from({ length: 6 }, (_, i) => {
                    const angle = (Math.PI / 2) + (i * Math.PI * 2) / 6
                    return `${cx + r * Math.cos(angle)},${cy - r * Math.sin(angle)}`
                  }).join(' ')
                  return <polygon key={idx} points={pts} fill={idx === 0 ? '#F7F9FB' : 'none'} stroke="#DDE2E8" strokeWidth="0.8" />
                })}
                {Array.from({ length: 6 }, (_, i) => {
                  const cx = 150, cy = 142
                  const angle = (Math.PI / 2) + (i * Math.PI * 2) / 6
                  return (
                    <line key={i} x1={cx} y1={cy} x2={cx + 100 * Math.cos(angle)} y2={cy - 100 * Math.sin(angle)} stroke="#DDE2E8" strokeWidth="0.8" />
                  )
                })}
                {(() => {
                  const cx = 150, cy = 142
                  const values = [0.78, 0.62, 0.58, 0.55, 0.72, 0.82]
                  const pts = values.map((v, i) => {
                    const angle = (Math.PI / 2) + (i * Math.PI * 2) / 6
                    return `${cx + 100 * v * Math.cos(angle)},${cy - 100 * v * Math.sin(angle)}`
                  }).join(' ')
                  return (
                    <>
                      <polygon points={pts} fill="rgba(91,155,213,0.15)" stroke="#5B9BD5" strokeWidth="2.5" />
                      {values.map((v, i) => {
                        const angle = (Math.PI / 2) + (i * Math.PI * 2) / 6
                        const px = cx + 100 * v * Math.cos(angle)
                        const py = cy - 100 * v * Math.sin(angle)
                        return <circle key={i} cx={px} cy={py} r="4.5" fill="#5B9BD5" />
                      })}
                    </>
                  )
                })()}
                {/* 중앙 점수 */}
                <text x="150" y="148" textAnchor="middle" fontSize="32" fill="#2E5C8A" fontWeight="900">68점</text>
                {[
                  { label: '학업역량', x: 150, y: 26 },
                  { label: '탐구 깊이', x: 262, y: 82 },
                  { label: '진로 연결성', x: 262, y: 210 },
                  { label: '공동체역량', x: 150, y: 268 },
                  { label: '창의융합역량', x: 36, y: 210 },
                  { label: '자기주도성', x: 36, y: 82 },
                ].map((item, i) => (
                  <text key={i} x={item.x} y={item.y} textAnchor="middle" fontSize="11" fill="#8B95A1" fontWeight="500">{item.label}</text>
                ))}
              </svg>
            </div>
          </div>

          {/* ===== 구분선 2 (고정) ===== */}
          <hr className="border-gray-200" style={{ marginBottom: '20px' }} />

          {/* ── 학생 유형 ── */}
          <h3 className="mb-3 text-base font-extrabold text-gray-900">
            학업적 호기심과 주도적 탐구 역량이 돋보이는 <span className="underline decoration-2 underline-offset-4">융합형 탐구 학생</span>
          </h3>

          {/* 해시태그 */}
          <div className="mb-3 flex flex-wrap gap-2">
            {['#교과 개념의 융합적 해석', '#주도적인 발표와 협업', '#질문을 확장하는 자기주도성'].map(tag => (
              <span key={tag} className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-600">
                {tag}
              </span>
            ))}
          </div>

          {/* 요약 텍스트 */}
          <p className="mb-6 text-xs leading-6 text-gray-600">
            교과 개념을 실생활 및 사회적 이슈와 연결하는 사고력이 강하고, 수업 안팎의 탐구를 통해 전공 적합성을 설득력 있게 보여주는 흐름이 확인됩니다. 맡은 책임을 끝까지 수행하는 태도와 공동체 안에서의 성실함이 함께 읽히며, 학업에 대한 탐구심과 성취가 안정적으로 드러납니다. 다음 단계에서는 희망 전공과 연결되는 후속 탐구를 더 또렷하게 남기면 완성도가 높아집니다.
          </p>

          {/* ── 성장 흐름 요약 ── */}
          <h3 className="mb-1 text-sm font-extrabold text-gray-900">성장 흐름 요약</h3>
          <p className="mb-4 text-xs text-gray-500">
            <span className="font-extrabold" style={{ color: '#5B9BD5' }}>UNIROAD</span>: 건축·도시 관심에서 출발해 경제·정치로 전환, 3학년에서 정치외교 주제를 수학적 분석 도구로 실증하는 흐름입니다.
          </p>

          {/* 화살표 스텝 (쉐브론) 6개 */}
          <div className="mb-6 flex" style={{ height: '90px' }}>
            {[
              { num: '1', title: '1-1', desc: '건축·도시 탐색', sub: '공간과 인간 관계 탐구', color: '#B8D4E8', zIndex: 6 },
              { num: '2', title: '1-2', desc: '사회 이슈 관심', sub: '스타트업·부동산 정책 탐구', color: '#96C3DE', zIndex: 5 },
              { num: '3', title: '2-1', desc: '경제·법 심화', sub: '그레셤법칙·비례대표제 분석', color: '#7FB3D5', zIndex: 4 },
              { num: '4', title: '2-2', desc: '수학 도구 접목', sub: 'FTA 통계·회귀분석 첫 적용', color: '#5B9BD5', zIndex: 3 },
              { num: '5', title: '3-1', desc: '정치외교 정량화', sub: '선거 확률분석·PCCMI 설계', color: '#3D7EBF', zIndex: 2 },
              { num: '6', title: '3-2', desc: '전공 역량 종합', sub: '계엄령×문화산업 회귀분석', color: '#2E5C8A', zIndex: 1 },
            ].map((step, i, arr) => (
              <div key={i} className="relative flex-1" style={{ marginRight: i < arr.length - 1 ? '-12px' : 0, zIndex: step.zIndex }}>
                <svg viewBox="0 0 140 90" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
                  {i === 0
                    ? <polygon points="0,0 124,0 140,45 124,90 0,90" fill={step.color} />
                    : i === arr.length - 1
                      ? <polygon points="0,0 140,0 140,90 0,90 16,45" fill={step.color} />
                      : <polygon points="0,0 124,0 140,45 124,90 0,90 16,45" fill={step.color} />
                  }
                </svg>
                <div className="relative z-10 flex h-full flex-col justify-center" style={{ paddingLeft: i === 0 ? '10px' : '22px', paddingRight: '6px' }}>
                  <div className="flex items-center gap-1">
                    <span className="flex h-4 w-4 items-center justify-center rounded-full bg-white/25 text-[8px] font-bold text-white">{step.num}</span>
                    <span className="text-[9px] font-bold text-white">{step.title}</span>
                  </div>
                  <p className="mt-1 text-[9px] font-bold leading-tight text-white">{step.desc}</p>
                  <p className="mt-0.5 text-[7px] leading-tight text-white/75">{step.sub}</p>
                </div>
              </div>
            ))}
          </div>

          {/* 구분선 */}
          <hr className="mb-5 border-gray-200" />

          {/* ── 성장 흐름의 핵심 포인트 ── */}
          <h3 className="mb-4 text-sm font-extrabold text-gray-900">성장 흐름의 핵심 포인트</h3>
          <div className="mb-6 grid grid-cols-3 gap-4">
            {[
              { num: '1', label: '관심 전환', desc: '건축·도시에서 경제·정치로 관심이 이동하며, 사회 구조에 대한 분석적 시각이 형성되기 시작합니다.' },
              { num: '2', label: '도구 습득', desc: '경제 이론(그레셤 법칙)과 수학 도구(회귀분석, 확률론)를 정치 현상 분석에 직접 접목하기 시작합니다.' },
              { num: '3', label: '전공 실증', desc: 'PCCMI 지수를 독자적으로 설계하고, 선거·의회 데이터를 정량 분석하여 정치외교 전공 적합성을 실증합니다.' },
            ].map((item, i) => (
              <div key={i} className="rounded-lg border border-gray-200 p-4">
                <div className="mb-2 flex items-center gap-1.5">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: '#5B9BD5' }}>
                    {item.num}
                  </span>
                  <span className="text-xs font-bold text-gray-900">{item.label}</span>
                </div>
                <p className="text-[11px] leading-5 text-gray-500">{item.desc}</p>
              </div>
            ))}
          </div>

        </div>

        {/* 하단 풋터 */}
        <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-10 py-4">
          <p className="text-xs text-gray-500">
            Written by <span className="font-extrabold" style={{ color: '#5B9BD5' }}>UNIROAD</span>
          </p>
          <p className="text-xs text-gray-400">Page 1</p>
        </div>

      </div>

      {/* ========== 2페이지 ========== */}
      <div className="mx-auto mt-8 max-w-[800px] border border-gray-200 bg-white shadow-md" style={{ minHeight: '1130px', position: 'relative' }}>
        {/* UNIROAD 워터마크 */}
        <div className="pointer-events-none absolute right-8 top-10 select-none" style={{ fontSize: '60px', fontWeight: 900, letterSpacing: '6px', color: 'rgba(0,0,0,0.04)' }}>
          UNIROAD
        </div>

        <div className="px-10 pb-6 pt-8">

          {/* Part 02 뱃지 */}
          <div className="mb-4">
            <span
              className="inline-block rounded-full px-4 py-1.5 text-xs font-bold text-white"
              style={{ backgroundColor: '#5B9BD5' }}
            >
              Part 02 진단과 보완
            </span>
          </div>

          {/* ── 생기부의 핵심 강점 ── */}
          <h2 className="mb-4 text-sm font-extrabold text-gray-900">학교생활기록부 핵심 강점</h2>

          <div className="mb-6 flex flex-col gap-3">
            {/* 1번: 교과 등급 히트맵 */}
            <div className="rounded-lg border border-gray-200 overflow-hidden">
              <div className="flex items-center gap-2 px-5 pt-4 pb-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: '#5B9BD5' }}>1</span>
                <span className="text-sm font-bold text-gray-900">학업 역량</span>
                <span className="text-[10px] text-gray-400">— 교과 성적 전반</span>
              </div>
              <p className="px-5 pb-2 text-[11px] leading-5 text-gray-500">
                사회 과목군이 전 학기 1등급으로 안정적이며, 수학은 4등급에서 1등급까지 꾸준히 상승하는 성장세가 뚜렷합니다.
              </p>
              <div className="flex justify-center px-5 pb-3">
                {(() => {
                  const subjects = ['국어', '수학', '영어', '사회선택', '과학']
                  const semesters = ['1-1', '1-2', '2-1', '2-2', '3-1', '3-2']
                  const data: (number | null)[][] = [
                    [1, 1, 2, 1, 1, 1],
                    [4, 2, 3, 2, 1, 1],
                    [1, 1, 1, 2, null, null],
                    [1, 1, 1, 1, 1, 1],
                    [3, 2, null, null, null, null],
                  ]
                  const bgColor = (g: number | null) => {
                    if (g === null) return '#F9FAFB'
                    if (g === 1) return '#DBEAFE'
                    if (g === 2) return '#EFF6FF'
                    return 'transparent'
                  }
                  return (
                    <table className="text-center" style={{ borderCollapse: 'collapse', width: '420px' }}>
                      <thead>
                        <tr>
                          <th style={{ width: '48px', padding: '2px 0' }} />
                          {semesters.map(s => (
                            <th key={s} style={{ padding: '2px 0', fontSize: '11px', fontWeight: 600, color: '#94A3B8' }}>{s}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {subjects.map((subj, row) => (
                          <tr key={subj} style={{ borderTop: '1px solid #F1F5F9' }}>
                            <td style={{ padding: '3px 6px 3px 0', fontSize: '12px', fontWeight: 600, color: '#374151', textAlign: 'left' }}>{subj}</td>
                            {semesters.map((_, col) => {
                              const v = data[row][col]
                              return (
                                <td key={col} style={{ padding: '3px 0', fontSize: '13px', fontWeight: 700, color: v === null ? '#D1D5DB' : '#374151', backgroundColor: bgColor(v) }}>
                                  {v === null ? '-' : v}
                                </td>
                              )
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )
                })()}
              </div>
            </div>

            {/* 2번: 공동체 역량 */}
            <div className="rounded-lg border border-gray-200 overflow-hidden">
              <div className="flex items-center gap-2 px-5 pt-4 pb-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: '#5B9BD5' }}>2</span>
                <span className="text-sm font-bold text-gray-900">공동체 역량</span>
                <span className="text-[10px] text-gray-400">— 2학년 자율활동</span>
              </div>
              <div className="flex">
                <div className="flex-1 border-r border-gray-100 px-5 pb-4">
                  <p className="text-[11px] leading-5 text-gray-600" style={{ fontStyle: 'italic' }}>"학급 부회장으로서 학급 자치법정 제도를 기획·운영하며, 갈등 상황에서 양측 입장을 정리해 합의안을 도출하는 조정 역할을 수행함. 학급 규칙 제·개정 회의를 주도하고, 전교생 대상 설문조사를 실시하여 다수결과 소수 의견 반영의 균형을 실증적으로 보여줌."</p>
                </div>
                <div className="flex-1 px-5 pb-4">
                  <p className="text-[11px] leading-5 text-gray-500">단순 참여가 아닌 제도 기획과 갈등 조정까지 수행한 점이 강점입니다. 정치외교 전공과의 연결성도 높아, 실제 민주적 의사결정 과정을 학급 단위에서 경험한 서사로 읽힙니다.</p>
                </div>
              </div>
            </div>

            {/* 3번: 심화탐구흐름 - 복잡 플로우차트 */}
            <div className="rounded-lg border border-gray-200 overflow-hidden">
              <div className="flex items-center gap-2 px-5 pt-4 pb-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: '#5B9BD5' }}>
                  3
                </span>
                <span className="text-sm font-bold text-gray-900">심화탐구흐름</span>
                <span className="text-[10px] text-gray-400">— 세특 전반</span>
              </div>
              <p className="px-5 pb-2 text-[11px] leading-5 text-gray-500">
                경제 현상에 대한 호기심에서 출발하여, 동아리와 교과 양쪽에서 수학·통계 도구를 정치 분석에 접목하고, 3학년에서 회귀분석까지 독자적으로 설계하는 흐름이 구체적이고 일관됩니다.
              </p>
              <div className="px-5 pb-4">
                <svg viewBox="0 0 900 270" className="w-full" style={{ height: '195px' }}>
                  <defs>
                    <marker id="ah" markerWidth="7" markerHeight="5" refX="7" refY="2.5" orient="auto">
                      <path d="M0,0 L7,2.5 L0,5" fill="none" stroke="#94A3B8" strokeWidth="1" />
                    </marker>
                  </defs>

                  {/* ===== COL 1: 시작 (x=10) ===== */}
                  <rect x="10" y="105" width="100" height="36" rx="18" fill="#2E5C8A" />
                  <text x="60" y="121" textAnchor="middle" fontSize="9" fill="white" fontWeight="700">경제 현상</text>
                  <text x="60" y="132" textAnchor="middle" fontSize="8" fill="white" opacity="0.8">관심 형성</text>

                  {/* Arrow 1 → 분기 */}
                  <line x1="110" y1="123" x2="155" y2="123" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="133" y="117" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">왜?</text>

                  {/* ===== COL 2: 분기 마름모 (x=160) ===== */}
                  <polygon points="195,95 230,123 195,151 160,123" fill="none" stroke="#C0392B" strokeWidth="1.5" />
                  <text x="195" y="121" textAnchor="middle" fontSize="8" fill="#C0392B" fontWeight="700">진로</text>
                  <text x="195" y="131" textAnchor="middle" fontSize="7" fill="#C0392B">탐색</text>

                  {/* 분기 → 위(동아리) */}
                  <line x1="195" y1="95" x2="195" y2="52" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="195" y1="52" x2="258" y2="52" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="230" y="46" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">사회이슈 호기심</text>

                  {/* 분기 → 아래(교과) */}
                  <line x1="195" y1="151" x2="195" y2="198" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="195" y1="198" x2="258" y2="198" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="230" y="192" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">교과 개념 적용</text>

                  {/* ===== COL 3: 1학년 활동 (x=262) ===== */}
                  {/* 위: 동아리 */}
                  <rect x="262" y="34" width="120" height="36" rx="4" fill="#EBF4FA" stroke="#5B9BD5" strokeWidth="1.2" />
                  <text x="322" y="49" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">시사탐구반(NIC)</text>
                  <text x="322" y="60" textAnchor="middle" fontSize="7" fill="#6B7280">AI 저작권 쟁점 탐구</text>

                  {/* 아래: 교과 */}
                  <rect x="262" y="180" width="120" height="36" rx="4" fill="#EBF4FA" stroke="#7FB3D5" strokeWidth="1.2" />
                  <text x="322" y="195" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">경제·한국사 세특</text>
                  <text x="322" y="206" textAnchor="middle" fontSize="7" fill="#6B7280">부동산 정책 비교 탐구</text>

                  {/* Arrow COL3 위 → COL4 위 */}
                  <line x1="382" y1="52" x2="430" y2="52" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="406" y="46" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">수학으로 확장</text>

                  {/* Arrow COL3 아래 → COL4 아래 */}
                  <line x1="382" y1="198" x2="430" y2="198" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="406" y="192" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">제도 분석으로</text>

                  {/* ===== COL 4: 2학년 활동 (x=434) ===== */}
                  {/* 위: 동아리 */}
                  <rect x="434" y="34" width="120" height="36" rx="4" fill="#EBF4FA" stroke="#5B9BD5" strokeWidth="1.2" />
                  <text x="494" y="49" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">창의수학반</text>
                  <text x="494" y="60" textAnchor="middle" fontSize="7" fill="#6B7280">폴스비-포퍼 지수</text>

                  {/* 아래: 교과 */}
                  <rect x="434" y="180" width="120" height="36" rx="4" fill="#EBF4FA" stroke="#7FB3D5" strokeWidth="1.2" />
                  <text x="494" y="195" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">정치와법·경제</text>
                  <text x="494" y="206" textAnchor="middle" fontSize="7" fill="#6B7280">플라자 합의·그레셤 법칙</text>

                  {/* 위+아래 → 중앙 합류 */}
                  <line x1="494" y1="70" x2="494" y2="100" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="504" y="88" fontSize="7" fill="#5B9BD5" fontWeight="600">데이터로</text>
                  <text x="504" y="96" fontSize="7" fill="#5B9BD5" fontWeight="600">실증</text>
                  <line x1="494" y1="180" x2="494" y2="148" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="504" y="162" fontSize="7" fill="#5B9BD5" fontWeight="600">경제 이론</text>
                  <text x="504" y="170" fontSize="7" fill="#5B9BD5" fontWeight="600">뒷받침</text>

                  {/* 중앙 합류 노드 */}
                  <rect x="444" y="104" width="100" height="40" rx="20" fill="#5B9BD5" />
                  <text x="494" y="121" textAnchor="middle" fontSize="8" fill="white" fontWeight="700">FTA 통계 프로젝트</text>
                  <text x="494" y="132" textAnchor="middle" fontSize="7" fill="white" opacity="0.8">회귀분석 첫 적용</text>

                  {/* Arrow 합류 → COL5 마름모 */}
                  <line x1="544" y1="124" x2="588" y2="124" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="566" y="118" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">정치로 전환</text>

                  {/* ===== COL 5: 3학년 분기 마름모 (x=593) ===== */}
                  <polygon points="620,96 652,124 620,152 588,124" fill="none" stroke="#C0392B" strokeWidth="1.5" />
                  <text x="620" y="122" textAnchor="middle" fontSize="8" fill="#C0392B" fontWeight="700">전공</text>
                  <text x="620" y="132" textAnchor="middle" fontSize="7" fill="#C0392B">심화</text>

                  {/* 분기 → 위 */}
                  <line x1="620" y1="96" x2="620" y2="52" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="620" y1="52" x2="660" y2="52" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="650" y="46" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">정량화</text>

                  {/* 분기 → 아래 */}
                  <line x1="620" y1="152" x2="620" y2="198" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="620" y1="198" x2="660" y2="198" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="650" y="192" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">구조 분석</text>

                  {/* ===== COL 6: 3학년 활동 (x=664) ===== */}
                  <rect x="664" y="30" width="110" height="44" rx="4" fill="#EBF4FA" stroke="#5B9BD5" strokeWidth="1.2" />
                  <text x="719" y="45" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">확률과 통계</text>
                  <text x="719" y="55" textAnchor="middle" fontSize="7" fill="#6B7280">선거 단일화 확률분석</text>
                  <text x="719" y="65" textAnchor="middle" fontSize="7" fill="#6B7280">아이언돔 요격 확률론</text>

                  <rect x="664" y="178" width="110" height="44" rx="4" fill="#EBF4FA" stroke="#7FB3D5" strokeWidth="1.2" />
                  <text x="719" y="193" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">사회문화·심화수학</text>
                  <text x="719" y="203" textAnchor="middle" fontSize="7" fill="#6B7280">유효 정당 수 비교</text>
                  <text x="719" y="213" textAnchor="middle" fontSize="7" fill="#6B7280">의료 불평등 구조 분석</text>

                  {/* 위+아래 → 최종 합류 */}
                  <line x1="774" y1="52" x2="800" y2="52" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="800" y1="52" x2="800" y2="100" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="812" y="78" fontSize="7" fill="#5B9BD5" fontWeight="600">융합</text>
                  <line x1="774" y1="198" x2="800" y2="198" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="800" y1="198" x2="800" y2="148" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="812" y="170" fontSize="7" fill="#5B9BD5" fontWeight="600">종합</text>

                  {/* ===== COL 7: 최종 성과 ===== */}
                  <rect x="760" y="104" width="130" height="40" rx="20" fill="#2E5C8A" />
                  <text x="825" y="120" textAnchor="middle" fontSize="8" fill="white" fontWeight="700">PCCMI 지수 착안</text>
                  <text x="825" y="132" textAnchor="middle" fontSize="7" fill="white" opacity="0.8">계엄령×문화산업 회귀분석</text>

                  {/* ===== 학년 라벨 ===== */}
                  <text x="322" y="16" textAnchor="middle" fontSize="8" fill="#94A3B8" fontWeight="600">1학년</text>
                  <text x="494" y="16" textAnchor="middle" fontSize="8" fill="#94A3B8" fontWeight="600">2학년</text>
                  <text x="719" y="16" textAnchor="middle" fontSize="8" fill="#94A3B8" fontWeight="600">3학년</text>

                  {/* 구분 점선 */}
                  <line x1="408" y1="10" x2="408" y2="230" stroke="#E5E7EB" strokeWidth="0.8" strokeDasharray="4 3" />
                  <line x1="640" y1="10" x2="640" y2="230" stroke="#E5E7EB" strokeWidth="0.8" strokeDasharray="4 3" />

                  {/* ===== 범례 ===== */}
                  <rect x="10" y="250" width="10" height="10" rx="2" fill="#EBF4FA" stroke="#5B9BD5" strokeWidth="1" />
                  <text x="24" y="259" fontSize="7.5" fill="#6B7280">동아리·교과 활동</text>
                  <polygon points="115,255 121,250 127,255 121,260" fill="none" stroke="#C0392B" strokeWidth="1" />
                  <text x="131" y="259" fontSize="7.5" fill="#6B7280">분기점</text>
                  <rect x="170" y="250" width="10" height="10" rx="5" fill="#5B9BD5" />
                  <text x="184" y="259" fontSize="7.5" fill="#6B7280">합류·핵심 성과</text>
                  <line x1="260" y1="255" x2="280" y2="255" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="284" y="259" fontSize="7.5" fill="#6B7280">화살표 위 = 이어지는 맥락</text>
                </svg>
              </div>
            </div>
          </div>

        </div>

        {/* 하단 풋터 */}
        <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-10 py-4">
          <p className="text-xs text-gray-500">
            Written by <span className="font-extrabold" style={{ color: '#5B9BD5' }}>UNIROAD</span>
          </p>
          <p className="text-xs text-gray-400">Page 2</p>
        </div>

      </div>

      {/* ========== 3페이지: 약점 ========== */}
      <div className="mx-auto mt-8 max-w-[800px] border border-gray-200 bg-white shadow-md" style={{ minHeight: '1130px', position: 'relative' }}>
        <div className="pointer-events-none absolute right-8 top-10 select-none" style={{ fontSize: '60px', fontWeight: 900, letterSpacing: '6px', color: 'rgba(0,0,0,0.04)' }}>
          UNIROAD
        </div>

        <div className="px-10 pb-6 pt-8">

          <div className="mb-4">
            <span
              className="inline-block rounded-full px-4 py-1.5 text-xs font-bold text-white"
              style={{ backgroundColor: '#5B9BD5' }}
            >
              Part 02 진단과 보완
            </span>
          </div>

          <h2 className="mb-4 text-sm font-extrabold text-gray-900">학교생활기록부 핵심 약점</h2>

          <div className="mb-6 flex flex-col gap-3">
            {/* 1번: 서술 깊이 바 차트 */}
            <div className="rounded-lg border border-gray-200 overflow-hidden">
              <div className="flex items-center gap-2 px-5 pt-4 pb-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: '#C0392B' }}>1</span>
                <span className="text-sm font-bold text-gray-900">세특 서술 깊이 변화</span>
                <span className="text-[10px] text-gray-400">— 세특 전반</span>
              </div>
              <p className="px-5 pb-2 text-[11px] leading-5 text-gray-500">
                1학년에서는 '체감함', '발견함' 등 감상형 서술이 다수였으나, 3학년으로 갈수록 '분석함', '도출함' 등 실증형 서술로 전환됩니다. 다만 일부 과목에서 여전히 감상형 마무리가 남아 있어 깊이감이 아쉽습니다.
              </p>
              <div className="px-5 pb-4">
                {(() => {
                  const rows = [
                    { label: '1학년', sense: 70, evidence: 30, senseEx: '~체감함, ~느낌', evidEx: '~조사함' },
                    { label: '2학년', sense: 45, evidence: 55, senseEx: '~알게됨', evidEx: '~분석함, ~설명함' },
                    { label: '3학년', sense: 20, evidence: 80, senseEx: '~깨달음', evidEx: '~도출함, ~설계함' },
                  ]
                  const barW = 420, barH = 24, labelW = 55, rowGap = 14, startY = 10
                  const svgH = startY + rows.length * (barH + rowGap) + 40
                  return (
                    <svg viewBox={`0 0 600 ${svgH}`} className="w-full" style={{ height: '130px' }}>
                      {rows.map((row, i) => {
                        const y = startY + i * (barH + rowGap)
                        const senseW = barW * (row.sense / 100)
                        const evidW = barW * (row.evidence / 100)
                        return (
                          <g key={i}>
                            <text x={labelW - 8} y={y + barH / 2 + 3} textAnchor="end" fontSize="10" fill="#374151" fontWeight="600">{row.label}</text>
                            <rect x={labelW} y={y} width={senseW} height={barH} rx="4" fill="#E8A0A0" />
                            <text x={labelW + senseW / 2} y={y + barH / 2 + 3} textAnchor="middle" fontSize="8" fill="#991B1B" fontWeight="700">{row.sense}%</text>
                            <rect x={labelW + senseW} y={y} width={evidW} height={barH} rx="4" fill="#5B9BD5" />
                            <text x={labelW + senseW + evidW / 2} y={y + barH / 2 + 3} textAnchor="middle" fontSize="8" fill="white" fontWeight="700">{row.evidence}%</text>
                            <text x={labelW + barW + 8} y={y + barH / 2 + 3} fontSize="7" fill="#9CA3AF">{row.evidEx}</text>
                          </g>
                        )
                      })}
                      <rect x={labelW} y={svgH - 22} width={12} height={12} rx="2" fill="#E8A0A0" />
                      <text x={labelW + 16} y={svgH - 12} fontSize="8" fill="#6B7280">감상형 (~체감함, ~발견함)</text>
                      <rect x={labelW + 180} y={svgH - 22} width={12} height={12} rx="2" fill="#5B9BD5" />
                      <text x={labelW + 196} y={svgH - 12} fontSize="8" fill="#6B7280">실증형 (~분석함, ~도출함)</text>
                    </svg>
                  )
                })()}
              </div>
            </div>

            {/* 2번: 전공 연결성 */}
            {[
              {
                num: 2, title: '전공 연결성', color: '#C0392B',
                chunk: '건축과 도시 계획이 인간에게 어떻게 얼마나 큰 영향을 미치는지 보여주는 사례를 조사하기 위해서 \'공간과 인간 사이의 관계에 대한 탐구\'라는 제목으로 프로젝트를 계획하고 영어 기사 4편을 선정하여 8주간 포트폴리오를 작성함.',
                source: '1학년 영어 세특',
                feedback: '자연과학, 통계, 공학적 소양이 폭넓게 보이지만, 왜 이 활동들이 희망 전공(정치외교)으로 이어지는지 한 줄 서사가 조금 더 필요합니다. 건축·경제·정치 등 관심사가 분산되어 보입니다.',
              },
            ].map((item) => (
              <div key={item.num} className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="flex items-center gap-2 px-5 pt-4 pb-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: item.color }}>
                    {item.num}
                  </span>
                  <span className="text-sm font-bold text-gray-900">{item.title}</span>
                  <span className="text-[10px] text-gray-400">— {item.source}</span>
                </div>
                <div className="flex">
                  <div className="flex-1 border-r border-gray-100 px-5 pb-4">
                    <p className="text-[11px] leading-5 text-gray-600" style={{ fontStyle: 'italic' }}>"{item.chunk}"</p>
                  </div>
                  <div className="flex-1 px-5 pb-4">
                    <p className="text-[11px] leading-5 text-gray-500">{item.feedback}</p>
                  </div>
                </div>
              </div>
            ))}

            {/* 3번: 성장성 - 약점 플로우차트 */}
            <div className="rounded-lg border border-gray-200 overflow-hidden">
              <div className="flex items-center gap-2 px-5 pt-4 pb-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: '#C0392B' }}>
                  3
                </span>
                <span className="text-sm font-bold text-gray-900">성장성</span>
                <span className="text-[10px] text-gray-400">— 진로활동 1~3학년</span>
              </div>
              <p className="px-5 pb-2 text-[11px] leading-5 text-gray-500">
                진로 희망이 경제학→정치외교로 전환되지만, 왜 바뀌었는지 연결 문장이 없어 성장 흐름이 끊겨 보입니다. 빨간 점선 구간이 보완이 필요한 지점입니다.
              </p>
              <div className="px-5 pb-4">
                <svg viewBox="0 0 900 200" className="w-full" style={{ height: '150px' }}>
                  <defs>
                    <marker id="ah2" markerWidth="7" markerHeight="5" refX="7" refY="2.5" orient="auto">
                      <path d="M0,0 L7,2.5 L0,5" fill="none" stroke="#94A3B8" strokeWidth="1" />
                    </marker>
                    <marker id="ah-red" markerWidth="7" markerHeight="5" refX="7" refY="2.5" orient="auto">
                      <path d="M0,0 L7,2.5 L0,5" fill="none" stroke="#C0392B" strokeWidth="1" />
                    </marker>
                  </defs>

                  <rect x="10" y="55" width="110" height="36" rx="4" fill="#EBF4FA" stroke="#5B9BD5" strokeWidth="1.2" />
                  <text x="65" y="70" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">희망: 경제학</text>
                  <text x="65" y="81" textAnchor="middle" fontSize="7" fill="#6B7280">스타트업 프로젝트</text>
                  <text x="65" y="44" textAnchor="middle" fontSize="8" fill="#94A3B8" fontWeight="600">1학년</text>

                  <line x1="120" y1="73" x2="165" y2="73" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah2)" />
                  <text x="143" y="67" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">관심 확장</text>

                  <polygon points="195,50 225,73 195,96 165,73" fill="none" stroke="#C0392B" strokeWidth="1.5" />
                  <text x="195" y="71" textAnchor="middle" fontSize="7" fill="#C0392B" fontWeight="700">진로</text>
                  <text x="195" y="80" textAnchor="middle" fontSize="7" fill="#C0392B">갈림</text>

                  <line x1="195" y1="50" x2="195" y2="28" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="195" y1="28" x2="268" y2="28" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah2)" />
                  <text x="235" y="22" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">수학 도구 습득</text>

                  <line x1="195" y1="96" x2="195" y2="130" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="195" y1="130" x2="268" y2="130" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah2)" />
                  <text x="235" y="124" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">정치 뉴스 관심</text>

                  <rect x="272" y="10" width="120" height="36" rx="4" fill="#EBF4FA" stroke="#5B9BD5" strokeWidth="1.2" />
                  <text x="332" y="25" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">경제 세특·수학</text>
                  <text x="332" y="36" textAnchor="middle" fontSize="7" fill="#6B7280">그레셤 법칙·FTA 분석</text>

                  <rect x="272" y="112" width="120" height="36" rx="4" fill="#EBF4FA" stroke="#7FB3D5" strokeWidth="1.2" />
                  <text x="332" y="127" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">정치와법 세특</text>
                  <text x="332" y="138" textAnchor="middle" fontSize="7" fill="#6B7280">비례대표제·플라자 합의</text>

                  <text x="332" y="3" textAnchor="middle" fontSize="8" fill="#94A3B8" fontWeight="600">2학년</text>

                  <line x1="392" y1="28" x2="440" y2="28" stroke="#C0392B" strokeWidth="1.5" strokeDasharray="5 3" />
                  <line x1="440" y1="28" x2="440" y2="62" stroke="#C0392B" strokeWidth="1.5" strokeDasharray="5 3" markerEnd="url(#ah-red)" />
                  <text x="450" y="42" fontSize="7" fill="#C0392B" fontWeight="700">왜 전환?</text>
                  <text x="450" y="51" fontSize="7" fill="#C0392B">(연결 부재)</text>

                  <line x1="392" y1="130" x2="440" y2="130" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="440" y1="130" x2="440" y2="96" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah2)" />

                  <polygon points="470,73 500,50 530,73 500,96" fill="none" stroke="#C0392B" strokeWidth="1.5" />
                  <text x="500" y="71" textAnchor="middle" fontSize="7" fill="#C0392B" fontWeight="700">희망</text>
                  <text x="500" y="80" textAnchor="middle" fontSize="7" fill="#C0392B">전환</text>

                  <line x1="440" y1="73" x2="470" y2="73" stroke="#C0392B" strokeWidth="1.5" strokeDasharray="5 3" markerEnd="url(#ah-red)" />

                  <line x1="530" y1="73" x2="575" y2="73" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah2)" />
                  <text x="553" y="67" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">정치외교 확정</text>

                  <rect x="578" y="55" width="130" height="36" rx="4" fill="#EBF4FA" stroke="#5B9BD5" strokeWidth="1.2" />
                  <text x="643" y="70" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">희망: 정치외교</text>
                  <text x="643" y="81" textAnchor="middle" fontSize="7" fill="#6B7280">PCCMI·선거 분석·의회 비교</text>
                  <text x="643" y="44" textAnchor="middle" fontSize="8" fill="#94A3B8" fontWeight="600">3학년</text>

                  <line x1="708" y1="73" x2="755" y2="73" stroke="#C0392B" strokeWidth="1.5" strokeDasharray="5 3" markerEnd="url(#ah-red)" />
                  <text x="732" y="67" textAnchor="middle" fontSize="7" fill="#C0392B" fontWeight="700">후속 탐구?</text>

                  <rect x="758" y="55" width="130" height="36" rx="18" fill="none" stroke="#C0392B" strokeWidth="1.5" strokeDasharray="5 3" />
                  <text x="823" y="70" textAnchor="middle" fontSize="8" fill="#C0392B" fontWeight="700">결론·후속 연구</text>
                  <text x="823" y="81" textAnchor="middle" fontSize="7" fill="#C0392B">기록 부재</text>

                  <line x1="240" y1="0" x2="240" y2="160" stroke="#E5E7EB" strokeWidth="0.8" strokeDasharray="4 3" />
                  <line x1="555" y1="0" x2="555" y2="160" stroke="#E5E7EB" strokeWidth="0.8" strokeDasharray="4 3" />

                  <line x1="10" y1="180" x2="30" y2="180" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah2)" />
                  <text x="34" y="183" fontSize="7.5" fill="#6B7280">자연스러운 연결</text>
                  <line x1="130" y1="180" x2="150" y2="180" stroke="#C0392B" strokeWidth="1.5" strokeDasharray="5 3" markerEnd="url(#ah-red)" />
                  <text x="154" y="183" fontSize="7.5" fill="#C0392B" fontWeight="600">연결 부재 (보완 필요)</text>
                </svg>
              </div>
            </div>
          </div>

          <hr className="border-gray-200" style={{ marginBottom: '20px' }} />

          <h2 className="mb-2 text-sm font-extrabold text-gray-900">생기부 핵심 진단</h2>
          <p className="text-xs leading-6 text-gray-600">
            현재의 폭넓은 관심사를 특정 전공 분야의 심화 연구로 좁혀 전문성을 강화하는 방식이 가장 효과적입니다.
          </p>

        </div>

        <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-10 py-4">
          <p className="text-xs text-gray-500">
            Written by <span className="font-extrabold" style={{ color: '#5B9BD5' }}>UNIROAD</span>
          </p>
          <p className="text-xs text-gray-400">Page 3</p>
        </div>

      </div>

      {/* ========== 4페이지 ========== */}
      <div className="mx-auto mt-8 max-w-[800px] border border-gray-200 bg-white shadow-md" style={{ minHeight: '1130px', position: 'relative' }}>
        {/* UNIROAD 워터마크 */}
        <div className="pointer-events-none absolute right-8 top-10 select-none" style={{ fontSize: '60px', fontWeight: 900, letterSpacing: '6px', color: 'rgba(0,0,0,0.04)' }}>
          UNIROAD
        </div>

        <div className="px-10 pb-6 pt-8">

          {/* Part 03 뱃지 */}
          <div className="mb-4">
            <span
              className="inline-block rounded-full px-4 py-1.5 text-xs font-bold text-white"
              style={{ backgroundColor: '#5B9BD5' }}
            >
              Part 03 합격자 비교 분석
            </span>
          </div>

          {/* 합격자 비교 섹션 제목 */}
          <h2 className="mb-1 text-sm font-extrabold text-gray-900">합격자 생기부와의 비교</h2>
          <p className="mb-4 text-xs text-gray-500">동일 전공(정치외교) 합격자의 세특과 나란히 비교하여 보완 포인트를 찾습니다.</p>

          {/* 비교 카드 1: 탐구 깊이 */}
          <div className="mb-4 overflow-hidden rounded-lg border border-gray-200">
            <div className="flex items-center gap-3 px-5 pt-3 pb-2" style={{ borderLeft: '3px solid #5B9BD5' }}>
              <span className="text-lg font-black" style={{ color: '#5B9BD5', lineHeight: 1 }}>01</span>
              <div>
                <span className="text-sm font-bold text-gray-900">탐구 깊이 비교</span>
                <span className="ml-2 text-[10px] text-gray-400">세특 서술 방식</span>
              </div>
            </div>
            <div className="flex" style={{ borderTop: '1px solid #F1F5F9' }}>
              <div className="flex-1 border-r border-gray-100 px-5 py-3">
                <div className="mb-1.5 flex items-center gap-1.5">
                  <span className="rounded px-2 py-0.5 text-[9px] font-bold text-white" style={{ backgroundColor: '#2E5C8A' }}>합격자</span>
                  <span className="text-[10px] text-gray-400">S대 정치외교학과</span>
                </div>
                <p className="text-[11px] leading-5 text-gray-600">
                  "선거구 획정 과정에서 인구 편차 허용 기준이 헌법재판소 결정에 따라 변화해 온 과정을 분석하고, 2:1 기준이 적용된 이후에도 농어촌 지역의 과소대표 문제가 해소되지 않음을 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>인구 데이터와 의석 배분 비율로 실증</mark>함. 이를 토대로 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>권역별 비례대표제 도입 시 예상되는 의석 변화를 시뮬레이션하여 대안의 실효성을 검증</mark>하고, 한계점까지 서술함."
                </p>
              </div>
              <div className="flex-1 px-5 py-3">
                <div className="mb-1.5 flex items-center gap-1.5">
                  <span className="rounded px-2 py-0.5 text-[9px] font-bold text-white" style={{ backgroundColor: '#6B7280' }}>이주안</span>
                  <span className="text-[10px] text-gray-400">정치와법 세특</span>
                </div>
                <p className="text-[11px] leading-5 text-gray-600">
                  "2차세계대전 이후 국제경제와 국제질서의 변화과정을 살펴본 후 '플라자 합의로 인한 동아시아 국제 질서의 변화'를 주제로 <mark style={{ backgroundColor: '#FECACA', padding: '1px 2px', borderRadius: '2px' }}>글을 작성하고 발표</mark>함. 환율과 니케이지수의 상관관계를 다루며 일본 경제가 충격을 받은 <mark style={{ backgroundColor: '#FECACA', padding: '1px 2px', borderRadius: '2px' }}>인과관계를 5단계로 설명</mark>함."
                </p>
              </div>
            </div>
            <div className="px-5 py-2.5" style={{ backgroundColor: '#F8FAFC', borderTop: '1px solid #F1F5F9' }}>
              <p className="text-[11px] leading-5 text-gray-600">
                합격자는 <span className="font-bold" style={{ color: '#2E5C8A' }}>데이터 수집 → 실증 분석 → 시뮬레이션 → 한계 서술</span> 4단계를 밟은 반면, 학생은 <span className="font-bold" style={{ color: '#C0392B' }}>인과관계 정리 → 발표</span>에서 멈춥니다. 검증·대안 제시 단계를 추가하면 서술 깊이가 올라갑니다.
              </p>
            </div>
          </div>

          {/* 비교 카드 2: 전공 연결성 */}
          <div className="mb-4 overflow-hidden rounded-lg border border-gray-200">
            <div className="flex items-center gap-3 px-5 pt-3 pb-2" style={{ borderLeft: '3px solid #5B9BD5' }}>
              <span className="text-lg font-black" style={{ color: '#5B9BD5', lineHeight: 1 }}>02</span>
              <div>
                <span className="text-sm font-bold text-gray-900">전공 연결성 비교</span>
                <span className="ml-2 text-[10px] text-gray-400">교과 간 서사 연결</span>
              </div>
            </div>
            <div className="flex" style={{ borderTop: '1px solid #F1F5F9' }}>
              <div className="flex-1 border-r border-gray-100 px-5 py-3">
                <div className="mb-1.5 flex items-center gap-1.5">
                  <span className="rounded px-2 py-0.5 text-[9px] font-bold text-white" style={{ backgroundColor: '#2E5C8A' }}>합격자</span>
                  <span className="text-[10px] text-gray-400">Y대 정치외교학과</span>
                </div>
                <p className="text-[11px] leading-5 text-gray-600">
                  "1학년 통합사회에서 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>국제 분쟁의 원인</mark>을 다룬 뒤, 2학년 세계사에서 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>냉전기 대리전의 구조를 분석</mark>하고, 같은 학기 정치와법에서 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>국제법상 무력사용 금지 원칙</mark>의 예외 조항을 탐구함. 3학년 사회문화에서는 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>분쟁 지역 난민의 사회 통합</mark> 과정을 문화 변동 이론으로 해석하여, 안보-법-사회를 잇는 일관된 탐구 서사를 완성함."
                </p>
              </div>
              <div className="flex-1 px-5 py-3">
                <div className="mb-1.5 flex items-center gap-1.5">
                  <span className="rounded px-2 py-0.5 text-[9px] font-bold text-white" style={{ backgroundColor: '#6B7280' }}>이주안</span>
                  <span className="text-[10px] text-gray-400">세특 전반</span>
                </div>
                <p className="text-[11px] leading-5 text-gray-600">
                  "1학년 영어에서 <mark style={{ backgroundColor: '#FECACA', padding: '1px 2px', borderRadius: '2px' }}>건축과 도시 계획</mark> 탐구, 국어에서 공간과 장소 서평, 통합과학에서 건축 재료 탐구를 수행. 2학년에서 <mark style={{ backgroundColor: '#FECACA', padding: '1px 2px', borderRadius: '2px' }}>경제·정치와법</mark>으로 관심이 이동하고, 3학년에서 <mark style={{ backgroundColor: '#FECACA', padding: '1px 2px', borderRadius: '2px' }}>정치외교 관련 탐구</mark>(PCCMI 지수, 선거 분석)로 전환됨. 1학년 건축 관심사와 3학년 정치외교 사이의 연결 서사가 명시되지 않음."
                </p>
              </div>
            </div>
            <div className="px-5 py-2.5" style={{ backgroundColor: '#F8FAFC', borderTop: '1px solid #F1F5F9' }}>
              <p className="text-[11px] leading-5 text-gray-600">
                합격자는 <span className="font-bold" style={{ color: '#2E5C8A' }}>국제 분쟁이라는 하나의 축</span>을 안보→법→사회로 확장하며 일관된 서사를 구축한 반면, 학생은 <span className="font-bold" style={{ color: '#C0392B' }}>건축→경제→정치로 관심사 자체가 전환</span>되어 학년 간 연결이 약합니다. "왜 관심이 바뀌었는지"를 한 문장으로 연결하면 설득력이 높아집니다.
              </p>
            </div>
          </div>

          {/* 비교 카드 3: 데이터 활용 능력 */}
          <div className="mb-4 overflow-hidden rounded-lg border border-gray-200">
            <div className="flex items-center gap-3 px-5 pt-3 pb-2" style={{ borderLeft: '3px solid #5B9BD5' }}>
              <span className="text-lg font-black" style={{ color: '#5B9BD5', lineHeight: 1 }}>03</span>
              <div>
                <span className="text-sm font-bold text-gray-900">데이터 활용 능력 비교</span>
                <span className="ml-2 text-[10px] text-gray-400">탐구 방법론</span>
              </div>
            </div>
            <div className="flex" style={{ borderTop: '1px solid #F1F5F9' }}>
              <div className="flex-1 border-r border-gray-100 px-5 py-3">
                <div className="mb-1.5 flex items-center gap-1.5">
                  <span className="rounded px-2 py-0.5 text-[9px] font-bold text-white" style={{ backgroundColor: '#2E5C8A' }}>합격자</span>
                  <span className="text-[10px] text-gray-400">K대 정치외교학과</span>
                </div>
                <p className="text-[11px] leading-5 text-gray-600">
                  "OECD 국가별 투표율 데이터를 직접 수집하여 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>다중 회귀분석을 실시</mark>하고, 의무투표제·선거일 공휴일 여부·비례대표 비율을 독립변수로 설정하여 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>투표율에 대한 설명력(R²=0.67)을 도출</mark>함. 분석 결과를 바탕으로 한국형 투표율 제고 방안 3가지를 제안하고 각각의 실현 가능성을 평가함."
                </p>
              </div>
              <div className="flex-1 px-5 py-3">
                <div className="mb-1.5 flex items-center gap-1.5">
                  <span className="rounded px-2 py-0.5 text-[9px] font-bold text-white" style={{ backgroundColor: '#6B7280' }}>이주안</span>
                  <span className="text-[10px] text-gray-400">확률과 통계 세특</span>
                </div>
                <p className="text-[11px] leading-5 text-gray-600">
                  "폴스비-포퍼 경쟁지수를 직접 계산하고, <mark style={{ backgroundColor: '#FECACA', padding: '1px 2px', borderRadius: '2px' }}>대한민국 국회의원 선거의 경쟁도를 수치화</mark>함. 선거 단일화가 이뤄졌을 때의 확률을 시뮬레이션하여 <mark style={{ backgroundColor: '#FECACA', padding: '1px 2px', borderRadius: '2px' }}>결과를 표로 정리</mark>함. 다만 통계적 유의성 검증이나 변수 통제 설계는 포함되지 않음."
                </p>
              </div>
            </div>
            <div className="px-5 py-2.5" style={{ backgroundColor: '#F8FAFC', borderTop: '1px solid #F1F5F9' }}>
              <p className="text-[11px] leading-5 text-gray-600">
                합격자는 <span className="font-bold" style={{ color: '#2E5C8A' }}>데이터 수집 → 변수 설계 → 통계 분석 → 정책 제안</span>의 완결 구조를 갖춘 반면, 학생은 <span className="font-bold" style={{ color: '#C0392B' }}>지수 계산 → 표 정리</span>에서 멈춰 방법론적 엄밀함이 부족합니다. 유의성 검증 단계를 추가하면 차별화됩니다.
              </p>
            </div>
          </div>

          {/* 형광 범례 */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1">
              <span className="inline-block rounded-sm px-1.5 py-0.5 text-[9px]" style={{ backgroundColor: '#BDE0FE' }}>파랑</span>
              <span className="text-[10px] text-gray-400">합격자 핵심 표현</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="inline-block rounded-sm px-1.5 py-0.5 text-[9px]" style={{ backgroundColor: '#FECACA' }}>빨강</span>
              <span className="text-[10px] text-gray-400">학생 보완 필요 표현</span>
            </div>
          </div>

          {/* CTA 배너 */}
          <div className="mt-8 rounded-lg border border-blue-200 px-6 py-5 text-center" style={{ backgroundColor: '#F0F7FF' }}>
            <p className="mb-1 text-[15px] font-extrabold text-gray-900">
              다음 학기에 뭘 해야 할지 궁금하다면?
            </p>
            <p className="text-[12px]" style={{ color: '#5B9BD5' }}>
              유니로드와 상담해 보세요!
            </p>
          </div>

        </div>

        {/* 하단 풋터 */}
        <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-10 py-4">
          <p className="text-xs text-gray-500">
            Written by <span className="font-extrabold" style={{ color: '#5B9BD5' }}>UNIROAD</span>
          </p>
          <p className="text-xs text-gray-400">Page 4</p>
        </div>

      </div>
    </div>
  )
}

export default SchoolRecordOneTimeReportPage
