import type { Point } from '@/types'
import { toolFootprint, type FootprintConfig } from '@/lib/toolDimensions'
import { getGridSizeError } from '@/lib/constants'

export function ToolMeasurements({ tool, config }: { tool: { points: Point[]; height_mm?: number | null }; config?: FootprintConfig }) {
  const footprint = toolFootprint(tool.points, config)
  const limitError = footprint ? getGridSizeError(footprint.x, footprint.y) : null
  return (
    <span className="block text-[10px] leading-4 text-text-secondary" title={config
      ? 'Minimum footprint in the saved orientation using the current bin settings. Height is measured by you.'
      : 'Reference minimum footprint in the saved orientation: standard walls, stacking lip, 1 mm clearance, whole grid. Height is measured by you.'}>
      {footprint ? `${footprint.x}×${footprint.y}u` : 'Footprint unknown'}
      {' · '}{tool.height_mm == null ? 'Height not set' : `${tool.height_mm} mm high`}
      {limitError && <span className="block" title={limitError}>Exceeds bin limits</span>}
    </span>
  )
}
