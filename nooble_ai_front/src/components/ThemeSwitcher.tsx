"use client";

import { useTheme } from "@/utils/useTheme";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Monitor, Moon, Sun, Grid, Laptop2 } from "lucide-react";

export function ThemeSwitcher() {
  const { theme, setTheme, mode, setMode } = useTheme();

  return (
    <div className="flex flex-col gap-3">
      {/* Info Header */}
      <div className="flex items-center gap-2">
        <div className="h-px flex-1 bg-gradient-to-r from-transparent to-primary/50" />
        <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-sm font-medium text-transparent">
          Customize Your Experience
        </span>
        <div className="h-px flex-1 bg-gradient-to-l from-transparent to-primary/50" />
      </div>

      {/* Theme Switcher Container */}
      <div className="relative overflow-hidden rounded-xl border bg-background/95 p-4 backdrop-blur-xl before:pointer-events-none before:absolute before:inset-0 before:rounded-[inherit] before:border before:border-transparent before:[background:linear-gradient(to_right,var(--color-primary),var(--color-accent),var(--color-primary))_border-box] before:[mask-composite:exclude_!important] before:[mask:linear-gradient(white_0_0)_padding-box,_linear-gradient(white_0_0)]">
        {/* Theme Controls */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
          {/* Theme Select */}
          <div className="flex-1">
            <Select
              value={theme}
              onValueChange={(value: typeof theme) => setTheme(value)}
            >
              <SelectTrigger className="w-full border-0 bg-background/50 backdrop-blur-sm">
                <SelectValue placeholder="Select theme" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="default">
                  <div className="flex items-center">
                    <Grid className="mr-2 h-4 w-4 text-primary" />
                    Default
                  </div>
                </SelectItem>
                <SelectItem value="ios">
                  <div className="flex items-center">
                    <Laptop2 className="mr-2 h-4 w-4 text-primary" />
                    iOS
                  </div>
                </SelectItem>
                <SelectItem value="minimal">
                  <div className="flex items-center">
                    <Monitor className="mr-2 h-4 w-4 text-primary" />
                    Minimal
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Mode Select */}
          <div className="flex-1">
            <Select
              value={mode}
              onValueChange={(value: typeof mode) => setMode(value)}
            >
              <SelectTrigger className="w-full border-0 bg-background/50 backdrop-blur-sm">
                <SelectValue placeholder="Select mode" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="light">
                  <div className="flex items-center">
                    <Sun className="mr-2 h-4 w-4 text-primary" />
                    Light
                  </div>
                </SelectItem>
                <SelectItem value="dark">
                  <div className="flex items-center">
                    <Moon className="mr-2 h-4 w-4 text-primary" />
                    Dark
                  </div>
                </SelectItem>
                <SelectItem value="system">
                  <div className="flex items-center">
                    <Monitor className="mr-2 h-4 w-4 text-primary" />
                    System
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>
    </div>
  );
}
