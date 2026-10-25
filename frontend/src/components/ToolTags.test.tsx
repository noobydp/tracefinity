// @vitest-environment jsdom
import { useState } from 'react'
import { afterEach, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { ToolTagsEditor, ToolTagFilter } from './ToolTags'

afterEach(cleanup)

function Editor() {
  const [tags, setTags] = useState(['Sockets'])
  return <ToolTagsEditor tags={tags} onChange={setTags} />
}

it('adds a multi-word tag with Enter, prevents duplicates, and removes tags', () => {
  render(<Editor />)
  const input = screen.getByLabelText('Tags')
  fireEvent.change(input, { target: { value: '  Hex keys  ' } })
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(screen.getByRole('button', { name: 'Remove tag Hex keys' })).toBeTruthy()
  fireEvent.change(input, { target: { value: 'hex KEYS' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add tag' }))
  expect(screen.getAllByRole('button', { name: /Remove tag/ })).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: 'Remove tag Sockets' }))
  fireEvent.click(screen.getByRole('button', { name: 'Remove tag Hex keys' }))
  expect(screen.queryByRole('button', { name: /Remove tag/ })).toBeNull()
})

it('keeps a removed tag filter clearable when no remaining tool carries it', () => {
  function Filter() {
    const [value, setValue] = useState('sockets')
    return <ToolTagFilter tags={[]} value={value} onChange={setValue} />
  }
  render(<Filter />)
  const select = screen.getByRole('combobox', { name: 'Filter by tag' }) as HTMLSelectElement
  expect(select.value).toBe('sockets')
  fireEvent.change(select, { target: { value: '' } })
  expect(select.value).toBe('')
})
