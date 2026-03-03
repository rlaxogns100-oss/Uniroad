import React from 'react'
import { Link } from 'react-router-dom'
import {
  getStudentGuideMethods as getStudentMethods,
  guideUserTypeTabs as userTypeTabs,
  type GuideMethodId as MethodId,
  type GuideUserType as UserType,
} from '../data/schoolRecordGuide'

function SchoolRecordGuidePage() {
  const [userType, setUserType] = React.useState<UserType>('student')
  const methods = getStudentMethods(userType)
  const [methodId, setMethodId] = React.useState<MethodId>(methods[0].id)

  React.useEffect(() => {
    if (!methods.some((method) => method.id === methodId)) {
      setMethodId(methods[0].id)
    }
  }, [methods, methodId])

  const currentMethod = methods.find((method) => method.id === methodId) || methods[0]

  return (
    <div className="min-h-screen bg-[#F9FAFB]">
      <div className="mx-auto w-full max-w-6xl px-4 pb-20 pt-8 sm:px-6">
        <header className="mb-6 rounded-[20px] bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-bold text-[#3182F6]">학교생활기록부 다운로드 안내</p>
              <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-[#191F28]">문서열람번호 없이 파일 업로드로 연동하기</h1>
              <p className="mt-3 text-base font-medium text-[#4E5968]">
                문서열람번호 입력 방식은 제외했습니다. 아래 방법 중 하나로 파일을 저장해 업로드해 주세요.
              </p>
            </div>
            <Link
              to="/school-record-deep?tab=link"
              className="inline-flex h-11 items-center justify-center rounded-xl bg-[#3182F6] px-4 text-sm font-bold text-white transition hover:bg-[#1f6fe2]"
            >
              연동 페이지로 이동
            </Link>
          </div>
        </header>

        <section className="mb-4 rounded-[20px] bg-white p-4 shadow-sm sm:p-5">
          <div className="grid grid-cols-2 gap-2">
            {userTypeTabs.map((tab) => {
              const active = tab.id === userType
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setUserType(tab.id)}
                  className={`h-11 rounded-xl text-sm font-bold transition ${
                    active ? 'bg-[#E8F1FF] text-[#3182F6]' : 'bg-[#F2F4F6] text-[#4E5968] hover:bg-[#E9EDF2]'
                  }`}
                >
                  {tab.label}
                </button>
              )
            })}
          </div>
        </section>

        <section className="mb-4 rounded-[20px] bg-white p-4 shadow-sm sm:p-5">
          <div className="flex flex-wrap gap-2">
            {methods.map((method) => {
              const active = method.id === methodId
              return (
                <button
                  key={method.id}
                  type="button"
                  onClick={() => setMethodId(method.id)}
                  className={`rounded-xl px-4 py-2 text-sm font-bold transition ${
                    active ? 'bg-[#191F28] text-white' : 'bg-[#F2F4F6] text-[#4E5968] hover:bg-[#E9EDF2]'
                  }`}
                >
                  {method.label}
                </button>
              )
            })}
          </div>
        </section>

        <section className="space-y-4">
          <div className="rounded-[20px] bg-white p-6 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-wide text-[#6B7684]">{currentMethod.short}</p>
            <h2 className="mt-1 text-2xl font-extrabold text-[#191F28]">{currentMethod.label}</h2>
            {currentMethod.links && currentMethod.links.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {currentMethod.links.map((item) => (
                  <a
                    key={item.href}
                    href={item.href}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-9 items-center justify-center rounded-lg border border-[#D9E2EC] px-3 text-xs font-bold text-[#3182F6] transition hover:bg-[#F4F8FF]"
                  >
                    {item.label}
                  </a>
                ))}
              </div>
            )}
          </div>

          {currentMethod.sections.map((section) => (
            <article key={section.title} className="rounded-[20px] bg-white p-6 shadow-sm">
              <h3 className="text-xl font-extrabold text-[#191F28]">{section.title}</h3>
              {section.summary && <p className="mt-2 text-sm font-medium text-[#4E5968]">{section.summary}</p>}

              <ol className="mt-5 space-y-6">
                {section.steps.map((step, index) => (
                  <li key={`${section.title}-${step.title}-${index}`} className="rounded-2xl bg-[#F9FAFB] p-4">
                    <div className="mb-3 flex items-center gap-3">
                      <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[#E8F1FF] text-sm font-extrabold text-[#3182F6]">
                        {index + 1}
                      </span>
                      <p className="text-lg font-bold text-[#191F28]">{step.title}</p>
                    </div>
                    <p className="text-sm font-medium leading-6 text-[#4E5968]">{step.description}</p>
                    {step.warning && <p className="mt-2 text-sm font-semibold text-[#D14343]">{step.warning}</p>}
                    {step.image && (
                      <div className="mt-4 overflow-hidden rounded-xl border border-[#EEF1F4] bg-white p-2">
                        <img src={step.image} alt={step.title} className="h-auto w-full rounded-lg" loading="lazy" />
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            </article>
          ))}

          <footer className="rounded-[20px] bg-white p-6 shadow-sm">
            <h3 className="text-lg font-extrabold text-[#191F28]">참고사항</h3>
            <ul className="mt-3 space-y-2 text-sm font-medium leading-6 text-[#4E5968]">
              <li>• 나이스 4세대 개편으로 인해 위 방식은 2022년 2월 이후 졸업생/재학생 기준입니다.</li>
              <li>• 2022년 2월 이전 졸업생은 생활기록부를 직접 입력해 주세요.</li>
            </ul>
          </footer>
        </section>
      </div>
    </div>
  )
}

export default SchoolRecordGuidePage
