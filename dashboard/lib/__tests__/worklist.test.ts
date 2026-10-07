import { describe, it, expect } from "vitest";
import fixture from "../../../fixtures/integration-v1/worklist.json";
import { parseWorklist } from "../worklist";
describe("worklist import",()=>{
 it("keeps every unresolved and unsupported item",()=>{const w=parseWorklist(JSON.stringify(fixture)); expect(w.items).toHaveLength(10); expect(w.items.filter(i=>i.state==="unsupported")).toHaveLength(4);});
 it.each(["public","private"])("refuses %s",kind=>{expect(()=>parseWorklist(JSON.stringify({...fixture,data_kind:kind}))).toThrow();});
 it("rejects missing citations and duplicate item IDs",()=>{const f=structuredClone(fixture); f.items[1].item_id=f.items[0].item_id;expect(()=>parseWorklist(JSON.stringify(f))).toThrow();const g=JSON.parse(JSON.stringify(fixture));delete g.items.find((i:{plan_diff:unknown})=>i.plan_diff).plan_diff.changes[0].old.citation;expect(()=>parseWorklist(JSON.stringify(g))).toThrow();});
 it("rejects absent evidence collections",()=>{const f=JSON.parse(JSON.stringify(fixture));delete f.items.find((i:{plan_diff:unknown})=>i.plan_diff).plan_diff.evidence;expect(()=>parseWorklist(JSON.stringify(f))).toThrow();});
 it("rejects approval state",()=>{const f=JSON.parse(JSON.stringify(fixture));f.items[0].review_state="approved";expect(()=>parseWorklist(JSON.stringify(f))).toThrow();});
});

it.each(["years", "amount", "client", "state", "artifact"])("rejects semantic mismatch %s", key => {
 const f=JSON.parse(JSON.stringify(fixture));
 const item=f.items.find((i:{plan_diff:unknown})=>i.plan_diff);
 if(key==="years")item.plan_diff.new_year=2030;
 if(key==="amount")item.plan_diff.changes[0].old.value.amount="-99";
 if(key==="client")item.coverage.client_id="wrong-client";
 if(key==="state")f.items.find((i:{state:string})=>i.state==="unsupported").state="ready_for_review";
 if(key==="artifact")item.plan_artifact="not-pinned.json";
 expect(()=>parseWorklist(JSON.stringify(f))).toThrow();
});

it.each(["percent", "precision", "category", "field", "absent", "added", "removed", "crosswalk", "flag"])("rejects engine invariant violation %s", key => {
 const f=JSON.parse(JSON.stringify(fixture)), d=f.items.find((i:{plan_diff:unknown})=>i.plan_diff).plan_diff, c=d.changes[0];
 if(key==="percent")c.old.value={kind:"coinsurance",percent:"101"};
 if(key==="precision")c.old.value.amount="999999999999999";
 if(key==="category")c.category="copays";
 if(key==="field")c.old.name="pcp_copay";
 if(key==="absent")c.old=null;
 if(key==="added")c.direction="added";
 if(key==="removed")c.direction="removed";
 if(key==="crosswalk")d.old_plan_id=null;
 if(key==="flag")d.shop_again=false;
 expect(()=>parseWorklist(JSON.stringify(f))).toThrow();
});

it.each(["constructor", "__proto__", "toString"])("rejects unknown inherited-name key %s at every object depth", key => {
 const f=JSON.parse(JSON.stringify(fixture));
 Object.defineProperty(f, key, {value: {}, enumerable: true});
 expect(()=>parseWorklist(JSON.stringify(f))).toThrow();
 const nested=JSON.parse(JSON.stringify(fixture));
 Object.defineProperty(nested.items[0], key, {value: {}, enumerable: true});
 expect(()=>parseWorklist(JSON.stringify(nested))).toThrow();
});
