function ReportKimMinseop() {
  return (
    <div className="min-h-screen bg-gray-100 py-6">
      {/* ========== 1페이지 ========== */}
      <div className="mx-auto max-w-[800px] border border-gray-200 bg-white shadow-md" style={{ minHeight: '1130px', position: 'relative' }}>
        <div className="pointer-events-none absolute right-8 top-10 select-none" style={{ fontSize: '60px', fontWeight: 900, letterSpacing: '6px', color: 'rgba(0,0,0,0.04)' }}>UNIROAD</div>
        <div className="px-10 pb-6 pt-8">
          <div className="mb-4">
            <span className="inline-block rounded-full px-4 py-1.5 text-xs font-bold text-white" style={{ backgroundColor: '#5B9BD5' }}>Part 01 학생 유형 요약</span>
          </div>
          <h1 className="mb-1 text-xl font-extrabold text-gray-900" style={{ letterSpacing: '-0.02em' }}>김민섭학생의 학교생활기록부 심층 분석</h1>
          <p className="mb-6 text-xs text-gray-400">생성 시각: 2026. 3. 10. 오후 2:30:00</p>
          <hr className="border-gray-200" style={{ marginBottom: '20px' }} />

          <h3 className="mb-3 text-base font-extrabold text-gray-900">교과 성적 흐름과 6대 핵심 지표</h3>

          <div className="flex items-center" style={{ height: '265px', marginBottom: '14px', gap: '12px' }}>
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
                  const xs = [60, 147, 235, 322, 410]
                  const gy = (g: number) => 48 + (g - 1) * 65
                  const subjects = [
                    { name: '국어', grades: [4,4,3,4,2], color: '#F97316' },
                    { name: '수학', grades: [2,1,1,1,3], color: '#EF4444' },
                    { name: '영어', grades: [3,3,2,3,2], color: '#22C55E' },
                    { name: '과학', grades: [4,4,2,3,null] as (number|null)[], color: '#EAB308' },
                    { name: '사회', grades: [3,3,null,null,null] as (number|null)[], color: '#A855F7' },
                  ]
                  const avgAll = [3.2, 3.0, 2.1, 2.6, 2.75]
                  const avgMain = [3.2, 3.0, 2.0, 2.75, 2.33]
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
                <line x1="310" y1="35" x2="320" y2="35" stroke="#2E5C8A" strokeWidth="2.5" />
                <text x="324" y="38" fontSize="8" fill="#6B7280">전교과</text>
                <line x1="358" y1="35" x2="368" y2="35" stroke="#A8D0E0" strokeWidth="2.5" />
                <text x="372" y="38" fontSize="8" fill="#6B7280">국영수사과</text>
                {[60,147,235,322,410].map((x, i) => (
                  <g key={`vl${i}`}>
                    <line x1={x} y1={48} x2={x} y2={243} stroke="#E5E8EB" strokeWidth="0.6" strokeDasharray="3 3" />
                    <text x={x} y="270" textAnchor="middle" fontSize="9" fill="#B0B8C1">{['1-1','1-2','2-1','2-2','3-1'][i]}</text>
                  </g>
                ))}
              </svg>
            </div>

            <div className="h-full" style={{ width: '200px', flexShrink: 0, overflow: 'hidden' }}>
              <svg viewBox="5 20 290 265" preserveAspectRatio="xMidYMid meet" className="h-full w-full">
                {[1, 0.75, 0.5, 0.25].map((s, idx) => {
                  const cx = 150, cy = 142, r = 100 * s
                  const pts = Array.from({ length: 6 }, (_, i) => {
                    const angle = (Math.PI / 2) + (i * Math.PI * 2) / 6
                    return `${cx + r * Math.cos(angle)},${cy - r * Math.sin(angle)}`
                  }).join(' ')
                  return <polygon key={idx} points={pts} fill={idx === 0 ? '#F7F9FB' : 'none'} stroke="#DDE2E8" strokeWidth="0.8" />
                })}
                {Array.from({ length: 6 }, (_, i) => {
                  const cx = 150, cy = 142
                  const angle = (Math.PI / 2) + (i * Math.PI * 2) / 6
                  return <line key={i} x1={cx} y1={cy} x2={cx + 100 * Math.cos(angle)} y2={cy - 100 * Math.sin(angle)} stroke="#DDE2E8" strokeWidth="0.8" />
                })}
                {(() => {
                  const cx = 150, cy = 142
                  const values = [0.62, 0.72, 0.55, 0.68, 0.62, 0.75]
                  const pts = values.map((v, i) => {
                    const angle = (Math.PI / 2) + (i * Math.PI * 2) / 6
                    return `${cx + 100 * v * Math.cos(angle)},${cy - 100 * v * Math.sin(angle)}`
                  }).join(' ')
                  return (
                    <>
                      <polygon points={pts} fill="rgba(91,155,213,0.15)" stroke="#5B9BD5" strokeWidth="2.5" />
                      {values.map((v, i) => {
                        const angle = (Math.PI / 2) + (i * Math.PI * 2) / 6
                        return <circle key={i} cx={cx + 100 * v * Math.cos(angle)} cy={cy - 100 * v * Math.sin(angle)} r="4.5" fill="#5B9BD5" />
                      })}
                    </>
                  )
                })()}
                <text x="150" y="148" textAnchor="middle" fontSize="32" fill="#2E5C8A" fontWeight="900">65점</text>
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

          <hr className="border-gray-200" style={{ marginBottom: '20px' }} />

          <h3 className="mb-3 text-base font-extrabold text-gray-900">
            자기주도적 탐구력과 수리·과학 융합이 돋보이는 <span className="underline decoration-2 underline-offset-4">융합형 탐구 학생</span>
          </h3>
          <div className="mb-3 flex flex-wrap gap-2">
            {['#수학·과학 융합 탐구', '#자기주도 학습과 멘토링', '#공학적 사고와 실험 설계'].map(tag => (
              <span key={tag} className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-600">{tag}</span>
            ))}
          </div>
          <p className="mb-6 text-xs leading-6 text-gray-600">
            수학 교과에서 1등급을 다수 달성하며 뛰어난 수리 역량을 보여주고, 이를 물리·공학 분야에 자연스럽게 접목하는 융합적 사고가 돋보입니다. 또래 협력학습 멘토 활동과 학급 내 자발적 역할 수행에서 공동체 역량이 확인됩니다. 다만, 국어 교과의 성적 변동과 진로 전환의 연결 서사를 보완하면 완성도가 크게 높아집니다.
          </p>

          <h3 className="mb-1 text-sm font-extrabold text-gray-900">성장 흐름 요약</h3>
          <p className="mb-4 text-xs text-gray-500">
            <span className="font-extrabold" style={{ color: '#5B9BD5' }}>UNIROAD</span>: 수학·과학 기초에서 출발해 프로그래밍·반도체로 확장, 3학년에서 사이클로이드·이차곡선 등 공학적 문제를 수학으로 실증하는 흐름입니다.
          </p>

          <div className="mb-6 flex" style={{ height: '90px' }}>
            {[
              { num: '1', title: '1-1', desc: '기초 역량 형성', sub: '수학독서토론·과학캠프', color: '#B8D4E8', zIndex: 6 },
              { num: '2', title: '1-2', desc: '수학 역량 도약', sub: '수학 1등급 달성', color: '#96C3DE', zIndex: 5 },
              { num: '3', title: '2-1', desc: '공학 탐구 시작', sub: '프로그래밍·반도체 조사', color: '#7FB3D5', zIndex: 4 },
              { num: '4', title: '2-2', desc: '수리 도구 심화', sub: '확통 1등급·미적분 활용', color: '#5B9BD5', zIndex: 3 },
              { num: '5', title: '3-1', desc: '융합 탐구 실증', sub: '사이클로이드·이차곡선', color: '#3D7EBF', zIndex: 2 },
              { num: '6', title: '3-2', desc: '전공 종합 심화', sub: '심화수학·물리Ⅱ 탐구', color: '#2E5C8A', zIndex: 1 },
            ].map((step, i, arr) => (
              <div key={i} className="relative flex-1" style={{ marginRight: i < arr.length - 1 ? '-12px' : 0, zIndex: step.zIndex }}>
                <svg viewBox="0 0 140 90" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
                  {i === 0
                    ? <polygon points="0,0 124,0 140,45 124,90 0,90" fill={step.color} />
                    : i === arr.length - 1
                      ? <polygon points="0,0 140,0 140,90 0,90 16,45" fill={step.color} />
                      : <polygon points="0,0 124,0 140,45 124,90 0,90 16,45" fill={step.color} />}
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

          <hr className="mb-5 border-gray-200" />
          <h3 className="mb-4 text-sm font-extrabold text-gray-900">성장 흐름의 핵심 포인트</h3>
          <div className="mb-6 grid grid-cols-3 gap-4">
            {[
              { num: '1', label: '관심 심화', desc: '수학·과학 기초에서 프로그래밍, 반도체, 공학으로 자연스럽게 관심이 깊어지며 이공계 진로가 구체화됩니다.' },
              { num: '2', label: '도구 습득', desc: '미적분, 확률과 통계, 기하 등 수학 도구를 물리학·공학 분야에 직접 접목하기 시작합니다.' },
              { num: '3', label: '전공 실증', desc: '사이클로이드 곡선의 공학적 활용, 이차곡선의 광학적 성질 등 독자적 탐구를 수행하여 공학 적합성을 실증합니다.' },
            ].map((item, i) => (
              <div key={i} className="rounded-lg border border-gray-200 p-4">
                <div className="mb-2 flex items-center gap-1.5">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: '#5B9BD5' }}>{item.num}</span>
                  <span className="text-xs font-bold text-gray-900">{item.label}</span>
                </div>
                <p className="text-[11px] leading-5 text-gray-500">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-10 py-4">
          <p className="text-xs text-gray-500">Written by <span className="font-extrabold" style={{ color: '#5B9BD5' }}>UNIROAD</span></p>
          <p className="text-xs text-gray-400">Page 1</p>
        </div>
      </div>

      {/* ========== 2페이지: 강점 ========== */}
      <div className="mx-auto mt-8 max-w-[800px] border border-gray-200 bg-white shadow-md" style={{ minHeight: '1130px', position: 'relative' }}>
        <div className="pointer-events-none absolute right-8 top-10 select-none" style={{ fontSize: '60px', fontWeight: 900, letterSpacing: '6px', color: 'rgba(0,0,0,0.04)' }}>UNIROAD</div>
        <div className="px-10 pb-6 pt-8">
          <div className="mb-4">
            <span className="inline-block rounded-full px-4 py-1.5 text-xs font-bold text-white" style={{ backgroundColor: '#5B9BD5' }}>Part 02 진단과 보완</span>
          </div>
          <h2 className="mb-4 text-sm font-extrabold text-gray-900">학교생활기록부 핵심 강점</h2>

          <div className="mb-6 flex flex-col gap-3">
            {/* 강점 1: 수학 교과 역량 — 히트맵 */}
            <div className="rounded-lg border border-gray-200 overflow-hidden">
              <div className="flex items-center gap-2 px-5 pt-4 pb-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: '#5B9BD5' }}>1</span>
                <span className="text-sm font-bold text-gray-900">수학 교과 역량</span>
                <span className="text-[10px] text-gray-400">— 교과 성적 전반</span>
              </div>
              <p className="px-5 pb-2 text-[11px] leading-5 text-gray-500">
                수학 교과에서 1-2학기부터 2-2학기까지 4개 학기 연속 1등급을 유지하며 뛰어난 수리 역량을 보여줍니다. 화학Ⅰ에서도 1등급을 기록하는 등 이과 핵심 과목에서 강세를 보입니다.
              </p>
              <div className="flex justify-center px-5 pb-3">
                {(() => {
                  const subjects = ['국어', '수학', '영어', '사회', '과학']
                  const semesters = ['1-1', '1-2', '2-1', '2-2', '3-1']
                  const data: (number | null)[][] = [
                    [4, 4, 3, 4, 2],
                    [2, 1, 1, 1, 3],
                    [3, 3, 2, 3, 2],
                    [3, 3, null, null, null],
                    [4, 4, 2, 3, null],
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

            {/* 강점 2: 공학적 탐구와 실험 설계 — 좌측 세특 / 우측 분석 */}
            <div className="rounded-lg border border-gray-200 overflow-hidden">
              <div className="flex items-center gap-2 px-5 pt-4 pb-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: '#5B9BD5' }}>2</span>
                <span className="text-sm font-bold text-gray-900">공학적 탐구와 실험 설계</span>
                <span className="text-[10px] text-gray-400">— 3학년 융합과학탐구반</span>
              </div>
              <div className="flex">
                <div className="flex-1 border-r border-gray-100 px-5 pb-4">
                  <p className="text-[11px] leading-5 text-gray-600" style={{ fontStyle: 'italic' }}>"사이클로이드 곡선의 공학적인 활용을 탐구하여 매개변수를 이용하여 수학적으로 나타내고 곡선의 길이, 곡선과 축으로 둘러싸인 부분의 넓이를 구함. 직선과 사이클로이드 곡선을 비교하여 강하시간이 직선보다 짧음을 수학적으로 풀어 보고, 강하 실험을 함."</p>
                </div>
                <div className="flex-1 px-5 pb-4">
                  <p className="text-[11px] leading-5 text-gray-500">이론(매개변수 표현) → 수학적 증명(강하시간 비교) → 물리 실험(실증) → 결과 검증까지 4단계 탐구를 완수한 점이 핵심 강점입니다. 삼각함수·적분을 실제 공학 문제에 접목한 사례로, 공학 전공 적합성을 강하게 보여줍니다.</p>
                </div>
              </div>
            </div>

            {/* 강점 3: 자기주도 학습과 멘토링 — 좌측 세특 / 우측 분석 */}
            <div className="rounded-lg border border-gray-200 overflow-hidden">
              <div className="flex items-center gap-2 px-5 pt-4 pb-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: '#5B9BD5' }}>3</span>
                <span className="text-sm font-bold text-gray-900">자기주도 학습과 멘토링</span>
                <span className="text-[10px] text-gray-400">— 3학년 자율활동</span>
              </div>
              <div className="flex">
                <div className="flex-1 border-r border-gray-100 px-5 pb-4">
                  <p className="text-[11px] leading-5 text-gray-600" style={{ fontStyle: 'italic' }}>"학급특색 또래 협력학습의 수학 도움팀의 멘토로 활동하며 본인이 맡은 멘티 그룹과 미적분 문제 풀이 시간을 정기적으로 갖고 문제 풀이 설명을 해 줌. 수학 교과에 대한 적극적인 흥미를 갖고 수학 교과를 어려워하는 친구들에게 재미있게 문제 풀이를 해주는 등 큰 도움이 됨."</p>
                </div>
                <div className="flex-1 px-5 pb-4">
                  <p className="text-[11px] leading-5 text-gray-500">단순 과외가 아닌 정기적 멘토링 시스템을 운영한 점이 돋보입니다. 자신의 수학 역량을 타인의 학습에 기여하는 방식으로 확장하며, 교수법·의사소통 능력까지 입증합니다. 공학 전공에서 요구하는 팀워크와 지식 공유 역량의 근거가 됩니다.</p>
                </div>
              </div>
            </div>

            {/* 강점 4: 심화탐구흐름 — 플로우차트 */}
            <div className="rounded-lg border border-gray-200 overflow-hidden">
              <div className="flex items-center gap-2 px-5 pt-4 pb-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: '#5B9BD5' }}>4</span>
                <span className="text-sm font-bold text-gray-900">심화탐구흐름</span>
                <span className="text-[10px] text-gray-400">— 세특 전반</span>
              </div>
              <p className="px-5 pb-2 text-[11px] leading-5 text-gray-500">
                수학 기초에서 출발하여 프로그래밍·반도체로 확장하고, 3학년에서 사이클로이드·이차곡선 등 수학을 공학에 직접 적용하는 흐름이 일관됩니다.
              </p>
              <div className="px-5 pb-4">
                <svg viewBox="0 0 900 270" className="w-full" style={{ height: '195px' }}>
                  <defs>
                    <marker id="ah" markerWidth="7" markerHeight="5" refX="7" refY="2.5" orient="auto">
                      <path d="M0,0 L7,2.5 L0,5" fill="none" stroke="#94A3B8" strokeWidth="1" />
                    </marker>
                  </defs>
                  <rect x="10" y="105" width="100" height="36" rx="18" fill="#2E5C8A" />
                  <text x="60" y="121" textAnchor="middle" fontSize="9" fill="white" fontWeight="700">수학·과학</text>
                  <text x="60" y="132" textAnchor="middle" fontSize="8" fill="white" opacity="0.8">기초 관심</text>
                  <line x1="110" y1="123" x2="155" y2="123" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="133" y="117" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">탐구 확장</text>
                  <polygon points="195,95 230,123 195,151 160,123" fill="none" stroke="#C0392B" strokeWidth="1.5" />
                  <text x="195" y="121" textAnchor="middle" fontSize="8" fill="#C0392B" fontWeight="700">진로</text>
                  <text x="195" y="131" textAnchor="middle" fontSize="7" fill="#C0392B">탐색</text>
                  <line x1="195" y1="95" x2="195" y2="52" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="195" y1="52" x2="258" y2="52" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="230" y="46" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">수학 심화</text>
                  <line x1="195" y1="151" x2="195" y2="198" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="195" y1="198" x2="258" y2="198" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="230" y="192" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">과학 실험</text>
                  <rect x="262" y="34" width="120" height="36" rx="4" fill="#EBF4FA" stroke="#5B9BD5" strokeWidth="1.2" />
                  <text x="322" y="49" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">수학독서토론반</text>
                  <text x="322" y="60" textAnchor="middle" fontSize="7" fill="#6B7280">수학 개념·논리 탐구</text>
                  <rect x="262" y="180" width="120" height="36" rx="4" fill="#EBF4FA" stroke="#7FB3D5" strokeWidth="1.2" />
                  <text x="322" y="195" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">통합과학·탐구실험</text>
                  <text x="322" y="206" textAnchor="middle" fontSize="7" fill="#6B7280">극저온·DNA 실험</text>
                  <line x1="382" y1="52" x2="430" y2="52" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="406" y="46" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">코딩으로 확장</text>
                  <line x1="382" y1="198" x2="430" y2="198" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="406" y="192" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">물질·소재로</text>
                  <rect x="434" y="34" width="120" height="36" rx="4" fill="#EBF4FA" stroke="#5B9BD5" strokeWidth="1.2" />
                  <text x="494" y="49" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">프로그래밍 동아리</text>
                  <text x="494" y="60" textAnchor="middle" fontSize="7" fill="#6B7280">파이썬·게임 개발</text>
                  <rect x="434" y="180" width="120" height="36" rx="4" fill="#EBF4FA" stroke="#7FB3D5" strokeWidth="1.2" />
                  <text x="494" y="195" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">화학Ⅰ·물리Ⅰ</text>
                  <text x="494" y="206" textAnchor="middle" fontSize="7" fill="#6B7280">반도체·메모리 탐구</text>
                  <line x1="494" y1="70" x2="494" y2="100" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="504" y="88" fontSize="7" fill="#5B9BD5" fontWeight="600">수학으로</text>
                  <text x="504" y="96" fontSize="7" fill="#5B9BD5" fontWeight="600">실증</text>
                  <line x1="494" y1="180" x2="494" y2="148" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="504" y="162" fontSize="7" fill="#5B9BD5" fontWeight="600">물리 원리</text>
                  <text x="504" y="170" fontSize="7" fill="#5B9BD5" fontWeight="600">뒷받침</text>
                  <rect x="444" y="104" width="100" height="40" rx="20" fill="#5B9BD5" />
                  <text x="494" y="121" textAnchor="middle" fontSize="8" fill="white" fontWeight="700">미적분 활용 탐구</text>
                  <text x="494" y="132" textAnchor="middle" fontSize="7" fill="white" opacity="0.8">애니메이션·CT 적용</text>
                  <line x1="544" y1="124" x2="588" y2="124" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <text x="566" y="118" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">공학 심화</text>
                  <polygon points="620,96 652,124 620,152 588,124" fill="none" stroke="#C0392B" strokeWidth="1.5" />
                  <text x="620" y="122" textAnchor="middle" fontSize="8" fill="#C0392B" fontWeight="700">전공</text>
                  <text x="620" y="132" textAnchor="middle" fontSize="7" fill="#C0392B">심화</text>
                  <line x1="620" y1="96" x2="620" y2="52" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="620" y1="52" x2="660" y2="52" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <line x1="620" y1="152" x2="620" y2="198" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="620" y1="198" x2="660" y2="198" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <rect x="664" y="30" width="110" height="44" rx="4" fill="#EBF4FA" stroke="#5B9BD5" strokeWidth="1.2" />
                  <text x="719" y="45" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">융합과학탐구반</text>
                  <text x="719" y="55" textAnchor="middle" fontSize="7" fill="#6B7280">사이클로이드 곡선</text>
                  <text x="719" y="65" textAnchor="middle" fontSize="7" fill="#6B7280">강하실험 실증</text>
                  <rect x="664" y="178" width="110" height="44" rx="4" fill="#EBF4FA" stroke="#7FB3D5" strokeWidth="1.2" />
                  <text x="719" y="193" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">기하·물리Ⅱ</text>
                  <text x="719" y="203" textAnchor="middle" fontSize="7" fill="#6B7280">이차곡선 광학 활용</text>
                  <text x="719" y="213" textAnchor="middle" fontSize="7" fill="#6B7280">포물선·타원·쌍곡선</text>
                  <line x1="774" y1="52" x2="800" y2="52" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="800" y1="52" x2="800" y2="100" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <line x1="774" y1="198" x2="800" y2="198" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="800" y1="198" x2="800" y2="148" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah)" />
                  <rect x="760" y="104" width="130" height="40" rx="20" fill="#2E5C8A" />
                  <text x="825" y="120" textAnchor="middle" fontSize="8" fill="white" fontWeight="700">공학적 문제해결</text>
                  <text x="825" y="132" textAnchor="middle" fontSize="7" fill="white" opacity="0.8">수학×물리 융합 역량</text>
                  <text x="322" y="16" textAnchor="middle" fontSize="8" fill="#94A3B8" fontWeight="600">1학년</text>
                  <text x="494" y="16" textAnchor="middle" fontSize="8" fill="#94A3B8" fontWeight="600">2학년</text>
                  <text x="719" y="16" textAnchor="middle" fontSize="8" fill="#94A3B8" fontWeight="600">3학년</text>
                  <line x1="408" y1="10" x2="408" y2="230" stroke="#E5E7EB" strokeWidth="0.8" strokeDasharray="4 3" />
                  <line x1="640" y1="10" x2="640" y2="230" stroke="#E5E7EB" strokeWidth="0.8" strokeDasharray="4 3" />
                  <rect x="10" y="250" width="10" height="10" rx="2" fill="#EBF4FA" stroke="#5B9BD5" strokeWidth="1" />
                  <text x="24" y="259" fontSize="7.5" fill="#6B7280">동아리·교과 활동</text>
                  <polygon points="115,255 121,250 127,255 121,260" fill="none" stroke="#C0392B" strokeWidth="1" />
                  <text x="131" y="259" fontSize="7.5" fill="#6B7280">분기점</text>
                  <rect x="170" y="250" width="10" height="10" rx="5" fill="#5B9BD5" />
                  <text x="184" y="259" fontSize="7.5" fill="#6B7280">합류·핵심 성과</text>
                </svg>
              </div>
            </div>
          </div>
        </div>
        <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-10 py-4">
          <p className="text-xs text-gray-500">Written by <span className="font-extrabold" style={{ color: '#5B9BD5' }}>UNIROAD</span></p>
          <p className="text-xs text-gray-400">Page 2</p>
        </div>
      </div>

      {/* ========== 3페이지: 약점 ========== */}
      <div className="mx-auto mt-8 max-w-[800px] border border-gray-200 bg-white shadow-md" style={{ minHeight: '1130px', position: 'relative' }}>
        <div className="pointer-events-none absolute right-8 top-10 select-none" style={{ fontSize: '60px', fontWeight: 900, letterSpacing: '6px', color: 'rgba(0,0,0,0.04)' }}>UNIROAD</div>
        <div className="px-10 pb-6 pt-8">
          <div className="mb-4">
            <span className="inline-block rounded-full px-4 py-1.5 text-xs font-bold text-white" style={{ backgroundColor: '#5B9BD5' }}>Part 02 진단과 보완</span>
          </div>
          <h2 className="mb-4 text-sm font-extrabold text-gray-900">학교생활기록부 핵심 약점</h2>

          <div className="mb-6 flex flex-col gap-3">
            {/* 약점 1: 국어 교과 성적 불안정 — 좌측 세특 / 우측 피드백 */}
            <div className="rounded-lg border border-gray-200 overflow-hidden">
              <div className="flex items-center gap-2 px-5 pt-4 pb-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: '#C0392B' }}>1</span>
                <span className="text-sm font-bold text-gray-900">국어 교과 성적 불안정</span>
                <span className="text-[10px] text-gray-400">— 국어 교과 전반</span>
              </div>
              <div className="flex">
                <div className="flex-1 border-r border-gray-100 px-5 pb-4">
                  <p className="text-[11px] leading-5 text-gray-600" style={{ fontStyle: 'italic' }}>"평소 관심 분야를 전달하는 활동을 위해 '집에서 직접 만드는 요거트인 티벳 버섯'에 대해 자신이 직접 경험한 사례를 인용하여 재미있게 발표함. 모둠활동 때 적극적으로 의견을 제시하고 과제를 해결하며 문제해결 능력, 공동체 역량을 기름."</p>
                </div>
                <div className="flex-1 px-5 pb-4">
                  <p className="text-[11px] leading-5 text-gray-500">국어 교과가 1-1~2-2까지 3~4등급에 머물러 있습니다. 세특 서술도 '발표함', '역량을 기름' 등 활동 나열에 가까워 깊이 있는 분석이 부족합니다. 공학 전공이라도 논리적 글쓰기·비판적 독해 역량은 면접과 학업에 핵심이므로, 기술 주제 글쓰기로 연결하면 보완됩니다.</p>
                </div>
              </div>
            </div>

            {/* 약점 2: 진로 전환 연결성 — 약점 플로우차트 */}
            <div className="rounded-lg border border-gray-200 overflow-hidden">
              <div className="flex items-center gap-2 px-5 pt-4 pb-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: '#C0392B' }}>2</span>
                <span className="text-sm font-bold text-gray-900">진로 전환 연결성</span>
                <span className="text-[10px] text-gray-400">— 진로활동 1~3학년</span>
              </div>
              <p className="px-5 pb-2 text-[11px] leading-5 text-gray-500">
                진로 희망이 컴퓨터공학자→진로탐색중→엔지니어로 전환되지만, 왜 바뀌었는지 연결 문장이 없어 흐름이 끊겨 보입니다. 특히 2학년 '진로탐색중'이 공백으로 남습니다.
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
                  <text x="65" y="70" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">희망: 컴퓨터공학자</text>
                  <text x="65" y="81" textAnchor="middle" fontSize="7" fill="#6B7280">수학독서토론·코딩</text>
                  <text x="65" y="44" textAnchor="middle" fontSize="8" fill="#94A3B8" fontWeight="600">1학년</text>
                  <line x1="120" y1="73" x2="165" y2="73" stroke="#C0392B" strokeWidth="1.5" strokeDasharray="5 3" markerEnd="url(#ah-red)" />
                  <text x="143" y="67" textAnchor="middle" fontSize="7" fill="#C0392B" fontWeight="600">왜 전환?</text>
                  <rect x="168" y="55" width="120" height="36" rx="18" fill="none" stroke="#C0392B" strokeWidth="1.5" strokeDasharray="5 3" />
                  <text x="228" y="70" textAnchor="middle" fontSize="8" fill="#C0392B" fontWeight="700">진로탐색중</text>
                  <text x="228" y="81" textAnchor="middle" fontSize="7" fill="#C0392B">(연결 서사 부재)</text>
                  <text x="228" y="44" textAnchor="middle" fontSize="8" fill="#94A3B8" fontWeight="600">2학년</text>
                  <line x1="228" y1="91" x2="228" y2="130" stroke="#94A3B8" strokeWidth="1.2" />
                  <line x1="228" y1="130" x2="300" y2="130" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah2)" />
                  <text x="268" y="124" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">프로그래밍·반도체</text>
                  <rect x="303" y="112" width="120" height="36" rx="4" fill="#EBF4FA" stroke="#5B9BD5" strokeWidth="1.2" />
                  <text x="363" y="127" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">화학Ⅰ·프로그래밍</text>
                  <text x="363" y="138" textAnchor="middle" fontSize="7" fill="#6B7280">반도체·게임 개발</text>
                  <line x1="288" y1="73" x2="340" y2="73" stroke="#C0392B" strokeWidth="1.5" strokeDasharray="5 3" markerEnd="url(#ah-red)" />
                  <text x="314" y="67" textAnchor="middle" fontSize="7" fill="#C0392B" fontWeight="700">구체화?</text>
                  <polygon points="370,50 400,73 370,96 340,73" fill="none" stroke="#C0392B" strokeWidth="1.5" />
                  <text x="370" y="71" textAnchor="middle" fontSize="7" fill="#C0392B" fontWeight="700">전공</text>
                  <text x="370" y="80" textAnchor="middle" fontSize="7" fill="#C0392B">전환</text>
                  <line x1="400" y1="73" x2="445" y2="73" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah2)" />
                  <text x="423" y="67" textAnchor="middle" fontSize="7" fill="#5B9BD5" fontWeight="600">공학으로</text>
                  <rect x="448" y="55" width="130" height="36" rx="4" fill="#EBF4FA" stroke="#5B9BD5" strokeWidth="1.2" />
                  <text x="513" y="70" textAnchor="middle" fontSize="8" fill="#2E5C8A" fontWeight="700">희망: 엔지니어</text>
                  <text x="513" y="81" textAnchor="middle" fontSize="7" fill="#6B7280">사이클로이드·이차곡선</text>
                  <text x="513" y="44" textAnchor="middle" fontSize="8" fill="#94A3B8" fontWeight="600">3학년</text>
                  <line x1="578" y1="73" x2="625" y2="73" stroke="#C0392B" strokeWidth="1.5" strokeDasharray="5 3" markerEnd="url(#ah-red)" />
                  <text x="602" y="67" textAnchor="middle" fontSize="7" fill="#C0392B" fontWeight="700">어떤 공학?</text>
                  <rect x="628" y="55" width="130" height="36" rx="18" fill="none" stroke="#C0392B" strokeWidth="1.5" strokeDasharray="5 3" />
                  <text x="693" y="70" textAnchor="middle" fontSize="8" fill="#C0392B" fontWeight="700">구체 분야 미정</text>
                  <text x="693" y="81" textAnchor="middle" fontSize="7" fill="#C0392B">기계? 전기? SW?</text>
                  <line x1="145" y1="0" x2="145" y2="160" stroke="#E5E7EB" strokeWidth="0.8" strokeDasharray="4 3" />
                  <line x1="435" y1="0" x2="435" y2="160" stroke="#E5E7EB" strokeWidth="0.8" strokeDasharray="4 3" />
                  <line x1="10" y1="180" x2="30" y2="180" stroke="#94A3B8" strokeWidth="1.2" markerEnd="url(#ah2)" />
                  <text x="34" y="183" fontSize="7.5" fill="#6B7280">자연스러운 연결</text>
                  <line x1="130" y1="180" x2="150" y2="180" stroke="#C0392B" strokeWidth="1.5" strokeDasharray="5 3" markerEnd="url(#ah-red)" />
                  <text x="154" y="183" fontSize="7.5" fill="#C0392B" fontWeight="600">연결 부재 (보완 필요)</text>
                </svg>
              </div>
            </div>

            {/* 약점 3: 세특 서술 깊이 편차 — 좌측 세특 / 우측 피드백 */}
            <div className="rounded-lg border border-gray-200 overflow-hidden">
              <div className="flex items-center gap-2 px-5 pt-4 pb-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: '#C0392B' }}>3</span>
                <span className="text-sm font-bold text-gray-900">세특 서술 깊이 편차</span>
                <span className="text-[10px] text-gray-400">— 3학년 미적분 세특</span>
              </div>
              <div className="flex">
                <div className="flex-1 border-r border-gray-100 px-5 pb-4">
                  <p className="text-[11px] leading-5 text-gray-600" style={{ fontStyle: 'italic' }}>"만화영화를 구현할 때 미분 공식을 이용하여 수식화하면 크기를 변화시키거나 움직임이 생길 때의 변화를 예측하여 영화의 제작이 훨씬 수월할 뿐 아니라 제작 시간과 제작비용을 아낄 수 있음을 알게 되었고... 다양한 분야에서 미적분이 활용된다는 사실을 알게 됨."</p>
                </div>
                <div className="flex-1 px-5 pb-4">
                  <p className="text-[11px] leading-5 text-gray-500">'~알게 됨'이 6회 이상 반복되며 감상형 서술에 머물고 있습니다. 3학년 사이클로이드 탐구에서는 실증적 서술이 보이지만, 미적분 세특은 활용 사례 나열에 그칩니다. '알게 됨' → '직접 계산하여 검증함', '수치를 비교 분석함' 등 실증형 어미로 전환하면 서술 깊이가 올라갑니다.</p>
                </div>
              </div>
            </div>
          </div>

          <hr className="border-gray-200" style={{ marginBottom: '20px' }} />
          <h2 className="mb-2 text-sm font-extrabold text-gray-900">생기부 핵심 진단</h2>
          <p className="text-xs leading-6 text-gray-600">
            수학·과학 융합 탐구력은 우수하나, 진로 전환의 연결 서사를 명확히 하고 세특 서술을 감상형에서 실증형으로 전환하면 공학 전공 적합성이 크게 강화됩니다.
          </p>
        </div>
        <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-10 py-4">
          <p className="text-xs text-gray-500">Written by <span className="font-extrabold" style={{ color: '#5B9BD5' }}>UNIROAD</span></p>
          <p className="text-xs text-gray-400">Page 3</p>
        </div>
      </div>

      {/* ========== 4페이지: 합격자 비교 ========== */}
      <div className="mx-auto mt-8 max-w-[800px] border border-gray-200 bg-white shadow-md" style={{ minHeight: '1130px', position: 'relative' }}>
        <div className="pointer-events-none absolute right-8 top-10 select-none" style={{ fontSize: '60px', fontWeight: 900, letterSpacing: '6px', color: 'rgba(0,0,0,0.04)' }}>UNIROAD</div>
        <div className="px-10 pb-6 pt-8">
          <div className="mb-4">
            <span className="inline-block rounded-full px-4 py-1.5 text-xs font-bold text-white" style={{ backgroundColor: '#5B9BD5' }}>Part 03 합격자 비교 분석</span>
          </div>
          <h2 className="mb-1 text-sm font-extrabold text-gray-900">합격자 생기부와의 비교</h2>
          <p className="mb-4 text-xs text-gray-500">동일 전공(공학) 합격자의 세특과 나란히 비교하여 보완 포인트를 찾습니다.</p>

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
                  <span className="text-[10px] text-gray-400">S대 기계공학과</span>
                </div>
                <p className="text-[11px] leading-5 text-gray-600">
                  "사이클로이드 곡선의 등시성을 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>라그랑주 역학으로 유도</mark>하고, 진자의 주기가 진폭에 무관함을 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>수치 시뮬레이션과 실험 데이터를 교차 검증</mark>하여 이론과 실험의 오차율 2.3%를 도출함. <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>오차 원인을 공기저항과 마찰로 분석</mark>하고 보정 방법을 제안함."
                </p>
              </div>
              <div className="flex-1 px-5 py-3">
                <div className="mb-1.5 flex items-center gap-1.5">
                  <span className="rounded px-2 py-0.5 text-[9px] font-bold text-white" style={{ backgroundColor: '#6B7280' }}>김민섭</span>
                  <span className="text-[10px] text-gray-400">융합과학탐구반</span>
                </div>
                <p className="text-[11px] leading-5 text-gray-600">
                  "사이클로이드곡선을 매개변수를 이용하여 수학적으로 나타내고 곡선의 길이를 구함. 직선과 사이클로이드 곡선을 비교하여 <mark style={{ backgroundColor: '#FECACA', padding: '1px 2px', borderRadius: '2px' }}>강하시간이 짧음을 수학적으로 풀어 보고, 강하 실험을 함</mark>. 실험 결과로 <mark style={{ backgroundColor: '#FECACA', padding: '1px 2px', borderRadius: '2px' }}>물리적 실험과 수학 풀이가 동일함을 알 수 있었음</mark>."
                </p>
              </div>
            </div>
            <div className="px-5 py-2.5" style={{ backgroundColor: '#F8FAFC', borderTop: '1px solid #F1F5F9' }}>
              <p className="text-[11px] leading-5 text-gray-600">
                합격자는 <span className="font-bold" style={{ color: '#2E5C8A' }}>이론 유도 → 수치 시뮬레이션 → 실험 → 오차 분석 → 보정 제안</span> 5단계를 밟은 반면, 학생은 <span className="font-bold" style={{ color: '#C0392B' }}>수학적 풀이 → 실험 확인</span>에서 멈춥니다. 오차 분석과 보정 단계를 추가하면 탐구 깊이가 올라갑니다.
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
                  <span className="text-[10px] text-gray-400">K대 전기전자공학과</span>
                </div>
                <p className="text-[11px] leading-5 text-gray-600">
                  "1학년 통합과학에서 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>반도체 원리</mark>를 탐구한 뒤, 2학년 물리학Ⅰ에서 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>다이오드 회로를 직접 설계·측정</mark>하고, 화학Ⅰ에서 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>실리콘 결정 구조와 도핑 원리</mark>를 연결함. 3학년 물리학Ⅱ에서 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>양자역학 기반 밴드갭 분석</mark>으로 반도체→회로→양자 일관된 서사를 완성함."
                </p>
              </div>
              <div className="flex-1 px-5 py-3">
                <div className="mb-1.5 flex items-center gap-1.5">
                  <span className="rounded px-2 py-0.5 text-[9px] font-bold text-white" style={{ backgroundColor: '#6B7280' }}>김민섭</span>
                  <span className="text-[10px] text-gray-400">세특 전반</span>
                </div>
                <p className="text-[11px] leading-5 text-gray-600">
                  "1학년에서 <mark style={{ backgroundColor: '#FECACA', padding: '1px 2px', borderRadius: '2px' }}>수학독서토론·과학캠프</mark> 참여, 2학년에서 <mark style={{ backgroundColor: '#FECACA', padding: '1px 2px', borderRadius: '2px' }}>프로그래밍·반도체 조사</mark>, 3학년에서 <mark style={{ backgroundColor: '#FECACA', padding: '1px 2px', borderRadius: '2px' }}>사이클로이드·이차곡선 탐구</mark>. 수학→프로그래밍→역학 문제로 관심이 이동하지만, 하나의 축으로 일관된 서사가 명시되지 않음."
                </p>
              </div>
            </div>
            <div className="px-5 py-2.5" style={{ backgroundColor: '#F8FAFC', borderTop: '1px solid #F1F5F9' }}>
              <p className="text-[11px] leading-5 text-gray-600">
                합격자는 <span className="font-bold" style={{ color: '#2E5C8A' }}>반도체라는 하나의 축</span>을 원리→설계→물질→양자로 심화하며 일관된 서사를 구축한 반면, 학생은 <span className="font-bold" style={{ color: '#C0392B' }}>수학·프로그래밍·역학 등 관심사가 분산</span>되어 학년 간 연결이 약합니다. "수학적 모델링으로 공학 문제를 해결한다"는 축을 명시하면 설득력이 높아집니다.
              </p>
            </div>
          </div>

          {/* 비교 카드 3: 데이터 활용 */}
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
                  <span className="text-[10px] text-gray-400">Y대 신소재공학과</span>
                </div>
                <p className="text-[11px] leading-5 text-gray-600">
                  "열전도도 측정 실험에서 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>온도-시간 데이터를 직접 수집</mark>하고, 푸리에 열전도 법칙의 1차원 모델로 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>이론값과 실측값의 회귀분석(R²=0.94)</mark>을 실시함. 경계 조건 변화에 따른 <mark style={{ backgroundColor: '#BDE0FE', padding: '1px 2px', borderRadius: '2px' }}>민감도 분석</mark>을 수행하여 모델의 한계를 정량적으로 서술함."
                </p>
              </div>
              <div className="flex-1 px-5 py-3">
                <div className="mb-1.5 flex items-center gap-1.5">
                  <span className="rounded px-2 py-0.5 text-[9px] font-bold text-white" style={{ backgroundColor: '#6B7280' }}>김민섭</span>
                  <span className="text-[10px] text-gray-400">융합과학탐구반</span>
                </div>
                <p className="text-[11px] leading-5 text-gray-600">
                  "직선과 사이클로이드 곡선을 비교하여 사이클로이드 곡선의 강하시간이 직선의 강하시간보다 짧음을 <mark style={{ backgroundColor: '#FECACA', padding: '1px 2px', borderRadius: '2px' }}>수학적으로 풀어 보고, 강하 실험을 함</mark>. 실험 결과로 <mark style={{ backgroundColor: '#FECACA', padding: '1px 2px', borderRadius: '2px' }}>물리적 실험과 수학 풀이가 동일함을 알 수 있었음</mark>."
                </p>
              </div>
            </div>
            <div className="px-5 py-2.5" style={{ backgroundColor: '#F8FAFC', borderTop: '1px solid #F1F5F9' }}>
              <p className="text-[11px] leading-5 text-gray-600">
                합격자는 <span className="font-bold" style={{ color: '#2E5C8A' }}>데이터 수집 → 수학 모델링 → 회귀분석 → 민감도 분석 → 한계 서술</span>의 완결 구조를 갖춘 반면, 학생은 <span className="font-bold" style={{ color: '#C0392B' }}>수학 풀이 → 실험 확인</span>에서 멈춰 정량적 검증이 부족합니다. 오차율 계산이나 변수 통제를 추가하면 차별화됩니다.
              </p>
            </div>
          </div>

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

          <div className="mt-8 rounded-lg border border-blue-200 px-6 py-5 text-center" style={{ backgroundColor: '#F0F7FF' }}>
            <p className="mb-1 text-[15px] font-extrabold text-gray-900">다음 학기에 뭘 해야 할지 궁금하다면?</p>
            <p className="text-[12px]" style={{ color: '#5B9BD5' }}>유니로드와 상담해 보세요!</p>
          </div>
        </div>
        <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-10 py-4">
          <p className="text-xs text-gray-500">Written by <span className="font-extrabold" style={{ color: '#5B9BD5' }}>UNIROAD</span></p>
          <p className="text-xs text-gray-400">Page 4</p>
        </div>
      </div>
    </div>
  )
}

export default ReportKimMinseop
