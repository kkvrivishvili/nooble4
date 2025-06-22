import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'

export default function DashboardPage() {
  return (
    <div className="container mx-auto py-10">
      <Card>
        <CardHeader>
          <CardTitle>Dashboard</CardTitle>
        </CardHeader>
        <CardContent>
          <p>Welcome to your dashboard!</p>
        </CardContent>
      </Card>
    </div>
  )
}
