import { apiDownload, apiRequest } from '@/shared/lib/api'
import { getAccessToken } from '@/shared/lib/auth'
import type {
  CompliancePackagePayload,
  ComplianceReportDefinition,
  ComplianceReportResult,
  ComplianceReportRun,
  ComplianceReportType,
} from '@/shared/api/types'

import { tr } from '@/shared/i18n/i18n'
const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || '/api/v1'

function queryString(filters: Record<string, string | boolean | undefined | null | string[]> = {}) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) {
      for (const item of value) params.append(key, item)
      continue
    }
    params.set(key, String(value))
  }
  const encoded = params.toString()
  return encoded ? `?${encoded}` : ''
}

export type ComplianceFilters = {
  date_from?: string
  date_to?: string
  parcel_id?: string
  parcel_ids?: string[]
  crop?: string
  product?: string
  operator?: string
  activity_type_id?: string
  worker_id?: string
  include_costs?: boolean
}

export function listComplianceDefinitions() {
  return apiRequest<ComplianceReportDefinition[]>('/compliance/definitions')
}

export function listComplianceRuns() {
  return apiRequest<ComplianceReportRun[]>('/compliance/runs')
}

export function getComplianceReport(reportType: ComplianceReportType, filters: ComplianceFilters = {}) {
  return apiRequest<ComplianceReportResult>(`/compliance/reports/${reportType}${queryString(filters)}`)
}

export function downloadComplianceCsv(reportType: ComplianceReportType, filters: ComplianceFilters = {}) {
  return apiDownload(
    `/compliance/reports/${reportType}/export.csv${queryString(filters)}`,
    `agrotwin-${reportType}.csv`,
  )
}

export function downloadCompliancePdf(reportType: ComplianceReportType, filters: ComplianceFilters = {}) {
  return apiDownload(
    `/compliance/reports/${reportType}/export.pdf${queryString(filters)}`,
    `agrotwin-${reportType}.pdf`,
  )
}

export async function fetchCompliancePackage(payload: CompliancePackagePayload): Promise<Blob> {
  const token = getAccessToken()
  const response = await fetch(`${API_URL}/compliance/package`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw new Error(tr('Generisanje paketa nije uspelo'))
  }
  return response.blob()
}
