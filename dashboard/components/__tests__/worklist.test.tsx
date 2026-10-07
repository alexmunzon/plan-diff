import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it } from "vitest";
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
