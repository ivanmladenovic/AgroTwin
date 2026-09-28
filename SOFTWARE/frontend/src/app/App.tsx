import { useEffect } from 'react'
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AppLayout } from '@/app/AppLayout'
import { GuestRoute, ProtectedRoute, SuperuserRoute } from '@/app/route-guards'
import { isAuthenticated, subscribeAuth } from '@/shared/lib/auth'
import { ActivityCreatePage } from '@/features/journal/ActivityCreatePage'
import { ActivityDetailPage } from '@/features/journal/ActivityDetailPage'
import { CostSummaryPage } from '@/features/journal/CostSummaryPage'
import { InvoicesPage } from '@/features/invoices/InvoicesPage'
import { JournalPage } from '@/features/journal/JournalPage'
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
import { OrchardIndexPage } from '@/features/orchard/OrchardIndexPage'
import { OrchardMapPage } from '@/features/orchard/OrchardMapPage'
import { ParcelSoilAnalysesPage } from '@/features/orchard/ParcelSoilAnalysesPage'
import { TreeJournalPage } from '@/features/orchard/TreeJournalPage'
import { HarvestDetailPage } from '@/features/production/HarvestDetailPage'
import { HarvestFormPage } from '@/features/production/HarvestFormPage'
import { ProductionPage } from '@/features/production/ProductionPage'
import { ParcelReportPage } from '@/features/reports/ParcelReportPage'
import { ContextPreviewPage } from '@/features/context/ContextPreviewPage'
import { BenchmarkPage } from '@/features/benchmark/BenchmarkPage'

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
            <Route path="orchard/:parcelId/soil-analyses" element={<ParcelSoilAnalysesPage />} />
            <Route path="orchard/:parcelId/production/new" element={<HarvestFormPage />} />
            <Route path="orchard/:parcelId/production/:harvestId" element={<HarvestDetailPage />} />
            <Route path="orchard/:parcelId/production" element={<ProductionPage />} />
            <Route path="orchard/:parcelId" element={<OrchardMapPage />} />
            <Route path="orchard/:parcelId/report" element={<ParcelReportPage />} />
            <Route path="orchard/:parcelId/trees/:treeId" element={<TreeJournalPage />} />
            <Route path="reports" element={<ParcelReportPage />} />
            <Route path="production" element={<ProductionPage />} />
            <Route path="journal" element={<JournalPage />} />
            <Route path="journal/schedule" element={<SchedulePage />} />
            <Route path="activities/new" element={<ActivityCreatePage />} />
            <Route path="activities/:activityId" element={<ActivityDetailPage />} />
            <Route path="costs" element={<CostSummaryPage />} />
            <Route path="invoices" element={<InvoicesPage />} />
            <Route path="health" element={<HealthIndexPage />} />
            <Route path="health/new" element={<ReportProblemPage />} />
            <Route path="health/:caseId" element={<DiseaseDetailPage />} />
            <Route path="agronomist/:conversationId?" element={<AgronomistPage />} />
            <Route path="knowledge" element={<KnowledgePage />} />
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
