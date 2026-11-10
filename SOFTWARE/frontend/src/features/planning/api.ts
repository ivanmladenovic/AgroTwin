import { apiRequest } from '@/shared/lib/api'
import type {
  ExpertReviewStatus,
  PlanningDashboard,
  PlanningParcelSummary,
  PlanningPlan,
  PlanningPlanItem,
  PlanningPlanType,
  PlanningPriorityLevel,
  PlanningSeason,
  PlanningSeasonStatus,
} from '@/shared/api/types'

export function getPlanningSummary(parcelId: string) {
  return apiRequest<PlanningParcelSummary>(`/planning/parcels/${parcelId}/summary`)
}

export function getPlanningDashboard(parcelId: string, year: number) {
  return apiRequest<PlanningDashboard>(`/planning/parcels/${parcelId}/dashboard?year=${year}`)
}

export function listPlanningSeasons(parcelId: string) {
  return apiRequest<PlanningSeason[]>(`/planning/parcels/${parcelId}/seasons`)
}

export function createPlanningSeason(
  parcelId: string,
  payload: {
    year: number
    status?: PlanningSeasonStatus
    copy_from_season_id?: string | null
    copy_previous_plan?: boolean
  },
) {
  return apiRequest<PlanningSeason>(`/planning/parcels/${parcelId}/seasons`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getPlanningSeason(seasonId: string) {
  return apiRequest<PlanningSeason>(`/planning/seasons/${seasonId}`)
}

export function finishPlanningSeason(seasonId: string) {
  return apiRequest<PlanningSeason>(`/planning/seasons/${seasonId}/finish`, { method: 'POST' })
}

export function copyPlanningFromSeason(seasonId: string, sourceSeasonId: string) {
  return apiRequest<PlanningSeason>(`/planning/seasons/${seasonId}/copy-from`, {
    method: 'POST',
    body: JSON.stringify({ source_season_id: sourceSeasonId }),
  })
}

export function listPlanningPlans(seasonId: string) {
  return apiRequest<PlanningPlan[]>(`/planning/seasons/${seasonId}/plans`)
}

export function createPlanningPlan(seasonId: string, type: PlanningPlanType) {
  return apiRequest<PlanningPlan>(`/planning/seasons/${seasonId}/plans`, {
    method: 'POST',
    body: JSON.stringify({ type }),
  })
}

export function getPlanningPlan(planId: string) {
  return apiRequest<PlanningPlan>(`/planning/plans/${planId}`)
}

export function generateProtectionPlan(
  seasonId: string,
  payload: { replace_generated?: boolean; include_knowledge?: boolean } = {},
) {
  return apiRequest<PlanningPlan>(`/planning/seasons/${seasonId}/plans/protection/generate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function generateNutritionPlan(
  seasonId: string,
  payload: { replace_generated?: boolean; include_knowledge?: boolean } = {},
) {
  return apiRequest<PlanningPlan>(`/planning/seasons/${seasonId}/plans/nutrition/generate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function generateIrrigationPlan(
  seasonId: string,
  payload: { replace_generated?: boolean; include_knowledge?: boolean } = {},
) {
  return apiRequest<PlanningPlan>(`/planning/seasons/${seasonId}/plans/irrigation/generate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updatePlanningSeason(seasonId: string, payload: { status?: PlanningSeasonStatus }) {
  return apiRequest<PlanningSeason>(`/planning/seasons/${seasonId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function createPlanningPlanItem(
  planId: string,
  payload: {
    title: string
    description?: string | null
    scope_type?: 'parcel' | 'row' | 'tree'
    scope_id?: string
    planned_date_from?: string | null
    planned_date_to?: string | null
    item_kind?: string
    stream?: string
    source?: string
    reason?: string | null
    evidence?: Array<Record<string, unknown>>
    status?: string
    expert_review_status?: string
  },
) {
  return apiRequest<PlanningPlanItem>(`/planning/plans/${planId}/items`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updatePlanningPlanItem(
  planId: string,
  itemId: string,
  payload: {
    status?: string
    expert_review_status?: string
    related_activity_id?: string | null
  },
) {
  return apiRequest<PlanningPlanItem>(`/planning/plans/${planId}/items/${itemId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function submitExpertReview(planId: string, itemId: string, note?: string) {
  return apiRequest<PlanningPlanItem>(`/planning/plans/${planId}/items/${itemId}/expert-review/submit`, {
    method: 'POST',
    body: JSON.stringify({ note: note || null }),
  })
}

export function decideExpertReview(
  planId: string,
  itemId: string,
  reviewId: string,
  payload: {
    status: ExpertReviewStatus
    comment?: string
    title?: string
    description?: string
    reason?: string
    priority_level?: PlanningPriorityLevel
  },
) {
  return apiRequest<PlanningPlanItem>(
    `/planning/plans/${planId}/items/${itemId}/expert-review/${reviewId}/decide`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}
