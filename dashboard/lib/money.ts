// Copied from agency-intake-kit dashboard/lib/money.ts at a54faee (formatMoney only).
// Money arrives as exact decimal text ("61.05", "-24.50", "0.000901"). This is the one place
// that formats it. It never becomes a float, so no cents can be lost.
const MONEY = /^(-?)(\d+)(?:\.(\d+))?$/;

function parts(text: string): [sign: string, whole: string, frac: string | undefined] {
  const match = MONEY.exec(text);
  if (!match) throw new Error(`Not a money amount: ${JSON.stringify(text)}`);
  return [match[1], match[2], match[3]];
}

/** "1234.50" becomes "$1,234.50". Keeps every decimal place the engine wrote. */
export function formatMoney(text: string): string {
  const [sign, whole, frac] = parts(text);
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${sign}$${grouped}${frac === undefined ? "" : `.${frac}`}`;
}
