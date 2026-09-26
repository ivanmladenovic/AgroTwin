import { ReportProblemForm } from '@/features/health/ReportProblemForm'

export function ReportProblemPage() {
  return (
    <div className="w-full space-y-6">
      <div>
        <p className="kicker">Zdravlje stabala</p>
        <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Prijavi problem</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Zabeležite simptome, fotografije i obuhvat. Ovo nije medicinska ni agronomska dijagnoza.
        </p>
      </div>
      <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
        <ReportProblemForm />
      </div>
    </div>
  )
}
