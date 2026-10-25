'use client'

import { useState } from 'react'

export function ToolHeightInput({ value, onChange }: { value: number | null; onChange: (value: number | null) => void }) {
  const [error, setError] = useState('')

  function commit(raw: string) {
    const next = raw.trim() === '' ? null : Number(raw)
    if (next !== null && (!Number.isFinite(next) || next <= 0)) {
      setError('Enter a positive height, or leave blank if unknown.')
      return
    }
    setError('')
    if (next !== value) onChange(next)
  }

  return (
    <div className="mt-2">
      <label htmlFor="tool-height" className="text-xs text-text-secondary">Tool height (mm)</label>
      <input
        key={value ?? 'unknown'} id="tool-height" type="number" min="0" step="any" defaultValue={value ?? ''}
        aria-invalid={Boolean(error)} aria-describedby="tool-height-help"
        onChange={() => setError('')}
        onBlur={event => commit(event.target.value)}
        onKeyDown={event => { if (event.key === 'Enter') event.currentTarget.blur() }}
        className="mt-1 block w-full rounded-[7px] border border-border-subtle bg-inset px-2 py-1 text-xs text-text-primary focus:border-accent outline-none"
      />
      <p id="tool-height-help" className="mt-1 text-[11px] text-text-secondary">Measured thickness; blank means unknown.</p>
      {error && <p role="alert" className="mt-1 text-xs text-text-primary">{error}</p>}
    </div>
  )
}
