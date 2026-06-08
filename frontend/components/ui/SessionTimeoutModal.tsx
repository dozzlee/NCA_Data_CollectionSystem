"use client";

interface SessionTimeoutModalProps {
  onStaySignedIn: () => void;
  onSignOut: () => void;
}

export function SessionTimeoutModal({ onStaySignedIn, onSignOut }: SessionTimeoutModalProps) {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div
        className="w-full max-w-sm rounded-[16px] bg-white p-8 shadow-[0_16px_42px_rgba(0,45,91,0.18)]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="session-timeout-title"
      >
        <div className="mb-1 flex h-12 w-12 items-center justify-center rounded-full bg-[#fff3bf]">
          <span className="text-[20px]" aria-hidden>⏱</span>
        </div>
        <h2 id="session-timeout-title" className="mt-4 text-[20px] font-semibold text-[#191c1e]">
          Your session is about to expire
        </h2>
        <p className="mt-2 text-[14px] text-[#43474f] leading-relaxed">
          You will be signed out in 2 minutes due to inactivity. Stay signed in to continue working.
        </p>
        <div className="mt-6 flex flex-col gap-3">
          <button
            onClick={onStaySignedIn}
            className="w-full rounded-[8px] bg-[#001836] px-4 py-2.5 text-[14px] font-semibold text-white transition-colors hover:bg-[#002d5b] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/40"
          >
            Stay signed in
          </button>
          <button
            onClick={onSignOut}
            className="w-full rounded-[8px] border border-[#c3c6d0] px-4 py-2.5 text-[14px] font-medium text-[#43474f] transition-colors hover:bg-[#f2f4f6] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
