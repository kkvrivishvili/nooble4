import { GithubIcon } from "lucide-react";
import ModalVideo from "@/components/landingpage/modal-video";
import { Button } from "@/components/ui/Button";
import Link from "next/link";

export default function HeroHome() {
  return (
    <section>
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        {/* Hero content */}
        <div className="py-12 md:py-20">
          {/* Section header */}
          <div className="pb-12 text-center md:pb-20">
            <h1
              className="animate-[var(--animate-gradient)] bg-gradient-to-r from-primary via-accent to-primary bg-[length:200%_auto] bg-clip-text pb-5 font-nacelle text-4xl font-semibold text-transparent md:text-5xl"
              data-aos="fade-up"
            >
              An Open-Source Next.js Boilerplate
            </h1>
            <div className="mx-auto max-w-3xl">
              <p
                className="mb-8 text-xl text-muted-foreground"
                data-aos="fade-up"
                data-aos-delay={200}
              >
                A modular, scalable, and reusable SaaS boilerplate built with
                Next.js 15, TypeScript, Tailwind CSS, and Supabase.
              </p>
              <div className="mx-auto max-w-xs sm:flex sm:max-w-none sm:justify-center">
                {/* Primary Button - GitHub */}
                <div data-aos="fade-up" data-aos-delay={400}>
                  <Link href="https://github.com/Vindusvisker/Nextjs-Supabase-Boilerplate">
                    <Button
                      variant="primary"
                      size="lg"
                      className="group mb-4 w-full sm:mb-0 sm:w-auto"
                    >
                      GitHub Repository
                      <GithubIcon className="ml-2 h-4 w-4 opacity-50 transition-transform duration-150 group-hover:translate-x-0.5" />
                    </Button>
                  </Link>
                </div>
                {/* Secondary Button - Portfolio */}
                <div data-aos="fade-up" data-aos-delay={600}>
                  <Link href="https://www.mruud.com/">
                    <Button
                      variant="secondary"
                      size="lg"
                      className="ml-0 w-full sm:ml-6 sm:w-auto"
                    >
                      My Indie Portfolio
                    </Button>
                  </Link>
                </div>
              </div>
            </div>
          </div>

          {/* Hero image */}
          <ModalVideo
            thumbWidth={1104}
            thumbHeight={576}
            thumbAlt="Modal video thumbnail"
            video="/videos/video.mp4"
            videoWidth={1920}
            videoHeight={1080}
          />
        </div>
      </div>
    </section>
  );
}
