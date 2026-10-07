// Copied from agency-intake-kit dashboard/components/severity-badge.tsx at a54faee.
import { CircleAlert, CircleCheck, Info, OctagonX, TriangleAlert, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

// Fixed meanings. Color is never the only signal: every tone has an icon and a word.
export type Tone = "blocker" | "error" | "warning" | "info" | "pass";

export const TONES: Record<Tone, { label: string; icon: LucideIcon; color: string }> = {
  blocker: { label: "Blocker", icon: OctagonX, color: "status-error" },
  error: { label: "Error", icon: TriangleAlert, color: "status-error" },
  warning: { label: "Warning", icon: CircleAlert, color: "status-warning" },
  info: { label: "Info", icon: Info, color: "status-info" },
  pass: { label: "Pass", icon: CircleCheck, color: "status-pass" },
};

export function SeverityIcon({ tone, className }: { tone: Tone; className?: string }) {
  const Icon = TONES[tone].icon;
  return <Icon aria-hidden className={cn("size-4 shrink-0", TONES[tone].color, className)} />;
}

export function SeverityBadge({ tone, label }: { tone: Tone; label?: string }) {
  return (
    <span className="severity-badge">
      <SeverityIcon tone={tone} className="size-3.5" />
      {label ?? TONES[tone].label}
    </span>
  );
}
