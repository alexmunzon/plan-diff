// Copied from agency-intake-kit dashboard/components/tiles.tsx at a54faee.
import { SeverityIcon, type Tone } from "@/components/severity-badge";
import { cn } from "@/lib/utils";

export const CARD = "panel";

interface TileProps {
  label: string;
  value: string;
  context?: string;
  tone?: Tone;
  /** Shown flat and gray when the run never reached this check. */
  muted?: boolean;
}

export function Tile({ label, value, context, tone, muted }: TileProps) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn(CARD, "kpi-card", muted && "kpi-muted")}
    >
      <p className="kpi-label">
        {tone && !muted && <SeverityIcon tone={tone} />}
        {label}
      </p>
      <p className={cn("kpi-value", muted && "muted")}>
        {value}
      </p>
      {context && <p className="kpi-context tabular-nums">{context}</p>}
    </div>
  );
}
