import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import CountryPicker from '../components/intake/CountryPicker'
import PrioritiesInput from '../components/intake/PrioritiesInput'
import ProfileForm, { type FormErrors } from '../components/intake/ProfileForm'
import AmbientBackground from '../components/shared/AmbientBackground'
import { sectionEyebrowClass } from '../components/shared/formStyles'
import Logo from '../components/shared/Logo'
import { useCompare } from '../hooks/useCompare'
import type { CareerStage, CompareRequest } from '../types'
import GeneratingScreen from './LoadingPage'

// career_stage starts unselected, so the form state allows '' until validated.
type IntakeForm = Omit<CompareRequest, 'career_stage'> & { career_stage: CareerStage | '' }

const INITIAL_FORM: IntakeForm = {
  citizenship: '',
  degree_field: '',
  career_stage: '',
  country_a: 'US',
  country_b: 'UK',
  user_context: '',
}

// Trust signals shown under the masthead, each with a minimal line icon.
const TRUST_SIGNALS: { label: string; icon: React.ReactNode }[] = [
  {
    label: 'Live OECD & BLS data',
    icon: (
      <path
        d="M3 13.5 L7 9 L10 11.5 L14 6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    ),
  },
  {
    label: 'Visa rules cited & dated',
    icon: (
      <>
        <path d="M4 2.5 H10 L13 5.5 V14 a0.5 0.5 0 0 1 -0.5 0.5 H4 a0.5 0.5 0 0 1 -0.5 -0.5 V3 a0.5 0.5 0 0 1 0.5 -0.5 Z" />
        <path d="M6 8.5 H11 M6 11 H11" strokeLinecap="round" />
      </>
    ),
  },
  {
    label: 'We never choose for you',
    icon: (
      <>
        <path d="M8 2 L13.5 4.2 V8 c0 3.4 -2.4 5.4 -5.5 6.4 C4.9 13.4 2.5 11.4 2.5 8 V4.2 Z" />
        <path d="M5.8 8.2 L7.3 9.7 L10.3 6.4" strokeLinecap="round" strokeLinejoin="round" />
      </>
    ),
  },
]

function validate(form: IntakeForm): FormErrors {
  const errors: FormErrors = {}
  if (!form.citizenship.trim()) errors.citizenship = 'Citizenship is required.'
  if (!form.degree_field.trim()) errors.degree_field = 'Degree field is required.'
  if (!form.career_stage) errors.career_stage = 'Select a career stage.'
  if (form.country_a === form.country_b) errors.country_b = 'Pick two different countries.'
  if (!form.user_context.trim()) errors.user_context = 'Tell us what matters most to you.'
  return errors
}

function SectionHeader({ index, title }: { index: string; title: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="font-mono text-[11px] font-semibold text-path-a/80">{index}</span>
      <h2 className={sectionEyebrowClass}>{title}</h2>
      <span className="h-px flex-1 bg-gradient-to-r from-line to-transparent" />
    </div>
  )
}

export default function IntakePage() {
  const [form, setForm] = useState<IntakeForm>(INITIAL_FORM)
  const [errors, setErrors] = useState<FormErrors>({})
  const { submit, loading, error } = useCompare()
  const navigate = useNavigate()

  function handleChange(field: keyof CompareRequest, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const found = validate(form)
    setErrors(found)
    if (Object.keys(found).length > 0) return

    try {
      // career_stage is non-empty here (validation passed).
      const payload = await submit(form as CompareRequest)
      navigate('/dashboard', { state: { payload } })
    } catch {
      // error is surfaced from the hook below; stay on the page.
    }
  }

  return (
    <>
      <AmbientBackground />
      <main className="mx-auto max-w-2xl px-5 py-12 sm:py-16">
        <header>
          <div className="flex items-center gap-2.5">
            <Logo size={26} />
            <p className="font-mono text-xs font-medium uppercase tracking-[0.28em] text-ink-muted">
              Tradeoff
            </p>
          </div>

          <h1 className="mt-6 font-display text-3xl font-bold leading-[1.1] tracking-tight text-ink sm:text-[2.6rem]">
            Where should you
            <br className="hidden sm:block" />{' '}
            <span className="bg-gradient-to-r from-path-a via-ink to-path-b bg-clip-text text-transparent">
              build your career?
            </span>
          </h1>
          <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-ink-muted">
            Two countries, compared honestly — wages, cost of living, taxes, and the visa
            routes your citizenship actually opens.
          </p>

          <ul className="mt-7 flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-[11px] uppercase tracking-[0.08em] text-ink-muted">
            {TRUST_SIGNALS.map((item) => (
              <li key={item.label} className="flex items-center gap-2 whitespace-nowrap">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  aria-hidden
                  className="text-path-a"
                >
                  {item.icon}
                </svg>
                {item.label}
              </li>
            ))}
          </ul>
        </header>

        <form
          onSubmit={handleSubmit}
          noValidate
          className="mt-10 space-y-9 rounded-2xl border border-line/70 bg-surface/40 p-6 shadow-2xl shadow-black/30 backdrop-blur-sm sm:mt-12 sm:p-8"
        >
          <section className="space-y-4">
            <SectionHeader index="01" title="You" />
            <ProfileForm
              citizenship={form.citizenship}
              degreeField={form.degree_field}
              careerStage={form.career_stage}
              errors={errors}
              onChange={handleChange}
            />
          </section>

          <section className="space-y-4">
            <SectionHeader index="02" title="The choice" />
            <CountryPicker
              countryA={form.country_a}
              countryB={form.country_b}
              errors={errors}
              onChange={handleChange}
            />
          </section>

          <section className="space-y-4">
            <SectionHeader index="03" title="What matters" />
            <PrioritiesInput value={form.user_context} errors={errors} onChange={handleChange} />
          </section>

          {error && (
            <p role="alert" className="text-sm text-signal">
              {error}
            </p>
          )}

          <div className="space-y-3 pt-1">
            <button
              type="submit"
              disabled={loading}
              className="group flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-path-a to-[#2E97A6] px-4 py-3.5 font-medium text-paper shadow-lg shadow-path-a/20 transition duration-200 hover:shadow-xl hover:shadow-path-a/30 focus-visible:ring-2 focus-visible:ring-path-a focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? 'Comparing…' : 'Compare the two paths'}
              {!loading && (
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  aria-hidden
                  className="transition-transform duration-200 group-hover:translate-x-0.5"
                >
                  <path d="M3 8 H12 M8 4 L12 8 L8 12" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </button>
            <p className="text-center text-sm text-ink-muted">
              We lay out the trade-offs side by side. The decision stays yours.
            </p>
          </div>
        </form>
      </main>

      {loading && (
        <div className="fixed inset-0 z-50">
          <GeneratingScreen countryA={form.country_a} countryB={form.country_b} />
        </div>
      )}
    </>
  )
}
