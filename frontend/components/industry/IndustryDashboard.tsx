"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  Activity,
  AreaChart as AreaChartIcon,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  CalendarRange,
  Check,
  ChevronRight,
  CircleAlert,
  Database,
  Download,
  FileChartColumn,
  FileSearch,
  Filter,
  Gauge,
  Info,
  Layers3,
  LineChart as LineChartIcon,
  LoaderCircle,
  Maximize2,
  Menu,
  PanelTop,
  Plus,
  RadioTower,
  RefreshCcw,
  Search,
  SlidersHorizontal,
  Sparkles,
  Table2,
  Target,
  Upload,
  Wifi,
  X,
} from "lucide-react";
import {
  FormEvent,
  ReactNode,
  RefObject,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { cn } from "@/lib/utils";
import {
  PALETTE,
  buildChartData,
  chartUnit,
  downloadCsv,
  forecastSeries,
  formatValue,
  getHeadlineMetric,
  percentChange,
  prepareSeries,
  sortPeriods,
} from "@/lib/industry-dashboard/analytics";
import {
  ChartDatum,
  ChartKind,
  CoveragePlacement,
  CustomChart,
  DashboardViewId,
  Granularity,
  IndicatorSeries,
  IndustryChart,
  IndustryDashboardDataset,
  SortMode,
  TrendMode,
  WorkbookPreview,
} from "@/lib/industry-dashboard/types";
import { parseIndustryWorkbook } from "@/lib/industry-dashboard/workbook";
import {
  ForecastVisual,
  MetricSparkline,
  ReferenceChartVisual,
} from "@/components/industry/ReferenceCharts";
import {
  InsightStrip,
  MetricSnapshotTable,
} from "@/components/industry/DashboardSummary";
import { chartAccent, seriesColor, seriesDash } from "@/lib/industry-dashboard/visuals";

type DashboardMode = "analytics" | "coverage";
type Range = { start: string; end: string };

const CONTROL =
  "h-10 rounded-[10px] border border-[#dce2e9] bg-white px-3 text-[12px] font-medium text-[#30343b] outline-none transition focus:border-[#0a66c2] focus:ring-2 focus:ring-[#0a66c2]/15 disabled:cursor-not-allowed disabled:bg-[#f3f5f7] disabled:text-[#9aa1aa]";
const ICON_BUTTON =
  "inline-flex h-9 w-9 items-center justify-center rounded-[9px] border border-[#e0e5eb] bg-white text-[#53606d] transition hover:border-[#b8c8d9] hover:bg-[#f5f8fb] hover:text-[#002d5b] focus:outline-none focus:ring-2 focus:ring-[#0a66c2]/25";

const VIEW_META: Record<
  DashboardViewId,
  { label: string; short: string; icon: React.ElementType; color: string; soft: string }
> = {
  industry: {
    label: "Industry Overview",
    short: "Industry",
    icon: Gauge,
    color: "#002d5b",
    soft: "#eaf1f8",
  },
  mobile: {
    label: "Mobile Industry",
    short: "Mobile",
    icon: RadioTower,
    color: "#0a66c2",
    soft: "#e8f2ff",
  },
  fixed: {
    label: "Fixed Network",
    short: "Fixed",
    icon: Activity,
    color: "#7b3fc6",
    soft: "#f2eaff",
  },
  bwa: {
    label: "BWA",
    short: "BWA",
    icon: Wifi,
    color: "#00877c",
    soft: "#e3f7f4",
  },
};

function hasNumericData(data: ChartDatum[], series: IndicatorSeries[]) {
  return data.some((datum) =>
    series.some((item) => typeof datum[item.name] === "number")
  );
}

function sourceOrder(chart: IndustryChart) {
  return Math.min(
    ...chart.placementContexts.map((context) => context.sourceOrder),
    Number.MAX_SAFE_INTEGER
  );
}

function chartGridClass(chart: IndustryChart, heroIndex: number) {
  if (chart.presentation.emphasis === "hero") {
    if (heroIndex === 0) return "md:col-span-2 xl:col-span-7";
    if (heroIndex === 1) return "md:col-span-2 xl:col-span-5";
    return "md:col-span-2 xl:col-span-6";
  }
  if (chart.presentation.emphasis === "wide") return "md:col-span-2 xl:col-span-6";
  if (chart.presentation.emphasis === "compact") return "xl:col-span-3";
  return "xl:col-span-4";
}

function modalAnimation(reduceMotion: boolean | null) {
  return reduceMotion
    ? { initial: false, animate: {}, exit: {} }
    : {
        initial: { opacity: 0, x: 24 },
        animate: { opacity: 1, x: 0 },
        exit: { opacity: 0, x: 24 },
      };
}

function useDialogFocus(
  open: boolean,
  closeRef: RefObject<HTMLButtonElement>,
  onClose: () => void
) {
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previous?.focus();
    };
  }, [closeRef, onClose, open]);
}

function LoadingState() {
  return (
    <div className="space-y-4" aria-label="Loading Industry Dashboard">
      <div className="h-28 animate-pulse rounded-[16px] bg-[#e8edf2]" />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div
            key={index}
            className="h-28 animate-pulse rounded-[14px] bg-[#edf1f5]"
          />
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="h-80 animate-pulse rounded-[16px] bg-[#edf1f5]" />
        <div className="h-80 animate-pulse rounded-[16px] bg-[#edf1f5]" />
      </div>
    </div>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex min-h-[420px] items-center justify-center">
      <div className="max-w-md rounded-[16px] border border-[#f0ccd0] bg-white p-7 text-center shadow-sm">
        <CircleAlert className="mx-auto text-[#b4232c]" size={28} aria-hidden="true" />
        <h2 className="mt-4 text-[18px] font-semibold text-[#191c1e]">
          The industry dataset could not be loaded
        </h2>
        <p className="mt-2 text-[13px] leading-6 text-[#626a73]">
          The page is intact, but the normalized workbook history is unavailable.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 inline-flex h-10 items-center gap-2 rounded-[10px] bg-[#002d5b] px-4 text-[12px] font-semibold text-white focus:outline-none focus:ring-2 focus:ring-[#0a66c2]/30"
        >
          <RefreshCcw size={14} aria-hidden="true" />
          Try again
        </button>
      </div>
    </div>
  );
}

function MetricCard({
  chart,
  rangeEnd,
  operator,
  operatorNames,
  index,
  reduceMotion,
}: {
  chart: IndustryChart;
  rangeEnd: string;
  operator: string;
  operatorNames: string[];
  index: number;
  reduceMotion: boolean | null;
}) {
  const metric = getHeadlineMetric(chart, rangeEnd, operator, operatorNames);
  const qoq = percentChange(metric.value, metric.previous);
  const yoy = percentChange(metric.value, metric.yearAgo);
  const change = yoy ?? qoq;
  const positive = change !== null && change >= 0;
  const color = chartAccent(index);
  const sparklineSeries =
    chart.series.find((item) => item.name === metric.seriesName) ?? chart.series[0] ?? null;

  return (
    <article
      className={cn(
        "group relative min-w-0 overflow-hidden rounded-[15px] border border-[#e0e6eb] bg-white px-4 pb-3 pt-4 shadow-[0_7px_20px_rgba(0,45,91,0.045)]",
        index % 3 === 1 && "bg-gradient-to-br from-white to-[#fbf8ff]",
        index % 3 === 2 && "bg-gradient-to-br from-white to-[#f5fbfb]"
      )}
    >
      <span
        className="absolute inset-x-0 top-0 h-[3px]"
        style={{ backgroundColor: color }}
        aria-hidden="true"
      />
      <div className="flex items-start justify-between gap-3">
        <p className="line-clamp-2 min-h-9 text-[11px] font-semibold leading-[18px] text-[#59616b]">
          {chart.title}
        </p>
        <span
          className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[9px]"
          style={{ backgroundColor: `${color}16`, color }}
        >
          <Activity size={15} aria-hidden="true" />
        </span>
      </div>
      <p className="mt-2.5 truncate text-[26px] font-semibold tracking-[-0.04em] text-[#181b1f] tabular-nums">
        {formatValue(metric.value, chart.unit, { compact: true })}
      </p>
      <div className="mt-2 flex items-center justify-between gap-2 text-[10px]">
        {change === null ? (
          <span className="text-[#858c95]">Change unavailable</span>
        ) : (
          <span
            className={cn(
              "inline-flex items-center gap-1 font-semibold",
              positive ? "text-[#16835c]" : "text-[#b4232c]"
            )}
          >
            {positive ? (
              <ArrowUpRight size={13} aria-hidden="true" />
            ) : (
              <ArrowDownRight size={13} aria-hidden="true" />
            )}
            {Math.abs(change).toFixed(1)}% {yoy !== null ? "YoY" : "period"}
          </span>
        )}
        <span className="truncate text-[#8a9199]">{metric.period}</span>
      </div>
      <div className="mt-2 -mx-1">
        <MetricSparkline
          chart={chart}
          series={sparklineSeries}
          color={color}
          reduceMotion={reduceMotion}
        />
      </div>
    </article>
  );
}

function ChartLegend({
  series,
  hidden,
  onToggle,
  interactive = true,
}: {
  series: IndicatorSeries[];
  hidden: Set<string>;
  onToggle: (name: string) => void;
  interactive?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1.5" aria-label="Chart series">
      {series.map((item, index) => {
        const isHidden = hidden.has(item.name);
        const content = (
          <>
            <span
              className="h-2 w-2 rounded-full"
              style={{
                backgroundColor: isHidden ? "#c6ccd2" : seriesColor(item.name, index),
              }}
              aria-hidden="true"
            />
            <span
              className="h-px w-2.5"
              style={{
                borderTop: `2px ${seriesDash(index) ? "dashed" : "solid"} ${
                  isHidden ? "#c6ccd2" : seriesColor(item.name, index)
                }`,
              }}
              aria-hidden="true"
            />
            {item.name}
          </>
        );

        if (!interactive) {
          return (
            <span
              key={item.name}
              className="inline-flex items-center gap-1.5 px-1 py-0.5 text-[10px] font-medium text-[#5d6670]"
            >
              {content}
            </span>
          );
        }

        return (
          <button
            key={item.name}
            type="button"
            aria-pressed={!isHidden}
            onClick={() => onToggle(item.name)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-1 py-0.5 text-[10px] font-medium outline-none transition focus:ring-2 focus:ring-[#0a66c2]/25",
              isHidden ? "text-[#9aa1a8] line-through" : "text-[#5d6670]"
            )}
          >
            {content}
          </button>
        );
      })}
    </div>
  );
}

function ChartVisual({
  chart,
  series,
  data,
  hidden,
  unit,
  height = 260,
  reduceMotion,
  compositionSeries,
  compositionData,
  activeOperator,
  operatorNames,
  onOperatorChange,
  forecastStart,
}: {
  chart: IndustryChart;
  series: IndicatorSeries[];
  data: ChartDatum[];
  hidden: Set<string>;
  unit: string;
  height?: number;
  reduceMotion: boolean | null;
  compositionSeries?: IndicatorSeries[];
  compositionData?: ChartDatum[];
  activeOperator?: string;
  operatorNames?: string[];
  onOperatorChange?: (operator: string) => void;
  forecastStart?: string;
}) {
  return (
    <ReferenceChartVisual
      chart={chart}
      series={series}
      data={data}
      hidden={hidden}
      unit={unit}
      height={height}
      reduceMotion={reduceMotion}
      compositionSeries={compositionSeries}
      compositionData={compositionData}
      activeOperator={activeOperator}
      operatorNames={operatorNames}
      onOperatorChange={onOperatorChange}
      forecastStart={forecastStart}
    />
  );
}

function ChartTable({
  data,
  series,
  unit,
}: {
  data: ChartDatum[];
  series: IndicatorSeries[];
  unit: string;
}) {
  return (
    <div className="overflow-x-auto rounded-[10px] border border-[#e2e7ec]">
      <table className="min-w-full border-collapse text-left text-[11px]">
        <caption className="sr-only">Underlying chart observations</caption>
        <thead className="bg-[#f5f7f9] text-[#58616b]">
          <tr>
            <th scope="col" className="sticky left-0 bg-[#f5f7f9] px-3 py-2 font-semibold">
              Period
            </th>
            {series.map((item) => (
              <th key={item.name} scope="col" className="whitespace-nowrap px-3 py-2 font-semibold">
                {item.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((datum) => (
            <tr key={datum.period} className="border-t border-[#edf0f3]">
              <th
                scope="row"
                className="sticky left-0 whitespace-nowrap bg-white px-3 py-2 font-medium text-[#4f5964]"
              >
                {datum.period}
              </th>
              {series.map((item) => (
                <td key={item.name} className="whitespace-nowrap px-3 py-2 text-[#343a42] tabular-nums">
                  {formatValue(
                    typeof datum[item.name] === "number"
                      ? (datum[item.name] as number)
                      : null,
                    unit
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChartCard({
  chart,
  range,
  granularity,
  trendMode,
  operator,
  operatorNames,
  globalTable,
  reduceMotion,
  onDetails,
  onOperatorChange,
  viewLabel,
}: {
  chart: IndustryChart;
  range: Range;
  granularity: Granularity;
  trendMode: TrendMode;
  operator: string;
  operatorNames: string[];
  globalTable: boolean;
  reduceMotion: boolean | null;
  onDetails: (chart: IndustryChart, trigger: HTMLButtonElement) => void;
  onOperatorChange: (operator: string) => void;
  viewLabel: string;
}) {
  const [shareMode, setShareMode] = useState(false);
  const [tableOpen, setTableOpen] = useState(false);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const series = useMemo(
    () =>
      prepareSeries(chart, {
        shareMode,
        operator,
        operatorNames,
        granularity,
        trendMode,
      }),
    [chart, granularity, operator, operatorNames, shareMode, trendMode]
  );
  const data = useMemo(
    () => buildChartData(series, range, granularity),
    [granularity, range, series]
  );
  const compositionSeries = useMemo(
    () =>
      chart.shareSeries.length
        ? prepareSeries(chart, {
            shareMode: true,
            operator,
            operatorNames,
            granularity,
            trendMode: "absolute",
          })
        : [],
    [chart, granularity, operator, operatorNames]
  );
  const compositionData = useMemo(
    () => buildChartData(compositionSeries, range, granularity),
    [compositionSeries, granularity, range]
  );
  const unit = chartUnit(chart, trendMode, shareMode);
  const showTable = globalTable || tableOpen;
  const visualHeight =
    chart.presentation.emphasis === "hero"
      ? 300
      : chart.presentation.emphasis === "compact"
        ? 220
        : 265;

  useEffect(() => {
    setHidden(new Set());
  }, [operator, shareMode]);

  const exportChart = () => {
    const rows: (string | number | null)[][] = [
      [
        "Dashboard",
        "Chart",
        "Granularity",
        "Trend mode",
        "Unit",
        "Period",
        "Series",
        "Value",
        "Source workbook",
        "Source sheet",
        "Provenance",
      ],
    ];
    for (const datum of data) {
      for (const item of series) {
        rows.push([
          viewLabel,
          chart.title,
          granularity,
          trendMode,
          unit,
          datum.period,
          item.name,
          typeof datum[item.name] === "number" ? (datum[item.name] as number) : null,
          chart.sourceWorkbook,
          chart.sourceSheet,
          chart.provenance ?? "baseline",
        ]);
      }
    }
    downloadCsv(`${chart.id}-${range.end.replace(" ", "-")}.csv`, rows);
  };

  const toggleSeries = (name: string) => {
    setHidden((current) => {
      const next = new Set(current);
      if (next.has(name)) next.delete(name);
      else if (next.size < Math.max(0, series.length - 1)) next.add(name);
      return next;
    });
  };

  return (
    <motion.article
      layout={!reduceMotion}
      data-chart-id={chart.id}
      className="min-w-0 overflow-hidden rounded-[17px] border border-[#dee5eb] bg-white p-4 shadow-[0_8px_24px_rgba(0,45,91,0.05)] sm:p-5"
    >
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-[0.075em] text-[#7b838c]">
              {VIEW_META[chart.sectorId].short}
            </span>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[9px] font-semibold",
                chart.provenance === "uploaded"
                  ? "bg-[#e3f7ef] text-[#15704d]"
                  : "bg-[#eef2f6] text-[#62707c]"
              )}
            >
              {chart.provenance === "uploaded" ? "Uploaded" : "Workbook baseline"}
            </span>
          </div>
          <h3 className="mt-1.5 text-[14px] font-semibold leading-5 text-[#1a1d21]">
            {chart.title}
          </h3>
          <p className="mt-1 text-[10px] text-[#858d96]">
            {chart.unitLabel} · {chart.sourceSheet}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            className={ICON_BUTTON}
            aria-label={`${showTable ? "Hide" : "Show"} data table for ${chart.title}`}
            aria-pressed={showTable}
            onClick={() => setTableOpen((value) => !value)}
          >
            <Table2 size={15} aria-hidden="true" />
          </button>
          <button
            type="button"
            className={ICON_BUTTON}
            aria-label={`Export ${chart.title} as CSV`}
            onClick={exportChart}
          >
            <Download size={15} aria-hidden="true" />
          </button>
          <button
            type="button"
            className={ICON_BUTTON}
            aria-label={`Open details for ${chart.title}`}
            onClick={(event) => onDetails(chart, event.currentTarget)}
          >
            <Maximize2 size={15} aria-hidden="true" />
          </button>
        </div>
      </header>

      <div className="mt-3 flex min-h-6 flex-wrap items-center justify-between gap-2">
        <ChartLegend series={series} hidden={hidden} onToggle={toggleSeries} />
        {chart.shareSeries.length > 0 && (
          <div className="flex rounded-[8px] bg-[#f1f4f7] p-0.5 text-[9px] font-semibold">
            <button
              type="button"
              className={cn(
                "rounded-[6px] px-2 py-1",
                !shareMode ? "bg-white text-[#183a5b] shadow-sm" : "text-[#7a838c]"
              )}
              onClick={() => setShareMode(false)}
              aria-pressed={!shareMode}
            >
              Value
            </button>
            <button
              type="button"
              className={cn(
                "rounded-[6px] px-2 py-1",
                shareMode ? "bg-white text-[#183a5b] shadow-sm" : "text-[#7a838c]"
              )}
              onClick={() => setShareMode(true)}
              aria-pressed={shareMode}
            >
              Share
            </button>
          </div>
        )}
      </div>

      <div className="mt-2">
        <ChartVisual
          chart={chart}
          series={series}
          data={data}
          hidden={hidden}
          unit={unit}
          height={visualHeight}
          reduceMotion={reduceMotion}
          compositionSeries={compositionSeries}
          compositionData={compositionData}
          activeOperator={operator}
          operatorNames={operatorNames}
          onOperatorChange={onOperatorChange}
        />
      </div>
      {showTable && (
        <div className="mt-3">
          <ChartTable data={data} series={series} unit={unit} />
        </div>
      )}
      {chart.note && (
        <p className="mt-3 flex items-start gap-1.5 border-t border-[#eef1f4] pt-3 text-[10px] leading-4 text-[#747d86]">
          <Info size={12} className="mt-0.5 shrink-0" aria-hidden="true" />
          {chart.note}
        </p>
      )}
    </motion.article>
  );
}

function DetailDrawer({
  chart,
  open,
  onClose,
  range,
  granularity,
  trendMode,
  operator,
  operatorNames,
  reduceMotion,
  charts,
}: {
  chart: IndustryChart | null;
  open: boolean;
  onClose: () => void;
  range: Range;
  granularity: Granularity;
  trendMode: TrendMode;
  operator: string;
  operatorNames: string[];
  reduceMotion: boolean | null;
  charts: IndustryChart[];
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useDialogFocus(open, closeRef, onClose);

  if (!chart) return null;
  const series = prepareSeries(chart, {
    shareMode: false,
    operator,
    operatorNames,
    granularity,
    trendMode,
  });
  const data = buildChartData(series, range, granularity);
  const supporting = charts.filter((item) => chart.supportingChartIds.includes(item.id));

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[80]">
          <motion.button
            type="button"
            aria-label="Close indicator details"
            className="absolute inset-0 bg-[#001b35]/45 backdrop-blur-[2px]"
            onClick={onClose}
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.section
            role="dialog"
            aria-modal="true"
            aria-labelledby="indicator-detail-title"
            className="absolute inset-y-0 right-0 w-full max-w-[760px] overflow-y-auto bg-[#f7f9fb] shadow-[-18px_0_50px_rgba(0,27,53,0.18)]"
            {...modalAnimation(reduceMotion)}
          >
            <header className="sticky top-0 z-10 border-b border-[#dfe5eb] bg-white/95 px-5 py-4 backdrop-blur sm:px-7">
              <div className="flex items-start justify-between gap-5">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[#6c7680]">
                    Indicator detail · {VIEW_META[chart.sectorId].label}
                  </p>
                  <h2
                    id="indicator-detail-title"
                    className="mt-1 text-[19px] font-semibold tracking-[-0.02em] text-[#15191d]"
                  >
                    {chart.title}
                  </h2>
                </div>
                <button
                  ref={closeRef}
                  type="button"
                  className={ICON_BUTTON}
                  onClick={onClose}
                  aria-label="Close indicator details"
                >
                  <X size={17} aria-hidden="true" />
                </button>
              </div>
            </header>
            <div className="space-y-4 p-5 sm:p-7">
              <section className="rounded-[16px] border border-[#dfe5eb] bg-white p-4 sm:p-5">
                <ChartLegend
                  series={series}
                  hidden={new Set()}
                  onToggle={() => undefined}
                  interactive={false}
                />
                <ChartVisual
                  chart={chart}
                  series={series}
                  data={data}
                  hidden={new Set()}
                  unit={chartUnit(chart, trendMode, false)}
                  height={360}
                  reduceMotion={reduceMotion}
                />
              </section>
              <section className="grid gap-3 sm:grid-cols-2">
                {[
                  ["Source workbook", chart.sourceWorkbook],
                  ["Source sheet", chart.sourceSheet],
                  ["Display unit", chart.unitLabel],
                  ["Data provenance", chart.provenance === "uploaded" ? "Uploaded workbook" : "Bundled workbook baseline"],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-[12px] border border-[#dfe5eb] bg-white p-4">
                    <p className="text-[9px] font-semibold uppercase tracking-[0.07em] text-[#838b94]">
                      {label}
                    </p>
                    <p className="mt-1.5 break-words text-[12px] font-medium text-[#323942]">
                      {value}
                    </p>
                  </div>
                ))}
              </section>
              <section className="rounded-[16px] border border-[#dfe5eb] bg-white p-4 sm:p-5">
                <div className="mb-3 flex items-center gap-2">
                  <Table2 size={16} className="text-[#0a66c2]" aria-hidden="true" />
                  <h3 className="text-[13px] font-semibold text-[#20252a]">
                    Underlying observations
                  </h3>
                </div>
                <ChartTable
                  data={data}
                  series={series}
                  unit={chartUnit(chart, trendMode, false)}
                />
              </section>
              {supporting.length > 0 && (
                <section className="rounded-[16px] border border-[#dfe5eb] bg-white p-4 sm:p-5">
                  <h3 className="text-[13px] font-semibold text-[#20252a]">
                    Supporting metrics
                  </h3>
                  <p className="mt-1 text-[11px] text-[#737c86]">
                    These workbook series support the Word-defined indicator without
                    creating additional indicator placements.
                  </p>
                  <div className="mt-3 space-y-2">
                    {supporting.map((item) => (
                      <div
                        key={item.id}
                        className="flex items-center justify-between gap-3 rounded-[10px] bg-[#f4f7f9] px-3 py-2.5"
                      >
                        <span className="text-[11px] font-medium text-[#3d4650]">
                          {item.title}
                        </span>
                        <span className="text-[10px] text-[#747d86]">{item.unitLabel}</span>
                      </div>
                    ))}
                  </div>
                </section>
              )}
              <section className="rounded-[16px] border border-[#dfe5eb] bg-white p-4 sm:p-5">
                <h3 className="text-[13px] font-semibold text-[#20252a]">
                  Coverage and methodology
                </h3>
                <p className="mt-2 text-[11px] leading-5 text-[#69727c]">
                  {chart.note || "No additional methodology note was supplied."}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {chart.placementContexts.map((context) => (
                    <span
                      key={`${context.sourceOrder}-${context.section}`}
                      className="rounded-full border border-[#dce3e9] bg-[#f7f9fb] px-2.5 py-1 text-[9px] font-semibold text-[#64707b]"
                    >
                      #{context.sourceOrder} · {context.sector} / {context.section}
                    </span>
                  ))}
                </div>
                <p className="mt-3 rounded-[10px] bg-[#fff7de] px-3 py-2 text-[10px] leading-4 text-[#6e5411]">
                  Targets were not supplied; no actual-versus-target conclusion is shown.
                </p>
              </section>
            </div>
          </motion.section>
        </div>
      )}
    </AnimatePresence>
  );
}

function FilterControls({
  dataset,
  range,
  setRange,
  granularity,
  setGranularity,
  trendMode,
  setTrendMode,
  operator,
  setOperator,
  search,
  setSearch,
  sort,
  setSort,
}: {
  dataset: IndustryDashboardDataset;
  range: Range;
  setRange: (range: Range) => void;
  granularity: Granularity;
  setGranularity: (value: Granularity) => void;
  trendMode: TrendMode;
  setTrendMode: (value: TrendMode) => void;
  operator: string;
  setOperator: (value: string) => void;
  search: string;
  setSearch: (value: string) => void;
  sort: SortMode;
  setSort: (value: SortMode) => void;
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-[1fr_1fr_0.8fr_0.9fr_1fr_1.2fr_0.8fr]">
      <label className="grid gap-1">
        <span className="text-[9px] font-semibold uppercase tracking-[0.065em] text-[#747d87]">
          From
        </span>
        <select
          value={range.start}
          onChange={(event) => setRange({ ...range, start: event.target.value })}
          className={CONTROL}
          aria-label="Start period"
        >
          {dataset.periods
            .filter((period) => dataset.periods.indexOf(period) <= dataset.periods.indexOf(range.end))
            .map((period) => (
              <option key={period}>{period}</option>
            ))}
        </select>
      </label>
      <label className="grid gap-1">
        <span className="text-[9px] font-semibold uppercase tracking-[0.065em] text-[#747d87]">
          To
        </span>
        <select
          value={range.end}
          onChange={(event) => setRange({ ...range, end: event.target.value })}
          className={CONTROL}
          aria-label="End period"
        >
          {dataset.periods
            .filter((period) => dataset.periods.indexOf(period) >= dataset.periods.indexOf(range.start))
            .map((period) => (
              <option key={period}>{period}</option>
            ))}
        </select>
      </label>
      <label className="grid gap-1">
        <span className="text-[9px] font-semibold uppercase tracking-[0.065em] text-[#747d87]">
          Granularity
        </span>
        <select
          value={granularity}
          onChange={(event) => setGranularity(event.target.value as Granularity)}
          className={CONTROL}
          aria-label="Granularity"
        >
          <option value="monthly" disabled>
            Monthly · unavailable
          </option>
          <option value="quarterly">Quarterly</option>
          <option value="yearly">Yearly</option>
        </select>
      </label>
      <label className="grid gap-1">
        <span className="text-[9px] font-semibold uppercase tracking-[0.065em] text-[#747d87]">
          Trend
        </span>
        <select
          value={trendMode}
          onChange={(event) => setTrendMode(event.target.value as TrendMode)}
          className={CONTROL}
          aria-label="Trend mode"
        >
          <option value="absolute">Absolute</option>
          <option value="qoq">Period change</option>
          <option value="yoy">Year-on-year</option>
          <option value="index">Index · base 100</option>
        </select>
      </label>
      <label className="grid gap-1">
        <span className="text-[9px] font-semibold uppercase tracking-[0.065em] text-[#747d87]">
          Operator
        </span>
        <select
          value={operator}
          onChange={(event) => setOperator(event.target.value)}
          className={CONTROL}
          aria-label="Operator"
        >
          <option value="all">All operators</option>
          {dataset.operators.map((item) => (
            <option key={item.name} value={item.name}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <label className="grid gap-1">
        <span className="text-[9px] font-semibold uppercase tracking-[0.065em] text-[#747d87]">
          Search
        </span>
        <span className="relative">
          <Search
            size={14}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#8b949d]"
            aria-hidden="true"
          />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Indicators or series"
            className={cn(CONTROL, "w-full pl-9")}
            aria-label="Search indicators"
          />
        </span>
      </label>
      <label className="grid gap-1">
        <span className="text-[9px] font-semibold uppercase tracking-[0.065em] text-[#747d87]">
          Sort
        </span>
        <select
          value={sort}
          onChange={(event) => setSort(event.target.value as SortMode)}
          className={CONTROL}
          aria-label="Sort charts"
        >
          <option value="source">Source order</option>
          <option value="title">Indicator A–Z</option>
          <option value="latest">Latest value</option>
        </select>
      </label>
    </div>
  );
}

function ForecastDialog({
  open,
  onClose,
  charts,
  defaultChartId,
  operator,
  operatorNames,
  reduceMotion,
}: {
  open: boolean;
  onClose: () => void;
  charts: IndustryChart[];
  defaultChartId: string;
  operator: string;
  operatorNames: string[];
  reduceMotion: boolean | null;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const [chartId, setChartId] = useState(defaultChartId);
  const [horizon, setHorizon] = useState(4);
  useDialogFocus(open, closeRef, onClose);

  useEffect(() => {
    if (defaultChartId) setChartId(defaultChartId);
  }, [defaultChartId]);

  const chart = charts.find((item) => item.id === chartId) ?? charts[0];
  if (!chart) return null;
  const series = prepareSeries(chart, {
    shareMode: false,
    operator,
    operatorNames,
    granularity: "quarterly",
    trendMode: "absolute",
  });
  const forecastable = series.filter(
    (item) => item.values.filter((point) => point.value !== null).length >= 2
  );
  const forecasts = forecastable.map((item) => ({
    name: item.name,
    values: forecastSeries(item, horizon),
  }));

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[85] flex items-center justify-center p-3 sm:p-6">
          <motion.button
            type="button"
            className="absolute inset-0 bg-[#001b35]/50 backdrop-blur-[2px]"
            onClick={onClose}
            aria-label="Close forecast panel"
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.section
            role="dialog"
            aria-modal="true"
            aria-labelledby="forecast-title"
            className="relative max-h-[90vh] w-full max-w-[760px] overflow-y-auto rounded-[18px] bg-[#f8fafb] shadow-[0_24px_80px_rgba(0,27,53,0.25)]"
            initial={reduceMotion ? false : { opacity: 0, y: 18, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.985 }}
          >
            <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-[#e0e5ea] bg-white px-5 py-4 sm:px-6">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[#7b3fc6]">
                  Planning estimate
                </p>
                <h2 id="forecast-title" className="mt-1 text-[18px] font-semibold text-[#181c20]">
                  Indicator forecast
                </h2>
              </div>
              <button
                ref={closeRef}
                type="button"
                className={ICON_BUTTON}
                onClick={onClose}
                aria-label="Close forecast panel"
              >
                <X size={17} aria-hidden="true" />
              </button>
            </header>
            <div className="space-y-4 p-5 sm:p-6">
              <div className="grid gap-3 sm:grid-cols-[1fr_180px]">
                <label className="grid gap-1">
                  <span className="text-[10px] font-semibold text-[#66717c]">Metric</span>
                  <select
                    value={chart.id}
                    onChange={(event) => setChartId(event.target.value)}
                    className={CONTROL}
                  >
                    {charts.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.title}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="grid gap-1">
                  <span className="text-[10px] font-semibold text-[#66717c]">
                    Forecast horizon
                  </span>
                  <select
                    value={horizon}
                    onChange={(event) => setHorizon(Number(event.target.value))}
                    className={CONTROL}
                  >
                    {[1, 2, 3, 4].map((value) => (
                      <option key={value} value={value}>
                        {value} {value === 1 ? "quarter" : "quarters"}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="rounded-[14px] border border-[#e1e6eb] bg-white p-3 sm:p-4">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[10px] font-semibold text-[#4d5964]">
                    Historical trend and planning estimate
                  </p>
                  <div className="flex items-center gap-3 text-[9px] text-[#73808b]">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="h-0.5 w-4 bg-[#1677ff]" aria-hidden="true" />
                      Historical
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <span className="w-4 border-t-2 border-dashed border-[#7b3fc6]" aria-hidden="true" />
                      Estimate
                    </span>
                  </div>
                </div>
                <ForecastVisual
                  chart={chart}
                  series={forecastable}
                  forecasts={forecasts}
                  reduceMotion={reduceMotion}
                />
              </div>
              <div className="rounded-[14px] border border-[#e1e6eb] bg-white p-4">
                <div className="grid gap-2 sm:grid-cols-2">
                  {forecasts.slice(0, 4).map((item, index) => (
                    <div key={item.name} className="rounded-[11px] bg-[#f5f7f9] p-3">
                      <div className="flex items-center gap-2">
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ backgroundColor: PALETTE[index % PALETTE.length] }}
                        />
                        <p className="truncate text-[10px] font-semibold text-[#5c6670]">
                          {item.name}
                        </p>
                      </div>
                      <p className="mt-2 text-[18px] font-semibold text-[#20252a]">
                        {formatValue(item.values.at(-1)?.value ?? null, chart.unit, {
                          compact: true,
                        })}
                      </p>
                      <p className="mt-0.5 text-[9px] text-[#848c95]">
                        {item.values.at(-1)?.period}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
              <div className="overflow-x-auto rounded-[12px] border border-[#e1e6eb] bg-white">
                <table className="min-w-full text-left text-[11px]">
                  <caption className="sr-only">Forecast values</caption>
                  <thead className="bg-[#f2f5f7] text-[#59636d]">
                    <tr>
                      <th className="px-3 py-2 font-semibold">Series</th>
                      {forecasts[0]?.values.map((point) => (
                        <th key={point.period} className="whitespace-nowrap px-3 py-2 font-semibold">
                          {point.period}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {forecasts.map((item) => (
                      <tr key={item.name} className="border-t border-[#edf0f3]">
                        <th className="whitespace-nowrap px-3 py-2 font-medium text-[#3f4852]">
                          {item.name}
                        </th>
                        {item.values.map((point) => (
                          <td key={point.period} className="whitespace-nowrap px-3 py-2 tabular-nums">
                            {formatValue(point.value, chart.unit)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-start gap-2 rounded-[11px] border border-[#ead7a4] bg-[#fff9e8] p-3 text-[10px] leading-5 text-[#6f5718]">
                <Info size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
                A simple linear trend is fitted to the latest eight valid quarterly
                observations. These values are planning guidance, not official NCA
                projections or targets.
              </div>
            </div>
          </motion.section>
        </div>
      )}
    </AnimatePresence>
  );
}

function UploadDialog({
  open,
  onClose,
  dataset,
  onApply,
  reduceMotion,
}: {
  open: boolean;
  onClose: () => void;
  dataset: IndustryDashboardDataset;
  onApply: (preview: WorkbookPreview) => void;
  reduceMotion: boolean | null;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<WorkbookPreview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useDialogFocus(open, closeRef, onClose);

  useEffect(() => {
    if (!open) {
      setPreview(null);
      setError("");
      setBusy(false);
    }
  }, [open]);

  const inspectFile = async (file: File) => {
    setBusy(true);
    setError("");
    setPreview(null);
    try {
      setPreview(await parseIndustryWorkbook(file, dataset));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The workbook could not be read.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[85] flex items-center justify-center p-3 sm:p-6">
          <motion.button
            type="button"
            className="absolute inset-0 bg-[#001b35]/50 backdrop-blur-[2px]"
            aria-label="Close workbook upload"
            onClick={onClose}
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.section
            role="dialog"
            aria-modal="true"
            aria-labelledby="upload-title"
            className="relative max-h-[90vh] w-full max-w-[660px] overflow-y-auto rounded-[18px] bg-white shadow-[0_24px_80px_rgba(0,27,53,0.25)]"
            initial={reduceMotion ? false : { opacity: 0, y: 18, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.985 }}
          >
            <header className="flex items-start justify-between gap-4 border-b border-[#e0e5ea] px-5 py-4 sm:px-6">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[#0a66c2]">
                  Session data
                </p>
                <h2 id="upload-title" className="mt-1 text-[18px] font-semibold text-[#181c20]">
                  Upload an NCA workbook
                </h2>
              </div>
              <button
                ref={closeRef}
                type="button"
                className={ICON_BUTTON}
                onClick={onClose}
                aria-label="Close workbook upload"
              >
                <X size={17} aria-hidden="true" />
              </button>
            </header>
            <div className="space-y-4 p-5 sm:p-6">
              <button
                type="button"
                className="flex w-full flex-col items-center justify-center rounded-[14px] border border-dashed border-[#aebdca] bg-[#f8fafc] px-6 py-9 text-center transition hover:border-[#0a66c2] hover:bg-[#f2f7fc] focus:outline-none focus:ring-2 focus:ring-[#0a66c2]/25"
                onClick={() => inputRef.current?.click()}
              >
                {busy ? (
                  <LoaderCircle className="animate-spin text-[#0a66c2]" size={27} aria-hidden="true" />
                ) : (
                  <Upload className="text-[#0a66c2]" size={27} aria-hidden="true" />
                )}
                <span className="mt-3 text-[13px] font-semibold text-[#2e3740]">
                  {busy ? "Inspecting workbook…" : "Choose an .xlsx workbook"}
                </span>
                <span className="mt-1 text-[10px] text-[#7b848d]">
                  Maximum 20 MB · processed only in this browser session
                </span>
              </button>
              <input
                ref={inputRef}
                type="file"
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                className="sr-only"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void inspectFile(file);
                }}
              />
              {error && (
                <div role="alert" className="flex items-start gap-2 rounded-[11px] bg-[#fff0f1] p-3 text-[11px] leading-5 text-[#9c2730]">
                  <CircleAlert size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
                  {error}
                </div>
              )}
              {preview && (
                <div className="rounded-[14px] border border-[#dce4ea] bg-[#f9fbfc] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[12px] font-semibold text-[#293139]">{preview.fileName}</p>
                      <p className="mt-1 text-[10px] text-[#6f7983]">
                        {preview.recognizedSheets.length} recognized sheets ·{" "}
                        {preview.updatedChartIds.length} charts · {preview.updatedSeries} series
                      </p>
                    </div>
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#e3f7ef] text-[#15704d]">
                      <Check size={16} aria-hidden="true" />
                    </span>
                  </div>
                  {preview.warnings.length > 0 && (
                    <ul className="mt-3 space-y-1 rounded-[10px] bg-[#fff8e7] p-3 text-[10px] leading-4 text-[#6e571c]">
                      {preview.warnings.slice(0, 4).map((warning) => (
                        <li key={warning}>• {warning}</li>
                      ))}
                    </ul>
                  )}
                  <div className="mt-4 flex justify-end">
                    <button
                      type="button"
                      onClick={() => {
                        onApply(preview);
                        onClose();
                      }}
                      className="inline-flex h-10 items-center gap-2 rounded-[10px] bg-[#002d5b] px-4 text-[12px] font-semibold text-white focus:outline-none focus:ring-2 focus:ring-[#0a66c2]/30"
                    >
                      <Check size={14} aria-hidden="true" />
                      Apply session data
                    </button>
                  </div>
                </div>
              )}
              <p className="text-[10px] leading-5 text-[#79828b]">
                Sheets are matched to the exact source-sheet names documented in the
                Word inventory. Unmatched charts keep their bundled baseline and remain
                visibly labeled. Refreshing the page clears uploaded data.
              </p>
            </div>
          </motion.section>
        </div>
      )}
    </AnimatePresence>
  );
}

function CustomChartDialog({
  open,
  onClose,
  charts,
  onAdd,
  reduceMotion,
}: {
  open: boolean;
  onClose: () => void;
  charts: IndustryChart[];
  onAdd: (chart: CustomChart) => void;
  reduceMotion: boolean | null;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const available = charts.filter((chart) => chart.provenance === "uploaded");
  const [sourceChartId, setSourceChartId] = useState(available[0]?.id ?? "");
  const [title, setTitle] = useState("");
  const [type, setType] = useState<ChartKind>("line");
  const [seriesNames, setSeriesNames] = useState<string[]>([]);
  useDialogFocus(open, closeRef, onClose);

  useEffect(() => {
    if (available.length && !available.some((item) => item.id === sourceChartId)) {
      setSourceChartId(available[0].id);
    }
  }, [available, sourceChartId]);

  const source = available.find((chart) => chart.id === sourceChartId);
  useEffect(() => {
    setSeriesNames(source?.series.slice(0, 2).map((item) => item.name) ?? []);
    setTitle(source ? `${source.title} · custom view` : "");
    setType(source?.type ?? "line");
  }, [source]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!source || !title.trim() || !seriesNames.length) return;
    onAdd({
      id: `custom-${Date.now()}`,
      title: title.trim(),
      sourceChartId: source.id,
      seriesNames,
      type,
    });
    onClose();
  };

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[85] flex items-center justify-center p-3 sm:p-6">
          <motion.button
            type="button"
            className="absolute inset-0 bg-[#001b35]/50 backdrop-blur-[2px]"
            onClick={onClose}
            aria-label="Close custom chart builder"
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.form
            onSubmit={submit}
            role="dialog"
            aria-modal="true"
            aria-labelledby="custom-chart-title"
            className="relative w-full max-w-[580px] rounded-[18px] bg-white shadow-[0_24px_80px_rgba(0,27,53,0.25)]"
            initial={reduceMotion ? false : { opacity: 0, y: 18, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.985 }}
          >
            <header className="flex items-start justify-between gap-4 border-b border-[#e0e5ea] px-5 py-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[#7b3fc6]">
                  Uploaded data
                </p>
                <h2 id="custom-chart-title" className="mt-1 text-[18px] font-semibold text-[#181c20]">
                  Create a custom chart
                </h2>
              </div>
              <button
                ref={closeRef}
                type="button"
                className={ICON_BUTTON}
                onClick={onClose}
                aria-label="Close custom chart builder"
              >
                <X size={17} aria-hidden="true" />
              </button>
            </header>
            <div className="space-y-4 p-5">
              <label className="grid gap-1">
                <span className="text-[10px] font-semibold text-[#67717b]">Source metric</span>
                <select
                  value={sourceChartId}
                  onChange={(event) => setSourceChartId(event.target.value)}
                  className={CONTROL}
                >
                  {available.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.title}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1">
                <span className="text-[10px] font-semibold text-[#67717b]">Chart title</span>
                <input
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  className={CONTROL}
                  required
                />
              </label>
              <fieldset>
                <legend className="text-[10px] font-semibold text-[#67717b]">Series</legend>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {source?.series.map((item) => {
                    const checked = seriesNames.includes(item.name);
                    return (
                      <label
                        key={item.name}
                        className={cn(
                          "flex cursor-pointer items-center gap-2 rounded-[9px] border px-3 py-2 text-[11px]",
                          checked
                            ? "border-[#9dbce0] bg-[#eef5fc] text-[#173d64]"
                            : "border-[#e0e5ea] text-[#59636d]"
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() =>
                            setSeriesNames((current) =>
                              checked
                                ? current.filter((name) => name !== item.name)
                                : [...current, item.name]
                            )
                          }
                        />
                        {item.name}
                      </label>
                    );
                  })}
                </div>
              </fieldset>
              <fieldset>
                <legend className="text-[10px] font-semibold text-[#67717b]">Chart type</legend>
                <div className="mt-2 grid grid-cols-3 gap-2">
                  {[
                    ["line", LineChartIcon, "Line"],
                    ["area", AreaChartIcon, "Area"],
                    ["bar", BarChart3, "Bar"],
                  ].map(([value, Icon, label]) => (
                    <button
                      key={String(value)}
                      type="button"
                      onClick={() => setType(value as ChartKind)}
                      className={cn(
                        "flex h-12 items-center justify-center gap-2 rounded-[10px] border text-[11px] font-semibold",
                        type === value
                          ? "border-[#0a66c2] bg-[#eef5fc] text-[#0a5aab]"
                          : "border-[#e0e5ea] text-[#65707a]"
                      )}
                    >
                      <Icon size={15} aria-hidden="true" />
                      {String(label)}
                    </button>
                  ))}
                </div>
              </fieldset>
              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={!source || !title.trim() || !seriesNames.length}
                  className="inline-flex h-10 items-center gap-2 rounded-[10px] bg-[#002d5b] px-4 text-[12px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45"
                >
                  <Plus size={14} aria-hidden="true" />
                  Add custom chart
                </button>
              </div>
            </div>
          </motion.form>
        </div>
      )}
    </AnimatePresence>
  );
}

function CoverageView({
  dataset,
  onExport,
}: {
  dataset: IndustryDashboardDataset;
  onExport: (placements: CoveragePlacement[]) => void;
}) {
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState<"all" | DashboardViewId>("all");
  const [sort, setSort] = useState<"source" | "title" | "section">("source");
  const placements = useMemo(() => {
    const term = search.trim().toLowerCase();
    return dataset.coverage
      .filter(
        (item) =>
          (sector === "all" || item.sectorId === sector) &&
          (!term ||
            [item.graph, item.section, item.sector, item.sourceSheet, ...item.series]
              .join(" ")
              .toLowerCase()
              .includes(term))
      )
      .sort((a, b) => {
        if (sort === "title") return a.graph.localeCompare(b.graph);
        if (sort === "section")
          return `${a.sector}-${a.section}-${a.sourceOrder}`.localeCompare(
            `${b.sector}-${b.section}-${b.sourceOrder}`,
            undefined,
            { numeric: true }
          );
        return a.sourceOrder - b.sourceOrder;
      });
  }, [dataset.coverage, search, sector, sort]);
  const distinct = new Set(placements.map((item) => item.graph)).size;

  return (
    <div className="space-y-4">
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Coverage summary">
        {[
          {
            label: "Source placements",
            value: `${placements.length}/${dataset.summary.chartPlacements}`,
            icon: Layers3,
          },
          {
            label: "Distinct graphs",
            value: `${distinct}/${dataset.summary.distinctWordGraphs}`,
            icon: BarChart3,
          },
          {
            label: "Workbook records",
            value: dataset.summary.referenceChartRecords,
            icon: Database,
          },
          { label: "Targets supplied", value: "None", icon: Target },
        ].map(({ label, value, icon: Icon }) => (
          <article key={label} className="rounded-[14px] border border-[#dfe5ea] bg-white p-4">
            <div className="flex items-center justify-between">
              <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-[#78818a]">
                {label}
              </p>
              <Icon size={15} className="text-[#0a66c2]" aria-hidden="true" />
            </div>
            <p className="mt-2 text-[23px] font-semibold text-[#1b2025]">{value}</p>
          </article>
        ))}
      </section>
      <section className="rounded-[16px] border border-[#dde4ea] bg-white shadow-[0_7px_22px_rgba(0,45,91,0.045)]">
        <header className="border-b border-[#e5e9ed] p-4 sm:p-5">
          <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-end">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.075em] text-[#0a66c2]">
                Traceability register
              </p>
              <h2 className="mt-1 text-[17px] font-semibold text-[#1b2025]">
                Coverage &amp; sources
              </h2>
              <p className="mt-1 text-[11px] text-[#747e88]">
                Every Word-document placement is mapped to its analytical chart record.
              </p>
            </div>
            <button
              type="button"
              onClick={() => onExport(placements)}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-[10px] border border-[#dce3e9] bg-white px-3 text-[11px] font-semibold text-[#3e4a55] hover:bg-[#f5f7f9]"
            >
              <Download size={14} aria-hidden="true" />
              Export visible rows
            </button>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            <label className="relative">
              <span className="sr-only">Search coverage</span>
              <Search
                size={14}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#8a939c]"
              />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search indicators, series, or sheets"
                className={cn(CONTROL, "w-full pl-9")}
              />
            </label>
            <select
              value={sector}
              onChange={(event) => setSector(event.target.value as "all" | DashboardViewId)}
              className={CONTROL}
              aria-label="Filter coverage by sector"
            >
              <option value="all">All sectors</option>
              <option value="mobile">Mobile Industry</option>
              <option value="fixed">Fixed Network</option>
              <option value="bwa">BWA</option>
            </select>
            <select
              value={sort}
              onChange={(event) => setSort(event.target.value as "source" | "title" | "section")}
              className={CONTROL}
              aria-label="Sort coverage"
            >
              <option value="source">Source order</option>
              <option value="title">Indicator A–Z</option>
              <option value="section">Sector and section</option>
            </select>
          </div>
        </header>
        {placements.length ? (
          <>
            <div className="hidden overflow-x-auto md:block">
              <table className="min-w-full border-collapse text-left text-[11px]">
                <caption className="sr-only">Word-document indicator coverage</caption>
                <thead className="bg-[#f5f7f9] text-[#59636d]">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Source</th>
                    <th className="px-4 py-3 font-semibold">Sector / section</th>
                    <th className="px-4 py-3 font-semibold">Indicator</th>
                    <th className="px-4 py-3 font-semibold">Series</th>
                    <th className="px-4 py-3 font-semibold">Source sheet</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {placements.map((item) => (
                    <tr key={item.id} className="border-t border-[#edf0f3] align-top">
                      <td className="whitespace-nowrap px-4 py-3 font-semibold text-[#0a66c2]">
                        #{String(item.sourceOrder).padStart(2, "0")}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-[#5a646e]">
                        {item.sector}
                        <br />
                        <span className="text-[#8a929a]">{item.section}</span>
                      </td>
                      <td className="min-w-[240px] px-4 py-3 font-medium text-[#2b3239]">
                        {item.graph}
                        {item.duplicatePlacement && (
                          <span className="ml-2 rounded-full bg-[#f1e9fb] px-2 py-0.5 text-[8px] font-semibold text-[#7541a9]">
                            repeated
                          </span>
                        )}
                      </td>
                      <td className="min-w-[220px] px-4 py-3 leading-5 text-[#68727c]">
                        {item.series.join(" · ")}
                      </td>
                      <td className="min-w-[200px] px-4 py-3 text-[#5c6670]">
                        {item.sourceSheet}
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1 rounded-full bg-[#e8f5ee] px-2 py-1 text-[9px] font-semibold text-[#176f4e]">
                          <Check size={10} aria-hidden="true" />
                          Mapped
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="divide-y divide-[#edf0f3] md:hidden">
              {placements.map((item) => (
                <article key={item.id} className="p-4">
                  <p className="text-[9px] font-semibold uppercase tracking-[0.055em] text-[#77818a]">
                    #{String(item.sourceOrder).padStart(2, "0")} · {item.sector} / {item.section}
                  </p>
                  <h3 className="mt-1.5 text-[12px] font-semibold leading-5 text-[#252b31]">
                    {item.graph}
                  </h3>
                  <p className="mt-1 text-[10px] leading-4 text-[#747e87]">
                    {item.series.join(" · ")}
                  </p>
                  <p className="mt-2 rounded-[8px] bg-[#f5f7f9] px-2.5 py-2 text-[9px] text-[#5f6973]">
                    {item.sourceSheet}
                  </p>
                </article>
              ))}
            </div>
          </>
        ) : (
          <div className="px-5 py-14 text-center">
            <FileSearch className="mx-auto text-[#9ca5ae]" size={26} aria-hidden="true" />
            <h3 className="mt-3 text-[13px] font-semibold text-[#3b444d]">No indicators found</h3>
            <p className="mt-1 text-[11px] text-[#7b848d]">Adjust the search or sector filter.</p>
          </div>
        )}
      </section>
      <section className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-[16px] border border-[#dde4ea] bg-white p-5">
          <div className="flex items-center gap-2">
            <BookOpen size={16} className="text-[#0a66c2]" aria-hidden="true" />
            <h2 className="text-[14px] font-semibold text-[#23292f]">Document-defined capabilities</h2>
          </div>
          <dl className="mt-4 grid gap-3">
            {dataset.commonElements.map((item) => (
              <div key={item.field} className="grid gap-1 border-b border-[#eef1f4] pb-3 last:border-0">
                <dt className="text-[10px] font-semibold text-[#4b5661]">{item.field}</dt>
                <dd className="text-[10px] leading-5 text-[#747e88]">
                  {item.field === "Granularity"
                    ? "Quarterly and curated yearly views are active. Monthly remains unavailable until a compatible upload supplies monthly observations."
                    : item.details}
                </dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="rounded-[16px] border border-[#dde4ea] bg-white p-5">
          <div className="flex items-center gap-2">
            <CircleAlert size={16} className="text-[#b67a00]" aria-hidden="true" />
            <h2 className="text-[14px] font-semibold text-[#23292f]">Data-quality notes</h2>
          </div>
          <ul className="mt-4 space-y-3 text-[10px] leading-5 text-[#6c7680]">
            {dataset.dataQualityNotes.map((note) => (
              <li key={note} className="flex gap-2">
                <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#d69b20]" />
                {note}
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}

export function IndustryDashboard() {
  const reduceMotion = useReducedMotion();
  const [dataset, setDataset] = useState<IndustryDashboardDataset | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [loadVersion, setLoadVersion] = useState(0);
  const [mode, setMode] = useState<DashboardMode>("analytics");
  const [activeView, setActiveView] = useState<DashboardViewId>("industry");
  const [activeSectionId, setActiveSectionId] = useState("industry-overview");
  const [range, setRange] = useState<Range>({ start: "", end: "" });
  const [granularity, setGranularity] = useState<Granularity>("quarterly");
  const [trendMode, setTrendMode] = useState<TrendMode>("absolute");
  const [operator, setOperator] = useState("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortMode>("source");
  const [globalTable, setGlobalTable] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [detailChart, setDetailChart] = useState<IndustryChart | null>(null);
  const [forecastOpen, setForecastOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [customOpen, setCustomOpen] = useState(false);
  const [overrides, setOverrides] = useState<WorkbookPreview["chartOverrides"]>({});
  const [uploadName, setUploadName] = useState("");
  const [customCharts, setCustomCharts] = useState<CustomChart[]>([]);
  const detailTrigger = useRef<HTMLButtonElement | null>(null);
  const baselineDataset = useRef<IndustryDashboardDataset | null>(null);

  useEffect(() => {
    let active = true;
    setLoadError(false);
    fetch("/data/industry-dashboard.json")
      .then((response) => {
        if (!response.ok) throw new Error("Dataset request failed.");
        return response.json() as Promise<IndustryDashboardDataset>;
      })
      .then((value) => {
        if (!active) return;
        baselineDataset.current = value;
        setDataset(value);
        const end = value.metadata.latestObservedPeriod;
        setRange({
          start: value.periods[Math.max(0, value.periods.length - 12)],
          end,
        });
      })
      .catch(() => {
        if (active) setLoadError(true);
      });
    return () => {
      active = false;
    };
  }, [loadVersion]);

  const charts = useMemo<IndustryChart[]>(
    () =>
      dataset?.charts.map((chart) =>
        overrides[chart.id]
          ? {
              ...chart,
              series: overrides[chart.id].series,
              shareSeries: overrides[chart.id].shareSeries,
              provenance: "uploaded" as const,
            }
          : { ...chart, provenance: "baseline" as const }
      ) ?? [],
    [dataset, overrides]
  );
  const chartMap = useMemo(
    () => new Map(charts.map((chart) => [chart.id, chart])),
    [charts]
  );

  const currentSector =
    activeView === "industry"
      ? null
      : dataset?.sectors.find((sector) => sector.id === activeView) ?? null;
  const sections =
    activeView === "industry"
      ? [{ id: "industry-overview", label: "Overview", chartIds: dataset?.industryOverview.chartIds ?? [] }]
      : currentSector?.sections ?? [];
  const activeSection =
    sections.find((section) => section.id === activeSectionId) ?? sections[0];
  const currentDefinition =
    activeView === "industry" ? dataset?.industryOverview : currentSector;
  const operatorNames = useMemo(
    () => dataset?.operators.map((item) => item.name) ?? [],
    [dataset]
  );

  useEffect(() => {
    if (!dataset) return;
    const nextSections =
      activeView === "industry"
        ? [{ id: "industry-overview", chartIds: dataset.industryOverview.chartIds }]
        : dataset.sectors.find((sector) => sector.id === activeView)?.sections ?? [];
    setActiveSectionId(nextSections[0]?.id ?? "");
    const count =
      activeView === "industry"
        ? dataset.industryOverview.defaultRange
        : Number.parseInt(
            dataset.sectors.find((sector) => sector.id === activeView)?.defaultRange ?? "10",
            10
          );
    setRange({
      start: dataset.periods[Math.max(0, dataset.periods.length - count)],
      end: dataset.metadata.latestObservedPeriod,
    });
    setSearch("");
    setOperator("all");
    setTrendMode("absolute");
  }, [activeView, dataset]);

  const visibleCharts = useMemo(() => {
    if (!dataset || !activeSection) return [];
    const term = search.trim().toLowerCase();
    const candidates = activeSection.chartIds
      .map((id) => chartMap.get(id))
      .filter((chart): chart is IndustryChart => Boolean(chart))
      .filter(
        (chart) =>
          !term ||
          [chart.title, chart.sourceSheet, ...chart.series.map((item) => item.name)]
            .join(" ")
            .toLowerCase()
            .includes(term)
      );
    return candidates.sort((a, b) => {
      if (sort === "title") return a.title.localeCompare(b.title);
      if (sort === "latest") {
        const aValue =
          getHeadlineMetric(a, range.end, operator, operatorNames).value ?? -Infinity;
        const bValue =
          getHeadlineMetric(b, range.end, operator, operatorNames).value ?? -Infinity;
        return bValue - aValue;
      }
      return sourceOrder(a) - sourceOrder(b);
    });
  }, [
    activeSection,
    chartMap,
    dataset,
    operator,
    operatorNames,
    range.end,
    search,
    sort,
  ]);

  const renderedCustomCharts = useMemo<IndustryChart[]>(
    () =>
      customCharts.flatMap((custom) => {
          const source = chartMap.get(custom.sourceChartId);
          if (!source) return [];
          const customChart: IndustryChart = {
            ...source,
            id: custom.id,
            title: custom.title,
            type: custom.type,
            presentation: {
              kind:
                custom.type === "area"
                  ? "gradientArea"
                  : custom.type === "bar"
                    ? "groupedBar"
                    : custom.type === "combo"
                      ? "combo"
                      : "lineBand",
              emphasis: "wide",
              showComposition: false,
              showRanking: false,
              averageBand: false,
            },
            series: source.series.filter((item) => custom.seriesNames.includes(item.name)),
            shareSeries: [],
            placementContexts: [],
            coverageIds: [],
            note: `Session-only custom view based on ${source.title}.`,
          };
          return [customChart];
        }),
    [chartMap, customCharts]
  );

  if (!dataset && !loadError) return <LoadingState />;
  if (!dataset || loadError) {
    return <ErrorState onRetry={() => setLoadVersion((value) => value + 1)} />;
  }

  const defaultForecastTitle =
    activeView === "industry"
      ? "Mobile Data Traffic"
      : currentSector?.defaultForecastMetric ?? "";
  const defaultForecastId =
    charts.find((chart) => chart.wordGraphTitle === defaultForecastTitle)?.id ??
    visibleCharts[0]?.id ??
    "";
  const viewLabel = currentDefinition?.label ?? "Industry";
  const metricCharts = visibleCharts.slice(0, activeView === "industry" ? 6 : 4);
  const hasUpload = Object.keys(overrides).length > 0;

  const exportCoverage = (placements: CoveragePlacement[]) => {
    downloadCsv("industry-dashboard-coverage.csv", [
      ["Source order", "Sector", "Section", "Indicator", "Series", "Source sheet", "Chart IDs", "Targets"],
      ...placements.map((item) => [
        item.sourceOrder,
        item.sector,
        item.section,
        item.graph,
        item.series.join("; "),
        item.sourceSheet,
        item.chartIds.join("; "),
        "Not supplied",
      ]),
    ]);
  };

  const exportVisible = () => {
    const rows: (string | number | null)[][] = [
      ["Dashboard", "Section", "Chart", "Unit", "Period", "Series", "Value", "Source workbook", "Source sheet", "Provenance"],
    ];
    for (const chart of visibleCharts) {
      const series = prepareSeries(chart, {
        shareMode: false,
        operator,
        operatorNames,
        granularity,
        trendMode,
      });
      const data = buildChartData(series, range, granularity);
      for (const datum of data) {
        for (const item of series) {
          rows.push([
            viewLabel,
            activeSection?.label ?? "Overview",
            chart.title,
            chartUnit(chart, trendMode, false),
            datum.period,
            item.name,
            typeof datum[item.name] === "number" ? (datum[item.name] as number) : null,
            chart.sourceWorkbook,
            chart.sourceSheet,
            chart.provenance ?? "baseline",
          ]);
        }
      }
    }
    downloadCsv(
      `industry-${activeView}-${range.end.replace(" ", "-")}.csv`,
      rows
    );
  };

  return (
    <div className="mx-auto w-full max-w-[1720px] space-y-4 pb-10">
      <header className="overflow-hidden rounded-[17px] border border-[#d9e1e8] bg-white shadow-[0_8px_26px_rgba(0,45,91,0.055)]">
        <div className="border-b border-[#e7ebef] px-4 py-4 sm:px-6 sm:py-5">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
            <div className="max-w-3xl">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#e7f7ef] px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.065em] text-[#13734e]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#16a36a]" aria-hidden="true" />
                  Workbook history
                </span>
                <span className="rounded-full bg-[#eef2f6] px-2.5 py-1 text-[9px] font-semibold text-[#64717d]">
                  Through {dataset.metadata.latestObservedPeriod}
                </span>
                {hasUpload && (
                  <span className="rounded-full bg-[#eee7f8] px-2.5 py-1 text-[9px] font-semibold text-[#6e3da0]">
                    Session override · {uploadName}
                  </span>
                )}
              </div>
              <h1 className="mt-3 text-[25px] font-semibold tracking-[-0.035em] text-[#15191d] sm:text-[30px]">
                Industry Dashboard
              </h1>
              <p className="mt-1.5 max-w-2xl text-[12px] leading-5 text-[#65707a]">
                Cross-sector telecommunications trends with Word-defined indicator
                coverage and workbook-level source lineage.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div
                className="flex rounded-[10px] border border-[#dce3e9] bg-[#f3f6f8] p-1"
                role="tablist"
                aria-label="Dashboard mode"
              >
                {[
                  ["analytics", PanelTop, "Analytics"],
                  ["coverage", BookOpen, "Coverage & Sources"],
                ].map(([value, Icon, label]) => (
                  <button
                    key={String(value)}
                    type="button"
                    role="tab"
                    aria-selected={mode === value}
                    onClick={() => setMode(value as DashboardMode)}
                    className={cn(
                      "inline-flex h-8 items-center gap-1.5 rounded-[7px] px-3 text-[10px] font-semibold transition",
                      mode === value
                        ? "bg-white text-[#173d64] shadow-sm"
                        : "text-[#6f7a85] hover:text-[#34414d]"
                    )}
                  >
                    <Icon size={13} aria-hidden="true" />
                    {String(label)}
                  </button>
                ))}
              </div>
              {mode === "analytics" && (
                <>
                  <button
                    type="button"
                    onClick={() => setUploadOpen(true)}
                    className="inline-flex h-10 items-center gap-2 rounded-[10px] border border-[#dce3e9] bg-white px-3 text-[10px] font-semibold text-[#40505f] hover:bg-[#f6f8fa]"
                  >
                    <Upload size={14} aria-hidden="true" />
                    Upload workbook
                  </button>
                  {hasUpload && (
                    <button
                      type="button"
                      onClick={() => setCustomOpen(true)}
                      className="inline-flex h-10 items-center gap-2 rounded-[10px] border border-[#d6c5ea] bg-[#f7f2fc] px-3 text-[10px] font-semibold text-[#6f3da2]"
                    >
                      <Plus size={14} aria-hidden="true" />
                      Custom chart
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        {mode === "analytics" && (
          <>
            <nav
              className="flex min-h-[80px] items-center gap-2 overflow-x-auto border-b border-[#e3e9ee] bg-[#fbfcfd] px-4 py-3 sm:min-h-[92px] sm:gap-3 sm:px-6 sm:py-4"
              role="tablist"
              aria-label="Industry dashboard sector"
            >
              {(Object.keys(VIEW_META) as DashboardViewId[]).map((view) => {
                const meta = VIEW_META[view];
                const Icon = meta.icon;
                return (
                  <button
                    key={view}
                    type="button"
                    role="tab"
                    aria-selected={activeView === view}
                    onClick={() => setActiveView(view)}
                    className={cn(
                      "flex h-12 shrink-0 items-center gap-2 rounded-[12px] border px-4 text-[11px] font-semibold transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0a66c2]/35 focus-visible:ring-offset-2 sm:h-14 sm:px-5 sm:text-[12px]",
                      activeView === view
                        ? "text-white shadow-[0_8px_20px_rgba(0,45,91,0.16)]"
                        : "border-[#dfe6ec] bg-white text-[#65717c] shadow-[0_2px_7px_rgba(0,45,91,0.035)] hover:border-[#bfd0df] hover:bg-[#f3f7fa] hover:text-[#263d52]"
                    )}
                    style={
                      activeView === view
                        ? {
                            backgroundColor: meta.color,
                            borderColor: meta.color,
                            boxShadow: `0 8px 20px ${meta.color}2b`,
                          }
                        : undefined
                    }
                  >
                    <Icon
                      size={16}
                      style={{ color: activeView === view ? "#ffffff" : meta.color }}
                      aria-hidden="true"
                    />
                    {meta.label}
                  </button>
                );
              })}
            </nav>
            <div className="flex flex-col gap-3 px-4 py-3 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0">
                <h2 className="text-[14px] font-semibold text-[#252b31]">
                  {activeView === "industry"
                    ? dataset.industryOverview.title
                    : currentSector?.dashboardTitle}
                </h2>
                <p className="mt-0.5 max-w-3xl text-[10px] leading-4 text-[#78818a]">
                  {currentDefinition?.scope}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="inline-flex h-9 items-center gap-2 rounded-[9px] border border-[#dce3e9] bg-white px-3 text-[10px] font-semibold text-[#465461] lg:hidden"
                  onClick={() => setFilterOpen(true)}
                >
                  <Filter size={13} aria-hidden="true" />
                  Filters
                </button>
                <button
                  type="button"
                  className={cn(
                    "inline-flex h-9 items-center gap-2 rounded-[9px] border px-3 text-[10px] font-semibold",
                    globalTable
                      ? "border-[#9bb9d7] bg-[#edf5fc] text-[#17538e]"
                      : "border-[#dce3e9] bg-white text-[#465461]"
                  )}
                  onClick={() => setGlobalTable((value) => !value)}
                  aria-pressed={globalTable}
                >
                  <Table2 size={13} aria-hidden="true" />
                  Data tables
                </button>
                <button
                  type="button"
                  className="inline-flex h-9 items-center gap-2 rounded-[9px] border border-[#dce3e9] bg-white px-3 text-[10px] font-semibold text-[#465461]"
                  onClick={exportVisible}
                >
                  <Download size={13} aria-hidden="true" />
                  Export view
                </button>
                <button
                  type="button"
                  className="inline-flex h-9 items-center gap-2 rounded-[9px] bg-[#0a66c2] px-3 text-[10px] font-semibold text-white shadow-sm"
                  onClick={() => setForecastOpen(true)}
                >
                  <Sparkles size={13} aria-hidden="true" />
                  Forecast
                </button>
                {hasUpload && (
                  <button
                    type="button"
                    className="inline-flex h-9 items-center gap-2 rounded-[9px] border border-[#e0d4ed] bg-[#faf7fd] px-3 text-[10px] font-semibold text-[#6f3e9d]"
                    onClick={() => {
                      setOverrides({});
                      setUploadName("");
                      setCustomCharts([]);
                      if (baselineDataset.current) {
                        const baseline = baselineDataset.current;
                        setDataset(baseline);
                        const count =
                          activeView === "industry"
                            ? baseline.industryOverview.defaultRange
                            : Number.parseInt(
                                baseline.sectors.find(
                                  (sector) => sector.id === activeView
                                )?.defaultRange ?? "10",
                                10
                              );
                        setRange({
                          start:
                            baseline.periods[
                              Math.max(0, baseline.periods.length - count)
                            ],
                          end: baseline.metadata.latestObservedPeriod,
                        });
                      }
                    }}
                  >
                    <RefreshCcw size={13} aria-hidden="true" />
                    Reset data
                  </button>
                )}
              </div>
            </div>
          </>
        )}
      </header>

      {mode === "coverage" ? (
        <CoverageView dataset={dataset} onExport={exportCoverage} />
      ) : (
        <>
          <section className="hidden rounded-[15px] border border-[#dce3e9] bg-white p-4 shadow-[0_5px_16px_rgba(0,45,91,0.035)] lg:block">
            <FilterControls
              dataset={dataset}
              range={range}
              setRange={setRange}
              granularity={granularity}
              setGranularity={setGranularity}
              trendMode={trendMode}
              setTrendMode={setTrendMode}
              operator={operator}
              setOperator={setOperator}
              search={search}
              setSearch={setSearch}
              sort={sort}
              setSort={setSort}
            />
          </section>

          <section className="flex gap-2 overflow-x-auto pb-0.5" aria-label="Indicator sections">
            {sections.map((section) => (
              <button
                key={section.id}
                type="button"
                onClick={() => setActiveSectionId(section.id)}
                className={cn(
                  "shrink-0 rounded-full border px-3.5 py-2 text-[10px] font-semibold transition",
                  activeSection?.id === section.id
                    ? "border-[#0a66c2] bg-[#0a66c2] text-white shadow-sm"
                    : "border-[#dce3e9] bg-white text-[#61707d] hover:border-[#b7c6d4]"
                )}
                aria-pressed={activeSection?.id === section.id}
              >
                {section.label}
                <span
                  className={cn(
                    "ml-2 rounded-full px-1.5 py-0.5 text-[8px]",
                    activeSection?.id === section.id ? "bg-white/18 text-white" : "bg-[#eef2f5] text-[#7b858e]"
                  )}
                >
                  {section.chartIds.length}
                </span>
              </button>
            ))}
          </section>

          {metricCharts.length > 0 && (
            <section
              className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 2xl:grid-cols-6"
              aria-label="Latest indicator values"
            >
              {metricCharts.map((chart, index) => (
                <MetricCard
                  key={chart.id}
                  chart={chart}
                  rangeEnd={range.end}
                  operator={operator}
                  operatorNames={operatorNames}
                  index={index}
                  reduceMotion={reduceMotion}
                />
              ))}
            </section>
          )}

          <section className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.075em] text-[#0a66c2]">
                {activeSection?.label ?? "Overview"} analysis
              </p>
              <h2 className="mt-1 text-[18px] font-semibold tracking-[-0.02em] text-[#1c2126]">
                {visibleCharts.length} {visibleCharts.length === 1 ? "indicator" : "indicators"} in view
              </h2>
            </div>
            <p className="text-[10px] text-[#78828b]">
              {granularity === "yearly" ? "Curated annual aggregation" : "Quarterly observations"} ·{" "}
              {range.start}–{range.end}
            </p>
          </section>

          {visibleCharts.length > 0 && (
            <InsightStrip
              charts={visibleCharts}
              rangeEnd={range.end}
              operator={operator}
              operatorNames={operatorNames}
            />
          )}

          {visibleCharts.length ? (
            <section
              className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-12"
              aria-label="Indicator charts"
            >
              {visibleCharts.map((chart, index) => {
                const heroIndex =
                  visibleCharts
                    .slice(0, index + 1)
                    .filter((item) => item.presentation.emphasis === "hero").length - 1;
                return (
                  <div key={chart.id} className={chartGridClass(chart, heroIndex)}>
                    <ChartCard
                      chart={chart}
                      range={range}
                      granularity={granularity}
                      trendMode={trendMode}
                      operator={operator}
                      operatorNames={operatorNames}
                      globalTable={globalTable}
                      reduceMotion={reduceMotion}
                      viewLabel={viewLabel}
                      onOperatorChange={setOperator}
                      onDetails={(selected, trigger) => {
                        detailTrigger.current = trigger;
                        setDetailChart(selected);
                      }}
                    />
                  </div>
                );
              })}
              {renderedCustomCharts.map((chart) => (
                <div key={chart.id} className="md:col-span-2 xl:col-span-6">
                  <ChartCard
                    chart={chart}
                    range={range}
                    granularity={granularity}
                    trendMode={trendMode}
                    operator={operator}
                    operatorNames={operatorNames}
                    globalTable={globalTable}
                    reduceMotion={reduceMotion}
                    viewLabel={`${viewLabel} · Custom`}
                    onOperatorChange={setOperator}
                    onDetails={(selected, trigger) => {
                      detailTrigger.current = trigger;
                      setDetailChart(selected);
                    }}
                  />
                </div>
              ))}
            </section>
          ) : (
            <section className="rounded-[16px] border border-dashed border-[#cfd8e0] bg-white px-5 py-16 text-center">
              <FileSearch className="mx-auto text-[#9aa4ad]" size={29} aria-hidden="true" />
              <h2 className="mt-3 text-[14px] font-semibold text-[#36404a]">No indicators match</h2>
              <p className="mt-1 text-[11px] text-[#7c858e]">
                Clear the search or choose another section.
              </p>
              <button
                type="button"
                className="mt-4 rounded-[9px] border border-[#d7dfe6] px-3 py-2 text-[10px] font-semibold text-[#50606e]"
                onClick={() => setSearch("")}
              >
                Clear search
              </button>
            </section>
          )}

          {visibleCharts.length > 0 && (
            <MetricSnapshotTable
              charts={visibleCharts}
              rangeEnd={range.end}
              operator={operator}
              operatorNames={operatorNames}
            />
          )}

          <section className="flex flex-col gap-3 rounded-[14px] border border-[#dce4ea] bg-[#f9fbfc] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-2">
              <Info size={15} className="mt-0.5 shrink-0 text-[#0a66c2]" aria-hidden="true" />
              <p className="text-[10px] leading-5 text-[#68747f]">
                Observations come from the authorized workbook-derived dataset. Indicator
                names, sections, definitions, and source sheets follow{" "}
                {dataset.metadata.sourceDocument}. Targets are not supplied.
              </p>
            </div>
            <button
              type="button"
              className="inline-flex shrink-0 items-center gap-1 text-[10px] font-semibold text-[#0a5cab]"
              onClick={() => setMode("coverage")}
            >
              Review source coverage
              <ChevronRight size={13} aria-hidden="true" />
            </button>
          </section>
        </>
      )}

      <AnimatePresence>
        {filterOpen && (
          <div className="fixed inset-0 z-[75] lg:hidden">
            <motion.button
              type="button"
              className="absolute inset-0 bg-[#001b35]/45"
              onClick={() => setFilterOpen(false)}
              aria-label="Close filters"
              initial={reduceMotion ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            />
            <motion.aside
              role="dialog"
              aria-modal="true"
              aria-label="Dashboard filters"
              className="absolute inset-x-0 bottom-0 max-h-[86vh] overflow-y-auto rounded-t-[20px] bg-white p-5 shadow-[0_-18px_45px_rgba(0,27,53,0.2)]"
              initial={reduceMotion ? false : { y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
            >
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <SlidersHorizontal size={16} className="text-[#0a66c2]" />
                  <h2 className="text-[15px] font-semibold text-[#22282e]">Dashboard filters</h2>
                </div>
                <button
                  type="button"
                  className={ICON_BUTTON}
                  onClick={() => setFilterOpen(false)}
                  aria-label="Close filters"
                >
                  <X size={16} />
                </button>
              </div>
              <FilterControls
                dataset={dataset}
                range={range}
                setRange={setRange}
                granularity={granularity}
                setGranularity={setGranularity}
                trendMode={trendMode}
                setTrendMode={setTrendMode}
                operator={operator}
                setOperator={setOperator}
                search={search}
                setSearch={setSearch}
                sort={sort}
                setSort={setSort}
              />
              <button
                type="button"
                className="mt-5 h-11 w-full rounded-[10px] bg-[#002d5b] text-[12px] font-semibold text-white"
                onClick={() => setFilterOpen(false)}
              >
                Apply filters
              </button>
            </motion.aside>
          </div>
        )}
      </AnimatePresence>

      <DetailDrawer
        chart={detailChart}
        open={Boolean(detailChart)}
        onClose={() => {
          setDetailChart(null);
          requestAnimationFrame(() => detailTrigger.current?.focus());
        }}
        range={range}
        granularity={granularity}
        trendMode={trendMode}
        operator={operator}
        operatorNames={operatorNames}
        reduceMotion={reduceMotion}
        charts={charts}
      />
      <ForecastDialog
        open={forecastOpen}
        onClose={() => setForecastOpen(false)}
        charts={visibleCharts.length ? visibleCharts : charts.filter((chart) => !chart.isSupporting)}
        defaultChartId={defaultForecastId}
        operator={operator}
        operatorNames={operatorNames}
        reduceMotion={reduceMotion}
      />
      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        dataset={{ ...dataset, charts }}
        reduceMotion={reduceMotion}
        onApply={(preview) => {
          setOverrides((current) => ({ ...current, ...preview.chartOverrides }));
          setUploadName(preview.fileName);
          setDataset((current) =>
            current
              ? {
                  ...current,
                  periods: sortPeriods([...new Set([...current.periods, ...preview.periods])]),
                  metadata: {
                    ...current.metadata,
                    latestObservedPeriod: preview.latestObservedPeriod,
                  },
                }
              : current
          );
          setRange((current) => ({
            ...current,
            end: preview.latestObservedPeriod,
          }));
        }}
      />
      <CustomChartDialog
        open={customOpen}
        onClose={() => setCustomOpen(false)}
        charts={charts}
        reduceMotion={reduceMotion}
        onAdd={(chart) => setCustomCharts((current) => [...current, chart])}
      />
    </div>
  );
}
