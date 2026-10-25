import type { BinConfig, Point } from '@/types'
import { FACTORY_BIN_CONFIG } from './binDefaults'
import { binFitMargin, requiredGridUnits } from './constants'

export type FootprintConfig = Pick<BinConfig, 'wall_thickness' | 'stacking_lip' | 'cutout_clearance' | 'half_grid_base'>

/** Match bin creation in the tool's saved orientation. Library reference
 * values use standard settings; a bin picker may supply its current config. */
export function toolFootprint(points: Point[], config: FootprintConfig = FACTORY_BIN_CONFIG): { x: number; y: number } | null {
  if (points.length === 0) return null
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const point of points) {
    if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) return null
    minX = Math.min(minX, point.x)
    minY = Math.min(minY, point.y)
    maxX = Math.max(maxX, point.x)
    maxY = Math.max(maxY, point.y)
  }
  if (maxX <= minX || maxY <= minY) return null
  const margin = binFitMargin(config)
  return {
    x: requiredGridUnits(maxX - minX, margin, config.half_grid_base),
    y: requiredGridUnits(maxY - minY, margin, config.half_grid_base),
  }
}
