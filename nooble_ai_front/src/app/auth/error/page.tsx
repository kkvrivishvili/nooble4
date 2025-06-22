"use client";

import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import Link from "next/link";

const ERROR_MESSAGES = {
  "auth/no-code":
    "Authentication code was missing. Please try signing in again.",
  "auth/exchange-failed":
    "Failed to complete authentication. Please try again.",
  "auth/invalid-state":
    "Invalid authentication state. Please try signing in again.",
  "auth/unauthorized":
    "Your email is not authorized to access this application.",
  "auth/unknown": "An unexpected error occurred during authentication.",
} as const;

type ErrorCode = keyof typeof ERROR_MESSAGES;

export default function AuthErrorPage() {
  const searchParams = useSearchParams();
  const errorCode = searchParams.get("error") as ErrorCode;
  const errorMessage = searchParams.get("message");

  const displayMessage =
    ERROR_MESSAGES[errorCode] || "An error occurred during authentication.";
  const technicalDetails =
    errorMessage && errorCode === "auth/unknown"
      ? `Technical details: ${errorMessage}`
      : null;

  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
      <h1 className="text-2xl font-bold text-red-600 mb-4">
        Authentication Error
      </h1>

      <p className="text-muted-foreground mb-2">{displayMessage}</p>

      {technicalDetails && (
        <p className="text-sm text-muted-foreground mb-4">{technicalDetails}</p>
      )}

      <div className="flex gap-4 mt-6">
        <Link href="/auth/login">
          <Button variant="outline" size="md">
            Try Again
          </Button>
        </Link>

        <Link href="/">
          <Button variant="primary" size="md">
            Go Home
          </Button>
        </Link>
      </div>
    </div>
  );
}
