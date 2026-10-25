'use client'

import { useState } from 'react'
import { X } from 'lucide-react'
import { normalizeTags } from '@/lib/toolTags'

export function ToolTags({ tags }: { tags: string[] }) {
  if (tags.length === 0) return null
  return (
    <ul aria-label="Tags" className="mt-1.5 flex flex-wrap gap-1">
      {tags.map((tag, index) => (
        <li key={`${tag}-${index}`} className="max-w-full break-words rounded bg-inset px-1.5 py-0.5 text-[11px] text-text-secondary">
          {tag}
        </li>
      ))}
    </ul>
  )
}

export function ToolTagsEditor({ tags, onChange }: { tags: string[]; onChange: (tags: string[]) => void }) {
  const [draft, setDraft] = useState('')

  function addTag() {
    if (!draft.trim()) return
    onChange(normalizeTags([...tags, draft]))
    setDraft('')
  }

  return (
    <div>
      <label htmlFor="tool-tag" className="block text-[11px] font-semibold text-text-secondary">Tags</label>
      <div className="mt-1 flex gap-1.5">
        <input
          id="tool-tag"
          value={draft}
          onChange={event => setDraft(event.target.value)}
          onKeyDown={event => {
            if (event.key === 'Enter') { event.preventDefault(); addTag() }
            if (event.key === 'Escape') setDraft('')
          }}
          placeholder="e.g. hex keys"
          className="min-w-0 flex-1 rounded-[7px] border border-border-subtle bg-inset px-2 py-1.5 text-xs text-text-primary focus:border-accent outline-none"
        />
        <button type="button" onClick={addTag} disabled={!draft.trim()} className="btn-secondary px-2 text-xs">Add tag</button>
      </div>
      <ul aria-label="Tool tags" className="mt-1.5 flex flex-wrap gap-1">
        {tags.map((tag, index) => (
          <li key={`${tag}-${index}`} className="flex max-w-full items-center rounded bg-inset pl-2 text-xs text-text-secondary">
            <span className="min-w-0 break-words">{tag}</span>
            <button
              type="button"
              aria-label={`Remove tag ${tag}`}
              onClick={() => onChange(tags.filter((_, position) => position !== index))}
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded hover:text-text-primary focus-visible:outline-accent"
            ><X className="h-3.5 w-3.5" /></button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function ToolTagFilter({ tags, value, onChange }: { tags: string[]; value: string; onChange: (tag: string) => void }) {
  return (
    <label className="mb-3 flex items-center gap-2 text-xs text-text-secondary">
      Filter by tag
      <select value={value} onChange={event => onChange(event.target.value)} className="max-w-[220px] rounded-[7px] border border-border-subtle bg-surface px-2 py-1.5 text-text-primary">
        <option value="">All tags</option>
        {tags.map(tag => <option key={tag.toLowerCase()} value={tag.toLowerCase()}>{tag}</option>)}
        {value && !tags.some(tag => tag.toLowerCase() === value) && <option value={value}>{value}</option>}
      </select>
    </label>
  )
}
