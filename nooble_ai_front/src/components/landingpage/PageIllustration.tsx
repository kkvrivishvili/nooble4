import Image from "next/image";
import Illustration from "~/public/images/page-illustration.svg";
import BlurredShapeGray from "~/public/images/blurred-shape-gray.svg";
import BlurredShape from "~/public/images/blurred-shape.svg";

export default function PageIllustration({
  multiple = false,
}: {
  multiple?: boolean;
}) {
  return (
    <>
      <div
        className="pointer-events-none absolute left-1/2 top-0 -z-10 -translate-x-1/4 opacity-75 dark:opacity-50"
        aria-hidden="true"
      >
        <Image
          className="max-w-none mix-blend-multiply dark:mix-blend-lighten"
          src={Illustration}
          width={846}
          height={594}
          alt="Page illustration"
          priority
        />
      </div>
      {multiple && (
        <>
          <div
            className="pointer-events-none absolute left-1/2 top-[400px] -z-10 -mt-20 -translate-x-full opacity-40 dark:opacity-30"
            aria-hidden="true"
          >
            <Image
              className="max-w-none mix-blend-multiply dark:mix-blend-lighten"
              src={BlurredShapeGray}
              width={760}
              height={668}
              alt="Blurred shape"
            />
          </div>
          <div
            className="pointer-events-none absolute left-1/2 top-[440px] -z-10 -translate-x-1/3 opacity-60 dark:opacity-40"
            aria-hidden="true"
          >
            <Image
              className="max-w-none mix-blend-multiply dark:mix-blend-lighten bg-gradient-to-b from-primary/20 to-background"
              src={BlurredShape}
              width={760}
              height={668}
              alt="Blurred shape"
            />
          </div>
        </>
      )}
    </>
  );
}
