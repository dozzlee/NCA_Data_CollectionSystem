import { ProviderTopBar } from "@/components/layout/ProviderTopBar";
import { RoleRouteGuard } from "@/components/auth/RoleRouteGuard";

export default function ProviderLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleRouteGuard area="PROVIDER">
      <div className="workspace-background flex min-h-screen flex-col">
        <ProviderTopBar />
        <main className="flex-1 mx-auto w-full max-w-[1200px] px-6 py-8">
          {children}
        </main>
      </div>
    </RoleRouteGuard>
  );
}
