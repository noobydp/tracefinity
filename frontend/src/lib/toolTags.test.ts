import { describe, expect, it } from 'vitest'
import { libraryTags, matchesToolTag, normalizeTags } from './toolTags'

describe('tool tags', () => {
  it('trims, removes empty values and deduplicates without losing multi-word tags', () => {
    expect(normalizeTags([' Hex keys ', '', 'hex KEYS', 'Sockets', '  '])).toEqual(['Hex keys', 'Sockets'])
  })

  it('collects unique tags across projects for the library filter', () => {
    expect(libraryTags([{ tags: ['Sockets', 'Hex keys'] }, { tags: ['sockets', 'Measuring'] }, { tags: [] }]))
      .toEqual(['Hex keys', 'Measuring', 'Sockets'])
  })

  it('matches full tags without case sensitivity, while all includes untagged tools', () => {
    expect(matchesToolTag({ tags: ['Hex keys'] }, 'hex keys')).toBe(true)
    expect(matchesToolTag({ tags: ['Hex keys'] }, 'hex')).toBe(false)
    expect(matchesToolTag({ tags: [] }, 'hex keys')).toBe(false)
    expect(matchesToolTag({ tags: [] }, '')).toBe(true)
  })
})
