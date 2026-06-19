import type { CareerStage, CompareRequest } from '../../types'
import { CAREER_STAGES } from '../../types'
import { errorClass, inputClass, labelClass } from '../shared/formStyles'

export type FormErrors = Partial<Record<keyof CompareRequest, string>>

interface ProfileFormProps {
  citizenship: string
  degreeField: string
  careerStage: CareerStage | ''
  errors: FormErrors
  onChange: (field: keyof CompareRequest, value: string) => void
}

export default function ProfileForm({
  citizenship,
  degreeField,
  careerStage,
  errors,
  onChange,
}: ProfileFormProps) {
  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="citizenship" className={labelClass}>
          Citizenship
        </label>
        <input
          id="citizenship"
          type="text"
          className={inputClass}
          placeholder="e.g. India"
          value={citizenship}
          onChange={(e) => onChange('citizenship', e.target.value)}
          aria-invalid={Boolean(errors.citizenship)}
        />
        {errors.citizenship && <p className={errorClass}>{errors.citizenship}</p>}
      </div>

      <div>
        <label htmlFor="degree_field" className={labelClass}>
          Degree field
        </label>
        <input
          id="degree_field"
          type="text"
          className={inputClass}
          placeholder="e.g. Computer Science"
          value={degreeField}
          onChange={(e) => onChange('degree_field', e.target.value)}
          aria-invalid={Boolean(errors.degree_field)}
        />
        {errors.degree_field && <p className={errorClass}>{errors.degree_field}</p>}
      </div>

      <div>
        <label htmlFor="career_stage" className={labelClass}>
          Career stage
        </label>
        <select
          id="career_stage"
          className={inputClass}
          value={careerStage}
          onChange={(e) => onChange('career_stage', e.target.value)}
          aria-invalid={Boolean(errors.career_stage)}
        >
          <option value="">Select a stage…</option>
          {CAREER_STAGES.map((stage) => (
            <option key={stage.value} value={stage.value}>
              {stage.label}
            </option>
          ))}
        </select>
        {errors.career_stage && <p className={errorClass}>{errors.career_stage}</p>}
      </div>
    </div>
  )
}
