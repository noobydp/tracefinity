// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import HomePage from './page'
import type { ToolSummary } from '@/types'

const { tools } = vi.hoisted(() => ({ tools: [] as ToolSummary[] }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/hooks/useTheme', () => ({ useTheme: () => ({ theme: 'light' }) }))
vi.mock('@/components/ImageUploader', () => ({ ImageUploader: () => null }))
vi.mock('@/lib/api', () => ({
  listTools: async () => tools, listBins: async () => [], listProjects: async () => [], listPhotoStations: async () => [],
  getAvailableKeys: async () => ({ photo_stations: false }), getImageUrl: (url: string) => url,
}))

afterEach(() => { cleanup(); tools.length = 0; localStorage.clear() })

function tool(name: string, width: number, height: number | null): ToolSummary {
  return {
    id: name, name, height_mm: height, points: [{ x: 0, y: 0 }, { x: width, y: 30 }],
    point_count: 2, created_at: null, interior_rings: [], smoothed: false, smooth_level: 0.5,
    thumbnail_url: null, image_transform: null, image_context: null, category: null, drawer: null,
    tags: [], project_ids: [], review_status: null, needs_cleanup: false,
  }
}

it('combines height and footprint filters with name search, and clears only size limits', async () => {
  tools.push(tool('Metric short', 30, 10), tool('Metric tall', 30, 30), tool('Wide unknown', 80, null))
  render(<HomePage />)
  await screen.findByText('Metric short')
  fireEvent.click(screen.getByText('Filter by size'))
  fireEvent.change(screen.getByLabelText('Maximum tool height (mm)'), { target: { value: '15' } })
  expect(screen.queryByText('Metric tall')).toBeNull()
  expect(screen.queryByText('Wide unknown')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Clear size filters' }))
  expect(screen.getByText('Wide unknown')).toBeTruthy()
  const header = screen.getByRole('heading', { name: 'Tools' }).parentElement!.parentElement!
  fireEvent.click(within(header).getByRole('button', { name: /^Search$/ }))
  fireEvent.change(screen.getByPlaceholderText('Filter...'), { target: { value: 'Metric' } })
  fireEvent.change(screen.getByLabelText('Minimum grid width (u)'), { target: { value: '3' } })
  expect(screen.getByText('No tools match this filter.')).toBeTruthy()
  fireEvent.change(screen.getByLabelText('Maximum grid width (u)'), { target: { value: '1' } })
  expect(screen.getByRole('alert').textContent).toContain('Size filters paused')
  expect(screen.getByText('Metric short')).toBeTruthy()
  expect(screen.queryByText('Wide unknown')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Clear size filters' }))
  expect(screen.getByText('Metric tall')).toBeTruthy()
  expect(screen.queryByText('Wide unknown')).toBeNull()
})
