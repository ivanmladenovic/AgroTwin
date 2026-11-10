export type User = {
  id: string
  email: string
  full_name: string
  is_active: boolean
  is_superuser: boolean
  must_change_password?: boolean
  created_at: string
  updated_at: string
}

export type EnterpriseMembershipRole =
  | 'enterprise_admin'
  | 'enterprise_analyst'
  | 'enterprise_viewer'

export type EnterpriseOrganization = {
  id: string
  name: string
  slug: string
  logo_url: string | null
  description: string | null
  country: string | null
  default_currency: string
  timezone: string
  default_crop: string | null
  status: 'active' | 'inactive'
  default_scenario: 'conservative' | 'realistic' | 'optimistic' | 'custom'
  completeness_requirements: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type EnterpriseMembership = {
  id: string
  organization_id: string
  user_id: string
  role: EnterpriseMembershipRole
  status: 'active' | 'inactive' | 'invited'
  organization?: EnterpriseOrganization | null
  user_email?: string | null
  user_full_name?: string | null
  created_at: string
  updated_at: string
}

export type EnterpriseFollowUp = {
  id: string
  organization_id: string
  farm_id: string | null
  parcel_id: string | null
  alert_id: string | null
  assignee_user_id: string | null
  title: string
  body: string | null
  status: string
  due_on: string | null
  created_by_id: string | null
  farm_name: string | null
  parcel_name: string | null
  assignee_name: string | null
  created_at: string
  updated_at: string
}

export type EnterpriseDataQualityParcel = {
  parcel_id: string
  parcel_name: string
  farm_id: string
  producer_name: string | null
  buckets: string[]
}

export type EnterpriseDataQuality = {
  organization_id: string
  season_year: number
  date_from: string
  date_to: string
  assigned_parcels: number
  usable_scene: number
  cloudy_only: number
  no_scene: number
  insufficient_history: number
  open_alert: number
  incomplete: number
  notes: string[]
  parcels: EnterpriseDataQualityParcel[]
}

export type EnterpriseMeResponse = {
  user_id: string
  email: string
  full_name: string
  must_change_password: boolean
  memberships: EnterpriseMembership[]
}

export type EnterpriseSupplierLink = {
  id: string
  organization_id: string
  farm_id: string
  status: 'active' | 'inactive' | 'pending'
  relationship_start: string | null
  relationship_end: string | null
  internal_code: string | null
  internal_group: string | null
  internal_notes: string | null
  assigned_at: string
  farm_name: string | null
  farm_location: string | null
  producer_display_name: string | null
  owner_full_name: string | null
  public_producer_name: string | null
  assigned_parcel_count: number
  assigned_area_ha: string | null
  expected_yield_kg: string | null
  actual_yield_kg: string | null
  completeness_avg: number | null
  created_at: string
  updated_at: string
}

export type EnterpriseParcelSummary = {
  parcel_id: string
  farm_id: string
  parcel_name: string
  farm_name: string
  producer_display_name: string | null
  area_hectares: string | null
  tree_count: number
  default_variety: string | null
  varieties: Array<Record<string, unknown>>
  variety_names: string[]
  default_planting_year: number | null
  latitude: string | null
  longitude: string | null
  has_boundary: boolean
  completeness_score: number | null
  missing_fields: string[]
  expected_yield_kg: string | null
  latest_harvest_kg: string | null
}

export type EnterpriseActivityBrief = {
  id: string
  title: string
  performed_on: string
  status: string
  semantic_type: string | null
  activity_type_name: string | null
}

export type EnterpriseHarvestYearBrief = {
  year: number
  net_kg: string | null
  event_count: number
}

export type EnterpriseParcelDetail = EnterpriseParcelSummary & {
  boundary: Record<string, unknown> | null
  maps_url: string | null
  row_count: number | null
  trees_per_row: number | null
  planting_year_distribution: Record<string, number>
  harvest_years: number[]
  harvest_by_year: EnterpriseHarvestYearBrief[]
  latest_harvest_kg: string | null
  expected_yield_kg: string | null
  recent_activities: EnterpriseActivityBrief[]
  activity_counts: Record<string, number>
  protection_count: number
  fertilization_count: number
  irrigation_count: number
  observation_count: number
}

export type EnterpriseMapParcel = {
  parcel_id: string
  parcel_name: string
  producer_display_name: string | null
  latitude: number
  longitude: number
  area_hectares: string | null
  tree_count: number
  completeness_score: number | null
  issue_trees: number
  monitoring_trees: number
  healthy_trees: number
  open_cases: number
}

export type EnterpriseYearProductionRow = {
  year: number
  expected_yield_kg: string | null
  actual_yield_kg: string | null
  parcels_with_harvest: number
  assigned_parcels: number
}

export type EnterpriseVarietyProductionRow = {
  variety: string
  tree_count: number
  expected_yield_kg: string | null
  actual_yield_kg: string | null
  share_of_trees_percent: number | null
}

export type EnterpriseProductionAnalytics = {
  by_year: EnterpriseYearProductionRow[]
  by_variety: EnterpriseVarietyProductionRow[]
  notes: string[]
}

export type EnterpriseAggregateParcelSlice = {
  parcel_id: string
  parcel_name: string
  producer_display_name: string | null
  area_hectares: string | null
  tree_count: number
  variety_names: string[]
  expected_yield_kg: string | null
  actual_yield_kg: string | null
  activity_count: number | null
  completeness_score: number | null
}

export type EnterpriseAggregatePurchaseSlice = {
  purchase_id: string
  farm_id: string
  producer_display_name: string | null
  farm_name: string | null
  purchased_on: string
  quantity_kg: string
  quantity_basis: EnterpriseQuantityBasis
  currency: EnterprisePurchaseCurrency
  unit_price_per_kg: string
  total_amount: string
  notes: string | null
}

export type EnterpriseAggregatePurchaseSupplierRow = {
  farm_id: string
  producer_display_name: string | null
  farm_name: string | null
  purchase_count: number
  quantity_kg: string | null
  amount_by_currency: Record<string, string>
}

export type EnterpriseAggregateReport = {
  organization_name: string
  year: number
  generated_on: string
  parcel_count: number
  total_area_ha: string | null
  total_trees: number | null
  expected_yield_kg: string | null
  actual_yield_kg: string | null
  harvest_coverage_percent: number | null
  parcels: EnterpriseAggregateParcelSlice[]
  purchase_count: number
  purchased_quantity_kg: string | null
  purchase_totals_by_currency: Record<string, string>
  purchases: EnterpriseAggregatePurchaseSlice[]
  purchases_by_supplier: EnterpriseAggregatePurchaseSupplierRow[]
  notes: string[]
}

export type EnterpriseDashboardKPIs = {
  active_suppliers: number
  assigned_farms: number
  assigned_parcels: number
  total_area_ha: string | null
  total_trees: number | null
  expected_yield_kg: string | null
  actual_yield_kg: string | null
  harvest_coverage_percent: number | null
  parcels_missing_key_data: number
  parcels_with_issues: number
  season_year: number | null
  notes: string[]
}

export type EnterpriseMetricAvailability = {
  available: boolean
  value: number | null
  note: string | null
}

export type EnterpriseAttentionItem = {
  id: string
  category: string
  category_label: string
  parcel_id: string
  farm_id: string
  parcel_name: string
  farm_name: string
  producer_display_name: string | null
  event_date: string | null
  title: string
  description: string | null
  source: string
  review_status: string | null
  severity: string | null
  reason: string
  source_type: string
  source_id: string
  priority_rank: number
}

export type EnterpriseMonitoringObservationItem = {
  id: string
  parcel_id: string
  farm_id: string
  parcel_name: string
  farm_name: string
  producer_display_name: string | null
  performed_on: string
  title: string
  description: string | null
  semantic_type: string | null
  observation_category: string | null
  observation_severity: string | null
  observation_status: string | null
  activity_status: string
  activity_type_name: string | null
  source: string
  photo_url: string | null
  follow_up_of_id: string | null
  row_id: string | null
  tree_id: string | null
  category: string
}

export type EnterpriseMonitoringActivityItem = {
  id: string
  parcel_id: string
  farm_id: string
  parcel_name: string
  farm_name: string
  producer_display_name: string | null
  performed_on: string
  title: string
  description: string | null
  semantic_type: string | null
  activity_type_name: string | null
  status: string
  source: string
}

export type EnterpriseMonitoringPlanItem = {
  id: string
  parcel_id: string
  farm_id: string
  parcel_name: string
  farm_name: string
  producer_display_name: string | null
  title: string
  description: string | null
  planned_date_from: string | null
  planned_date_to: string | null
  status: string
  priority_level: string | null
  item_kind: string | null
  bucket: string
  source: string
}

export type EnterpriseWeatherSignal = {
  parcel_id: string
  farm_id: string
  parcel_name: string
  farm_name: string
  producer_display_name: string | null
  signal_kind: string
  title: string
  detail: string
  period_start: string | null
  period_end: string | null
  source: string
  observed_value: string | null
  threshold: string | null
  reason: string
  is_forecast: boolean
  has_matching_observation: boolean
}

export type EnterpriseDataQualityItem = {
  parcel_id: string
  farm_id: string
  parcel_name: string
  farm_name: string
  producer_display_name: string | null
  kind: string
  detail: string
  missing_fields: string[]
  completeness_score: number | null
  reference_date: string | null
}

export type EnterpriseMonitoringKpis = {
  open_problems: EnterpriseMetricAvailability
  new_observations: EnterpriseMetricAvailability
  pending_plan_tasks: EnterpriseMetricAvailability
  parcels_for_review: EnterpriseMetricAvailability
  incomplete_data: EnterpriseMetricAvailability
  stale_data: EnterpriseMetricAvailability
}

export type EnterpriseMonitoringFiltersMeta = {
  suppliers: Array<{ farm_id: string; label: string; farm_name: string }>
  parcels: Array<{ parcel_id: string; farm_id: string; label: string }>
  categories: string[]
  review_statuses: string[]
  severities: string[]
}

export type EnterpriseMonitoringCenter = {
  season_year: number
  period_from: string
  period_to: string
  kpis: EnterpriseMonitoringKpis
  attention_items: EnterpriseAttentionItem[]
  observations: EnterpriseMonitoringObservationItem[]
  activities: EnterpriseMonitoringActivityItem[]
  plan_items: EnterpriseMonitoringPlanItem[]
  weather_signals: EnterpriseWeatherSignal[]
  data_quality: EnterpriseDataQualityItem[]
  weather: EnterpriseMetricAvailability
  filters: EnterpriseMonitoringFiltersMeta
  notes: string[]
  category_labels: Record<string, string>
}

export type EnterpriseAlertWatchReview = {
  reviewed_at: string
  reviewed_by_name: string | null
  note: string | null
}

export type EnterpriseAlertWatchItem = {
  alert_id: string
  parcel_id: string
  farm_id: string
  producer_name: string | null
  parcel_name: string
  observation_date: string | null
  latest_observation_date: string | null
  processed_at: string | null
  affected_indices: string[]
  anomaly_kinds: string[]
  zone_keys: string[]
  tree_public_ids?: string[]
  severity: string
  status: string
  title: string
  summary: string | null
  recommended_actions: string[]
  last_analysis_at: string | null
  disclaimer: string | null
  company_review: EnterpriseAlertWatchReview | null
  intelligence_path: string
}

export type EnterpriseAlertReviewResult = {
  alert_id: string
  organization_id: string
  reviewed_at: string
  reviewed_by_name: string | null
  note: string | null
  producer_status: string
}

export type EnterpriseAlertWatchPage = {
  organization_id: string
  open_alerts: number
  alert_count: number
  satellite_anomaly_count: number
  limit: number
  offset: number
  items: EnterpriseAlertWatchItem[]
}

export type EnterprisePurchaseCurrency = 'RSD' | 'EUR'
export type EnterpriseQuantityBasis = 'bruto' | 'neto'

export type EnterpriseSupplierPrice = {
  id: string
  organization_id: string
  farm_id: string
  season_year: number
  currency: EnterprisePurchaseCurrency
  price_bruto_per_kg: string | null
  price_neto_per_kg: string | null
  notes: string | null
  producer_display_name: string | null
  farm_name: string | null
  created_at: string
  updated_at: string
}

export type EnterprisePurchase = {
  id: string
  organization_id: string
  farm_id: string
  purchased_on: string
  quantity_kg: string
  quantity_basis: EnterpriseQuantityBasis
  currency: EnterprisePurchaseCurrency
  unit_price_per_kg: string
  total_amount: string
  price_bruto_per_kg: string | null
  price_neto_per_kg: string | null
  notes: string | null
  producer_display_name: string | null
  farm_name: string | null
  created_by_id: string | null
  created_at: string
  updated_at: string
}

export type EnterpriseOtkupSupplierRow = {
  farm_id: string
  producer_display_name: string | null
  farm_name: string
  assigned_parcels: number
  parcels_with_harvest: number
  harvest_gross_kg: string | null
  harvest_net_kg: string | null
  harvest_event_count: number
  last_harvested_on: string | null
  currency: EnterprisePurchaseCurrency | null
  price_bruto_per_kg: string | null
  price_neto_per_kg: string | null
  price_notes: string | null
  purchase_count: number
  purchased_quantity_kg: string | null
  purchased_amount: string | null
  last_purchased_on: string | null
  total_quantity_kg: string | null
  total_amount: string | null
}

export type EnterpriseOtkupOverview = {
  season_year: number
  suppliers: EnterpriseOtkupSupplierRow[]
  purchase_count: number
  total_quantity_kg: string | null
  purchased_quantity_kg: string | null
  harvest_gross_kg: string | null
  harvest_net_kg: string | null
  suppliers_with_harvest: number
  totals_by_currency: Record<string, string>
  notes: string[]
}

export type EnterprisePlanningSeason = {
  id: string
  organization_id: string
  year: number
  name: string
  status: 'draft' | 'active' | 'closed'
  supply_target_kg: string | null
  created_at: string
  updated_at: string
}

export type EnterpriseYieldPlanItem = {
  id: string
  yield_plan_id: string
  farm_id: string
  parcel_id: string
  crop: string
  forecast_area_ha: string | null
  forecast_tree_count: number | null
  forecast_yield_kg: string
  forecast_yield_tonnes: string | null
  forecast_yield_kg_per_ha: string | null
  scenario_assumptions: Record<string, unknown>
  source_snapshot: Record<string, unknown>
  calculation_version: string
  data_quality: Record<string, unknown>
  parcel_name: string | null
  farm_name: string | null
  created_at: string
  updated_at: string
}

export type EnterpriseYieldPlan = {
  id: string
  organization_id: string
  planning_season_id: string
  name: string
  description: string | null
  scenario_type: 'conservative' | 'realistic' | 'optimistic' | 'custom'
  status: 'draft' | 'published' | 'archived'
  assumptions: Record<string, unknown>
  calculation_version: string
  created_by_id: string | null
  items: EnterpriseYieldPlanItem[]
  total_forecast_kg: string | null
  created_at: string
  updated_at: string
}

export type EnterpriseFarmCandidate = {
  farm_id: string
  name: string
  location_name: string | null
  already_linked: boolean
}

export type EnterpriseAssignableParcel = {
  parcel_id: string
  farm_id: string
  name: string
  area_hectares: string | null
  already_assigned: boolean
}

export type EnterpriseYieldComparisonRow = {
  parcel_id: string
  farm_id: string
  parcel_name: string | null
  farm_name: string | null
  forecast_yield_kg: string
  actual_net_yield_kg: string | null
  difference_kg: string | null
  difference_percent: number | null
  status: string
  harvest_events: number
}

export type EnterpriseYieldComparison = {
  plan_id: string
  plan_name: string
  scenario_type: string
  season_year: number
  total_forecast_kg: string
  total_actual_kg: string | null
  parcels_with_harvest: number
  parcels_missing_harvest: number
  rows: EnterpriseYieldComparisonRow[]
  notes: string[]
}

export type AdminAccountsOverview = {
  total_users: number
  client_users: number
  enterprise_users: number
  platform_admins: number
  enterprise_organizations: number
  active_supplier_links: number
  active_parcel_assignments: number
}

export type AdminUserSummary = {
  id: string
  email: string
  full_name: string
  is_active: boolean
  is_superuser: boolean
  must_change_password: boolean
  account_kinds: Array<'platform_admin' | 'client' | 'enterprise'>
  farm_count: number
  farms: Array<{
    farm_id: string
    name: string
    parcel_count: number
    location_name: string | null
  }>
  enterprise_memberships: Array<{
    organization_id: string
    organization_name: string
    role: string
    status: string
  }>
  created_at: string
  updated_at: string
}

export type AdminEnterpriseOrgSummary = {
  id: string
  name: string
  slug: string
  status: string
  member_count: number
  supplier_count: number
  assigned_parcel_count: number
  country: string | null
  created_at: string
  updated_at: string
}

export type AdminClientFarmDetail = {
  farm_id: string
  name: string
  location_name: string | null
  owner_id: string
  owner_email: string | null
  owner_name: string | null
  linked_as_supplier: boolean
  parcels: Array<{
    parcel_id: string
    name: string
    area_hectares: string | null
    assigned_to_org: boolean
  }>
}

export type AdminSupplierLinkDetail = {
  id: string
  farm_id: string
  farm_name: string | null
  owner_name: string | null
  owner_email: string | null
  status: string
  internal_code: string | null
  internal_group: string | null
  assigned_parcel_count: number
  assigned_at: string
  created_at: string
  updated_at: string
}

export type AdminParcelAssignmentDetail = {
  id: string
  farm_id: string
  parcel_id: string
  farm_name: string | null
  owner_name: string | null
  parcel_name: string | null
  status: string
  assigned_at: string
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
  production_method?: 'conventional' | 'organic'
  organic_scope?: 'none' | 'entire_parcel' | 'part_of_parcel'
  has_irrigation?: boolean
  irrigation_type?: 'drip' | 'sprinkler' | 'microsprinkler' | 'other' | null
  water_source?: string | null
  emitter_flow_lph?: string | null
  emitter_spacing_m?: string | null
  line_count?: number | null
  irrigation_sections?: number | null
  irrigation_pressure_bar?: string | null
  irrigation_efficiency?: string | null
  irrigation_notes?: string | null
  well_location: WellLocation | null
  well_x: string | null
  well_y: string | null
  tree_count: number
  created_at: string
  updated_at: string
  altitude: string | null
  boundary: Record<string, unknown> | null
  map_layout?: Record<string, unknown> | null
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
  planting_year?: number | null
  is_organic?: boolean
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
  latitude?: string | null
  longitude?: string | null
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
  boundary?: Record<string, unknown> | null
  planting_year?: number
  varieties?: ParcelVariety[]
  row_plan?: RowPlanItem[]
  production_method?: 'conventional' | 'organic'
  organic_scope?: 'none' | 'entire_parcel' | 'part_of_parcel'
  has_irrigation?: boolean
  irrigation_type?: 'drip' | 'sprinkler' | 'microsprinkler' | 'other' | null
  water_source?: string | null
  emitter_flow_lph?: number | null
  emitter_spacing_m?: number | null
  line_count?: number | null
  irrigation_sections?: number | null
  irrigation_pressure_bar?: number | null
  irrigation_efficiency?: number | null
  irrigation_notes?: string | null
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
  name?: string | null
  quantity: string | null
  unit: string | null
  volume?: string | null
  volume_unit?: string | null
  amount?: string | null
}

export type CostItem = {
  id: string
  created_at: string
  updated_at: string
  activity_id: string | null
  source?: string | null
  source_id?: string | null
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

export type ActivitySemanticType =
  | 'observation'
  | 'problem'
  | 'treatment'
  | 'fertilization'
  | 'irrigation'
  | 'monitoring'
  | 'pruning'
  | 'planting'
  | 'other'

export type ObservationCategory =
  | 'disease'
  | 'pest'
  | 'nutrient'
  | 'weather_damage'
  | 'water_stress'
  | 'tree_health'
  | 'fruit'
  | 'leaf'
  | 'soil'
  | 'other'
  | 'unknown'

export type ObservationStatus = 'new' | 'monitoring' | 'confirmed' | 'resolved' | 'rejected' | 'unknown'

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
  soil_analyses: SoilLabAnalysis[]
  photos: PhotoRecord[]
  harvest: ActivityHarvestSnippet | null
  plan_item: ActivityPlanItemSnippet | null
  disease_case: ActivityDiseaseSnippet | null
  subsidy: ActivitySubsidySnippet | null
  total_cost: string
  currency: string
  semantic_type: ActivitySemanticType
  observation_category: ObservationCategory | null
  observation_severity: DiseaseSeverity | null
  observation_status: ObservationStatus | null
  observation_id: string | null
  plan_item_id: string | null
  follow_up_of_id: string | null
}

export type ActivityHarvestSnippet = {
  id: string
  parcel_id: string | null
  harvested_on: string
  location_label: string
  gross_quantity: string | null
  loss_quantity: string
  net_quantity: string | null
  unit: string
  quality_category: string | null
  notes: string | null
}

export type ActivityPlanItemSnippet = {
  id: string
  plan_id: string
  plan_type: PlanningPlanType | string
  parcel_id: string | null
  year: number | null
  title: string
  planned_date_from: string | null
  planned_date_to: string | null
  status: string
  description: string | null
  products: Array<Record<string, unknown>>
}

export type ActivityDiseaseSnippet = {
  id: string
  parcel_id: string | null
  title: string
  category: string
  severity: string
  status: string
  detected_on: string
  location_label: string
  notes: string | null
}

export type ActivitySubsidySnippet = {
  id: string
  parcel_id: string | null
  title: string
  total_cost: string
  subsidy_amount: string
  subsidy_percent: string | null
  currency: string
  received_on: string
  notes: string | null
}

export type SoilLabVerificationStatus = 'extracted' | 'needs_review' | 'verified' | 'skipped'
export type SoilLabExtractionStatus = 'pending' | 'running' | 'succeeded' | 'failed'

export type SoilLabResult = {
  id: string
  created_at: string
  updated_at: string
  analysis_id: string
  parameter_code: string
  original_parameter_name: string
  value: string
  unit: string | null
  method: string | null
  depth_from_cm: string | null
  depth_to_cm: string | null
  extraction_confidence: string | null
  source_page: number | null
  raw_text: string | null
  verification_status: SoilLabVerificationStatus
  notes: string | null
  high_confidence: boolean
}

export type SoilLabAnalysis = {
  id: string
  created_at: string
  updated_at: string
  activity_id: string
  parcel_id: string
  tree_id: string
  tree_public_id: string | null
  row_id: string | null
  row_number: number | null
  sampled_on: string
  analysis_date: string | null
  laboratory_name: string | null
  sample_depth_from_cm: string | null
  sample_depth_to_cm: string | null
  original_filename: string
  content_type: string
  size_bytes: number | null
  extraction_status: SoilLabExtractionStatus
  verification_status: SoilLabVerificationStatus
  extraction_error: string | null
  result_count: number
  results: SoilLabResult[]
  source_kind: 'laboratory'
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
  line_items?: Array<{
    name?: string | null
    quantity?: number | null
    unit?: string | null
    volume?: number | null
    volume_unit?: string | null
    amount?: number | null
  }>
  cost_amount?: number | null
  notes?: string | null
  status?: ActivityStatus
  semantic_type?: ActivitySemanticType | null
  observation_category?: ObservationCategory | null
  observation_severity?: DiseaseSeverity | null
  observation_status?: ObservationStatus | null
  observation_id?: string | null
  plan_item_id?: string | null
  follow_up_of_id?: string | null
}

export type ActivityUpdatePayload = {
  status?: ActivityStatus
  performed_on?: string
  notes?: string | null
  description?: string | null
  semantic_type?: ActivitySemanticType | null
  observation_category?: ObservationCategory | null
  observation_severity?: DiseaseSeverity | null
  observation_status?: ObservationStatus | null
  observation_id?: string | null
  plan_item_id?: string | null
  follow_up_of_id?: string | null
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

export type CostStandaloneCreatePayload = {
  description: string
  cost_category_id: string
  amount: number
  currency?: string
  incurred_on: string
  parcel_id: string
  notes?: string | null
  activity_type_id?: string | null
}

export type CostFilters = {
  parcel_id?: string
  date_from?: string
  date_to?: string
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
  total_subsidies: string
  subsidy_percent_of_costs: string | null
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
  activity_id: string | null
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
  tree_ids?: string[]
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
  evidence?: {
    sources: Array<{
      document_id: string
      document_title: string
      pages: number[]
      section: string | null
      content: string
    }>
  }
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
  structured_refs: Array<{
    kind: string
    id?: string
    label: string
    extra?: Record<string, unknown> | null
  }> | null
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
  disease_case_id?: string | null
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
  gross_quantity: string | null
  loss_quantity: string
  net_quantity: string | null
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
  gross_quantity?: number | null
  loss_quantity?: number | null
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

export type ExpectedYieldCurvePoint = {
  age_year: number
  pessimistic: string
  realistic: string
  optimistic: string
  is_current: boolean
}

export type ExpectedYieldCohort = {
  planting_year: number
  age_year: number
  tree_count: number
  pessimistic_kg_per_tree: string
  realistic_kg_per_tree: string
  optimistic_kg_per_tree: string
  pessimistic_kg: string
  realistic_kg: string
  optimistic_kg: string
}

export type ExpectedYieldYearComparison = {
  year: number
  expected_pessimistic_kg: ReportOptionalAmount
  expected_pessimistic_net_kg: ReportOptionalAmount
  actual_net_kg: ReportOptionalAmount
  difference_kg: ReportOptionalAmount
  difference_percent: ReportOptionalAmount
  message: string | null
}

export type ExpectedYieldVarietyRow = {
  variety: string
  tree_count: number
  share_of_trees_percent: number | null
  pessimistic_kg: ReportOptionalAmount
  realistic_kg: ReportOptionalAmount
  optimistic_kg: ReportOptionalAmount
  realistic_net_kg: ReportOptionalAmount
}

export type ExpectedYield = {
  available: boolean
  unit: string
  known_tree_count: number
  unknown_tree_count: number
  active_tree_count: number
  mixed_ages: boolean
  age_years: number[]
  age_label: string | null
  message: string | null
  precision_note: string | null
  disclaimer: string | null
  methodology_type: string
  confidence: string
  source: string
  profile_version: string | null
  shell_to_net_ratio: string
  pessimistic_kg: ReportOptionalAmount
  realistic_kg: ReportOptionalAmount
  optimistic_kg: ReportOptionalAmount
  expected_per_tree_realistic: ReportOptionalAmount
  expected_per_hectare_realistic: ReportOptionalAmount
  pessimistic_net_kg: ReportOptionalAmount
  realistic_net_kg: ReportOptionalAmount
  optimistic_net_kg: ReportOptionalAmount
  expected_per_tree_realistic_net: ReportOptionalAmount
  expected_per_hectare_realistic_net: ReportOptionalAmount
  actual_net_kg: ReportOptionalAmount
  difference_kg: ReportOptionalAmount
  difference_percent: ReportOptionalAmount
  comparison_message: string | null
  cohorts: ExpectedYieldCohort[]
  curve: ExpectedYieldCurvePoint[]
  history: ExpectedYieldYearComparison[]
  by_variety: ExpectedYieldVarietyRow[]
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
    cumulative_gross_kg: string
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
  expected_yield: ExpectedYield
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

export type SoilStatus =
  | 'ok'
  | 'partial'
  | 'stale'
  | 'location_required'
  | 'unavailable'
  | 'rate_limited'
  | 'timeout'
  | 'malformed'

export type SoilDepthValue = {
  depth: string
  depth_label: string
  value: number
  unit: string
  uncertainty: number | null
  lower: number | null
  upper: number | null
}

export type SoilProperty = {
  key: string
  label: string
  unit: string
  value: number | null
  depth: string | null
  depth_label: string | null
  source: string
  source_type: 'modeled_estimate'
  source_label: string
  measured_at: string | null
  generated_at: string | null
  is_modeled: boolean
  available: boolean
  depths: SoilDepthValue[]
}

export type ParcelSoilProfile = {
  available: boolean
  status: SoilStatus
  is_stale: boolean
  message: string | null
  parcel_id: string
  parcel_name: string
  latitude: number | null
  longitude: number | null
  provider: string
  source: string
  source_type: 'modeled_estimate'
  source_label: string
  source_explanation: string
  dataset_version: string | null
  spatial_resolution: string
  fetched_at: string | null
  generated_at: string | null
  is_modeled: boolean
  can_refresh: boolean
  refresh_available_at: string | null
  depths: string[]
  properties: SoilProperty[]
  missing_properties: string[]
}

export type SatelliteZone = {
  zone_key: string
  geometry: Record<string, unknown>
  ndvi: string | null
  ndre: string | null
  ndwi: string | null
  ndvi_deviation: string | null
  tree_public_ids?: string[]
}

export type SatelliteAnomaly = {
  id: string
  zone_key: string | null
  tree_public_ids?: string[]
  kind: string
  index_name: string
  severity: string
  message: string
  details: Record<string, unknown>
  created_at: string
}

export type SatelliteObservationSummary = {
  id: string
  acquisition_date: string
  cloud_cover: string | null
  ndvi_mean: string | null
  ndre_mean: string | null
  ndwi_mean: string | null
  anomaly_count: number
  processing_status: string
  provider: string
  satellite: string
}

export type VisualizationLayer = {
  index: string
  url: string
  /** west, south, east, north (WGS84) */
  bbox: number[]
  width?: number | null
  height?: number | null
  native_resolution?: string | null
  display_resolution_m?: number | null
}

export type SatelliteSample = {
  observation_id: string
  index: string
  acquisition_date: string
  longitude: number
  latitude: number
  value: string | null
  source: 'zone_aggregate' | 'unavailable' | string
  zone_key: string | null
  message: string
}

export type SatelliteObservation = SatelliteObservationSummary & {
  parcel_id: string
  product_id: string
  acquisition_at: string | null
  processed_at: string | null
  ndvi_min: string | null
  ndvi_max: string | null
  ndvi_stddev: string | null
  ndre_min: string | null
  ndre_max: string | null
  ndwi_min: string | null
  ndwi_max: string | null
  image_reference: string | null
  visualization_refs: Record<string, string>
  visualization_layers?: VisualizationLayer[]
  index_formulas: Record<string, string>
  error_message: string | null
  zones: SatelliteZone[]
  anomalies: SatelliteAnomaly[]
  created_at: string
  updated_at: string
}

export type SatelliteHistoryPoint = {
  observation_id: string
  product_id: string
  provider: string
  acquisition_date: string
  processed_at: string | null
  cloud_cover: string | null
  quality: 'ok' | 'elevated_cloud' | 'unknown' | string
  ndvi_mean: string | null
  ndre_mean: string | null
  ndwi_mean: string | null
  ndvi_delta: string | null
  ndre_delta: string | null
  ndwi_delta: string | null
  ndvi_comparison_reliable: boolean | null
  ndre_comparison_reliable: boolean | null
  ndwi_comparison_reliable: boolean | null
  anomaly_count: number
  valid_pixel_counts: Record<string, number> | null
}

export type SatelliteAnomalyRecurrence = {
  zone_key: string | null
  kind: string
  index_name: string
  occurrence_count: number
  acquisition_dates: string[]
  relation: 'same_grid_cell' | 'potentially_related' | string
  note: string
}

export type SatelliteHistory = {
  parcel_id: string
  earliest_acquisition_date: string | null
  latest_acquisition_date: string | null
  date_from: string | null
  date_to: string | null
  truncated: boolean
  point_count: number
  points: SatelliteHistoryPoint[]
  repeated_anomalies: SatelliteAnomalyRecurrence[]
  notes: string[]
}

export type SatelliteChange = {
  index_name: string
  latest: string | null
  previous: string | null
  change_percent: string | null
}

export type SatelliteDataCapabilities = {
  has_boundary: boolean
  has_centroid: boolean
  has_aggregate_indices: boolean
  has_zone_statistics: boolean
  has_index_raster: boolean
  has_anomalies: boolean
  spatial_resolution_note: string | null
  sensor?: string
  display_resolution_m?: number
  native_resolutions?: Record<string, string>
  basemap_note?: string | null
}

export type ParcelSatelliteMonitoring = {
  parcel_id: string
  available: boolean
  status: string
  message: string | null
  provider: string
  index_formulas: Record<string, string>
  capabilities?: SatelliteDataCapabilities
  latest: SatelliteObservation | null
  previous: SatelliteObservation | null
  changes: SatelliteChange[]
  history: SatelliteObservationSummary[]
  anomalies: SatelliteAnomaly[]
}

export type SatelliteSyncResult = {
  parcel_id: string
  status: string
  message: string | null
  observation_id: string | null
  skipped_duplicate: boolean
}

export type ParcelAlertEvidence = {
  zone_keys?: string[]
  tree_public_ids?: string[]
  affected_indices?: string[]
  observation_date?: string | null
  data_quality_notes?: string[]
}

export type ParcelAlert = {
  id: string
  parcel_id: string
  severity: string
  status: string
  issue_key: string
  title: string
  summary: string
  observed_facts: string[]
  possible_causes: string[]
  recommended_actions: string[]
  source_events: string[]
  confidence: string | null
  evidence?: ParcelAlertEvidence
  created_at: string
  resolved_at: string | null
}

export type ParcelAnalysisRun = {
  id: string
  parcel_id: string
  status: string
  ai_called: boolean
  skip_reason: string | null
  trigger_kinds: string[]
  provider: string | null
  model: string | null
  validated_result: Record<string, unknown> | null
  error_message: string | null
  started_at: string
  finished_at: string | null
}

export type ParcelIntelligence = {
  parcel_id: string
  parcel_name?: string | null
  available: boolean
  active_alerts: ParcelAlert[]
  resolved_alerts: ParcelAlert[]
  last_analysis: ParcelAnalysisRun | null
  next_scheduled_at: string | null
  disclaimer: string
  read_only?: boolean
}

export type UserNotification = {
  id: string
  parcel_id: string | null
  alert_id: string | null
  severity: string
  title: string
  body: string
  read_at: string | null
  created_at: string
  payload: Record<string, unknown>
}

export type ContextRequestType =
  | 'PHOTO_ANALYSIS'
  | 'PROBLEM_ANALYSIS'
  | 'PARCEL_ANALYSIS'
  | 'SEASON_ANALYSIS'
  | 'ACTIVITY_ANALYSIS'

export type ContextBuildRequest = {
  request_type: ContextRequestType
  parcel_id?: string
  row_id?: string
  tree_id?: string
  photo_id?: string
  activity_id?: string
  disease_case_id?: string
  season_year?: number
  event_date?: string
  query?: string
  include_debug?: boolean
}

export type ContextDebugRecord = {
  kind: string
  id: string
  scope: string | null
  date: string | null
  relevance_score: number
  selected: boolean
  reasons: string[]
  temporal_relation: string | null
}

export type AgroTwinContext = {
  context_id: string
  context_version: string
  created_at: string
  request: {
    type: ContextRequestType
    query: string | null
    season_year: number | null
    event_date: string
  }
  subject: {
    type: string
    farm: { id: string; name: string }
    parcel: { id: string; name: string } | null
    row: { id: string; row_number: number } | null
    tree: { id: string; public_id: string } | null
  }
  soil: { status: string; source_type: string; is_stale: boolean } | null
  weather: { status: string; source: string } | null
  activities: Array<{ id: string; type: string; date: string; scope: string; relevance_score: number }>
  costs: { status: string; total: string | null } | null
  harvest: { status: string; event_count: number } | null
  photos: Array<{ id: string; url: string; is_current: boolean; relevance_score: number }>
  previous_ai_analyses: Array<{ id: string; finding: string; confidence: number; source_type: string }>
  warnings: Array<{ type: string; source: string; message: string }>
  data_quality: Record<string, string | null>
  debug: {
    providers_used: string[]
    provider_failures: Array<{ source: string; error: string }>
    collected: Record<string, number>
    filtered: Record<string, number>
    selected: Record<string, number>
    duration_ms: number
    records: ContextDebugRecord[]
  } | null
}

export type Subsidy = {
  id: string
  created_at: string
  updated_at: string
  farm_id: string
  parcel_id: string | null
  parcel_name: string | null
  title: string
  total_cost: string
  subsidy_amount: string
  subsidy_percent: string | null
  currency: string
  received_on: string
  notes: string | null
  activity_id: string | null
  created_by_id: string | null
}

export type SubsidyCreatePayload = {
  title: string
  total_cost: number
  subsidy_amount: number
  received_on: string
  parcel_id?: string | null
  notes?: string | null
}

export type OrchardSeason = {
  id: string
  created_at: string
  updated_at: string
  farm_id: string
  parcel_id: string | null
  parcel_name: string | null
  name: string
  starts_on: string
  ends_on: string
  notes: string | null
  created_by_id: string | null
}

export type OrchardSeasonPayload = {
  name: string
  starts_on: string
  ends_on: string
  parcel_id?: string | null
  notes?: string | null
}

export type TaskSchedule = {
  id: string
  created_at: string
  updated_at: string
  farm_id: string
  parcel_id: string | null
  parcel_name: string | null
  season_id: string | null
  season_name: string | null
  activity_type: CatalogItem
  title: string
  starts_on: string
  ends_on: string
  weekdays: number[]
  notes: string | null
  is_active: boolean
  created_by_id: string | null
  planned_count: number
}

export type TaskSchedulePayload = {
  title: string
  activity_type_id: string
  weekdays: number[]
  starts_on?: string | null
  ends_on?: string | null
  season_id?: string | null
  parcel_id?: string | null
  notes?: string | null
  is_active?: boolean
  whole_year?: boolean
  year?: number
}


export type PlanningSeasonStatus = 'draft' | 'active' | 'completed' | 'archived'
export type PlanningPlanType = 'protection' | 'nutrition' | 'irrigation'
export type PlanningPlanStatus =
  | 'draft'
  | 'ready_for_review'
  | 'expert_review'
  | 'approved'
  | 'rejected'
  | 'active'
  | 'completed'
export type PlanningItemStatus =
  | 'planned'
  | 'monitor'
  | 'observed'
  | 'needs_review'
  | 'approved'
  | 'completed'
  | 'cancelled'
export type PlanningItemSource = 'system' | 'agronomic_rule' | 'previous_plan' | 'history' | 'user' | 'ai'
export type PlanningExpertReviewStatus = 'not_required' | 'pending' | 'approved' | 'modified' | 'rejected'
export type ExpertReviewStatus = 'pending' | 'approved' | 'modified' | 'rejected'
export type PlanningScopeType = 'parcel' | 'row' | 'tree'
export type PlanningItemKind =
  | 'monitoring'
  | 'observation'
  | 'assessment'
  | 'expert_review'
  | 'intervention_pending'
  | 'soil_review'
  | 'nutrition_monitoring'
  | 'fertilization_window'
  | 'irrigation_monitoring'
  | 'irrigation_window'
  | 'estimated_need'
  | 'system_calculation'
export type PlanningStream = 'preventive' | 'reactive'
export type PlanningPriorityLevel = 'high' | 'medium' | 'low' | 'info'

export type ExpertReview = {
  id: string
  created_at: string
  updated_at: string
  plan_item_id: string
  farm_id: string
  requested_by_id: string | null
  reviewer_id: string | null
  reviewer_name: string | null
  status: ExpertReviewStatus
  reviewed_at: string | null
  comment: string | null
  original_recommendation_snapshot: Record<string, unknown>
  reviewed_recommendation_snapshot: Record<string, unknown> | null
}

export type PlanningPlanItem = {
  id: string
  created_at: string
  updated_at: string
  plan_id: string
  scope_type: PlanningScopeType
  scope_id: string
  title: string
  description: string | null
  planned_date_from: string | null
  planned_date_to: string | null
  priority: number
  priority_level: PlanningPriorityLevel
  priority_reason: string | null
  item_kind: PlanningItemKind
  stream: PlanningStream
  reason: string | null
  evidence: Array<Record<string, unknown>>
  missing_data: string[]
  related_activity_id: string | null
  status: PlanningItemStatus
  source: PlanningItemSource
  expert_review_status: PlanningExpertReviewStatus
  source_season_id: string | null
  source_plan_id: string | null
  source_plan_item_id: string | null
  display_status: string
  display_status_label: string
  requires_expert_review: boolean
  provenance: Record<string, unknown>
  expert_reviews: ExpertReview[]
}

export type PlanningPlan = {
  id: string
  created_at: string
  updated_at: string
  planning_season_id: string
  type: PlanningPlanType
  status: PlanningPlanStatus
  version: number
  item_count: number
  items: PlanningPlanItem[]
}

export type PlanningSeason = {
  id: string
  created_at: string
  updated_at: string
  farm_id: string
  parcel_id: string
  parcel_name: string | null
  year: number
  status: PlanningSeasonStatus
  copied_from_season_id: string | null
  created_by_id: string | null
  plans: PlanningPlan[]
}

export type PlanningParcelSummary = {
  parcel_id: string
  parcel_name: string
  farm_id: string
  area_hectares: number | null
  default_variety: string | null
  varieties: string[]
  default_planting_year: number | null
  well_location: string | null
  irrigation_hint: string | null
  has_irrigation: boolean
  irrigation_type: string | null
  organic_status: string | null
  organic_status_note: string
  latest_soil_analysis: {
    id: string
    sampled_on: string
    original_filename: string
    tree_id: string
    verification_status: string | null
    laboratory_name: string | null
    result_count: number
    source_kind: string
  } | null
  recent_activities: Array<{
    id: string
    title: string
    performed_on: string
    activity_type: string | null
    status: string
    semantic_type: string | null
    scope_type: string | null
    observation_category: string | null
    observation_status: string | null
    observation_id: string | null
    follow_up_of_id: string | null
    plan_item_id: string | null
  }>
  seasons: PlanningSeason[]
  previous_plans: Array<{
    season_id: string
    year: number
    plan_id: string
    plan_type: PlanningPlanType
    status: PlanningPlanStatus
    item_count: number
  }>
}

export type PlanningDashboard = {
  parcel_id: string
  parcel_name: string
  year: number
  season_id: string | null
  season_status: PlanningSeasonStatus | null
  previous_season: PlanningSeason | null
  priorities: Array<{
    plan_item_id: string
    plan_id: string
    plan_type: PlanningPlanType
    title: string
    display_status: string
    display_status_label: string
    priority_level: PlanningPriorityLevel
    planned_date_from: string | null
    scope_type: PlanningScopeType
    scope_id: string
    expert_review_status: PlanningExpertReviewStatus
    reason: string | null
  }>
  protection: {
    plan_type: PlanningPlanType
    plan_id: string | null
    status: string
    next_actions: string[]
    active_observations: number
    expert_review_pending: number
    expert_review_count: number
    soil_analysis: string | null
    system_status: string | null
    item_count: number
  }
  nutrition: {
    plan_type: PlanningPlanType
    plan_id: string | null
    status: string
    next_actions: string[]
    active_observations: number
    expert_review_pending: number
    expert_review_count: number
    soil_analysis: string | null
    system_status: string | null
    item_count: number
  }
  irrigation: {
    plan_type: PlanningPlanType
    plan_id: string | null
    status: string
    next_actions: string[]
    active_observations: number
    expert_review_pending: number
    expert_review_count: number
    soil_analysis: string | null
    system_status: string | null
    item_count: number
  }
}

export type WorkTaskStatus = 'planned' | 'completed' | 'cancelled'

export type Worker = {
  id: string
  farm_id: string
  first_name: string
  last_name: string
  hourly_rate: string
  active: boolean
  created_by_id: string | null
  created_at: string
  updated_at: string
}

export type WorkerCreatePayload = {
  first_name: string
  last_name: string
  hourly_rate: number | string
  active?: boolean
}

export type WorkerUpdatePayload = {
  first_name?: string
  last_name?: string
  hourly_rate?: number | string
  active?: boolean
}

export type WorkTask = {
  id: string
  farm_id: string
  parcel_id: string
  worker_id: string
  task_type_id: string
  description: string | null
  worked_on: string
  hours: string
  hourly_rate_snapshot: string
  labor_cost: string
  status: WorkTaskStatus
  cost_id: string | null
  created_by_id: string | null
  created_at: string
  updated_at: string
  worker_name: string | null
  parcel_name: string | null
  task_type: CatalogItem | null
}

export type WorkTaskCreatePayload = {
  worker_id: string
  parcel_id: string
  task_type_id: string
  description?: string | null
  worked_on: string
  hours: number | string
  hourly_rate?: number | string | null
  status?: WorkTaskStatus
}

export type WorkTaskUpdatePayload = {
  worker_id?: string
  parcel_id?: string
  task_type_id?: string
  description?: string | null
  worked_on?: string
  hours?: number | string
  hourly_rate?: number | string | null
  status?: WorkTaskStatus
}

export type WorkTaskFilters = {
  parcel_id?: string
  worker_id?: string
  task_type_id?: string
  status?: WorkTaskStatus
  date_from?: string
  date_to?: string
}

export type WorkforceBreakdownItem = {
  id: string | null
  label: string
  hours: string
  labor_cost: string
  task_count: number
}

export type WorkforceDashboard = {
  total_labor_cost: string
  total_hours: string
  worker_count: number
  task_count: number
  by_worker: WorkforceBreakdownItem[]
  by_task_type: WorkforceBreakdownItem[]
  by_parcel: WorkforceBreakdownItem[]
}

export type ParcelLaborSummary = {
  parcel_id: string
  total_hours: string
  total_labor_cost: string
  recent_tasks: WorkTask[]
}

export type PassportStatus = 'draft' | 'published' | 'finalized' | 'revoked'

export type PassportVisibility = {
  producer?: boolean
  orchard?: boolean
  location?: boolean
  product?: boolean
  quantity?: boolean
  production_practices?: boolean
}

export type HarvestLot = {
  id: string
  farm_id: string
  parcel_id: string
  harvest_id: string
  lot_number: string
  harvest_date: string
  quantity: string | null
  unit: string
  crop: string
  variety: string | null
  passport_token: string
  passport_status: PassportStatus
  visibility: PassportVisibility
  allow_indexing: boolean
  passport_version: string
  finalized_at: string | null
  revoked_at: string | null
  created_by_id: string | null
  created_at: string
  updated_at: string
  public_url: string
  qr_url: string
  parcel_name: string | null
  farm_name: string | null
  producer_name: string | null
  parcel_location: string | null
  varieties: string[]
  snapshot_version: number | null
}

export type HarvestLotCreatePayload = {
  harvest_id: string
  crop?: string | null
  variety?: string | null
  quantity?: number | string | null
  unit?: string | null
  visibility?: PassportVisibility
  allow_indexing?: boolean
  finalize?: boolean
}

export type HarvestLotUpdatePayload = {
  crop?: string | null
  variety?: string | null
  quantity?: number | string | null
  unit?: string | null
  visibility?: PassportVisibility
  allow_indexing?: boolean
}

export type PublicPracticeItem = {
  key: string
  label: string
  value: string
}

export type PublicPassport = {
  lot_number: string
  passport_version: string
  passport_status: PassportStatus
  created_at: string
  finalized: boolean
  allow_indexing: boolean
  producer: {
    name: string | null
    country: string | null
    logo_url: string | null
  } | null
  orchard: {
    farm_name: string | null
    location: string | null
    parcel_name: string | null
  } | null
  product: {
    crop: string | null
    variety: string | null
    varieties: string[]
    harvest_year: number | null
    harvest_date: string | null
    quantity: string | null
    unit: string | null
  } | null
  production_practices: PublicPracticeItem[] | null
  traceability: string[]
  metadata: {
    lot_number?: string
    passport_created_at?: string
    passport_version?: string
    finalized_at?: string | null
  }
}

export type ComplianceReportType =
  | 'farm_profile'
  | 'parcel_register'
  | 'plant_protection'
  | 'fertilization_inputs'
  | 'harvest_traceability'
  | 'farm_activity'
  | 'irrigation_water'
  | 'compliance_package'

export type ComplianceReportDefinition = {
  id: string
  type: ComplianceReportType
  title: string
  description: string | null
  data_source: string
  template: string
  version: string
  default_filters: Record<string, unknown>
  sort_order: number
  is_active: boolean
  include_in_default_package: boolean
  created_at: string
  updated_at: string
}

export type ComplianceIssue = {
  code: string
  severity: string
  message: string
  field: string | null
}

export type ComplianceReportResult = {
  meta: {
    report_type: ComplianceReportType
    title: string
    farm_name: string
    farm_id: string
    period_from: string | null
    period_to: string | null
    generated_at: string
    filters: Record<string, unknown>
    record_count: number
    definition_version: string
    disclaimer: string
    issues_count: number
  }
  columns: string[]
  rows: Record<string, string | number | null>[]
  issues: ComplianceIssue[]
}

export type ComplianceReportRun = {
  id: string
  farm_id: string
  report_type: ComplianceReportType
  title: string
  format: 'json' | 'csv' | 'pdf' | 'zip'
  filters: Record<string, unknown>
  period_from: string | null
  period_to: string | null
  parcel_ids: string[] | null
  record_count: number
  definition_id: string | null
  definition_version: string | null
  generated_by_id: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export type CompliancePackagePayload = {
  date_from?: string | null
  date_to?: string | null
  parcel_ids?: string[]
  report_types?: ComplianceReportType[]
  include_costs?: boolean
  as_zip?: boolean
}
