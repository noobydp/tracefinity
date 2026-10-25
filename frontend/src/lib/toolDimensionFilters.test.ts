import { describe, expect, it } from 'vitest'
import { EMPTY_DIMENSION_FILTERS, matchesToolDimensions, parseDimensionFilters } from './toolDimensionFilters'

const tool = { points: [{ x: 0, y: 0 }, { x: 80, y: 30 }], height_mm: 12.5 }
const parse = (values = {}) => parseDimensionFilters({ ...EMPTY_DIMENSION_FILTERS, ...values })

describe('tool size filters', () => {
  it.each([
    [{ minWidth: '3', maxWidth: '3' }, true], [{ maxWidth: '2' }, false],
    [{ minDepth: '1', maxDepth: '1' }, true], [{ minDepth: '2' }, false],
    [{ minHeight: '12.5', maxHeight: '12.5' }, true], [{ maxHeight: '12.4' }, false],
    [{ minWidth: '3', maxDepth: '1', maxHeight: '20' }, true],
    [{ maxWidth: '1', maxDepth: '3' }, false], // no implicit rotation
  ])('applies inclusive limits %j', (values, expected) => {
    expect(matchesToolDimensions(tool, parse(values).ranges)).toBe(expected)
  })

  it('keeps unknown height unless a height bound is active', () => {
    const unknown = { ...tool, height_mm: null }
    expect(matchesToolDimensions(unknown, parse().ranges)).toBe(true)
    expect(matchesToolDimensions(unknown, parse({ minWidth: '3' }).ranges)).toBe(true)
    expect(matchesToolDimensions(unknown, parse({ minHeight: '0' }).ranges)).toBe(false)
  })

  it('excludes missing outlines only when a footprint bound is active', () => {
    expect(matchesToolDimensions({ ...tool, points: [] }, parse({ maxHeight: '20' }).ranges)).toBe(true)
    expect(matchesToolDimensions({ ...tool, points: [] }, parse({ maxWidth: '3' }).ranges)).toBe(false)
  })

  it.each([{ minWidth: '-1' }, { maxHeight: 'Infinity' }, { minDepth: 'bad' }, { minWidth: '3', maxWidth: '1' }])('reports invalid ranges and pauses size filtering: %j', values => {
    const result = parse(values)
    expect(result.error).toBeTruthy()
    expect(result.ranges).toBeNull()
    expect(matchesToolDimensions(tool, result.ranges)).toBe(true)
  })
})
