import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import path from "node:path";
import fixture from "../../../fixtures/integration-v1/worklist.json";
import { WorklistView } from "../worklist";
import { parseWorklist } from "@/lib/worklist";
it("filters without losing totals and preserves valid state after rejected import",async()=>{
 render(<WorklistView initial={parseWorklist(JSON.stringify(fixture))}/>);
 fireEvent.change(screen.getByLabelText("Status"),{target:{value:"unsupported"}});
 expect(screen.getByRole("status")).toHaveTextContent("Showing 4 of 10");
 fireEvent.change(screen.getByLabelText(/Import synthetic/),{target:{files:[{size:2,text:async()=>"{}"}]}});
 await waitFor(()=>expect(screen.getByRole("alert")).toHaveTextContent("unchanged"));
 expect(screen.getByRole("status")).toHaveTextContent("Showing 4 of 10");
});

it("provides concise accessible names for import, status and search controls",()=>{
 render(<WorklistView initial={parseWorklist(JSON.stringify(fixture))}/>);
 expect(screen.getByLabelText("Import synthetic worklist JSON",{exact:true})).toHaveAttribute("type","file");
 expect(screen.getByRole("combobox",{name:/^Status$/})).toBeInTheDocument();
 expect(screen.getByRole("textbox",{name:/^Find client, policy or reason$/})).toBeInTheDocument();
});

it("keeps worklist controls visible in both themes",async()=>{
 const css=await readFile(path.join(process.cwd(),"app/globals.css"),"utf8");
 expect(css).toMatch(/\.worklist-controls input, \.worklist-controls select [{][^}]*border: 1px solid var\(--border\);[^}]*background: var\(--paper\);[^}]*color: var\(--ink\);/);
 render(<WorklistView initial={parseWorklist(JSON.stringify(fixture))}/>);
 expect(screen.getByRole("combobox",{name:/^Status$/}).closest(".worklist-controls")).not.toBeNull();
});
