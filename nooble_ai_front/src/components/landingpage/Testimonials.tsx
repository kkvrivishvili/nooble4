"use client";

import { useState } from "react";
import useMasonry from "@/lib/utils/useMasonry";
import Image, { StaticImageData } from "next/image";
import TestimonialImg01 from "~/public/images/testimonial-01.jpg";
import TestimonialImg02 from "~/public/images/testimonial-02.jpg";
import TestimonialImg03 from "~/public/images/testimonial-03.jpg";
import TestimonialImg04 from "~/public/images/testimonial-04.jpg";
import TestimonialImg05 from "~/public/images/testimonial-05.jpg";
import TestimonialImg06 from "~/public/images/testimonial-06.jpg";
import TestimonialImg07 from "~/public/images/testimonial-07.jpg";
import TestimonialImg08 from "~/public/images/testimonial-08.jpg";
import TestimonialImg09 from "~/public/images/testimonial-09.jpg";
import ClientImg01 from "~/public/images/client-logo-01.svg";
import ClientImg02 from "~/public/images/client-logo-02.svg";
import ClientImg03 from "~/public/images/client-logo-03.svg";
import ClientImg04 from "~/public/images/client-logo-04.svg";
import ClientImg05 from "~/public/images/client-logo-05.svg";
import ClientImg06 from "~/public/images/client-logo-06.svg";
import ClientImg07 from "~/public/images/client-logo-07.svg";
import ClientImg08 from "~/public/images/client-logo-08.svg";
import ClientImg09 from "~/public/images/client-logo-09.svg";

const testimonials = [
  {
    img: TestimonialImg01,
    clientImg: ClientImg01,
    name: "MaKayla P.",
    company: "Disney",
    content:
      "Lorem ipsum is a dummy or placeholder text commonly used in graphic design, publishing, and web development to fill empty spaces in a layout that does not yet have content.",
    categories: [1, 3, 5],
  },
  {
    img: TestimonialImg02,
    clientImg: ClientImg02,
    name: "Andrew K.",
    company: "Samsung",
    content:
      "Lorem ipsum is a dummy or placeholder text commonly used in graphic design, publishing, and web development to fill empty spaces in a layout that does not yet have content.",
    categories: [1, 2, 4],
  },
  {
    img: TestimonialImg03,
    clientImg: ClientImg03,
    name: "Lucy D.",
    company: "Rio",
    content:
      "Lorem ipsum is a dummy or placeholder text commonly used in graphic design, publishing, and web development to fill empty spaces in a layout that does not yet have content.",
    categories: [1, 2, 5],
  },
  {
    img: TestimonialImg04,
    clientImg: ClientImg04,
    name: "Pavel M.",
    company: "Canon",
    content:
      "Lorem ipsum is a dummy or placeholder text commonly used in graphic design, publishing, and web development to fill empty spaces in a layout that does not yet have content.",
    categories: [1, 4],
  },
  {
    img: TestimonialImg05,
    clientImg: ClientImg05,
    name: "Miriam E.",
    company: "Cadbury",
    content:
      "Lorem ipsum is a dummy or placeholder text commonly used in graphic design, publishing, and web development to fill empty spaces in a layout that does not yet have content.",
    categories: [1, 3, 5],
  },
  {
    img: TestimonialImg06,
    clientImg: ClientImg06,
    name: "Eloise V.",
    company: "Maffell",
    content:
      "Lorem ipsum is a dummy or placeholder text commonly used in graphic design, publishing, and web development to fill empty spaces in a layout that does not yet have content.",
    categories: [1, 3],
  },
  {
    img: TestimonialImg07,
    clientImg: ClientImg07,
    name: "Pierre-Gilles L.",
    company: "Binance",
    content:
      "Lorem ipsum is a dummy or placeholder text commonly used in graphic design, publishing, and web development to fill empty spaces in a layout that does not yet have content.",
    categories: [1, 2, 5],
  },
  {
    img: TestimonialImg08,
    clientImg: ClientImg08,
    name: "Danielle K.",
    company: "Forbes Inc.",
    content:
      "Lorem ipsum is a dummy or placeholder text commonly used in graphic design, publishing, and web development to fill empty spaces in a layout that does not yet have content.",
    categories: [1, 4],
  },
  {
    img: TestimonialImg09,
    clientImg: ClientImg09,
    name: "Mary P.",
    company: "Ray Ban",
    content:
      "Lorem ipsum is a dummy or placeholder text commonly used in graphic design, publishing, and web development to fill empty spaces in a layout that does not yet have content.",
    categories: [1, 2],
  },
];

export default function Testimonials() {
  const masonryContainer = useMasonry();
  const [category, setCategory] = useState<number>(1);

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6">
      <div className="border-t border-border/25 py-12 md:py-20">
        {/* Section header */}
        <div className="mx-auto max-w-3xl pb-12 text-center">
          <h2 className="animate-[var(--animate-gradient)] bg-gradient-to-r from-primary via-accent to-primary bg-[length:200%_auto] bg-clip-text pb-4 font-nacelle text-3xl font-semibold text-transparent md:text-4xl">
            Don't take our word for it
          </h2>
          <p className="text-lg text-muted-foreground">
            We provide tech-first solutions that empower decision-makers to
            build healthier and happier workspaces from anywhere in the world.
          </p>
        </div>

        <div>
          {/* Category buttons */}
          <div className="flex justify-center pb-12 max-md:hidden md:pb-16">
            <div className="relative inline-flex flex-wrap justify-center rounded-[1.25rem] bg-muted/40 p-1">
              {/* All button */}
              <button
                className={`flex h-8 flex-1 items-center gap-2.5 whitespace-nowrap rounded-full px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  category === 1
                    ? "relative bg-gradient-to-b from-background via-muted/60 to-background before:pointer-events-none before:absolute before:inset-0 before:rounded-[inherit] before:border before:border-transparent before:bg-gradient-to-b before:from-primary/0 before:to-primary/50 before:border-box before:[mask:linear-gradient(white,white)_padding-box,linear-gradient(white,white)]"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                aria-pressed={category === 1}
                onClick={() => setCategory(1)}
              >
                <svg
                  className={`fill-current ${
                    category === 1 ? "text-primary" : "text-muted-foreground"
                  }`}
                  xmlns="http://www.w3.org/2000/svg"
                  width={16}
                  height={16}
                >
                  <path d="M.062 10.003a1 1 0 0 1 1.947.455c-.019.08.01.152.078.19l5.83 3.333c.052.03.115.03.168 0l5.83-3.333a.163.163 0 0 0 .078-.188 1 1 0 0 1 1.947-.459 2.161 2.161 0 0 1-1.032 2.384l-5.83 3.331a2.168 2.168 0 0 1-2.154 0l-5.83-3.331a2.162 2.162 0 0 1-1.032-2.382Z" />
                  <path d="m7.854-7.981-5.83 3.332a.17.17 0 0 0 0 .295l5.828 3.33c.054.031.118.031.17.002l5.83-3.333a.17.17 0 0 0 0-.294L8.085 2.023a.172.172 0 0 0-.17-.001Z" />
                  <path d="M9.076.285l5.83 3.332c1.458.833 1.458 2.935 0 3.768l-5.83 3.333c-.667.38-1.485.38-2.153-.001l-5.83-3.332c-1.457-.833-1.457-2.935 0-3.767L6.925.285a2.173 2.173 0 0 1 2.15 0Z" />
                </svg>
                <span>All</span>
              </button>

              {/* Integrations button */}
              <button
                className={`flex h-8 flex-1 items-center gap-2.5 whitespace-nowrap rounded-full px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  category === 2
                    ? "relative bg-gradient-to-b from-background via-muted/60 to-background before:pointer-events-none before:absolute before:inset-0 before:rounded-[inherit] before:border before:border-transparent before:bg-gradient-to-b before:from-primary/0 before:to-primary/50 before:border-box before:[mask:linear-gradient(white,white)_padding-box,linear-gradient(white,white)]"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                aria-pressed={category === 2}
                onClick={() => setCategory(2)}
              >
                <svg
                  className={`fill-current ${
                    category === 2 ? "text-primary" : "text-muted-foreground"
                  }`}
                  xmlns="http://www.w3.org/2000/svg"
                  width={16}
                  height={16}
                >
                  <path d="M13.5 2H8V0H2v2h5.5a.5.5 0 0 1 .5.5V5H6v2h2v2H6v2h2v2.5a.5.5 0 0 1-.5.5H2v2h6v-2H3.5a.5.5 0 0 1-.5-.5V11h2V9H3V7h2V5H3V2.5a.5.5 0 0 1 .5-.5H8V0h6v2Z" />
                </svg>
                <span>Integrations</span>
              </button>

              {/* Customer Support button */}
              <button
                className={`flex h-8 flex-1 items-center gap-2.5 whitespace-nowrap rounded-full px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  category === 3
                    ? "relative bg-gradient-to-b from-background via-muted/60 to-background before:pointer-events-none before:absolute before:inset-0 before:rounded-[inherit] before:border before:border-transparent before:bg-gradient-to-b before:from-primary/0 before:to-primary/50 before:border-box before:[mask:linear-gradient(white,white)_padding-box,linear-gradient(white,white)]"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                aria-pressed={category === 3}
                onClick={() => setCategory(3)}
              >
                <svg
                  className={`fill-current ${
                    category === 3 ? "text-primary" : "text-muted-foreground"
                  }`}
                  xmlns="http://www.w3.org/2000/svg"
                  width={16}
                  height={16}
                >
                  <path d="M8 0C3.6 0 0 3.6 0 8s3.6 8 8 8 8-3.6 8-8-3.6-8-8-8Zm0 14c-3.3 0-6-2.7-6-6s2.7-6 6-6 6 2.7 6 6-2.7 6-6 6Z" />
                  <path d="M9 4H7v5h5V7H9V4Z" />
                </svg>
                <span>Customer Support</span>
              </button>

              {/* Development button */}
              <button
                className={`flex h-8 flex-1 items-center gap-2.5 whitespace-nowrap rounded-full px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  category === 4
                    ? "relative bg-gradient-to-b from-background via-muted/60 to-background before:pointer-events-none before:absolute before:inset-0 before:rounded-[inherit] before:border before:border-transparent before:bg-gradient-to-b before:from-primary/0 before:to-primary/50 before:border-box before:[mask:linear-gradient(white,white)_padding-box,linear-gradient(white,white)]"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                aria-pressed={category === 4}
                onClick={() => setCategory(4)}
              >
                <svg
                  className={`fill-current ${
                    category === 4 ? "text-primary" : "text-muted-foreground"
                  }`}
                  xmlns="http://www.w3.org/2000/svg"
                  width={16}
                  height={16}
                >
                  <path d="M15 9.3c-.1-.1-.1-.2-.2-.2L13.1 8l1.7-1.1c.1 0 .1-.1.2-.2.1-.2.1-.4 0-.6l-2-3.5c-.1-.2-.3-.3-.5-.3-.1 0-.2 0-.2.1L10.6 4 9 2.9c-.1-.1-.2-.1-.3-.1-.2 0-.4.1-.5.3l-2 3.5c-.1.2-.1.4 0 .6.1.1.1.2.2.2.2L8.1 8 6.4 9.1c-.1 0-.1.1-.2.2-.1.2-.1.4 0 .6l2 3.5c.1.2.3.3.5.3.1 0 .2 0 .2-.1L10.6 12l1.6 1.1c.1.1.2.1.3.1.2 0 .4-.1.5-.3l2-3.5c.1-.2.1-.4 0-.6ZM.1 15.4c.1.2.3.3.5.3.1 0 .2 0 .2-.1l1.7-1.1 1.6 1.1c.1.1.2.1.3.1.2 0 .4-.1.5-.3l2-3.5c.1-.2.1-.4 0-.6-.1-.1-.1-.2-.2-.2L5 10l1.7-1.1c.1 0 .1-.1.2-.2.1-.2.1-.4 0-.6l-2-3.5c-.1-.2-.3-.3-.5-.3-.1 0-.2 0-.2.1L2.5 5.6.9 4.5c-.1-.1-.2-.1-.3-.1-.2 0-.4.1-.5.3l-2 3.5c-.1.2-.1.4 0 .6.1.1.1.2.2.2L0 10l-1.7 1.1c-.1 0-.1.1-.2.2-.1.2-.1.4 0 .6l2 3.5Z" />
                </svg>
                <span>Development</span>
              </button>

              {/* Resources button */}
              <button
                className={`flex h-8 flex-1 items-center gap-2.5 whitespace-nowrap rounded-full px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  category === 5
                    ? "relative bg-gradient-to-b from-background via-muted/60 to-background before:pointer-events-none before:absolute before:inset-0 before:rounded-[inherit] before:border before:border-transparent before:bg-gradient-to-b before:from-primary/0 before:to-primary/50 before:border-box before:[mask:linear-gradient(white,white)_padding-box,linear-gradient(white,white)]"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                aria-pressed={category === 5}
                onClick={() => setCategory(5)}
              >
                <svg
                  className={`fill-current ${
                    category === 5 ? "text-primary" : "text-muted-foreground"
                  }`}
                  xmlns="http://www.w3.org/2000/svg"
                  width={16}
                  height={16}
                >
                  <path d="M7 14c-3.86 0-7-3.14-7-7s3.14-7 7-7 7 3.14 7 7-3.14 7-7 7ZM7 2C4.243 2 2 4.243 2 7s2.243 5 5 5 5-2.243 5-5-2.243-5-5-5Z" />
                  <path d="M15.707 14.293 13.314 11.9a8.019 8.019 0 0 1-1.414 1.414l2.393 2.393a.997.997 0 0 0 1.414 0 .999.999 0 0 0 0-1.414Z" />
                </svg>
                <span>Resources</span>
              </button>
            </div>
          </div>

          {/* Testimonials grid */}
          <div
            ref={masonryContainer}
            className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
          >
            {testimonials
              .filter((testimonial) =>
                testimonial.categories.includes(category)
              )
              .map((testimonial, index) => (
                <div
                  key={index}
                  className="relative rounded-2xl bg-muted/40 p-4 backdrop-blur"
                  data-aos="fade-up"
                >
                  <div className="mb-3 flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <Image
                        className="rounded-full"
                        src={testimonial.img}
                        width={48}
                        height={48}
                        alt={`Testimonial ${index + 1}`}
                      />
                      <div>
                        <div className="font-semibold text-foreground">
                          {testimonial.name}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {testimonial.company}
                        </div>
                      </div>
                    </div>
                    <Image
                      src={testimonial.clientImg}
                      width={100}
                      height={24}
                      alt={`${testimonial.company} logo`}
                      className="ml-4"
                    />
                  </div>
                  <p className="text-muted-foreground">{testimonial.content}</p>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}
