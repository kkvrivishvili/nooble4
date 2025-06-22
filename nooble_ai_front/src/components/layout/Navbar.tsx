"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { LogoutButton } from "@/components/auth/LogoutButton";
import { Button } from "@/components/ui/Button";

export function Navbar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const isAuthPage = pathname.startsWith("/auth");
  const isDashboardPage = pathname.startsWith("/dashboard");
  const isInvitePage = pathname.startsWith("/invite");

  // Preserve search params for auth links
  const authSearchParams = new URLSearchParams({
    ...(searchParams.get("invite") && { invite: searchParams.get("invite")! }),
    ...(searchParams.get("org") && { org: searchParams.get("org")! }),
    ...(searchParams.get("email") && { email: searchParams.get("email")! }),
  });

  const searchParamsString = authSearchParams.toString();
  const queryString = searchParamsString ? `?${searchParamsString}` : "";

  // Don't render navbar on dashboard or invite pages
  if (isDashboardPage || isInvitePage) return null;

  return (
    <header className="z-30 mt-2 w-full md:mt-5">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="relative flex h-14 items-center justify-between gap-3 rounded-2xl bg-gray-950/80 px-3 before:pointer-events-none before:absolute before:inset-0 before:rounded-[inherit] before:border before:border-transparent before:[background:linear-gradient(to_right,var(--color-gray-900),var(--color-gray-800),var(--color-gray-900))_border-box] before:[mask-composite:exclude_!important] before:[mask:linear-gradient(white_0_0)_padding-box,_linear-gradient(white_0_0)] after:absolute after:inset-0 after:-z-10 after:backdrop-blur-md">
          {/* Site branding */}
          <div className="flex flex-1 items-center">
            <Link href="/" className="font-semibold text-gray-200">
              DEMO BOILERPLATE
            </Link>
          </div>

          {/* Desktop navigation */}
          {!isAuthPage && (
            <div className="flex items-center gap-4">
              {pathname === "/" ? (
                <>
                  <Link href={`/auth/login${queryString}`}>
                    <Button
                      variant="primary"
                      size="md"
                      className="relative bg-linear-to-b from-gray-900 to-gray-900/60 bg-[length:100%_100%] bg-[bottom] py-[5px] text-gray-200 before:pointer-events-none before:absolute before:inset-0 before:rounded-[inherit] before:border before:border-transparent before:[background:linear-gradient(to_right,var(--color-gray-800),var(--color-gray-700),var(--color-gray-800))_border-box] before:[mask-composite:exclude_!important] before:[mask:linear-gradient(white_0_0)_padding-box,_linear-gradient(white_0_0)] hover:bg-[length:100%_150%]"
                    >
                      Login
                    </Button>
                  </Link>
                  <Link href={`/auth/signup${queryString}`}>
                    <Button
                      variant="glass"
                      size="md"
                      className="bg-linear-to-t from-blue-600 to-blue-500 bg-[length:100%_100%] bg-[bottom] py-[5px] text-white shadow-[inset_0px_1px_0px_0px_--theme(--color-white/.16)] hover:bg-[length:100%_150%]"
                    >
                      Sign Up
                    </Button>
                  </Link>
                </>
              ) : (
                <LogoutButton />
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
