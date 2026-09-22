import { redirect } from "next/navigation";

export default function LegacyProviderComplianceRedirect() {
  redirect("/provider/dashboard?attention_required=true");
}
