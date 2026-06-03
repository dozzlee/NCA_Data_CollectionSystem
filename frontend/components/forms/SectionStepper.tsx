"use client";

import { cn } from "@/lib/utils";
import { CheckCircle2, Circle, AlertCircle } from "lucide-react";

interface Section {
  section_code: string;
  title: string;
  required: number;
  provided: number;
  complete: boolean;
}

interface SectionStepperProps {
  sections: Section[];
  activeSection: string;
  onSelect: (code: string) => void;
  completionPct: number;
}

export function SectionStepper({ sections, activeSection, onSelect, completionPct }: SectionStepperProps) {
  return (
    <aside className="w-[240px] shrink-0 rounded-[16px] border border-[#e6e8ea] bg-white overflow-hidden"
      style={{ boxShadow: "0 2px 8px rgba(0,45,91,0.05)" }}>

      {/* Progress header */}
      <div className="px-4 py-4 border-b border-[#eceef0]">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[12px] font-semibold text-[#191c1e]">Form Progress</p>
          <p className="text-[12px] font-semibold text-[#0066cc] tabular-nums">{completionPct.toFixed(0)}%</p>
        </div>
        <div className="h-1.5 w-full rounded-full bg-[#eceef0] overflow-hidden">
          <div
            className="h-full rounded-full bg-[#0066cc] transition-all duration-500"
            style={{ width: `${completionPct}%` }}
          />
        </div>
      </div>

      {/* Section list */}
      <nav className="py-2 overflow-y-auto max-h-[calc(100vh-280px)]">
        {sections.map((section, i) => {
          const active = section.section_code === activeSection;
          const pct = section.required > 0 ? Math.round((section.provided / section.required) * 100) : 100;

          return (
            <button
              key={section.section_code}
              onClick={() => onSelect(section.section_code)}
              className={cn(
                "flex w-full items-start gap-3 px-4 py-3 text-left transition-colors",
                active
                  ? "bg-[#f2f4f6]"
                  : "hover:bg-[#f7f9fb]"
              )}
            >
              {/* Status icon */}
              <div className="mt-0.5 shrink-0">
                {section.complete ? (
                  <CheckCircle2 size={15} className="text-[#1f7a4d]" />
                ) : section.provided > 0 ? (
                  <AlertCircle size={15} className="text-[#ffd100]" />
                ) : (
                  <Circle size={15} className={active ? "text-[#0066cc]" : "text-[#c3c6d0]"} />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <p className={cn(
                  "text-[12px] font-medium leading-tight truncate",
                  active ? "text-[#191c1e]" : "text-[#43474f]"
                )}>
                  {i + 1}. {section.title}
                </p>
                {section.required > 0 && (
                  <p className="text-[10px] text-[#737780] mt-0.5 tabular-nums">
                    {section.provided}/{section.required} fields
                  </p>
                )}
              </div>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
