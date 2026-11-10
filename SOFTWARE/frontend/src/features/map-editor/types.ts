export type EditorMode =
  | 'select'
  | 'draw_boundary'
  | 'edit_boundary'
  | 'row_orientation'
  | 'generate_layout'
  | 'select_row'
  | 'select_tree'
  | 'edit_tree'
  | 'assign_variety'
  | 'measure'
  | 'inspect_index'

export type MapEditorPlantingConfig = {
  orientation_deg: number
  /** Polygon edge index used as parallel reference (authoritative on backend). */
  orientation_edge_index: number | null
  row_spacing_m: number
  tree_spacing_m: number
  first_row_offset_m: number
  last_row_offset_m: number
  row_end_offset_m: number
  tree_start_offset_m: number | null
  boundary_buffer_m: number
  target_row_count: number | null
  start_row_number: number
  number_rows_ascending: boolean
  default_variety: string | null
  default_planting_year: number | null
}

export type WizardStep =
  | 'basics'
  | 'boundary'
  | 'planting'
  | 'review'
  | 'varieties'
  | 'assign'
  | 'save'

export const WIZARD_STEPS: Array<{ id: WizardStep; label: string }> = [
  { id: 'basics', label: 'Naziv i lokacija' },
  { id: 'boundary', label: 'Granica' },
  { id: 'planting', label: 'Sadnja' },
  { id: 'review', label: 'Pregled' },
  { id: 'varieties', label: 'Sorte' },
  { id: 'assign', label: 'Dodela' },
  { id: 'save', label: 'Čuvanje' },
]

export type MapEditorMetrics = {
  area_m2: number
  area_ha: number
  perimeter_m: number
  vertex_count: number
  edge_lengths_m: number[]
  self_intersecting: boolean
  origin_lon: number | null
  origin_lat: number | null
}

export type MapEditorRowDraft = {
  draft_id: string
  row_number: number
  segment_index: number
  length_m: number
  tree_count: number
  geometry: GeoJSON.LineString | GeoJSON.MultiLineString
  default_variety: string | null
  default_planting_year: number | null
}

export type MapEditorTreeDraft = {
  draft_id: string
  row_draft_id: string
  row_number: number
  tree_number: number
  latitude: number
  longitude: number
  variety: string | null
  planting_year: number | null
  inherited_variety: boolean
  manually_placed: boolean
  existing_tree_id?: string | null
  existing_public_id?: string | null
}

export type MapEditorPreview = {
  boundary: GeoJSON.Polygon | GeoJSON.MultiPolygon
  metrics: MapEditorMetrics
  suggested_orientation_deg: number
  config: Record<string, unknown>
  rows: MapEditorRowDraft[]
  trees: MapEditorTreeDraft[]
  summary: {
    row_count: number
    segment_count: number
    tree_count: number
    trees_per_row: Record<string, number>
    average_trees_per_row: number
  }
  warnings: string[]
  notes: string[]
}

export type MapEditorState = {
  parcel_id: string
  name: string
  farm_id: string
  boundary: GeoJSON.Polygon | GeoJSON.MultiPolygon | null
  latitude: string | null
  longitude: string | null
  area_hectares: string | null
  row_spacing_m: string | null
  tree_spacing_m: string | null
  default_variety: string | null
  varieties: Array<{ name: string; role?: string; color?: string }>
  default_planting_year: number | null
  map_layout: Record<string, unknown> | null
  metrics: MapEditorMetrics | null
  has_geographic_boundary: boolean
  has_schematic_only_layout: boolean
  rows: Array<{
    id: string
    row_number: number
    tree_count: number
    variety: string | null
    planting_year: number | null
    geometry: GeoJSON.LineString | GeoJSON.MultiLineString | null
    segment_count: number
  }>
  trees: Array<{
    id: string
    public_id: string
    row_id: string
    row_number: number
    position_in_row: number
    latitude: number | null
    longitude: number | null
    variety: string | null
    planting_year: number | null
    status: string
    has_geographic_position: boolean
  }>
  suggested_orientation_deg: number | null
  warnings: string[]
}

export type MapEditorCommitPayload = {
  boundary: GeoJSON.Polygon | GeoJSON.MultiPolygon
  config: MapEditorPlantingConfig
  replace_planting: boolean
  create_missing_trees: boolean
  remove_unmatched_trees: boolean
  update_area_from_geometry: boolean
  rows?: MapEditorRowDraft[]
  trees?: MapEditorTreeDraft[]
  varieties?: Array<{ name: string; role: 'main' | 'pollinator' | 'other'; color: string }>
}

export type MapEditorCommitResult = {
  parcel_id: string
  boundary: GeoJSON.Polygon | GeoJSON.MultiPolygon
  metrics: MapEditorMetrics
  map_layout: Record<string, unknown>
  rows_updated: number
  trees_updated: number
  trees_created: number
  trees_removed: number
  warnings: string[]
  committed_at: string
}

export type MapEditorDraftCreatePayload = {
  farm_id?: string | null
  name: string
  boundary: GeoJSON.Polygon | GeoJSON.MultiPolygon
  config?: MapEditorPlantingConfig | null
  commit_planting?: boolean
}

export const DEFAULT_PLANTING_CONFIG: MapEditorPlantingConfig = {
  orientation_deg: 0,
  orientation_edge_index: null,
  row_spacing_m: 4.5,
  tree_spacing_m: 3.5,
  first_row_offset_m: 2.0,
  last_row_offset_m: 2.0,
  row_end_offset_m: 1.5,
  tree_start_offset_m: null,
  boundary_buffer_m: 0,
  target_row_count: null,
  start_row_number: 1,
  number_rows_ascending: true,
  default_variety: null,
  default_planting_year: new Date().getFullYear(),
}

export const MODE_LABELS: Record<EditorMode, string> = {
  select: 'Izbor / pregled',
  draw_boundary: 'Crtanje granice',
  edit_boundary: 'Izmena granice',
  row_orientation: 'Stranica / orijentacija',
  generate_layout: 'Generisanje rasporeda',
  select_row: 'Izbor reda',
  select_tree: 'Izbor stabla',
  edit_tree: 'Pomeranje stabla',
  assign_variety: 'Dodela sorte',
  measure: 'Merenje',
  inspect_index: 'Indeks vegetacije',
}
