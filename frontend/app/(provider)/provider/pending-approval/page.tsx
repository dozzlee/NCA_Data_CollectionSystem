import { redirect } from "next/navigation";

export default function PendingApprovalCompatibilityPage() {
  redirect("/provider/forms?provider_status=AWAITING_APPROVAL");
}
