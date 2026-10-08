/** Display wording only. The recorded explanation, including its thresholds, stays intact. */
export function ReviewReason({ reason }: { reason: string }) {
  const display = reason.replace(" cannot decide shop again:", " change flag needs review:");
  return (
    <>
      <span>{display.charAt(0).toUpperCase() + display.slice(1)}</span>
      {display !== reason && (
        <details className="technical-details">
          <summary>Original recorded reason</summary>
          <p>{reason}</p>
        </details>
      )}
    </>
  );
}
