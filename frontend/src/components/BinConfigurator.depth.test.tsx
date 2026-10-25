// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { BinConfigurator } from './BinConfigurator'
import { FACTORY_BIN_CONFIG } from '@/lib/binDefaults'

afterEach(cleanup)
beforeEach(() => localStorage.setItem('theme', 'dark'))

function row(label: string) {
  return within(screen.getByText(label, { exact: true }).parentElement!)
}

describe('bin depth controls', () => {
  it.each([[2, 7, 7.25], [3, 14, 14.25]])('keeps the requested depth when enabling the lip at %iu', (height, depth, maximum) => {
    const onChange = vi.fn()
    render(<BinConfigurator config={{ ...FACTORY_BIN_CONFIG, height_units: height, cutout_depth: depth, stacking_lip: false }} onChange={onChange} />)
    expect(row('Cutout Depth').getByRole('spinbutton').getAttribute('max')).toBe(String(maximum))
    fireEvent.click(row('Stacking lip').getByRole('button'))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ stacking_lip: true, cutout_depth: depth }))
  })

  it('accepts the full quarter-millimetre maximum', () => {
    const onChange = vi.fn()
    render(<BinConfigurator config={{ ...FACTORY_BIN_CONFIG, height_units: 2, cutout_depth: 7 }} onChange={onChange} />)
    const depth = row('Cutout Depth').getByRole('spinbutton')
    fireEvent.change(depth, { target: { value: '7.25' } })
    fireEvent.blur(depth)
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ cutout_depth: 7.25 }))
  })

  it('clamps a height reduction to the safe shallow depth and explains the limit', () => {
    const onChange = vi.fn()
    const { rerender } = render(<BinConfigurator config={FACTORY_BIN_CONFIG} onChange={onChange} />)
    const height = row('Height').getByRole('spinbutton')
    fireEvent.change(height, { target: { value: '1' } })
    fireEvent.blur(height)
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ height_units: 1, cutout_depth: 0.25 }))
    rerender(<BinConfigurator config={onChange.mock.lastCall![0]} onChange={onChange} />)
    const depth = row('Cutout Depth').getByRole('spinbutton')
    expect(depth.getAttribute('min')).toBe('0.25')
    expect(depth.getAttribute('max')).toBe('0.25')
    expect(screen.getByText(/A 1u bin leaves only 0.25mm/)).toBeTruthy()
    fireEvent.change(height, { target: { value: '2' } })
    fireEvent.blur(height)
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ height_units: 2, cutout_depth: 5 }))
  })
})
