import { useEffect } from 'react'
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes, useParams, useSearchParams } from 'react-router-dom'

import { AppLayout } from '@/app/AppLayout'
import { GuestRoute, ProtectedRoute, SuperuserRoute } from '@/app/route-guards'
import { isAuthenticated, subscribeAuth } from '@/shared/lib/auth'
import { ActivityCreatePage } from '@/features/journal/ActivityCreatePage'
import { ActivityDetailPage } from '@/features/journal/ActivityDetailPage'
import { CostSummaryPage } from '@/features/journal/CostSummaryPage'
import { CostsSectionLayout } from '@/features/journal/CostsSectionLayout'
import { InvoicesPage } from '@/features/invoices/InvoicesPage'
import { JournalPage } from '@/features/journal/JournalPage'
import { JournalSectionLayout } from '@/features/journal/JournalSectionLayout'
import { SchedulePage } from '@/features/journal/SchedulePage'
import { AgronomistPage } from '@/features/agronomist/AgronomistPage'
import { KnowledgePage } from '@/features/knowledge/KnowledgePage'
import { LoginPage } from '@/features/auth/LoginPage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { DiseaseDetailPage } from '@/features/health/DiseaseDetailPage'
import { HealthIndexPage } from '@/features/health/HealthIndexPage'
import { ReportProblemPage } from '@/features/health/ReportProblemPage'
import { CreateParcelPage } from '@/features/orchard/CreateParcelPage'
import { EditParcelPage } from '@/features/orchard/EditParcelPage'
import { IntelligencePage } from '@/features/orchard/IntelligencePage'
import { OrchardIndexPage } from '@/features/orchard/OrchardIndexPage'
import { OrchardMapPage } from '@/features/orchard/OrchardMapPage'
import { ParcelSoilAnalysesPage } from '@/features/orchard/ParcelSoilAnalysesPage'
import { SatelliteMonitoringPage } from '@/features/orchard/SatelliteMonitoringPage'
import { TreeJournalPage } from '@/features/orchard/TreeJournalPage'
import { MapEditorPage } from '@/features/map-editor/MapEditorPage'
import { HarvestDetailPage } from '@/features/production/HarvestDetailPage'
import { HarvestFormPage } from '@/features/production/HarvestFormPage'
import { ProductionPage } from '@/features/production/ProductionPage'
import { ParcelReportPage } from '@/features/reports/ParcelReportPage'
import { ReportsSectionLayout } from '@/features/reports/ReportsSectionLayout'
import { CompliancePage } from '@/features/compliance/CompliancePage'
import { ContextPreviewPage } from '@/features/context/ContextPreviewPage'
import { BenchmarkPage } from '@/features/benchmark/BenchmarkPage'
import { PlanningPage } from '@/features/planning/PlanningPage'
import { WorkforcePage } from '@/features/workforce/WorkforcePage'
import { PassportPage } from '@/features/passport/PassportPage'
import { EnterpriseLayout } from '@/features/enterprise/EnterpriseLayout'
import { EnterpriseIndexPage } from '@/features/enterprise/pages/EnterpriseIndexPage'
import { EnterpriseChangePasswordPage } from '@/features/enterprise/pages/EnterpriseChangePasswordPage'
import { EnterpriseDashboardPage } from '@/features/enterprise/pages/EnterpriseDashboardPage'
import { EnterpriseSuppliersPage } from '@/features/enterprise/pages/EnterpriseSuppliersPage'
import { EnterpriseSupplierDetailPage } from '@/features/enterprise/pages/EnterpriseSupplierDetailPage'
import { EnterpriseParcelsPage } from '@/features/enterprise/pages/EnterpriseParcelsPage'
import { EnterpriseParcelDetailPage } from '@/features/enterprise/pages/EnterpriseParcelDetailPage'
import { EnterpriseProductionPage } from '@/features/enterprise/pages/EnterpriseProductionPage'
import { EnterpriseRisksPage } from '@/features/enterprise/pages/EnterpriseRisksPage'
import { EnterpriseReportsPage } from '@/features/enterprise/pages/EnterpriseReportsPage'
import { EnterpriseSettingsPage } from '@/features/enterprise/pages/EnterpriseSettingsPage'
import { AdminAccountsPage } from '@/features/admin/AdminAccountsPage'
import { AdminEnterpriseLinkPage } from '@/features/admin/AdminEnterpriseLinkPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function AuthQuerySync() {
  const client = useQueryClient()
  useEffect(() => {
    return subscribeAuth(() => {
      if (!isAuthenticated()) {
        client.clear()
      }
    })
  }, [client])
  return null
}

function LegacyPlanningRedirect() {
  const { section } = useParams()
  const [params] = useSearchParams()
  const qs = params.toString()
  const path = section ? `/journal/planning/${section}` : '/journal/planning'
  return <Navigate to={qs ? `${path}?${qs}` : path} replace />
}

function EnterprisePlanningRedirect() {
  const { organizationId } = useParams()
  return <Navigate to={`/enterprise/${organizationId}/production?tab=planning`} replace />
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthQuerySync />
      <BrowserRouter>
        <Routes>
          <Route
            path="/login"
            element={
              <GuestRoute>
                <LoginPage />
              </GuestRoute>
            }
          />
          <Route path="/passport/:token" element={<PassportPage />} />
          <Route
            path="/enterprise/change-password"
            element={
              <ProtectedRoute>
                <EnterpriseChangePasswordPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/enterprise"
            element={
              <ProtectedRoute>
                <EnterpriseIndexPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/enterprise/:organizationId"
            element={
              <ProtectedRoute>
                <EnterpriseLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<EnterpriseDashboardPage />} />
            <Route path="suppliers" element={<EnterpriseSuppliersPage />} />
            <Route path="suppliers/:linkId" element={<EnterpriseSupplierDetailPage />} />
            <Route path="parcels" element={<EnterpriseParcelsPage />} />
            <Route path="parcels/:parcelId" element={<EnterpriseParcelDetailPage />} />
            <Route path="production" element={<EnterpriseProductionPage />} />
            <Route path="planning" element={<EnterprisePlanningRedirect />} />
            <Route path="risks" element={<EnterpriseRisksPage />} />
            <Route path="reports" element={<EnterpriseReportsPage />} />
            <Route path="settings" element={<EnterpriseSettingsPage />} />
          </Route>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="orchard" element={<OrchardIndexPage />} />
            <Route path="orchard/new" element={<CreateParcelPage />} />
            <Route path="orchard/:parcelId/edit" element={<EditParcelPage />} />
            <Route path="orchard/:parcelId/map-editor" element={<MapEditorPage />} />
            <Route path="orchard/:parcelId/satellite" element={<SatelliteMonitoringPage />} />
            <Route path="orchard/:parcelId/intelligence" element={<IntelligencePage />} />
            <Route path="orchard/:parcelId/soil-analyses" element={<ParcelSoilAnalysesPage />} />
            <Route path="orchard/:parcelId/production/new" element={<HarvestFormPage />} />
            <Route path="orchard/:parcelId/production/:harvestId" element={<HarvestDetailPage />} />
            <Route path="orchard/:parcelId/production" element={<ProductionPage />} />
            <Route path="orchard/:parcelId" element={<OrchardMapPage />} />
            <Route path="orchard/:parcelId/report" element={<ParcelReportPage />} />
            <Route path="orchard/:parcelId/trees/:treeId" element={<TreeJournalPage />} />
            <Route path="reports" element={<ReportsSectionLayout />}>
              <Route index element={<ParcelReportPage />} />
              <Route path="compliance" element={<CompliancePage />} />
            </Route>
            <Route path="production" element={<ProductionPage />} />
            <Route path="journal" element={<JournalSectionLayout />}>
              <Route index element={<JournalPage />} />
              <Route path="planning" element={<PlanningPage />} />
              <Route path="planning/:section" element={<PlanningPage />} />
              <Route path="schedule" element={<SchedulePage />} />
            </Route>
            <Route path="planning" element={<LegacyPlanningRedirect />} />
            <Route path="planning/:section" element={<LegacyPlanningRedirect />} />
            <Route path="activities/new" element={<ActivityCreatePage />} />
            <Route path="activities/:activityId" element={<ActivityDetailPage />} />
            <Route path="costs" element={<CostsSectionLayout />}>
              <Route index element={<CostSummaryPage />} />
              <Route path="workforce" element={<WorkforcePage />} />
              <Route path="invoices" element={<InvoicesPage />} />
            </Route>
            <Route path="invoices" element={<Navigate to="/costs/invoices" replace />} />
            <Route path="health" element={<HealthIndexPage />} />
            <Route path="health/new" element={<ReportProblemPage />} />
            <Route path="health/:caseId" element={<DiseaseDetailPage />} />
            <Route path="agronomist/:conversationId?" element={<AgronomistPage />} />
            <Route path="knowledge" element={<KnowledgePage />} />
            <Route
              path="admin"
              element={
                <SuperuserRoute>
                  <AdminAccountsPage />
                </SuperuserRoute>
              }
            />
            <Route
              path="admin/enterprise/:organizationId"
              element={
                <SuperuserRoute>
                  <AdminEnterpriseLinkPage />
                </SuperuserRoute>
              }
            />
            <Route path="dev/context" element={<ContextPreviewPage />} />
            <Route
              path="dev/benchmark"
              element={
                <SuperuserRoute>
                  <BenchmarkPage />
                </SuperuserRoute>
              }
            />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
