import { describe, expect, it } from 'vitest'
import { FACTORY_BIN_CONFIG } from './binDefaults'
import { toolFootprint } from './toolDimensions'

const rectangle = (width: number, depth: number) => [
  { x: -width / 2, y: -depth / 2 }, { x: width / 2, y: -depth / 2 },
  { x: width / 2, y: depth / 2 }, { x: -width / 2, y: depth / 2 },
]

describe('tool footprint matches automatic bin sizing', () => {
  // These are also measured against actual STL cavities by
  // backend/tests/test_bin_autosize_accuracy.py.
  it.each([
    [true, false, 1.6, 3], [false, false, 1.6, 2],
    [true, true, 1.6, 2.5], [true, false, 3, 3],
  ])('reserves lip/wall and clearance (%s, %s, %s)', (lip, halfGrid, wall, expected) => {
    const config = { ...FACTORY_BIN_CONFIG, stacking_lip: lip as boolean, half_grid_base: halfGrid as boolean, wall_thickness: wall as number, cutout_clearance: 0.1 }
    expect(toolFootprint(rectangle(80, 30), config)).toEqual({ x: expected, y: 1 })
    expect(toolFootprint(rectangle(30, 80), config)).toEqual({ x: 1, y: expected })
  })

  it('uses reference settings and recalculates after an outline edit', () => {
    expect(toolFootprint(rectangle(80, 30))).toEqual({ x: 3, y: 1 })
    expect(toolFootprint(rectangle(30, 30))).toEqual({ x: 1, y: 1 })
  })

  it('does not invent a footprint for missing or invalid geometry', () => {
    expect(toolFootprint([])).toBeNull()
    expect(toolFootprint([{ x: NaN, y: 0 }])).toBeNull()
    expect(toolFootprint([{ x: 0, y: 0 }])).toBeNull()
  })
})
