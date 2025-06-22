import { redirect } from "next/navigation";
import { use } from "react";
import PageIllustration from "@/components/landingpage/PageIllustration";
import Features from "@/components/landingpage/Features";
import Workflows from "@/components/landingpage/Workflows";
import Testimonials from "@/components/landingpage/Testimonials";
import CTA from "@/components/landingpage/CTA";
import HeroHome from "@/components/landingpage/Hero";
import Footer from "@/components/layout/Footer";
export default function Home({
  searchParams,
}: {
  searchParams: {
    code?: string; // PKCE auth code
    invite?: string; // Supabase auth invites
    token?: string; // Our org invites
    org?: string;
  };
}) {
  const params = use(Promise.resolve(searchParams));

  // If we have a code (from PKCE flow), redirect to oauth-callback
  if (params.code) {
    const searchParamsString = new URLSearchParams({
      code: params.code,
      ...(params.invite && { invite: params.invite }), // Keep Supabase invite param
      ...(params.org && { org: params.org }),
    }).toString();

    redirect(`/auth/oauth-callback?${searchParamsString}`);
  }

  // Our custom org invite token handling
  if (params.token) {
    redirect(`/invite?token=${params.token}`);
  }

  // Now render the landing page components
  return (
    <>
      <HeroHome />
      <PageIllustration />
      <div className="relative">
        <Workflows />
        <Features />
        <Testimonials />
        <CTA />
        <Footer />
      </div>
    </>
  );
}
