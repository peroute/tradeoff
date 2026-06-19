import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import CountryPicker from '../components/intake/CountryPicker'
import PrioritiesInput from '../components/intake/PrioritiesInput'
import ProfileForm, { type FormErrors } from '../components/intake/ProfileForm'
import { useCompare } from '../hooks/useCompare'
import type { CareerStage, CompareRequest } from '../types'

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
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">Compare your options</h1>
      <p className="mt-2 text-gray-600">
        Tell us about you and the two countries you're weighing. We'll compare wages,
        cost of living, taxes, and visa routes.
      </p>

      <form onSubmit={handleSubmit} noValidate className="mt-8 space-y-6">
        <ProfileForm
          citizenship={form.citizenship}
          degreeField={form.degree_field}
          careerStage={form.career_stage}
          errors={errors}
          onChange={handleChange}
        />
        <CountryPicker
          countryA={form.country_a}
          countryB={form.country_b}
          errors={errors}
          onChange={handleChange}
        />
        <PrioritiesInput value={form.user_context} errors={errors} onChange={handleChange} />

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? 'Comparing…' : 'Compare'}
        </button>
      </form>
    </main>
  )
}
