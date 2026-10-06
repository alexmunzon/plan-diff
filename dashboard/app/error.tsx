"use client";

import Link from "next/link";

export default function RunError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <section role="alert" className="panel recovery-panel space-y-4">
      <h1 className="page-title">This run could not be loaded</h1>
      <p>No results are shown because the run could not be read. Try again or return to an overview.</p>
      <button className="action-link action-primary" onClick={retry}>Try again</button>
      <p className="flex flex-wrap gap-4">
        <Link className="action-link" href="/">Synthetic demo</Link>
        <Link className="action-link" href="/texas">Public Texas run</Link>
      </p>
    </section>
  );
}
