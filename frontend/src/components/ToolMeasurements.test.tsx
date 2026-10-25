// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { ToolMeasurements } from './ToolMeasurements'

afterEach(cleanup)

it('distinguishes unknown height and updates when the outline or height changes', () => {
  const { rerender } = render(<ToolMeasurements tool={{ points: [{ x: 0, y: 0 }, { x: 80, y: 30 }] }} />)
  expect(screen.getByText('3×1u · Height not set')).toBeTruthy()
  rerender(<ToolMeasurements tool={{ points: [{ x: 0, y: 0 }, { x: 30, y: 30 }], height_mm: 12.5 }} />)
  expect(screen.getByText('1×1u · 12.5 mm high')).toBeTruthy()
})

it('does not present an oversized footprint as a printable bin', () => {
  render(<ToolMeasurements tool={{ points: [{ x: 0, y: 0 }, { x: 500, y: 500 }] }} />)
  expect(screen.getByText('Exceeds bin limits')).toBeTruthy()
})
