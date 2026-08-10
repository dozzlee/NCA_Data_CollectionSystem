import {
  ChartDatum,
  Granularity,
  HeadlineMetric,
  IndicatorSeries,
  IndustryChart,
  TrendMode,
} from "./types";
import { CHART_COLORS } from "./visuals";

export const PALETTE = [
  CHART_COLORS.blue,
  CHART_COLORS.violet,
  CHART_COLORS.teal,
  CHART_COLORS.amber,
  CHART_COLORS.coral,
  CHART_COLORS.slate,
  CHART_COLORS.green,
  "#d052a7",
];

const OPERATOR_ALIASES: Record<string, string> = {
  vodafone: "Telecel",
  airteltigo: "AT",
};

export function normalizeName(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

export function displayOperatorName(value: string) {
  return OPERATOR_ALIASES[normalizeName(value)] ?? value;
}

export function periodYear(period: string) {
  const match = period.match(/(20\d{2})/);
  return match ? Number(match[1]) : Number.NaN;
}

export function periodQuarter(period: string) {
  const match = period.match(/Q([1-4])/i);
  return match ? Number(match[1]) : 0;
}

export function periodIndex(period: string) {
  return periodYear(period) * 4 + periodQuarter(period) - 1;
}

export function sortPeriods(periods: string[]) {
  return [...periods].sort((a, b) => periodIndex(a) - periodIndex(b));
}

export function nextQuarter(period: string, offset = 1) {
  const absolute = periodIndex(period) + offset;
  const year = Math.floor(absolute / 4);
  const quarter = (absolute % 4) + 1;
  return `Q${quarter} ${year}`;
}

function aggregateSeries(series: IndicatorSeries): IndicatorSeries {
  const buckets = new Map<number, number[]>();
  for (const point of series.values) {
    if (point.value === null) continue;
    const year = periodYear(point.period);
    const bucket = buckets.get(year) ?? [];
    bucket.push(point.value);
    buckets.set(year, bucket);
  }

  return {
    ...series,
    values: [...buckets.entries()]
      .sort(([a], [b]) => a - b)
      .map(([year, values]) => {
        let value: number;
        if (series.aggregation === "sum") {
          value = values.reduce((total, item) => total + item, 0);
        } else if (series.aggregation === "average") {
          value = values.reduce((total, item) => total + item, 0) / values.length;
        } else {
          value = values.at(-1) ?? 0;
        }
        return { period: String(year), value };
      }),
  };
}

function transformSeries(
  series: IndicatorSeries,
  mode: TrendMode,
  granularity: Granularity
): IndicatorSeries {
  if (mode === "absolute") return series;
  const yearOffset = granularity === "quarterly" ? 4 : 1;
  const first = series.values.find((point) => point.value !== null)?.value ?? null;

  return {
    ...series,
    values: series.values.map((point, index) => {
      if (point.value === null) return point;
      if (mode === "index") {
        return {
          ...point,
          value: first && first !== 0 ? (point.value / first) * 100 : null,
        };
      }
      const offset = mode === "yoy" ? yearOffset : 1;
      const previous = series.values[index - offset]?.value ?? null;
      return {
        ...point,
        value:
          previous !== null && previous !== 0
            ? ((point.value - previous) / Math.abs(previous)) * 100
            : null,
      };
    }),
  };
}

export function chartUnit(chart: IndustryChart, mode: TrendMode, shareMode: boolean) {
  if (mode === "qoq" || mode === "yoy") return "%";
  if (mode === "index") return "index";
  if (shareMode) return "%";
  return chart.unit;
}

export function selectChartSeries(
  chart: IndustryChart,
  shareMode: boolean,
  operator: string,
  operatorNames: string[]
) {
  let series = shareMode && chart.shareSeries.length ? chart.shareSeries : chart.series;
  if (operator === "all") return series;

  const normalizedOperator = normalizeName(operator);
  const operatorSet = new Set(operatorNames.map(normalizeName));
  const hasOperatorSeries = series.some((item) =>
    operatorSet.has(normalizeName(displayOperatorName(item.name)))
  );
  if (!hasOperatorSeries) return series;

  series = series.filter(
    (item) =>
      normalizeName(displayOperatorName(item.name)) === normalizedOperator ||
      /industry total|total traffic|total$/i.test(item.name)
  );
  return series;
}

export function prepareSeries(
  chart: IndustryChart,
  options: {
    shareMode: boolean;
    operator: string;
    operatorNames: string[];
    granularity: Granularity;
    trendMode: TrendMode;
  }
) {
  const selected = selectChartSeries(
    chart,
    options.shareMode,
    options.operator,
    options.operatorNames
  );
  return selected.map((series) =>
    transformSeries(
      options.granularity === "yearly" ? aggregateSeries(series) : series,
      options.trendMode,
      options.granularity
    )
  );
}

export function buildChartData(
  series: IndicatorSeries[],
  range: { start: string; end: string },
  granularity: Granularity
) {
  const startIndex =
    granularity === "quarterly" ? periodIndex(range.start) : periodYear(range.start);
  const endIndex =
    granularity === "quarterly" ? periodIndex(range.end) : periodYear(range.end);
  const periods = sortPeriods(
    Array.from(new Set(series.flatMap((item) => item.values.map((point) => point.period))))
  ).filter((period) => {
    const index =
      granularity === "quarterly" ? periodIndex(period) : Number.parseInt(period, 10);
    return index >= startIndex && index <= endIndex;
  });

  return periods.map((period) => {
    const datum: ChartDatum = { period };
    for (const item of series) {
      datum[item.name] =
        item.values.find((point) => point.period === period)?.value ?? null;
    }
    return datum;
  });
}

function isOperatorSeries(seriesName: string, operatorNames: string[]) {
  const normalized = normalizeName(displayOperatorName(seriesName));
  return operatorNames.some((name) => normalizeName(name) === normalized);
}

export function getHeadlineMetric(
  chart: IndustryChart,
  endPeriod: string,
  operator: string,
  operatorNames: string[]
): HeadlineMetric {
  const series = selectChartSeries(chart, false, operator, operatorNames);
  const periodPosition = chart.series[0]?.values.findIndex(
    (point) => point.period === endPeriod
  );
  const index = periodPosition === undefined || periodPosition < 0 ? 0 : periodPosition;
  const preferred = series.find((item) =>
    /^(industry total|total |bwa subscriptions|usage per subscription|sms per subscription)/i.test(
      item.name
    )
  );
  const operatorSeries = series.filter((item) =>
    isOperatorSeries(item.name, operatorNames)
  );
  const selected =
    preferred ??
    (operatorSeries.length === 1 ? operatorSeries[0] : series.length === 1 ? series[0] : null);

  const valueAt = (offset: number) => {
    if (selected) return selected.values[index - offset]?.value ?? null;
    if (operatorSeries.length) {
      const values = operatorSeries
        .map((item) => item.values[index - offset]?.value)
        .filter((value): value is number => typeof value === "number");
      return values.length ? values.reduce((sum, value) => sum + value, 0) : null;
    }
    return series[0]?.values[index - offset]?.value ?? null;
  };

  return {
    value: valueAt(0),
    previous: valueAt(1),
    yearAgo: valueAt(4),
    period: endPeriod,
    seriesName: selected?.name ?? (operatorSeries.length ? "Operator total" : series[0]?.name ?? ""),
    derivedFromSum: !selected && operatorSeries.length > 1,
  };
}

export function percentChange(value: number | null, previous: number | null) {
  if (value === null || previous === null || previous === 0) return null;
  return ((value - previous) / Math.abs(previous)) * 100;
}

export function formatValue(
  value: number | null,
  unit: string,
  options: { compact?: boolean; signed?: boolean } = {}
) {
  if (value === null || !Number.isFinite(value)) return "Not available";
  const prefix = options.signed && value > 0 ? "+" : "";
  if (unit === "%") return `${prefix}${value.toFixed(1)}%`;
  if (unit === "index") return `${value.toFixed(1)}`;
  if (unit === "GHS") {
    return new Intl.NumberFormat("en-GH", {
      style: "currency",
      currency: "GHS",
      maximumFractionDigits: value < 10 ? 2 : 1,
      notation: options.compact ? "compact" : "standard",
    }).format(value);
  }
  const formatted = new Intl.NumberFormat("en-GB", {
    notation: options.compact ? "compact" : "standard",
    maximumFractionDigits: options.compact ? 1 : value < 100 ? 2 : 0,
  }).format(value);
  if (unit === "TB" || unit === "GB") return `${prefix}${formatted} ${unit}`;
  return `${prefix}${formatted}`;
}

export function forecastSeries(series: IndicatorSeries, horizon: number) {
  const history = series.values
    .filter((point): point is { period: string; value: number } => point.value !== null)
    .slice(-8);
  if (history.length < 2) return [];

  const n = history.length;
  const xMean = (n - 1) / 2;
  const yMean = history.reduce((sum, point) => sum + point.value, 0) / n;
  let numerator = 0;
  let denominator = 0;
  history.forEach((point, index) => {
    numerator += (index - xMean) * (point.value - yMean);
    denominator += (index - xMean) ** 2;
  });
  const slope = denominator ? numerator / denominator : 0;
  const intercept = yMean - slope * xMean;
  const lastPeriod = history.at(-1)?.period ?? "";

  return Array.from({ length: horizon }, (_, index) => ({
    period: nextQuarter(lastPeriod, index + 1),
    value: Math.max(0, intercept + slope * (n + index)),
  }));
}

export function csvCell(value: string | number | null) {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

export function downloadCsv(fileName: string, rows: (string | number | null)[][]) {
  const content = rows.map((row) => row.map(csvCell).join(",")).join("\n");
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
