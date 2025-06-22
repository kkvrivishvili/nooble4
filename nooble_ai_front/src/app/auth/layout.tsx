import { Card, CardContent } from '@/components/ui/Card'

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="bg-background">
      <div className="flex min-h-[calc(100vh-4rem)] flex-col justify-center py-12 sm:px-6 lg:px-8">
        <Card className="mx-auto w-full max-w-md">
          <CardContent className="p-6">
            {children}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
