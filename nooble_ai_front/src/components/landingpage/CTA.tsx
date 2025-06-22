import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { GithubIcon } from "lucide-react";
import BlurredShape from "~/public/images/blurred-shape.svg";

export default function Cta() {
  return (
    <section className="relative overflow-hidden">
      <div
        className="pointer-events-none absolute bottom-0 left-1/2 -z-10 -mb-24 ml-20 -translate-x-1/2"
        aria-hidden="true"
      >
        <Image
          className="max-w-none"
          src={BlurredShape}
          width={760}
          height={668}
          alt="Blurred shape"
        />
      </div>
      <div className="max-w6xl mx-auto px-4 sm:px-6">
        <div className="bg-background/50 py-12 md:py-20">
          <div className="mx-auto max-w-3xl text-center">
            <h2
              className="animate-[var(--animate-gradient)] bg-gradient-to-r from-primary via-accent to-primary bg-[length:200%_auto] bg-clip-text pb-8 font-nacelle text-3xl font-semibold text-transparent md:text-4xl"
              data-aos="fade-up"
            >
              Join the Open-Source Community
            </h2>
            <div className="mx-auto max-w-xs sm:flex sm:max-w-none sm:justify-center">
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
      </div>
    </section>
  );
}
