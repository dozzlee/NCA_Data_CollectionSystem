"use client";

import {
  Area,
  AreaChart,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  Pie,
  PieChart,
  RadialBar,
  RadialBarChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  TooltipProps,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowDownRight, ArrowUpRight, Database } from "lucide-react";
import { ChartDatum, IndicatorSeries, IndustryChart } from "@/lib/industry-dashboard/types";
import {
  displayOperatorName,
  formatValue,
  normalizeName,
  percentChange,
} from "@/lib/industry-dashboard/analytics";
import {
  CHART_COLORS,
  RECHARTS_AXIS,
  chartAccent,
  seriesColor,
  seriesDash,
} from "@/lib/industry-dashboard/visuals";
import { cn } from "@/lib/utils";

type OperatorChange = (operator: string) => void;

type ReferenceChartProps = {
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
  onOperatorChange?: OperatorChange;
  forecastStart?: string;
};

type TooltipExtraProps = {
  unit: string;
  provenance: string;
  combo: boolean;
};

function AnalyticalTooltip({
  active,
  payload,
  label,
  unit,
  provenance,
  combo,
}: TooltipProps<number, string> & TooltipExtraProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="min-w-[168px] rounded-[11px] border border-[#dce3e9] bg-white/95 p-3 shadow-[0_14px_36px_rgba(0,45,91,0.14)] backdrop-blur">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[10px] font-semibold text-[#26323d]">{String(label ?? "")}</p>
        <span className="rounded-full bg-[#eef3f7] px-2 py-0.5 text-[8px] font-semibold text-[#65717d]">
          {provenance}
        </span>
      </div>
      <div className="mt-2 space-y-1.5">
        {payload.map((item, index) => {
          const name = String(item.name ?? "");
          const value = typeof item.value === "number" ? item.value : Number(item.value);
          const itemUnit = combo && /penetration|rate|share/i.test(name) ? "%" : unit;
          return (
            <div key={`${name}-${index}`} className="flex items-center justify-between gap-4">
              <span className="flex min-w-0 items-center gap-1.5 text-[9px] text-[#66717c]">
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: item.color ?? seriesColor(name, index) }}
                  aria-hidden="true"
                />
                <span className="truncate">{name}</span>
              </span>
              <span className="shrink-0 text-[10px] font-semibold text-[#1e2933] tabular-nums">
                {formatValue(Number.isFinite(value) ? value : null, itemUnit)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function EmptyChart({ height }: { height: number }) {
  return (
    <div
      className="flex items-center justify-center rounded-[12px] border border-dashed border-[#d5dce3] bg-[#fafbfc]"
      style={{ height }}
    >
      <div className="max-w-xs px-5 text-center">
        <Database className="mx-auto text-[#99a2ab]" size={24} aria-hidden="true" />
        <p className="mt-3 text-[12px] font-semibold text-[#4f5964]">
          No observations in this selection
        </p>
        <p className="mt-1 text-[10px] leading-4 text-[#7b838c]">
          Widen the period range, clear the operator filter, or upload a compatible workbook.
        </p>
      </div>
    </div>
  );
}

function operatorForSeries(name: string, operatorNames: string[]) {
  const normalized = normalizeName(displayOperatorName(name));
  return operatorNames.find((operator) => normalizeName(operator) === normalized) ?? null;
}

function clickOperator(
  name: string,
  operatorNames: string[],
  activeOperator: string,
  onOperatorChange?: OperatorChange
) {
  const operator = operatorForSeries(name, operatorNames);
  if (!operator || !onOperatorChange) return;
  onOperatorChange(normalizeName(operator) === normalizeName(activeOperator) ? "all" : operator);
}

function visibleSeries(series: IndicatorSeries[], hidden: Set<string>) {
  return series.filter((item) => !hidden.has(item.name));
}

function hasValues(data: ChartDatum[], series: IndicatorSeries[]) {
  return data.some((datum) =>
    series.some((item) => typeof datum[item.name] === "number")
  );
}

function averageValue(data: ChartDatum[], series: IndicatorSeries[]) {
  const values = data.flatMap((datum) =>
    series
      .map((item) => datum[item.name])
      .filter((value): value is number => typeof value === "number")
  );
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}

function TemporalChart({
  chart,
  series,
  data,
  hidden,
  unit,
  height,
  reduceMotion,
  activeOperator = "all",
  operatorNames = [],
  onOperatorChange,
  forecastStart,
}: ReferenceChartProps & { height: number }) {
  const visible = visibleSeries(series, hidden);
  if (!hasValues(data, visible)) return <EmptyChart height={height} />;
  const kind = chart.presentation.kind;
  const combo = kind === "combo";
  const totalPattern = /total|industry total/i;
  const average = chart.presentation.averageBand ? averageValue(data, visible) : null;
  const gradientId = `industry-gradient-${chart.id.replace(/[^a-z0-9]/gi, "-")}`;

  return (
    <div
      role="img"
      aria-label={`${chart.title}. ${visible.map((item) => item.name).join(", ")} from ${
        data[0]?.period ?? "the first available period"
      } to ${data.at(-1)?.period ?? "the latest available period"}.`}
      style={{ height }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 14, right: combo ? 8 : 14, bottom: 2, left: -10 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={seriesColor(visible[0]?.name ?? "", 0)} stopOpacity={0.3} />
              <stop offset="100%" stopColor={seriesColor(visible[0]?.name ?? "", 0)} stopOpacity={0.015} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 5" vertical={false} />
          <XAxis
            dataKey="period"
            {...RECHARTS_AXIS}
            minTickGap={28}
            padding={{ left: 4, right: 4 }}
          />
          <YAxis
            yAxisId="left"
            {...RECHARTS_AXIS}
            axisLine={false}
            tickFormatter={(value) => formatValue(Number(value), unit, { compact: true })}
            width={64}
          />
          {combo && (
            <YAxis
              yAxisId="right"
              orientation="right"
              {...RECHARTS_AXIS}
              axisLine={false}
              tickFormatter={(value) => `${Number(value).toFixed(0)}%`}
              width={40}
            />
          )}
          <Tooltip
            cursor={{ stroke: "#9cadbc", strokeDasharray: "3 3" }}
            content={
              <AnalyticalTooltip
                unit={unit}
                provenance={chart.provenance === "uploaded" ? "Uploaded" : "Baseline"}
                combo={combo}
              />
            }
          />
          {average !== null && (
            <ReferenceLine
              yAxisId="left"
              y={average}
              stroke="#97a5b2"
              strokeDasharray="5 5"
              label={{ value: "8-period avg", fill: "#778490", fontSize: 9, position: "insideTopRight" }}
            />
          )}
          {forecastStart && (
            <ReferenceLine
              x={forecastStart}
              yAxisId="left"
              stroke={CHART_COLORS.violet}
              strokeDasharray="4 4"
              label={{ value: "Estimate", fill: CHART_COLORS.violet, fontSize: 9 }}
            />
          )}
          {visible.map((item, index) => {
            const color = seriesColor(item.name, index);
            const secondary = combo && /penetration|rate|share/i.test(item.name);
            const isTotal = totalPattern.test(item.name);
            const shared = {
              dataKey: item.name,
              yAxisId: secondary ? "right" : "left",
              isAnimationActive: !reduceMotion,
              onClick: () =>
                clickOperator(
                  item.name,
                  operatorNames,
                  activeOperator,
                  onOperatorChange
                ),
            };

            if (
              kind === "groupedBar" ||
              (kind === "stackedBar" && !isTotal) ||
              (combo && !secondary)
            ) {
              return (
                <Bar
                  key={item.name}
                  {...shared}
                  fill={color}
                  stackId={kind === "stackedBar" && !isTotal ? "stack" : undefined}
                  radius={[4, 4, 0, 0]}
                  maxBarSize={32}
                  opacity={0.92}
                />
              );
            }
            if (kind === "stackedArea" && !isTotal) {
              return (
                <Area
                  key={item.name}
                  {...shared}
                  type="monotone"
                  stackId="stack"
                  stroke={color}
                  fill={color}
                  fillOpacity={0.2}
                  strokeWidth={1.8}
                  connectNulls={false}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              );
            }
            if (kind === "gradientArea" || (kind === "stackedArea" && isTotal)) {
              if (kind === "stackedArea" && isTotal) {
                return (
                  <Line
                    key={item.name}
                    {...shared}
                    type="monotone"
                    stroke={CHART_COLORS.ink}
                    strokeWidth={2.3}
                    connectNulls={false}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                );
              }
              return (
                <Area
                  key={item.name}
                  {...shared}
                  type="monotone"
                  stroke={color}
                  fill={`url(#${gradientId})`}
                  strokeWidth={2.2}
                  connectNulls={false}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              );
            }
            return (
              <Line
                key={item.name}
                {...shared}
                type="monotone"
                stroke={color}
                strokeWidth={secondary || isTotal ? 2.4 : 2}
                strokeDasharray={
                  forecastStart && index === visible.length - 1
                    ? "5 4"
                    : seriesDash(index)
                }
                connectNulls={false}
                dot={false}
                activeDot={{ r: 4 }}
              />
            );
          })}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

type RankingItem = {
  name: string;
  value: number;
  previous: number | null;
  color: string;
};

function rankingItems(data: ChartDatum[], series: IndicatorSeries[]) {
  const latest = data.at(-1);
  const previous = data.at(-2);
  if (!latest) return [];
  return series
    .map((item, index): RankingItem | null => {
      const value = latest[item.name];
      if (typeof value !== "number" || /industry total|^total/i.test(item.name)) return null;
      return {
        name: item.name,
        value,
        previous: typeof previous?.[item.name] === "number" ? (previous[item.name] as number) : null,
        color: seriesColor(item.name, index),
      };
    })
    .filter((item): item is RankingItem => Boolean(item))
    .sort((a, b) => b.value - a.value);
}

export function LatestRanking({
  data,
  series,
  unit,
  activeOperator = "all",
  operatorNames = [],
  onOperatorChange,
  compact = false,
}: {
  data: ChartDatum[];
  series: IndicatorSeries[];
  unit: string;
  activeOperator?: string;
  operatorNames?: string[];
  onOperatorChange?: OperatorChange;
  compact?: boolean;
}) {
  const items = rankingItems(data, series);
  const max = items[0]?.value ?? 1;
  if (!items.length) return null;
  return (
    <div className={cn("space-y-2.5", compact && "space-y-2")} aria-label="Latest series ranking">
      {items.slice(0, compact ? 5 : 8).map((item, index) => {
        const change = percentChange(item.value, item.previous);
        const operator = operatorForSeries(item.name, operatorNames);
        const selected =
          operator && normalizeName(operator) === normalizeName(activeOperator);
        const className = cn(
              "grid w-full grid-cols-[20px_minmax(0,1fr)_auto] items-center gap-2 rounded-[9px] px-1.5 py-1 text-left transition",
              operator && "hover:bg-[#f3f7fa] focus:outline-none focus:ring-2 focus:ring-[#0a66c2]/20",
              selected && "bg-[#edf5fc]"
            );
        const content = (
          <>
            <span className="text-[9px] font-semibold text-[#89939d]">{index + 1}</span>
            <span className="min-w-0">
              <span className="flex items-center justify-between gap-2 text-[10px]">
                <span className="truncate font-semibold text-[#3f4b56]">{item.name}</span>
                <span className="shrink-0 font-semibold text-[#27343f] tabular-nums">
                  {formatValue(item.value, unit, { compact: true })}
                </span>
              </span>
              <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-[#edf1f4]">
                <span
                  className="block h-full rounded-full"
                  style={{
                    width: `${Math.max(4, (item.value / max) * 100)}%`,
                    backgroundColor: item.color,
                  }}
                />
              </span>
            </span>
            <span
              className={cn(
                "inline-flex min-w-10 items-center justify-end gap-0.5 text-[8px] font-semibold",
                change === null
                  ? "text-[#98a0a8]"
                  : change >= 0
                    ? "text-[#16835c]"
                    : "text-[#b4232c]"
              )}
            >
              {change !== null &&
                (change >= 0 ? (
                  <ArrowUpRight size={10} aria-hidden="true" />
                ) : (
                  <ArrowDownRight size={10} aria-hidden="true" />
                ))}
              {change === null ? "—" : `${Math.abs(change).toFixed(1)}%`}
            </span>
          </>
        );
        return operator ? (
          <button
            key={item.name}
            type="button"
            onClick={() =>
              clickOperator(item.name, operatorNames, activeOperator, onOperatorChange)
            }
            aria-pressed={Boolean(selected)}
            className={className}
          >
            {content}
          </button>
        ) : (
          <div key={item.name} className={className}>
            {content}
          </div>
        );
      })}
    </div>
  );
}

function CompositionPanel({
  data,
  series,
  unit,
  activeOperator,
  operatorNames,
  onOperatorChange,
  radial = false,
}: {
  data: ChartDatum[];
  series: IndicatorSeries[];
  unit: string;
  activeOperator: string;
  operatorNames: string[];
  onOperatorChange?: OperatorChange;
  radial?: boolean;
}) {
  const latest = data.at(-1);
  if (!latest) return null;
  const values = series
    .map((item, index) => ({
      name: item.name,
      value: typeof latest[item.name] === "number" ? (latest[item.name] as number) : 0,
      color: seriesColor(item.name, index),
    }))
    .filter((item) => item.value > 0 && !/^total|industry total/i.test(item.name));
  const total = values.reduce((sum, item) => sum + item.value, 0);
  if (!values.length || total <= 0) return null;
  const percentageValues =
    unit === "%"
      ? values
      : values.map((item) => ({ ...item, value: (item.value / total) * 100 }));

  if (radial) {
    const first = percentageValues[0];
    return (
      <div className="relative h-[190px]" role="img" aria-label={`${first.name} share ${first.value.toFixed(1)}%`}>
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            innerRadius="72%"
            outerRadius="98%"
            startAngle={90}
            endAngle={-270}
            data={[{ ...first, fill: first.color }]}
          >
            <RadialBar dataKey="value" cornerRadius={10} background={{ fill: "#eef2f5" }} />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-[25px] font-semibold tracking-[-0.04em] text-[#1b2630]">
            {first.value.toFixed(1)}%
          </span>
          <span className="mt-1 max-w-24 text-[9px] font-semibold text-[#6e7984]">
            {first.name} share
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="grid min-w-0 grid-cols-[150px_minmax(0,1fr)] items-center gap-2">
      <div className="relative h-[160px]" role="img" aria-label={`Latest composition for ${latest.period}`}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={percentageValues}
              dataKey="value"
              nameKey="name"
              innerRadius={45}
              outerRadius={67}
              paddingAngle={1}
              stroke="#fff"
              strokeWidth={2}
              onClick={(item) =>
                clickOperator(
                  String(item.name ?? ""),
                  operatorNames,
                  activeOperator,
                  onOperatorChange
                )
              }
            >
              {percentageValues.map((item) => (
                <Cell key={item.name} fill={item.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value) => [`${Number(value).toFixed(1)}%`, "Share"]}
              contentStyle={{
                borderRadius: 10,
                border: "1px solid #dce3e9",
                fontSize: 10,
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[15px] font-semibold text-[#1c2833]">{latest.period}</span>
          <span className="text-[8px] font-semibold uppercase tracking-[0.08em] text-[#89939d]">
            composition
          </span>
        </div>
      </div>
      <div className="space-y-2">
        {percentageValues.slice(0, 7).map((item) => (
          <button
            key={item.name}
            type="button"
            onClick={() =>
              clickOperator(item.name, operatorNames, activeOperator, onOperatorChange)
            }
            className="grid w-full grid-cols-[8px_minmax(0,1fr)_auto] items-center gap-2 rounded-md text-left text-[9px] focus:outline-none focus:ring-2 focus:ring-[#0a66c2]/20"
          >
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} />
            <span className="truncate text-[#66717c]">{item.name}</span>
            <span className="font-semibold text-[#27343f]">{item.value.toFixed(1)}%</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function ReferenceChartVisual(props: ReferenceChartProps) {
  const {
    chart,
    series,
    data,
    hidden,
    unit,
    height = 280,
    compositionSeries = [],
    compositionData = [],
    activeOperator = "all",
    operatorNames = [],
    onOperatorChange,
  } = props;
  const visible = visibleSeries(series, hidden);
  const kind = chart.presentation.kind;

  if (kind === "ranking") {
    return (
      <div style={{ minHeight: height }} className="flex items-center">
        <div className="w-full">
          <LatestRanking
            data={data}
            series={visible}
            unit={unit}
            activeOperator={activeOperator}
            operatorNames={operatorNames}
            onOperatorChange={onOperatorChange}
          />
        </div>
      </div>
    );
  }

  if (kind === "trendShare" || chart.presentation.showComposition) {
    const compositionSource = compositionData.length ? compositionData : data;
    const compositionItems = compositionSeries.length ? compositionSeries : visible;
    return (
      <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1.35fr)_minmax(270px,.65fr)]">
        <TemporalChart {...props} height={height} />
        <div className="flex min-w-0 items-center rounded-[12px] bg-[#f8fafc] px-3 py-2">
          <CompositionPanel
            data={compositionSource}
            series={compositionItems}
            unit={compositionSeries.length ? "%" : unit}
            activeOperator={activeOperator}
            operatorNames={operatorNames}
            onOperatorChange={onOperatorChange}
            radial={kind === "radialShare"}
          />
        </div>
      </div>
    );
  }

  if (kind === "radialShare") {
    return (
      <div className="grid gap-3 md:grid-cols-[minmax(0,1.4fr)_220px]">
        <TemporalChart {...props} height={height} />
        <CompositionPanel
          data={compositionData.length ? compositionData : data}
          series={compositionSeries.length ? compositionSeries : visible}
          unit={compositionSeries.length ? "%" : unit}
          activeOperator={activeOperator}
          operatorNames={operatorNames}
          onOperatorChange={onOperatorChange}
          radial
        />
      </div>
    );
  }

  return (
    <div>
      <TemporalChart {...props} height={height} />
      {chart.presentation.showRanking && (
        <div className="mt-3 border-t border-[#edf1f4] pt-3">
          <LatestRanking
            data={data}
            series={visible}
            unit={unit}
            activeOperator={activeOperator}
            operatorNames={operatorNames}
            onOperatorChange={onOperatorChange}
            compact
          />
        </div>
      )}
    </div>
  );
}

export function MetricSparkline({
  chart,
  series,
  color = chartAccent(0),
  reduceMotion,
}: {
  chart: IndustryChart;
  series: IndicatorSeries | null;
  color?: string;
  reduceMotion: boolean | null;
}) {
  const data =
    series?.values
      .filter((point): point is { period: string; value: number } => point.value !== null)
      .slice(-12) ?? [];
  const gradientId = `metric-spark-${chart.id.replace(/[^a-z0-9]/gi, "-")}`;
  if (data.length < 2) return <div className="h-10" aria-hidden="true" />;
  return (
    <div className="h-10" role="img" aria-label={`${chart.title} twelve-period sparkline`}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 1, bottom: 0, left: 1 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.26} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.8}
            fill={`url(#${gradientId})`}
            dot={false}
            connectNulls={false}
            isAnimationActive={!reduceMotion}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ForecastVisual({
  chart,
  series,
  forecasts,
  reduceMotion,
}: {
  chart: IndustryChart;
  series: IndicatorSeries[];
  forecasts: { name: string; values: { period: string; value: number }[] }[];
  reduceMotion: boolean | null;
}) {
  const history = series.map((item) => ({
    ...item,
    values: item.values
      .filter((point): point is { period: string; value: number } => point.value !== null)
      .slice(-8),
  }));
  const periods = [
    ...new Set([
      ...history.flatMap((item) => item.values.map((point) => point.period)),
      ...forecasts.flatMap((item) => item.values.map((point) => point.period)),
    ]),
  ];
  const data = periods.map((period) => {
    const datum: ChartDatum = { period };
    history.forEach((item) => {
      datum[`${item.name} history`] =
        item.values.find((point) => point.period === period)?.value ?? null;
    });
    forecasts.forEach((item) => {
      const historyItem = history.find((candidate) => candidate.name === item.name);
      const lastHistory = historyItem?.values.at(-1);
      datum[`${item.name} estimate`] =
        item.values.find((point) => point.period === period)?.value ??
        (lastHistory?.period === period ? lastHistory.value : null);
    });
    return datum;
  });
  const forecastStart = forecasts[0]?.values[0]?.period;
  if (!data.length || !forecastStart) return <EmptyChart height={260} />;

  return (
    <div
      className="h-[260px]"
      role="img"
      aria-label={`${chart.title} historical observations and planning estimates`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 14, right: 16, bottom: 2, left: -8 }}>
          <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="period" {...RECHARTS_AXIS} minTickGap={22} />
          <YAxis
            {...RECHARTS_AXIS}
            axisLine={false}
            tickFormatter={(value) => formatValue(Number(value), chart.unit, { compact: true })}
            width={66}
          />
          <Tooltip
            content={
              <AnalyticalTooltip
                unit={chart.unit}
                provenance="Planning estimate"
                combo={false}
              />
            }
          />
          <ReferenceLine
            x={forecastStart}
            stroke={CHART_COLORS.violet}
            strokeDasharray="4 4"
            label={{ value: "Estimate", fill: CHART_COLORS.violet, fontSize: 9 }}
          />
          {history.map((item, index) => (
            <Line
              key={`${item.name}-history`}
              type="monotone"
              dataKey={`${item.name} history`}
              stroke={seriesColor(item.name, index)}
              strokeWidth={2.2}
              dot={false}
              connectNulls={false}
              isAnimationActive={!reduceMotion}
            />
          ))}
          {forecasts.map((item, index) => (
            <Line
              key={`${item.name}-estimate`}
              type="monotone"
              dataKey={`${item.name} estimate`}
              stroke={seriesColor(item.name, index)}
              strokeWidth={2.2}
              strokeDasharray="6 5"
              dot={{ r: 2.5 }}
              connectNulls={false}
              isAnimationActive={!reduceMotion}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
