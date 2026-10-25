import type { ToolSummary } from '@/types'
import { toolFootprint } from './toolDimensions'

export interface DimensionFilterValues {
  minWidth: string; maxWidth: string
  minDepth: string; maxDepth: string
  minHeight: string; maxHeight: string
}

export const EMPTY_DIMENSION_FILTERS: DimensionFilterValues = {
  minWidth: '', maxWidth: '', minDepth: '', maxDepth: '', minHeight: '', maxHeight: '',
}

interface Range { min?: number; max?: number }
export interface DimensionRanges { width: Range; depth: Range; height: Range }

export function parseDimensionFilters(values: DimensionFilterValues): { ranges: DimensionRanges | null; error: string | null } {
  const ranges: DimensionRanges = { width: {}, depth: {}, height: {} }
  for (const [axis, minKey, maxKey] of [
    ['width', 'minWidth', 'maxWidth'], ['depth', 'minDepth', 'maxDepth'], ['height', 'minHeight', 'maxHeight'],
  ] as const) {
    for (const [bound, key] of [['min', minKey], ['max', maxKey]] as const) {
      if (!values[key].trim()) continue
      const number = Number(values[key])
      if (!Number.isFinite(number) || number < 0) return { ranges: null, error: `${axis}: enter finite values of zero or more.` }
      ranges[axis][bound] = number
    }
    const { min, max } = ranges[axis]
    if (min !== undefined && max !== undefined && min > max) {
      return { ranges: null, error: `${axis}: minimum must not exceed maximum.` }
    }
  }
  return { ranges, error: null }
}

function active(range: Range): boolean { return range.min !== undefined || range.max !== undefined }
function within(value: number, range: Range): boolean {
  return (range.min === undefined || value >= range.min) && (range.max === undefined || value <= range.max)
}

export function matchesToolDimensions(tool: Pick<ToolSummary, 'points' | 'height_mm'>, ranges: DimensionRanges | null): boolean {
  // Invalid ranges pause size filtering; name/status filters still apply.
  if (!ranges) return true
  if (active(ranges.height) && (tool.height_mm == null || !within(tool.height_mm, ranges.height))) return false
  if (active(ranges.width) || active(ranges.depth)) {
    const footprint = toolFootprint(tool.points)
    if (!footprint || !within(footprint.x, ranges.width) || !within(footprint.y, ranges.depth)) return false
  }
  return true
}
