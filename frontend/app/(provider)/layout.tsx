import { ProviderTopBar } from "@/components/layout/ProviderTopBar";

export default function ProviderLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-[#f7f9fb]">
      <ProviderTopBar />
      <main className="flex-1 mx-auto w-full max-w-[1200px] px-6 py-8">
        {children}
      </main>
    </div>
  );
}
