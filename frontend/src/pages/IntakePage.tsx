import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import CountryPicker from '../components/intake/CountryPicker'
import PrioritiesInput from '../components/intake/PrioritiesInput'
import ProfileForm, { type FormErrors } from '../components/intake/ProfileForm'
import { sectionEyebrowClass } from '../components/shared/formStyles'
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

function validate(form: IntakeForm): FormErrors {
  const errors: FormErrors = {}
  if (!form.citizenship.trim()) errors.citizenship = 'Citizenship is required.'
  if (!form.degree_field.trim()) errors.degree_field = 'Degree field is required.'
  if (!form.career_stage) errors.career_stage = 'Select a career stage.'
  if (form.country_a === form.country_b) errors.country_b = 'Pick two different countries.'
  if (!form.user_context.trim()) errors.user_context = 'Tell us what matters most to you.'
  return errors
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
    <main className="mx-auto max-w-2xl px-5 py-12 sm:py-16">
      <header>
        <p className="font-mono text-xs font-medium uppercase tracking-[0.28em] text-ink-muted">
          Tradeoff · a considered choice
        </p>
        <h1 className="mt-5 font-display text-3xl font-bold leading-tight text-ink sm:text-4xl">
          Where should you build your career?
        </h1>
        <p className="mt-3 max-w-xl text-ink-muted">
          Two countries, compared honestly — wages, cost of living, taxes, and the visa routes
          your citizenship actually opens.
        </p>

        <ul className="mt-7 flex flex-nowrap items-center justify-between gap-x-4 font-mono text-[11px] uppercase tracking-[0.08em] text-ink-muted">
          {[
            'Live OECD & BLS wage data',
            'Visa rules cited & dated',
            'We never choose for you',
          ].map((item) => (
            <li key={item} className="flex items-center gap-2 whitespace-nowrap">
              <span aria-hidden className="h-1.5 w-1.5 rounded-[1px] bg-path-a" />
              {item}
            </li>
          ))}
        </ul>
      </header>

      <form onSubmit={handleSubmit} noValidate className="mt-12 space-y-10">
        <section className="space-y-4">
          <div className="flex items-center gap-3">
            <h2 className={sectionEyebrowClass}>You</h2>
            <span className="h-px flex-1 bg-line" />
          </div>
          <ProfileForm
            citizenship={form.citizenship}
            degreeField={form.degree_field}
            careerStage={form.career_stage}
            errors={errors}
            onChange={handleChange}
          />
        </section>

        <section className="space-y-4">
          <div className="flex items-center gap-3">
            <h2 className={sectionEyebrowClass}>The choice</h2>
            <span className="h-px flex-1 bg-line" />
          </div>
          <CountryPicker
            countryA={form.country_a}
            countryB={form.country_b}
            errors={errors}
            onChange={handleChange}
          />
        </section>

        <section className="space-y-4">
          <div className="flex items-center gap-3">
            <h2 className={sectionEyebrowClass}>What matters</h2>
            <span className="h-px flex-1 bg-line" />
          </div>
          <PrioritiesInput value={form.user_context} errors={errors} onChange={handleChange} />
        </section>

        {error && (
          <p role="alert" className="text-sm text-signal">
            {error}
          </p>
        )}

        <div className="space-y-3">
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-ink px-4 py-3 font-medium text-paper transition-colors hover:bg-ink/90 focus-visible:ring-2 focus-visible:ring-path-a focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? 'Comparing…' : 'Compare'}
          </button>
          <p className="text-center text-sm text-ink-muted">
            We lay out the trade-offs side by side. The decision stays yours.
          </p>
        </div>
      </form>

      {loading && (
        <div className="fixed inset-0 z-50">
          <GeneratingScreen countryA={form.country_a} countryB={form.country_b} />
        </div>
      )}
    </main>
  )
}
