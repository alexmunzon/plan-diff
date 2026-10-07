import schema from "./worklist-schema.json";
import type { PlanDiff } from "./types";

type Schema = { $ref?: string; anyOf?: Schema[]; oneOf?: Schema[]; type?: string; const?: unknown; enum?: unknown[]; required?: string[]; properties?: Record<string, Schema>; additionalProperties?: boolean; items?: Schema; minimum?: number; maximum?: number; minLength?: number; maxLength?: number; pattern?: string };
export interface WorkItem {
  item_id: string; client_id: string; policy_id: string | null; identity_state: string;
  state: "ready_for_review" | "needs_review" | "unsupported"; review_state: "needs_review"; reasons: string[];
  coverage: null | { plan_id: string | null; plan_year: number | null; county: string | null; provenance: { source_file: string; row_number: number; artifact: string; artifact_row: number } };
  plan_artifact: string | null; plan_diff: PlanDiff | null;
}
export interface Worklist { run_id: string; agency_id: string; items: WorkItem[]; issues: { code: string; artifact: string | null; artifact_row: number | null }[]; packet_sha256: string }
function valid(value: unknown, rule: Schema): boolean {
  if (rule.$ref) return valid(value, (schema.$defs as Record<string, Schema>)[rule.$ref.split("/").pop()!] );
  if (rule.anyOf && !rule.anyOf.some(r => valid(value, r))) return false;
  if (rule.oneOf && rule.oneOf.filter(r => valid(value, r)).length !== 1) return false;
  if (Object.hasOwn(rule, "const") && value !== rule.const) return false;
  if (rule.enum && !rule.enum.includes(value)) return false;
  if (rule.type === "null") return value === null;
  if (rule.type === "array") return Array.isArray(value) && (!rule.items || value.every(v => valid(v, rule.items!)));
  if (rule.type === "object") {
    if (!value || typeof value !== "object" || Array.isArray(value)) return false;
    const obj = value as Record<string, unknown>, props = rule.properties ?? {};
    return !(rule.required ?? []).some(k => !Object.hasOwn(obj, k)) && Object.entries(obj).every(([k,v]) => Object.hasOwn(props, k) ? valid(v, props[k]) : rule.additionalProperties !== false);
  }
  if (rule.type === "string") return typeof value === "string" && value.length >= (rule.minLength ?? 0) && value.length <= (rule.maxLength ?? Infinity) && (!rule.pattern || new RegExp(rule.pattern).test(value));
  if (rule.type === "number" || rule.type === "integer") return typeof value === "number" && Number.isFinite(value) && (rule.type !== "integer" || Number.isInteger(value)) && value >= (rule.minimum ?? -Infinity) && value <= (rule.maximum ?? Infinity);
  if (rule.type === "boolean") return typeof value === "boolean";
  return true;
}
export function parseWorklist(text: string): Worklist {
  if (new TextEncoder().encode(text).length > 2_000_000) throw new Error("Worklist exceeds 2 MB limit");
  const value = JSON.parse(text);
  if (!valid(value, schema as Schema) || value.schema_version !== "1.0.0" || value.data_kind !== "synthetic" || value.purpose !== "synthetic review worklist; no suitability recommendation") throw new Error("Invalid synthetic worklist contract");
  if (value.items.length > 1000 || new Set(value.items.map((i: WorkItem) => i.item_id)).size !== value.items.length || value.items.some((i: WorkItem) => i.review_state !== "needs_review" || (i.plan_diff !== null && !Array.isArray(i.plan_diff.evidence)))) throw new Error("Invalid item inventory or review state");
  const pins = new Set(value.plan_artifacts.map((a: { path: string }) => a.path));
  if (pins.size !== value.plan_artifacts.length) throw new Error("Duplicate artifact pins");
  function checkMoney(node: unknown): void {
    if (!node || typeof node !== "object") return;
    for (const [key, v] of Object.entries(node)) {
      if ((key === "amount" || key === "percent") && (typeof v !== "string" || !/^\d+(\.\d{1,2})?$/.test(v))) throw new Error("Invalid decimal value");
      if (key === "percent" && typeof v === "string" && Number(v) > 100) throw new Error("Percent exceeds 100");
      if (key === "amount" && typeof v === "string" && v.replace(/^0+/, "").replace(".", "").length > 12) throw new Error("Amount exceeds precision");
      checkMoney(v);
    }
  }
  checkMoney(value);
  for (const i of value.items as WorkItem[]) {
    if (i.coverage && (i.coverage as unknown as { agency_id: string }).agency_id !== value.agency_id && !i.reasons.includes("WRONG_AGENCY")) throw new Error("Coverage agency mismatch without review reason");
    if (i.plan_diff && i.coverage && (i.coverage.plan_id !== i.plan_diff.old_plan_id || i.coverage.plan_year !== i.plan_diff.old_year)) throw new Error("Coverage comparison mismatch");
    if (i.coverage && (i.coverage as unknown as { client_id: string }).client_id !== i.client_id) throw new Error("Coverage identity mismatch");
    if (i.coverage && (i.coverage as unknown as { policy_id: string }).policy_id !== i.policy_id) throw new Error("Coverage policy mismatch");
    if (i.state === "ready_for_review" && (i.identity_state !== "resolved" || i.reasons.length || !i.coverage || !i.plan_diff)) throw new Error("Unresolved item cannot be ready for review");
    if (i.reasons.includes("UNSUPPORTED_LINE_OF_BUSINESS_OR_PLAN") && i.state !== "unsupported") throw new Error("Unsupported item state mismatch");
    if (i.plan_diff) validateDiff(i.plan_diff);
    if (i.plan_diff && (i.plan_diff.new_year !== i.plan_diff.old_year + 1 || !i.plan_artifact || !pins.has(i.plan_artifact))) throw new Error("Unbound plan comparison");
  }
  return value as Worklist;
}

// JSON Schema cannot express the engine's cross-field model validators.
function validateDiff(d: PlanDiff): void {
  const fail = () => { throw new Error("Inconsistent plan comparison"); };
  const review = d.review ?? [];
  if (d.shop_again === false && review.some(r => r.kind === "shop_again_uncertain" && r.severity === "high")) fail();
  if (d.shop_again === null && (!review.some(r => r.severity === "high") || d.reasons.length)) fail();
  if (d.crosswalk_status === null) {
    if (d.shop_again !== null || d.changes.length || d.old_plan_id === null || d.new_plan_id !== null) fail();
  } else {
    if ((d.old_plan_id !== null) !== (d.crosswalk_status !== "new")) fail();
    if ((d.new_plan_id !== null) !== (d.crosswalk_status !== "terminated")) fail();
    if (d.shop_again !== null && d.shop_again !== Boolean(d.reasons.length)) fail();
  }
  const categories: Record<string,string> = {monthly_premium:"premium", medical_deductible:"deductible", moop_in_network:"moop", drug_deductible:"drugs", drug_tier_1:"drugs", drug_tier_2:"drugs", drug_tier_3:"drugs", dental_allowance:"allowances", otc_allowance:"allowances"};
  for (const c of d.changes) {
    if (c.category !== (categories[c.field] ?? "copays")) fail();
    if ([c.old,c.new].some(v=>v !== null && v.name !== c.field)) fail();
    if (c.old === null && c.new === null) fail();
    if ((c.old === null || c.new === null) && c.direction !== "not_comparable") fail();
    if (c.direction === "added" && c.old?.value.kind !== "not_covered") fail();
    if (c.direction === "removed" && c.new?.value.kind !== "not_covered") fail();
  }
}
