import { apiRequest } from '@/shared/lib/api'

import type {
  MapEditorCommitPayload,
  MapEditorCommitResult,
  MapEditorDraftCreatePayload,
  MapEditorMetrics,
  MapEditorPlantingConfig,
  MapEditorPreview,
  MapEditorState,
} from '@/features/map-editor/types'

export function getMapEditorState(parcelId: string) {
  return apiRequest<MapEditorState>(`/parcels/${parcelId}/map-editor`)
}

export function computeMapEditorMetrics(boundary: GeoJSON.Polygon | GeoJSON.MultiPolygon, parcelId?: string) {
  const path = parcelId ? `/parcels/${parcelId}/map-editor/metrics` : '/map-editor/metrics'
  return apiRequest<MapEditorMetrics>(path, {
    method: 'POST',
    body: JSON.stringify({ boundary }),
  })
}

export function previewMapEditorLayout(
  boundary: GeoJSON.Polygon | GeoJSON.MultiPolygon,
  config: MapEditorPlantingConfig,
  parcelId?: string,
) {
  const path = parcelId ? `/parcels/${parcelId}/map-editor/preview` : '/map-editor/preview'
  return apiRequest<MapEditorPreview>(path, {
    method: 'POST',
    body: JSON.stringify({ boundary, config }),
  })
}

export function commitMapEditor(parcelId: string, payload: MapEditorCommitPayload) {
  return apiRequest<MapEditorCommitResult>(`/parcels/${parcelId}/map-editor/commit`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function createMapEditorParcel(payload: MapEditorDraftCreatePayload) {
  return apiRequest<MapEditorState>('/map-editor/parcels', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export type ResolveLocationResult = {
  latitude: number
  longitude: number
  label: string
  source: 'coordinates' | 'maps_url' | 'geocode'
}

export function resolveMapEditorLocation(query: string) {
  return apiRequest<ResolveLocationResult>('/map-editor/resolve-location', {
    method: 'POST',
    body: JSON.stringify({ query }),
  })
}
