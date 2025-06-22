"use client";

import { useState, useRef } from "react";
import type { StaticImageData } from "next/image";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import Image from "next/image";
import SecondaryIllustration from "~/public/images/secondary-illustration.svg";
import BoilerplateThumb from "~/public/images/boiler-plate-readme-background.jpeg";

interface ModalVideoProps {
  thumbWidth: number;
  thumbHeight: number;
  thumbAlt: string;
  video: string;
  videoWidth: number;
  videoHeight: number;
}

export default function ModalVideo({
  thumbWidth,
  thumbHeight,
  thumbAlt,
  video,
  videoWidth,
  videoHeight,
}: ModalVideoProps) {
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  return (
    <div className="relative">
      {/* Secondary illustration */}
      <div
        className="pointer-events-none absolute bottom-8 left-1/2 -z-10 -ml-28 -translate-x-1/2 translate-y-1/2"
        aria-hidden="true"
      >
        <Image
          className="md:max-w-none"
          src={SecondaryIllustration}
          width={1165}
          height={1012}
          alt="Secondary illustration"
        />
      </div>

      <Dialog.Root open={modalOpen} onOpenChange={setModalOpen}>
        <Dialog.Trigger asChild>
          <button
            className="group relative flex items-center justify-center rounded-2xl focus-visible:ring-2 focus-visible:ring-ring focus:outline-none"
            aria-label="Watch the video"
            data-aos="fade-up"
            data-aos-delay={200}
          >
            <figure className="relative overflow-hidden rounded-2xl before:absolute before:inset-0 before:-z-10 before:bg-gradient-to-br before:from-background before:via-primary/20 before:to-background">
              <Image
                className="opacity-50 grayscale"
                src={BoilerplateThumb}
                width={thumbWidth}
                height={thumbHeight}
                priority
                alt={thumbAlt}
              />
            </figure>
            {/* Play icon */}
            <span className="pointer-events-none absolute p-2.5 before:absolute before:inset-0 before:rounded-full before:bg-background before:duration-300 group-hover:before:scale-110">
              <span className="relative flex items-center gap-3">
                <svg
                  className="fill-primary"
                  xmlns="http://www.w3.org/2000/svg"
                  width={20}
                  height={20}
                >
                  <path
                    fill="url(#pla)"
                    fillRule="evenodd"
                    d="M10 20c5.523 0 10-4.477 10-10S15.523 0 10 0 0 4.477 0 10s4.477 10 10 10Zm3.5-10-5-3.5v7l5-3.5Z"
                    clipRule="evenodd"
                  />
                  <defs>
                    <linearGradient
                      id="pla"
                      x1={10}
                      x2={10}
                      y1={0}
                      y2={20}
                      gradientUnits="userSpaceOnUse"
                    >
                      <stop stopColor="hsl(var(--primary))" />
                      <stop
                        offset={1}
                        stopColor="hsl(var(--primary))"
                        stopOpacity=".72"
                      />
                    </linearGradient>
                  </defs>
                </svg>
                <span className="text-sm font-medium leading-tight text-muted-foreground">
                  Watch Demo
                  <span className="text-muted"> - </span>
                  3:47
                </span>
              </span>
            </span>
          </button>
        </Dialog.Trigger>

        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-background/70 backdrop-blur-sm transition-opacity duration-300 data-[state=closed]:opacity-0" />
          <Dialog.Content
            className="fixed inset-0 z-50 flex px-4 py-6 sm:px-6"
            onEscapeKeyDown={() => setModalOpen(false)}
            onPointerDownOutside={() => setModalOpen(false)}
          >
            <div className="mx-auto flex h-full max-w-6xl items-center">
              <div className="relative aspect-video max-h-full w-full overflow-hidden rounded-2xl bg-[hsl(var(--background))] shadow-lg">
                <Dialog.Title className="sr-only">Demo Video</Dialog.Title>
                <Dialog.Description className="sr-only">
                  A video demonstration of our product features
                </Dialog.Description>

                {/* Close button */}
                <Dialog.Close className="absolute right-4 top-4 z-50 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))] focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent">
                  <X className="h-4 w-4 text-[hsl(var(--foreground))]" />
                  <span className="sr-only">Close</span>
                </Dialog.Close>

                <video
                  ref={videoRef}
                  width={videoWidth}
                  height={videoHeight}
                  loop
                  controls
                >
                  <source src={video} type="video/mp4" />
                  Your browser does not support the video tag.
                </video>
              </div>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
