import { redirect } from "next/navigation";

// /provider/submissions with no ID redirects to the dashboard (submission list)
export default function ProviderSubmissionsIndexPage() {
  redirect("/provider/dashboard");
}
