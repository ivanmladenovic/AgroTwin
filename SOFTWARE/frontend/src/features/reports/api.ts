import { apiRequest } from '@/shared/lib/api'
import type { ParcelAnnualReport } from '@/shared/api/types'

export function getParcelAnnualReport(parcelId: string, year: number) {
  return apiRequest<ParcelAnnualReport>(`/parcels/${parcelId}/report?year=${year}`)
}
