import { WorklistView } from "@/components/worklist";
import fixture from "../../public/integration-v1/worklist.json";
import { parseWorklist } from "@/lib/worklist";
export default function WorklistPage() { return <WorklistView initial={parseWorklist(JSON.stringify(fixture))} />; }
