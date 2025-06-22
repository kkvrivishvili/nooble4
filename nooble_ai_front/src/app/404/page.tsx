"use client";

import { Suspense } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";

function NotFoundContent() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
      <h1 className="text-2xl font-bold text-red-600 mb-4">
        404 - Page Not Found
      </h1>

      <p className="text-muted-foreground mb-6">
        The page you're looking for doesn't exist or has been moved.
      </p>

      <div className="flex gap-4">
        <Link href="/">
          <Button variant="primary" size="md">
            Go Home
          </Button>
        </Link>
      </div>
    </div>
  );
}

export default function NotFoundPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
          <div className="animate-pulse">Loading...</div>
        </div>
      }
    >
      <NotFoundContent />
    </Suspense>
  );
}
