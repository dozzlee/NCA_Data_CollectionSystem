"use client";

import { ArrowDownRight, ArrowUpRight, Gauge, Medal, Sparkles } from "lucide-react";
import { IndustryChart } from "@/lib/industry-dashboard/types";
import {
  formatValue,
  getHeadlineMetric,
  percentChange,
} from "@/lib/industry-dashboard/analytics";
import { cn } from "@/lib/utils";

type SummaryProps = {
  charts: IndustryChart[];
  rangeEnd: string;
  operator: string;
  operatorNames: string[];
};

export function InsightStrip({
  charts,
  rangeEnd,
  operator,
  operatorNames,
}: SummaryProps) {
  const metrics = charts
    .map((chart) => {
      const metric = getHeadlineMetric(chart, rangeEnd, operator, operatorNames);
      return {
        chart,
        metric,
        growth: percentChange(metric.value, metric.yearAgo),
      };
    })
    .filter((item) => item.metric.value !== null);
  const growth = metrics
    .filter((item) => item.growth !== null)
    .sort((a, b) => (b.growth ?? -Infinity) - (a.growth ?? -Infinity))[0];
  const shareChart = charts.find((chart) => chart.shareSeries.length > 1);
  const shareValues =
    shareChart?.shareSeries
      .map((series) => ({
        name: series.name,
        value:
          series.values.find((point) => point.period === rangeEnd)?.value ?? null,
      }))
      .filter((item): item is { name: string; value: number } => item.value !== null)
      .sort((a, b) => b.value - a.value) ?? [];
  const leader = shareValues[0];
  const signal = metrics.find((item) =>
    /usage per subscription|penetration rate|minutes of use|sms per subscription/i.test(
      item.chart.title
    )
  );
  const currentCount = metrics.length;
  const insights = [
    growth
      ? {
          icon: ArrowUpRight,
          label: "Strongest annual movement",
          value: `${Math.abs(growth.growth ?? 0).toFixed(1)}%`,
          detail: `${growth.chart.title} ${
            (growth.growth ?? 0) >= 0 ? "increased" : "decreased"
          } year on year.`,
          tone: "green",
        }
      : null,
    leader && shareChart
      ? {
          icon: Medal,
          label: "Latest market leader",
          value: leader.name,
          detail: `${leader.value.toFixed(1)}% in ${shareChart.title.toLowerCase()}.`,
          tone: "violet",
        }
      : null,
    signal
      ? {
          icon: Gauge,
          label: "Latest intensity signal",
          value: formatValue(signal.metric.value, signal.chart.unit, { compact: true }),
          detail: `${signal.chart.title} at ${rangeEnd}.`,
          tone: "blue",
        }
      : {
          icon: Sparkles,
          label: "Current-period coverage",
          value: `${currentCount}/${charts.length}`,
          detail: "Indicators with a valid value in the selected period.",
          tone: "blue",
        },
  ].filter(
    (
      item
    ): item is {
      icon: typeof ArrowUpRight;
      label: string;
      value: string;
      detail: string;
      tone: string;
    } => Boolean(item)
  );

  if (!insights.length) return null;
  return (
    <section
      className="grid gap-3 lg:grid-cols-3"
      aria-label="Deterministic dashboard insights"
    >
      {insights.map((item) => {
        const Icon = item.icon;
        return (
          <article
            key={item.label}
            className="flex min-w-0 items-start gap-3 rounded-[15px] border border-[#e0e6eb] bg-white p-4 shadow-[0_6px_18px_rgba(0,45,91,0.035)]"
          >
            <span
              className={cn(
                "flex h-10 w-10 shrink-0 items-center justify-center rounded-full",
                item.tone === "green"
                  ? "bg-[#e3f7ef] text-[#148059]"
                  : item.tone === "violet"
                    ? "bg-[#f1eafb] text-[#7b3fc6]"
                    : "bg-[#e9f3ff] text-[#0a66c2]"
              )}
            >
              <Icon size={18} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="text-[9px] font-semibold uppercase tracking-[0.07em] text-[#7b8691]">
                {item.label}
              </p>
              <p className="mt-1 truncate text-[18px] font-semibold tracking-[-0.025em] text-[#1e2a35]">
                {item.value}
              </p>
              <p className="mt-1 text-[10px] leading-4 text-[#697580]">{item.detail}</p>
            </div>
          </article>
        );
      })}
    </section>
  );
}

export function MetricSnapshotTable({
  charts,
  rangeEnd,
  operator,
  operatorNames,
}: SummaryProps) {
  const rows = charts.map((chart) => {
    const metric = getHeadlineMetric(chart, rangeEnd, operator, operatorNames);
    const change = percentChange(metric.value, metric.yearAgo);
    return { chart, metric, change };
  });
  if (!rows.length) return null;
  return (
    <section className="overflow-hidden rounded-[17px] border border-[#dfe5eb] bg-white shadow-[0_7px_22px_rgba(0,45,91,0.04)]">
      <header className="flex items-end justify-between gap-4 border-b border-[#e8edf1] px-4 py-4 sm:px-5">
        <div>
          <p className="text-[9px] font-semibold uppercase tracking-[0.08em] text-[#0a66c2]">
            Detailed data
          </p>
          <h2 className="mt-1 text-[15px] font-semibold text-[#25313c]">
            Latest indicator snapshot
          </h2>
        </div>
        <p className="text-[9px] text-[#82909b]">{rangeEnd}</p>
      </header>
      <div className="hidden overflow-x-auto sm:block">
        <table className="min-w-full border-collapse text-left text-[10px]">
          <caption className="sr-only">Latest visible indicator values</caption>
          <thead className="bg-[#f7f9fb] text-[#66727d]">
            <tr>
              <th scope="col" className="px-5 py-2.5 font-semibold">Indicator</th>
              <th scope="col" className="px-4 py-2.5 text-right font-semibold">Value</th>
              <th scope="col" className="px-4 py-2.5 text-right font-semibold">YoY</th>
              <th scope="col" className="px-4 py-2.5 font-semibold">Source sheet</th>
              <th scope="col" className="px-5 py-2.5 font-semibold">Provenance</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ chart, metric, change }) => (
              <tr key={chart.id} className="border-t border-[#edf1f4]">
                <th scope="row" className="max-w-[360px] px-5 py-3 font-semibold text-[#35424e]">
                  {chart.title}
                </th>
                <td className="whitespace-nowrap px-4 py-3 text-right font-semibold text-[#26333e] tabular-nums">
                  {formatValue(metric.value, chart.unit, { compact: true })}
                </td>
                <td
                  className={cn(
                    "whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums",
                    change === null
                      ? "text-[#929ba4]"
                      : change >= 0
                        ? "text-[#16835c]"
                        : "text-[#b4232c]"
                  )}
                >
                  <span className="inline-flex items-center justify-end gap-1">
                    {change !== null &&
                      (change >= 0 ? (
                        <ArrowUpRight size={12} aria-hidden="true" />
                      ) : (
                        <ArrowDownRight size={12} aria-hidden="true" />
                      ))}
                    {change === null ? "—" : `${Math.abs(change).toFixed(1)}%`}
                  </span>
                </td>
                <td className="max-w-[260px] truncate px-4 py-3 text-[#687580]">
                  {chart.sourceSheet}
                </td>
                <td className="px-5 py-3">
                  <span
                    className={cn(
                      "rounded-full px-2 py-1 text-[8px] font-semibold",
                      chart.provenance === "uploaded"
                        ? "bg-[#e3f7ef] text-[#15704d]"
                        : "bg-[#eef2f6] text-[#63717d]"
                    )}
                  >
                    {chart.provenance === "uploaded" ? "Uploaded" : "Baseline"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="divide-y divide-[#edf1f4] sm:hidden">
        {rows.map(({ chart, metric, change }) => (
          <article key={chart.id} className="px-4 py-3">
            <p className="text-[10px] font-semibold leading-4 text-[#35424e]">{chart.title}</p>
            <div className="mt-2 flex items-center justify-between gap-3">
              <span className="text-[15px] font-semibold text-[#24313c]">
                {formatValue(metric.value, chart.unit, { compact: true })}
              </span>
              <span
                className={cn(
                  "text-[9px] font-semibold",
                  change === null
                    ? "text-[#929ba4]"
                    : change >= 0
                      ? "text-[#16835c]"
                      : "text-[#b4232c]"
                )}
              >
                {change === null ? "YoY unavailable" : `${change >= 0 ? "+" : "−"}${Math.abs(change).toFixed(1)}% YoY`}
              </span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
