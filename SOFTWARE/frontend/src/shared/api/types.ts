export type User = {
  id: string
  email: string
  full_name: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export type Farm = {
  id: string
  owner_id: string
  name: string
  description: string | null
  location_name: string | null
  latitude: string | null
  longitude: string | null
  area_hectares: string | null
  created_at: string
  updated_at: string
}

export type VarietyRole = 'main' | 'pollinator' | 'other'

export type ParcelVariety = {
  name: string
  role: VarietyRole
  color: string
}

export type Parcel = {
  id: string
  farm_id: string
  name: string
  code: string
  area_hectares: string | null
  latitude: string | null
  longitude: string | null
  notes: string | null
  maps_url: string | null
  row_count: number | null
  trees_per_row: number | null
  row_spacing_m: string | null
  tree_spacing_m: string | null
  default_variety: string | null
  varieties: ParcelVariety[]
  default_planting_year: number | null
  starting_tree_number: number
  well_location: WellLocation | null
  well_x: string | null
  well_y: string | null
  tree_count: number
  created_at: string
  updated_at: string
}

export type FarmDetail = Farm & {
  parcels: Parcel[]
}

export type ApiHealth = {
  status: string
  service: string
  database: string
}

export type HealthStatus = ApiHealth

export type TokenResponse = {
  access_token: string
  token_type: string
  user: User
}

export type TreeStatus = 'active' | 'removed' | 'replaced'
export type TreeHealthStatus = 'healthy' | 'monitoring' | 'issue' | 'unknown'
export type WellLocation =
  | 'north'
  | 'northeast'
  | 'east'
  | 'southeast'
  | 'south'
  | 'southwest'
  | 'west'
  | 'northwest'

export type OrchardRow = {
  id: string
  parcel_id: string
  row_number: number
  tree_count: number
  name: string | null
  variety: string | null
  created_at: string
  updated_at: string
}

export type TreeMapItem = {
  id: string
  parcel_id: string
  row_id: string
  public_id: string
  row_number: number
  position_in_row: number
  planting_year: number | null
  variety: string | null
  status: TreeStatus
  health_status: TreeHealthStatus
  has_severe_case?: boolean
  normalized_x: string
  normalized_y: string
  created_at: string
  updated_at: string
}

export type TreeDetail = TreeMapItem & {
  activity_count: number
  disease_issue_count: number
  total_cost: string
  journal_path: string
}

export type OrchardStats = {
  total_trees: number
  row_count: number
  trees_per_row: number | null
  area_hectares: string | null
  row_spacing_m: string | null
  tree_spacing_m: string | null
  healthy_trees: number
  monitoring_trees: number
  issue_trees: number
  unknown_trees: number
  active_trees: number
  removed_trees: number
  replaced_trees: number
}

export type OrchardTwin = {
  parcel: Parcel
  farm: Farm
  rows: OrchardRow[]
  trees: TreeMapItem[]
  stats: OrchardStats
  well: { location: WellLocation; x: string; y: string } | null
  width_m: string
  height_m: string
}

export type RowPlanItem = {
  row_number: number
  variety: string
  missing_positions: number[]
}

export type ParcelCreatePayload = {
  name: string
  area_hectares: number
  row_count: number
  trees_per_row: number
  row_spacing_m: number
  tree_spacing_m: number
  default_variety?: string
  varieties: ParcelVariety[]
  row_plan: RowPlanItem[]
  planting_year: number
  starting_tree_number: number
  notes?: string
  maps_url?: string | null
}

export type ParcelUpdatePayload = {
  name?: string
  area_hectares?: number
  notes?: string | null
  maps_url?: string | null
  planting_year?: number
  varieties?: ParcelVariety[]
  row_plan?: RowPlanItem[]
}

export type ActivityScope = 'parcel' | 'row' | 'tree'
export type ActivityStatus = 'planned' | 'in_progress' | 'completed' | 'cancelled'

export type CatalogItem = {
  id: string
  name: string
  slug: string
  description: string | null
  sort_order: number
  created_at: string
  updated_at: string
}

export type ActivityLineItem = {
  quantity: string | null
  unit: string | null
}

export type CostItem = {
  id: string
  created_at: string
  updated_at: string
  activity_id: string
  description: string
  cost_category: CatalogItem
  amount: string
  currency: string
  incurred_on: string
  notes: string | null
  receipt_filename: string | null
  scope_type: ActivityScope | 'farm'
  farm_id: string
  parcel_id: string | null
  row_id: string | null
  tree_id: string | null
  activity_title: string | null
  activity_type_name: string | null
  activity_line_items: ActivityLineItem[]
  parcel_name: string | null
  row_number: number | null
  tree_public_id: string | null
}

export type Activity = {
  id: string
  created_at: string
  updated_at: string
  activity_type: CatalogItem
  title: string
  description: string | null
  performed_on: string
  status: ActivityStatus
  quantity: string | null
  unit: string | null
  line_items: ActivityLineItem[]
  notes: string | null
  scope_type: ActivityScope | 'farm'
  farm_id: string
  parcel_id: string | null
  row_id: string | null
  row_ids: string[]
  row_numbers: number[]
  tree_id: string | null
  parcel_name: string | null
  row_number: number | null
  tree_public_id: string | null
  costs: CostItem[]
  total_cost: string
  currency: string
}

export type ActivityCreatePayload = {
  activity_type_id: string
  performed_on: string
  scope_type: ActivityScope
  parcel_id: string
  row_id?: string | null
  row_ids?: string[]
  tree_id?: string | null
  title?: string | null
  description?: string | null
  quantity?: number | null
  unit?: string | null
  line_items?: Array<{ quantity?: number | null; unit?: string | null }>
  cost_amount?: number | null
  notes?: string | null
  status?: ActivityStatus
}

export type ActivityUpdatePayload = {
  status?: ActivityStatus
  performed_on?: string
  notes?: string | null
  description?: string | null
}

export type CostCreatePayload = {
  description: string
  cost_category_id: string
  amount: number
  currency: string
  incurred_on?: string | null
  notes?: string | null
  receipt_filename?: string | null
}

export type NamedAmount = {
  id: string
  name: string
  slug: string
  amount: string
}

export type YearAmount = {
  year: number
  amount: string
}

export type CostSummary = {
  currency: string
  total_costs: string
  current_year_costs: string
  current_month_costs: string
  cost_per_tree: string | null
  cost_per_hectare: string | null
  active_tree_count: number
  area_hectares: string
  by_category: NamedAmount[]
  by_activity_type: NamedAmount[]
  by_year: YearAmount[]
  parcel_id: string | null
}

export type MonthAmount = {
  month: number
  amount: string
}

export type DashboardParcel = Parcel & {
  issue_trees: number
  monitoring_trees: number
  healthy_trees: number
  open_cases: number
}

export type DashboardStats = {
  parcel_count: number
  active_tree_count: number
  area_hectares: string
  year: number
  year_costs: string
  month_costs: string
  open_health_cases: number
  currency: string
}

export type DashboardOverview = {
  farm: Farm | null
  user_name: string
  stats: DashboardStats
  parcels: DashboardParcel[]
  year_by_category: NamedAmount[]
  year_by_month: MonthAmount[]
  lifetime_by_year: YearAmount[]
  recent_activities: Activity[]
  open_cases: DiseaseCase[]
  as_of: string
}

export type TimelineEvent = {
  occurred_on: string
  kind: 'activity' | 'disease' | 'observation'
  title: string
  subtitle: string | null
  amount: string | null
  currency: string | null
  scope_type: ActivityScope | 'farm' | null
  activity_id: string | null
  disease_id: string | null
  observation_id?: string | null
  is_direct: boolean
}

export type DiseaseCategory =
  | 'disease'
  | 'pest'
  | 'nutrient_deficiency'
  | 'water_stress'
  | 'physical_damage'
  | 'unknown'
  | 'other'

export type DiseaseStatus = 'open' | 'monitoring' | 'resolved' | 'unknown'
export type DiseaseSeverity = 'low' | 'medium' | 'high' | 'critical'

export type PhotoRecord = {
  id: string
  created_at: string
  updated_at: string
  farm_id: string
  entity_type: string
  entity_id: string
  original_filename: string
  content_type: string
  size_bytes: number
  caption: string | null
  taken_at: string | null
  uploaded_by_id: string | null
  uploaded_at: string
  url: string
}

export type Observation = {
  id: string
  created_at: string
  updated_at: string
  disease_case_id: string
  observed_on: string
  symptoms: string | null
  notes: string | null
  created_by_id: string | null
  photos: PhotoRecord[]
}

export type DiseaseCase = {
  id: string
  created_at: string
  updated_at: string
  farm_id: string
  parcel_id: string
  row_id: string | null
  tree_id: string | null
  title: string
  description: string | null
  category: DiseaseCategory
  severity: DiseaseSeverity
  status: DiseaseStatus
  detected_on: string
  resolved_on: string | null
  notes: string | null
  created_by_id: string | null
  parcel_name: string | null
  row_number: number | null
  tree_public_id: string | null
  observation_count: number
  photo_count: number
}

export type DiseaseCaseDetail = DiseaseCase & {
  observations: Observation[]
  photos: PhotoRecord[]
}

export type DiseaseCaseCreatePayload = {
  parcel_id: string
  row_id?: string | null
  tree_id?: string | null
  detected_on: string
  status: DiseaseStatus
  category: DiseaseCategory
  title: string
  description?: string | null
  severity: DiseaseSeverity
  notes?: string | null
  symptoms?: string | null
}

export type DiseaseCaseUpdatePayload = {
  status?: DiseaseStatus
  category?: DiseaseCategory
  title?: string
  description?: string | null
  severity?: DiseaseSeverity
  notes?: string | null
}

export type ObservationCreatePayload = {
  observed_on: string
  symptoms?: string | null
  notes?: string | null
}

export type TreeJournal = {
  tree: TreeDetail
  timeline: TimelineEvent[]
  activities: Activity[]
  related_activities: Activity[]
  diseases: DiseaseCase[]
  open_cases: DiseaseCase[]
  observations: Observation[]
  photos: PhotoRecord[]
  costs: CostItem[]
  related_costs: CostItem[]
  direct_cost_total: string
  orchard_cost_total: string
  currency: string
}

export type TreeOption = {
  id: string
  public_id: string
  row_id: string
  row_number: number
  position_in_row: number
  variety: string | null
}

export type ActivityFilters = {
  date_from?: string
  date_to?: string
  activity_type_id?: string
  scope_type?: ActivityScope | ''
  parcel_id?: string
  row_id?: string
  tree_id?: string
  status?: ActivityStatus | ''
}

export type KnowledgeCategory =
  | 'manual'
  | 'disease_guide'
  | 'pest_guide'
  | 'nutrition_guide'
  | 'plant_protection'
  | 'best_practice'
  | 'other'

export type KnowledgeDocument = {
  id: string
  created_at: string
  updated_at: string
  farm_id: string
  title: string
  category: KnowledgeCategory
  status: 'pending' | 'processing' | 'ready' | 'failed'
  description: string | null
  original_filename: string
  content_type: string
  size_bytes: number | null
  chunk_count: number
  page_count?: number
  image_count?: number
  source_kind?: string
  language?: string
  parser_version?: string | null
  ocr_version?: string | null
  processed_at?: string | null
  extra_metadata?: Record<string, unknown>
  error_message: string | null
  uploaded_by_id: string | null
}

export type KnowledgeHit = {
  chunk_id: string
  document_id: string
  document_title: string
  category: KnowledgeCategory
  page_number: number | null
  section_title: string | null
  content: string
  score: number
}

export type AgronomyQueryResult = {
  question: string
  mode: string
  sufficient_evidence: boolean
  out_of_scope: boolean
  answer: string
  citations: string[]
  debug?: {
    query: string
    detected_domain: string | null
    detected_topic: string | null
    searched_documents: string[]
    searched_sections: string[]
    retrieved_chunks: number
    selected_chunks: number
    retrieved_images: number
    confidence: number
    level: number
  } | null
}

export type KnowledgeSource = {
  document_id?: string
  document_title: string
  page_number?: number | null
  section_title?: string | null
  excerpt?: string | null
}

export type ChatMessageRecord = {
  id: string
  created_at: string
  updated_at: string
  role: 'user' | 'assistant' | 'system'
  content: string
  sources: KnowledgeSource[] | null
  structured_refs: Array<{ kind: string; id?: string; label: string }> | null
  provider: string | null
  model: string | null
}

export type ConversationSummary = {
  id: string
  created_at: string
  updated_at: string
  title: string
  farm_id: string | null
  parcel_id: string | null
  message_count: number
  last_message_at: string | null
}

export type ConversationDetail = ConversationSummary & {
  messages: ChatMessageRecord[]
}

export type DiseaseAnalysis = {
  id: string
  created_at: string
  updated_at: string
  farm_id: string
  disease_case_id: string
  photo_id: string | null
  likely_issue: string
  confidence: number
  observed_symptoms: string[]
  possible_alternatives: string[]
  recommended_inspection: string
  recommended_next_step: string
  supporting_sources: KnowledgeSource[]
  observed_facts: string
  uncertainty_notes: string
  disclaimer: string
  provider: string | null
  model: string | null
}

export type AIStatus = {
  provider: string
  chat_model: string
  embedding_model: string
  vision_model: string
  configured: boolean
}

export type InvoiceCategory = 'fuel' | 'other'
export type InvoiceKind = 'machine' | 'equipment' | 'other'

export type Invoice = {
  id: string
  created_at: string
  updated_at: string
  farm_id: string
  category: InvoiceCategory
  kind: InvoiceKind | null
  title: string
  vendor: string | null
  amount: string | null
  currency: string
  issued_on: string
  notes: string | null
  original_filename: string
  content_type: string
  size_bytes: number | null
  created_by_id: string | null
}

export type ReportChangeDirection = 'up' | 'down' | 'unchanged'
export type ReportChangeTone = 'positive' | 'negative' | 'neutral'
export type ReportKpiKind = 'count' | 'money' | 'mass' | 'text'

export type ReportYearChange = {
  available: boolean
  previous: string | null
  percent: string | null
  direction: ReportChangeDirection | null
  tone: ReportChangeTone | null
}

export type ReportOptionalAmount = {
  available: boolean
  value: string | null
}

export type ReportKpi = {
  key: string
  label: string
  available: boolean
  kind: ReportKpiKind
  value: string | null
  change: ReportYearChange
}

export type ReportHealthSummary = {
  total_trees: number
  active_trees: number
  healthy: number
  monitoring: number
  issue: number
  unknown: number
  removed: number
  replaced: number
  attention_count: number
}

export type ReportAttentionTree = {
  tree_id: string
  public_id: string
  row_id: string
  row_number: number
  health_status: TreeHealthStatus
  reason: string
  last_check_on: string | null
  days_since_check: number | null
}

export type ReportNamedCount = {
  id: string | null
  name: string
  slug: string | null
  count: number
}

export type ReportTimelineItem = {
  month: number
  performed_on: string
  title: string
  activity_type_name: string
  activity_type_slug: string | null
}

export type ReportActivitiesSummary = {
  completed_count: number
  planned_count: number
  recorded: boolean
  by_type: ReportNamedCount[]
  timeline: ReportTimelineItem[]
}

export type ReportPlannedActivity = {
  id: string
  performed_on: string
  title: string
  activity_type_name: string
  row_number: number | null
  tree_public_id: string | null
}

export type ReportNamedAmount = {
  id: string | null
  name: string
  slug: string | null
  amount: string
}

export type ReportMonthAmount = {
  month: number
  amount: string
}

export type ReportFinancialSummary = {
  recorded: boolean
  annual_cost: ReportOptionalAmount
  previous_year_cost: ReportOptionalAmount
  historical_cost: ReportOptionalAmount
  by_category: ReportNamedAmount[]
  by_activity: ReportNamedAmount[]
  monthly: ReportMonthAmount[]
  cost_per_hectare: ReportOptionalAmount
  cost_per_tree: ReportOptionalAmount
  cost_per_kg: ReportOptionalAmount
}

export type ReportProblemRow = {
  row_id: string
  row_number: number
  count: number
}

export type ReportProblemSummary = {
  recorded: boolean
  total: number
  open_count: number
  monitoring_count: number
  resolved_count: number
  by_category: ReportNamedCount[]
  by_row: ReportProblemRow[]
}

export type HarvestScope = 'parcel' | 'row' | 'tree'
export type HarvestQualityCategory = 'premium' | 'standard' | 'lower' | 'other'

export type HarvestEvent = {
  id: string
  created_at: string
  updated_at: string
  harvested_on: string
  scope_type: HarvestScope
  farm_id: string
  parcel_id: string | null
  row_id: string | null
  tree_id: string | null
  parcel_name: string | null
  row_number: number | null
  tree_public_id: string | null
  tree_status: string | null
  location_label: string
  gross_quantity: string
  loss_quantity: string
  net_quantity: string
  unit: string
  gross_kg: string | null
  loss_kg: string | null
  net_kg: string | null
  moisture_percent: string | null
  quality_category: HarvestQualityCategory | null
  damaged_percent: string | null
  empty_nuts_percent: string | null
  foreign_material_percent: string | null
  size_or_caliber: string | null
  notes: string | null
  activity_id: string | null
  created_by_id: string | null
  created_by_name: string | null
  photos: PhotoRecord[]
}

export type HarvestEventPayload = {
  harvested_on: string
  scope_type: HarvestScope
  row_id?: string | null
  tree_id?: string | null
  gross_quantity: number
  loss_quantity: number
  unit?: string
  moisture_percent?: number | null
  quality_category?: HarvestQualityCategory | null
  damaged_percent?: number | null
  empty_nuts_percent?: number | null
  foreign_material_percent?: number | null
  size_or_caliber?: string | null
  notes?: string | null
}

export type QualityAverage = {
  available: boolean
  value: string | null
  method: 'weighted' | null
  sample_count: number
}

export type ParcelProduction = {
  parcel_id: string
  parcel_name: string
  year: number
  unit: string
  area_hectares: string | null
  active_trees: number
  available_years: number[]
  recorded: boolean
  parcel_total_recorded: boolean
  measurement_note: string
  total_gross_quantity: ReportOptionalAmount
  total_loss_quantity: ReportOptionalAmount
  total_net_yield: ReportOptionalAmount
  harvest_event_count: number | null
  all_event_count: number
  first_harvest_date: string | null
  last_harvest_date: string | null
  yield_per_hectare: ReportOptionalAmount
  yield_per_tree: ReportOptionalAmount
  yield_per_tree_denominator: string | null
  events: HarvestEvent[]
  timeline: Array<{
    harvested_on: string
    event_count: number
    gross_kg: string
    loss_kg: string
    net_kg: string
    cumulative_net_kg: string
  }>
  row_summary: Array<{
    row_id: string
    row_number: number
    harvest_event_count: number
    net_kg: string
    active_trees: number
    yield_per_tree: ReportOptionalAmount
  }>
  tree_summary: Array<{
    tree_id: string
    public_id: string
    row_id: string
    row_number: number
    tree_status: TreeStatus
    health_status: TreeHealthStatus
    net_kg: string
    harvest_event_count: number
  }>
  quality_summary: {
    recorded: boolean
    moisture: QualityAverage
    damaged: QualityAverage
    empty_nuts: QualityAverage
    foreign_material: QualityAverage
    categories: Array<{ category: HarvestQualityCategory; net_kg: string; event_count: number }>
  }
  comparison: {
    available: boolean
    previous_year: number
    previous_net_yield: ReportOptionalAmount
    previous_yield_per_hectare: ReportOptionalAmount
    previous_harvest_event_count: number | null
    net_yield_change: ReportYearChange
    yield_per_hectare_change: ReportYearChange
    harvest_event_count_change: ReportYearChange
    message: string | null
  }
  photos: PhotoRecord[]
}

export type ReportYieldSummary = {
  recorded: boolean
  total_kg: string | null
  harvest_events: number | null
  first_harvest_date: string | null
  last_harvest_date: string | null
  per_hectare: ReportOptionalAmount
  per_tree: ReportOptionalAmount
  quality: {
    recorded: boolean
    moisture: QualityAverage
    damaged: QualityAverage
    empty_nuts: QualityAverage
    foreign_material: QualityAverage
    categories: Array<{ category: string; net_kg: string; event_count: number }>
  } | null
  source: 'harvest_event' | 'activity' | null
}

export type ReportComparisonRow = {
  key: string
  label: string
  kind: ReportKpiKind
  previous: string | null
  current: string | null
  change: ReportYearChange
}

export type ParcelAnnualReport = {
  parcel_summary: {
    parcel_id: string
    parcel_name: string
    parcel_code: string
    farm_name: string
    year: number
    previous_year: number
    generated_at: string
    generated_on: string
    area_hectares: string | null
    currency: string
    available_years: number[]
    comparison_available: boolean
  }
  executive_summary: string
  kpis: ReportKpi[]
  health_summary: ReportHealthSummary
  trees_requiring_attention: ReportAttentionTree[]
  trees_requiring_control: ReportAttentionTree[]
  activities_summary: ReportActivitiesSummary
  planned_activities: ReportPlannedActivity[]
  financial_summary: ReportFinancialSummary
  problem_summary: ReportProblemSummary
  yield_summary: ReportYieldSummary
  previous_year_comparison: ReportComparisonRow[]
  yearly_trend: {
    kind: 'monthly_costs'
    months: ReportMonthAmount[]
  }
}

export type WeatherStatus = 'ok' | 'stale' | 'no_location' | 'invalid_location' | 'unavailable'

export type DailyWeatherForecast = {
  date: string
  min_temperature: number | null
  max_temperature: number | null
  precipitation: number
  precipitation_probability: number | null
  symbol_code: string | null
}

export type ParcelWeather = {
  available: boolean
  status: WeatherStatus
  message: string | null
  parcel_id: string
  parcel_name: string
  latitude: number | null
  longitude: number | null
  timezone: string
  forecast: DailyWeatherForecast[]
  fetched_at: string | null
  source: string
}
