// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { ToolHeightInput } from './ToolHeightInput'

afterEach(cleanup)

it('allows free typing, commits on blur and clears height to unknown', () => {
  const onChange = vi.fn()
  const { rerender } = render(<ToolHeightInput value={null} onChange={onChange} />)
  const input = screen.getByLabelText('Tool height (mm)')
  fireEvent.change(input, { target: { value: '12.5' } })
  expect(onChange).not.toHaveBeenCalled()
  fireEvent.blur(input)
  expect(onChange).toHaveBeenCalledWith(12.5)
  rerender(<ToolHeightInput value={12.5} onChange={onChange} />)
  fireEvent.change(screen.getByLabelText('Tool height (mm)'), { target: { value: '' } })
  fireEvent.blur(screen.getByLabelText('Tool height (mm)'))
  expect(onChange).toHaveBeenLastCalledWith(null)
})

it('keeps the last saved height when the new height is invalid', () => {
  const onChange = vi.fn()
  render(<ToolHeightInput value={10} onChange={onChange} />)
  fireEvent.change(screen.getByLabelText('Tool height (mm)'), { target: { value: '-1' } })
  fireEvent.blur(screen.getByLabelText('Tool height (mm)'))
  expect(screen.getByRole('alert')).toBeTruthy()
  expect(onChange).not.toHaveBeenCalled()
})
