import { describe, expect, it } from 'vitest'
import { calcMaxCutoutDepth } from './BinConfigurator'

describe('calcMaxCutoutDepth', () => {
  it.each([[1, 0.25], [2, 7.25], [3, 14.25], [4, 21.25]])(
    '%iu preserves the base and 2mm floor with a %fmm maximum', (height, expected) => {
      expect(calcMaxCutoutDepth(height)).toBe(expected)
    },
  )
})
