"use client";

import Link from "next/link";

export default function RunError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <section role="alert" className="space-y-3">
      <h1 className="text-2xl font-semibold">This run could not be loaded</h1>
      <p>No results are shown because the run could not be read. Try again or return to an overview.</p>
      <button className="rounded border px-3 py-2" onClick={retry}>Try again</button>
      <p className="flex flex-wrap gap-4">
        <Link className="underline" href="/">Synthetic demo</Link>
        <Link className="underline" href="/texas">Public Texas run</Link>
      </p>
    </section>
  );
}
