/** Joins class names, skipping empty ones. Stands in for aik's `cn` package (one less dependency). */
export function cn(...names: (string | false | null | undefined)[]): string {
  return names.filter(Boolean).join(" ");
}
