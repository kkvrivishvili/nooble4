'use client';

import { HTMLAttributes, forwardRef } from 'react';
import { cn } from '@/utils/cn';

export const PageLoader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "fixed inset-0 z-50",
          "flex items-center justify-center",
          "bg-background/60 backdrop-blur-[2px]",
          "transition-all duration-300 ease-in-out",
          className
        )}
        {...props}
      >
        <svg
          viewBox="0 0 32 22"
          xmlns="http://www.w3.org/2000/svg"
          className={cn(
            "w-16 h-16",
            "[animation:spin_3s_ease-in-out_infinite]",
            "opacity-90 transition-opacity duration-200",
            "drop-shadow-lg"
          )}
          fill="currentColor"
        >
          <defs>
            <mask id="a">
              <rect width="100%" height="100%" fill="#fff" />
              <path d="M11.8 13.12a3 3 0 0 1 0-4.24l7.08-7.07a3 3 0 0 1 4.24 0l7.07 7.07a3 3 0 0 1 0 4.24l-7.07 7.07a3 3 0 0 1-4.24 0l-7.07-7.07Z">
                <animateTransform
                  attributeName="transform"
                  attributeType="XML"
                  type="rotate"
                  repeatCount="indefinite"
                  calcMode="spline"
                  keyTimes="0;1"
                  dur="5s"
                  keySplines="0 0 0.1 1"
                  from="0 21 11"
                  to="-360 21 11"
                />
              </path>
            </mask>
            <mask id="b">
              <rect width="100%" height="100%" fill="#fff" />
              <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M1.8 8.88a3 3 0 0 0 0 4.24l7.08 7.07a3 3 0 0 0 4.24 0l7.07-7.07a3 3 0 0 0 0-4.24L13.12 1.8a3 3 0 0 0-4.24 0L1.8 8.88Zm.71.7a2 2 0 0 0 0 2.83L9.6 19.5a2 2 0 0 0 2.82 0l7.08-7.08a2 2 0 0 0 0-2.82l-7.1-7.1a2 2 0 0 0-2.82 0L2.5 9.6Z"
              >
                <animateTransform
                  attributeName="transform"
                  attributeType="XML"
                  type="rotate"
                  repeatCount="indefinite"
                  calcMode="spline"
                  keyTimes="0;1"
                  dur="5s"
                  keySplines="0 0 0.1 1"
                  from="0 11 11"
                  to="720 11 11"
                />
              </path>
            </mask>
          </defs>
          <g mask="url(#a)">
            <path
              fillRule="evenodd"
              clipRule="evenodd"
              d="M1.8 8.88a3 3 0 0 0 0 4.24l7.08 7.07a3 3 0 0 0 4.24 0l7.07-7.07a3 3 0 0 0 0-4.24L13.12 1.8a3 3 0 0 0-4.24 0L1.8 8.88Zm.71.7a2 2 0 0 0 0 2.83L9.6 19.5a2 2 0 0 0 2.82 0l7.08-7.08a2 2 0 0 0 0-2.82l-7.1-7.1a2 2 0 0 0-2.82 0L2.5 9.6Z"
            >
              <animateTransform
                attributeName="transform"
                attributeType="XML"
                type="rotate"
                repeatCount="indefinite"
                calcMode="spline"
                keyTimes="0;1"
                dur="5s"
                keySplines="0 0 0.1 1"
                from="0 11 11"
                to="720 11 11"
              />
            </path>
          </g>
          <g mask="url(#b)">
            <path d="M11.8 13.12a3 3 0 0 1 0-4.24l7.08-7.07a3 3 0 0 1 4.24 0l7.07 7.07a3 3 0 0 1 0 4.24l-7.07 7.07a3 3 0 0 1-4.24 0l-7.07-7.07Z">
              <animateTransform
                attributeName="transform"
                attributeType="XML"
                type="rotate"
                repeatCount="indefinite"
                calcMode="spline"
                keyTimes="0;1"
                dur="5s"
                keySplines="0 0 0.1 1"
                from="0 21 11"
                to="-360 21 11"
              />
            </path>
          </g>
        </svg>
      </div>
    );
  }
);

PageLoader.displayName = 'PageLoader';
