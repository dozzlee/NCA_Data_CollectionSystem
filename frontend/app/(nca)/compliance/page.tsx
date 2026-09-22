import { redirect } from "next/navigation";

export default function LegacyComplianceRedirect() {
  redirect("/submissions?attention_required=true");
}
