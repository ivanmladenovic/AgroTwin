import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { changeEnterprisePassword, getEnterpriseMe } from '@/features/enterprise/api'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { tr } from '@/shared/i18n/i18n'

export function EnterpriseChangePasswordPage() {
  useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () =>
      changeEnterprisePassword({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['me'] })
      await queryClient.invalidateQueries({ queryKey: ['enterprise-me'] })
      const me = await getEnterpriseMe()
      const orgId = me.memberships[0]?.organization_id
      void navigate(orgId ? `/enterprise/${orgId}` : '/')
    },
    onError: (err: Error) => {
      setError(err.message || tr('Promena lozinke nije uspela'))
    },
  })

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-4 py-10">
      <h1 className="text-2xl font-semibold">{tr('Promena početne lozinke')}</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Pre pristupa Enterprise podacima obavezna je promena privremene lozinke.
      </p>
      <form
        className="mt-6 space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          setError(null)
          mutation.mutate()
        }}
      >
        <div className="space-y-1.5">
          <Label htmlFor="current">{tr('Trenutna lozinka')}</Label>
          <Input
            id="current"
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="next">{tr('Nova lozinka')}</Label>
          <Input
            id="next"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
          />
        </div>
        {error ? <p className="text-sm text-danger">{error}</p> : null}
        <Button type="submit" disabled={mutation.isPending || newPassword.length < 8}>
          {tr('Sačuvaj lozinku')}
        </Button>
      </form>
    </div>
  )
}
