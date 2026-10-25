'use client'

import { EMPTY_DIMENSION_FILTERS, type DimensionFilterValues } from '@/lib/toolDimensionFilters'

export function ToolDimensionFilters({ values, onChange, error }: {
  values: DimensionFilterValues
  onChange: (values: DimensionFilterValues) => void
  error: string | null
}) {
  const hasFilters = Object.values(values).some(value => value.trim())
  return (
    <details className="mb-3 rounded-[8px] border border-border-subtle bg-surface px-3 py-2">
      <summary className="cursor-pointer text-xs font-medium text-text-primary">
        Filter by size{error ? ' (paused — fix ranges)' : hasFilters ? ' (active)' : ''}
      </summary>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        {[
          { label: 'Grid width (u)', min: 'minWidth', max: 'maxWidth', step: '0.5' },
          { label: 'Grid depth (u)', min: 'minDepth', max: 'maxDepth', step: '0.5' },
          { label: 'Tool height (mm)', min: 'minHeight', max: 'maxHeight', step: 'any' },
        ].map(field => (
          <fieldset key={field.label}>
            <legend className="mb-1 text-xs text-text-primary">{field.label}</legend>
            <div className="flex gap-2">
              {(['min', 'max'] as const).map(bound => {
                const key = field[bound] as keyof DimensionFilterValues
                const label = bound === 'min' ? 'Minimum' : 'Maximum'
                return (
                  <label key={bound} className="min-w-0 flex-1 text-[11px] text-text-secondary">
                    {label}
                    <input
                      type="number" min="0" step={field.step} value={values[key]}
                      aria-label={`${label} ${field.label.toLowerCase()}`}
                      onChange={event => onChange({ ...values, [key]: event.target.value })}
                      className="mt-1 block w-full rounded-[7px] border border-border-subtle bg-inset px-2 py-1 text-xs text-text-primary focus:border-accent outline-none"
                    />
                  </label>
                )
              })}
            </div>
          </fieldset>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-text-secondary">Footprints use standard settings in the saved orientation. Tools with unknown height are excluded only when a height limit is set.</p>
      {error && <p role="alert" className="mt-2 text-xs text-text-primary">Size filters paused: {error}</p>}
      <button type="button" disabled={!hasFilters} onClick={() => onChange(EMPTY_DIMENSION_FILTERS)} className="btn-secondary mt-2 px-2 py-1 text-xs">Clear size filters</button>
    </details>
  )
}
