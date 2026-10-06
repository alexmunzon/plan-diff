import { ArrowDown, ArrowUp, CircleHelp, Equal, Minus, Plus, type LucideIcon } from "lucide-react";

import { SeverityIcon } from "@/components/severity-badge";
import { carrierPageUrl, citationText, directionText, lowConfidence, valueText, type DisplayDirection } from "@/lib/compare";
import type { Citation, ExtractedField, RunManifest } from "@/lib/types";

// Small pieces shared by the Plan comparison and Changes pages.

export const TABLE = "w-full border-collapse text-left text-sm tabular-nums";
export const TH = "border-b border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 dark:border-slate-800 dark:text-slate-400";
export const TD = "border-b border-slate-100 px-3 py-2 align-top dark:border-slate-800";

const ICONS: Record<DisplayDirection, LucideIcon> = {
  up: ArrowUp,
  down: ArrowDown,
  same: Equal,
  added: Plus,
  removed: Minus,
  not_comparable: CircleHelp,
  needs_review: CircleHelp,
};

/** Direction as a word plus an icon. The word carries the meaning; the icon only helps scanning. */
export function DirectionText({ direction }: { direction: DisplayDirection }) {
  const Icon = ICONS[direction];
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap">
      <Icon aria-hidden className="size-3.5 shrink-0 text-slate-500 dark:text-slate-400" />
      {directionText(direction)}
    </span>
  );
}

/** Document and page as text; a link only to the carrier's own copy when the run names one. */
export function CitationText({ citation, manifest }: { citation: Citation; manifest: RunManifest }) {
  const text = citationText(citation);
  const href = carrierPageUrl(manifest, citation);
  return (
    <span className="text-xs text-slate-600 dark:text-slate-400">
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer" className="underline">
          {text}
        </a>
      ) : (
        text
      )}
    </span>
  );
}

/** One year's value, its citation, and a warning when it was read with low confidence. */
export function ValueCell({ field, manifest, reviewWarning }: { field: ExtractedField | null; manifest: RunManifest; reviewWarning?: string | null }) {
  const warning = reviewWarning ?? lowConfidence(field, manifest.config.confidence_floor);
  return (
    <div className="space-y-0.5">
      <p className={field === null ? "text-slate-600 dark:text-slate-400" : undefined}>{valueText(field)}</p>
      {field && (
        <p>
          <CitationText citation={field.citation} manifest={manifest} />
        </p>
      )}
      {warning && field?.citation.text && <p className="text-xs">Source text: {field.citation.text}</p>}
      {warning && (
        <p className="inline-flex items-center gap-1 text-xs">
          <SeverityIcon tone="warning" className="size-3.5" />
          {warning}
        </p>
      )}
    </div>
  );
}
