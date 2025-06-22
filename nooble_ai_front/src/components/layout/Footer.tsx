import Image from "next/image";
import Link from "next/link";
import FooterIllustration from "~/public/images/footer-illustration.svg";

export default function Footer() {
  return (
    <footer>
      <div className="relative mx-auto max-w-6xl px-4 sm:px-6">
        {/* Footer illustration */}
        <div
          className="pointer-events-none absolute bottom-0 left-1/2 -z-10 -translate-x-1/2"
          aria-hidden="true"
        >
          <Image
            className="max-w-none"
            src={FooterIllustration}
            width={1076}
            height={378}
            alt="Footer illustration"
          />
        </div>

        <div className="border-t border-border/25 py-12 md:py-20">
          <div className="grid grid-cols-2 justify-between gap-12 sm:grid-rows-[auto_auto] md:grid-cols-4 md:grid-rows-[auto_auto] lg:grid-cols-[repeat(4,minmax(0,140px))_1fr] lg:grid-rows-1 xl:gap-20">
            {/* 1st block */}
            <div className="space-y-4">
              <h3 className="font-nacelle text-sm font-medium text-foreground">Product</h3>
              <ul className="space-y-3 text-sm">
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Features
                  </Link>
                </li>
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Integrations
                  </Link>
                </li>
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Pricing &amp; Plans
                  </Link>
                </li>
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Changelog
                  </Link>
                </li>
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Our method
                  </Link>
                </li>
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    User policy
                  </Link>
                </li>
              </ul>
            </div>

            {/* 2nd block */}
            <div className="space-y-4">
              <h3 className="font-nacelle text-sm font-medium text-foreground">Company</h3>
              <ul className="space-y-3 text-sm">
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    About us
                  </Link>
                </li>
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Diversity &amp; Inclusion
                  </Link>
                </li>
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Blog
                  </Link>
                </li>
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Careers
                  </Link>
                </li>
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Financial statements
                  </Link>
                </li>
              </ul>
            </div>

            {/* 3rd block */}
            <div className="space-y-4">
              <h3 className="font-nacelle text-sm font-medium text-foreground">Resources</h3>
              <ul className="space-y-3 text-sm">
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Community
                  </Link>
                </li>
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Terms of service
                  </Link>
                </li>
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Report a vulnerability
                  </Link>
                </li>
              </ul>
            </div>

            {/* 4th block */}
            <div className="space-y-4">
              <h3 className="font-nacelle text-sm font-medium text-foreground">Content Library</h3>
              <ul className="space-y-3 text-sm">
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Templates
                  </Link>
                </li>
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Tutorials
                  </Link>
                </li>
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Knowledge base
                  </Link>
                </li>
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Learn
                  </Link>
                </li>
                <li>
                  <Link href="#0" className="text-muted-foreground transition hover:text-primary">
                    Cookie manager
                  </Link>
                </li>
              </ul>
            </div>

            {/* 5th block */}
            <div className="col-span-2 md:col-span-4 lg:col-span-1 lg:text-right">
              <div className="mb-4">
                <Link 
                  href="/" 
                  className="bg-gradient-to-r from-primary to-accent bg-clip-text font-nacelle text-lg font-semibold text-transparent"
                >
                  DEMO BOILERPLATE
                </Link>
              </div>
              <div className="text-sm">
                <p className="mb-4 text-muted-foreground">
                  © Mruud.com
                  <span className="mx-2 text-border">·</span>
                  <Link href="/terms" className="text-muted-foreground transition hover:text-primary">
                    Terms
                  </Link>
                </p>
                <ul className="inline-flex gap-2">
                  <li>
                    <Link
                      href="https://x.com/mr_makermotion?s=21"
                      className="flex items-center justify-center text-primary transition hover:text-accent"
                      aria-label="Twitter"
                    >
                      <svg className="h-8 w-8 fill-current" viewBox="0 0 32 32">
                        <path d="m13.063 9 3.495 4.475L20.601 9h2.454l-5.359 5.931L24 23h-4.938l-3.866-4.893L10.771 23H8.316l5.735-6.342L8 9h5.063Zm-.74 1.347h-1.457l8.875 11.232h1.36l-8.778-11.232Z" />
                      </svg>
                    </Link>
                  </li>
                  <li>
                    <Link
                      href="https://www.mruud.com/"
                      className="flex items-center justify-center text-primary transition hover:text-accent"
                      aria-label="Medium"
                    >
                      <svg className="h-8 w-8 fill-current" viewBox="0 0 32 32">
                        <path d="M23 8H9a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1Zm-1.708 3.791-.858.823a.251.251 0 0 0-.1.241V18.9a.251.251 0 0 0 .1.241l.838.823v.181h-4.215v-.181l.868-.843c.085-.085.085-.11.085-.241v-4.887l-2.41 6.131h-.329l-2.81-6.13V18.1a.567.567 0 0 0 .156.472l1.129 1.37v.181h-3.2v-.181l1.129-1.37a.547.547 0 0 0 .146-.472v-4.749a.416.416 0 0 0-.138-.351l-1-1.209v-.181H13.8l2.4 5.283 2.122-5.283h2.971l-.001.181Z" />
                      </svg>
                    </Link>
                  </li>
                  <li>
                    <Link
                      href="https://github.com/Vindusvisker"
                      className="flex items-center justify-center text-primary transition hover:text-accent"
                      aria-label="Github"
                    >
                      <svg className="h-8 w-8 fill-current" viewBox="0 0 32 32">
                        <path d="M16 8.2c-4.4 0-8 3.6-8 8 0 3.5 2.3 6.5 5.5 7.6.4.1.5-.2.5-.4V22c-2.2.5-2.7-1-2.7-1-.4-.9-.9-1.2-.9-1.2-.7-.5.1-.5.1-.5.8.1 1.2.8 1.2.8.7 1.3 1.9.9 2.3.7.1-.5.3-.9.5-1.1-1.8-.2-3.6-.9-3.6-4 0-.9.3-1.6.8-2.1-.1-.2-.4-1 .1-2.1 0 0 .7-.2 2.2.8.6-.2 1.3-.3 2-.3s1.4.1 2 .3c1.5-1 2.2-.8 2.2-.8.4 1.1.2 1.9.1 2.1.5.6.8 1.3.8 2.1 0 3.1-1.9 3.7-3.7 3.9.3.4.6.9.6 1.6v2.2c0 .2.1.5.6.4 3.2-1.1 5.5-4.1 5.5-7.6-.1-4.4-3.7-8-8.1-8z" />
                      </svg>
                    </Link>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
