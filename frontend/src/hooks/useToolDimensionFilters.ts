import { useMemo, useState } from 'react'
import { EMPTY_DIMENSION_FILTERS, parseDimensionFilters } from '@/lib/toolDimensionFilters'

export function useToolDimensionFilters() {
  const [values, setValues] = useState(EMPTY_DIMENSION_FILTERS)
  const { ranges, error } = useMemo(() => parseDimensionFilters(values), [values])
  return { values, setValues, ranges, error }
}
