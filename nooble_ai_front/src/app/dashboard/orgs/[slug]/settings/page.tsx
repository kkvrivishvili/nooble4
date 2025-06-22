import { redirect } from 'next/navigation'

export default async function OrganizationSettings({
  params,
}: {
  params: { slug: string }
}) {
  return redirect(`/dashboard/orgs/${params.slug}/settings/general`)
} 
