import type { CellValue, Worksheet } from "exceljs";
import type {
  IndicatorSeries,
  IndustryChart,
  IndustryDashboardDataset,
  WorkbookPreview,
} from "./types";
import { normalizeName } from "./analytics";

const MAX_FILE_BYTES = 20 * 1024 * 1024;

function cellPrimitive(value: CellValue): string | number | Date | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "string" || typeof value === "number" || value instanceof Date) {
    return value;
  }
  if (typeof value === "object") {
    if ("result" in value) return cellPrimitive(value.result as CellValue);
    if ("text" in value && typeof value.text === "string") return value.text;
    if ("richText" in value && Array.isArray(value.richText)) {
      return value.richText.map((item) => item.text).join("");
    }
  }
  return String(value);
}

function toQuarter(value: string | number | Date | null) {
  if (value instanceof Date) {
    return `Q${Math.floor(value.getUTCMonth() / 3) + 1} ${value.getUTCFullYear()}`;
  }
  if (typeof value !== "string") return null;
  const quarter = value.match(/Q\s*([1-4])\D+(20\d{2})/i);
  if (quarter) return `Q${quarter[1]} ${quarter[2]}`;
  const reversed = value.match(/(20\d{2})\D+Q\s*([1-4])/i);
  if (reversed) return `Q${reversed[2]} ${reversed[1]}`;
  return null;
}

function worksheetMatrix(sheet: Worksheet) {
  const rows: (string | number | Date | null)[][] = [];
  sheet.eachRow({ includeEmpty: false }, (row) => {
    const values = Array.isArray(row.values) ? row.values.slice(1) : [];
    rows.push(values.map((value) => cellPrimitive(value as CellValue)));
  });
  return rows;
}

function sheetMatches(sourceSheet: string, workbookSheet: string) {
  const expected = normalizeName(sourceSheet);
  const actual = normalizeName(workbookSheet);
  return (
    expected === actual ||
    expected.startsWith(actual) ||
    actual.startsWith(expected) ||
    (expected.length > 12 && actual.includes(expected.slice(0, 12)))
  );
}

function labelMatches(value: unknown, expected: string) {
  if (typeof value !== "string") return false;
  const actual = normalizeName(value);
  const target = normalizeName(expected);
  if (!actual || !target) return false;
  return actual === target || actual.includes(target) || target.includes(actual);
}

function horizontalPeriods(
  matrix: ReturnType<typeof worksheetMatrix>
): { row: number; columns: { column: number; period: string }[] } | null {
  let best: { row: number; columns: { column: number; period: string }[] } | null = null;
  matrix.forEach((cells, row) => {
    const columns = cells
      .map((cell, column) => ({ column, period: toQuarter(cell) }))
      .filter((item): item is { column: number; period: string } => Boolean(item.period));
    if (columns.length >= 2 && (!best || columns.length > best.columns.length)) {
      best = { row, columns };
    }
  });
  return best;
}

function verticalPeriods(
  matrix: ReturnType<typeof worksheetMatrix>
): { column: number; rows: { row: number; period: string }[] } | null {
  const maxColumns = Math.max(0, ...matrix.map((row) => row.length));
  let best: { column: number; rows: { row: number; period: string }[] } | null = null;
  for (let column = 0; column < maxColumns; column += 1) {
    const rows = matrix
      .map((cells, row) => ({ row, period: toQuarter(cells[column] ?? null) }))
      .filter((item): item is { row: number; period: string } => Boolean(item.period));
    if (rows.length >= 2 && (!best || rows.length > best.rows.length)) {
      best = { column, rows };
    }
  }
  return best;
}

function numberValue(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value !== "string") return null;
  const parsed = Number(value.replace(/[,%\s]/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function periodIndex(period: string) {
  const match = period.match(/^Q([1-4])\s+(\d{4})$/);
  return match ? Number(match[2]) * 4 + Number(match[1]) - 1 : -1;
}

function sortObservations(values: IndicatorSeries["values"]) {
  return [...values].sort((a, b) => periodIndex(a.period) - periodIndex(b.period));
}

function parseHorizontal(
  matrix: ReturnType<typeof worksheetMatrix>,
  series: IndicatorSeries[]
) {
  const periods = horizontalPeriods(matrix);
  if (!periods) return { series, updated: 0 };
  let updated = 0;
  const next = series.map((item) => {
    const rowIndex = matrix.findIndex(
      (row, index) =>
        index !== periods.row && row.slice(0, Math.min(5, row.length)).some((cell) => labelMatches(cell, item.name))
    );
    if (rowIndex < 0) return item;
    const parsed = periods.columns
      .map(({ column, period }) => ({
        period,
        value: numberValue(matrix[rowIndex]?.[column]),
      }))
      .filter((point): point is { period: string; value: number } => point.value !== null);
    if (!parsed.length) return item;
    updated += 1;
    return {
      ...item,
      values: sortObservations(parsed),
    };
  });
  return { series: next, updated };
}

function parseVertical(
  matrix: ReturnType<typeof worksheetMatrix>,
  series: IndicatorSeries[]
) {
  const periods = verticalPeriods(matrix);
  if (!periods) return { series, updated: 0 };
  const firstDataRow = Math.min(...periods.rows.map((item) => item.row));
  const headerRows = matrix.slice(0, firstDataRow);
  let updated = 0;
  const next = series.map((item) => {
    let seriesColumn = -1;
    for (let row = headerRows.length - 1; row >= 0 && seriesColumn < 0; row -= 1) {
      seriesColumn = headerRows[row].findIndex((cell) => labelMatches(cell, item.name));
    }
    if (seriesColumn < 0) return item;
    const parsed = periods.rows
      .map(({ row, period }) => ({
        period,
        value: numberValue(matrix[row]?.[seriesColumn]),
      }))
      .filter((point): point is { period: string; value: number } => point.value !== null);
    if (!parsed.length) return item;
    updated += 1;
    return {
      ...item,
      values: sortObservations(parsed),
    };
  });
  return { series: next, updated };
}

function parseChartSheet(sheet: Worksheet, chart: IndustryChart) {
  const matrix = worksheetMatrix(sheet);
  const parseGroup = (series: IndicatorSeries[]) => {
    const horizontal = parseHorizontal(matrix, series);
    if (horizontal.updated) return horizontal;
    return parseVertical(matrix, series);
  };
  const normalizePercentSeries = (
    series: IndicatorSeries[],
    forcePercent = false
  ) =>
    series.map((item) => {
      const isPercent =
        forcePercent ||
        chart.unit === "percent" ||
        (chart.secondaryUnit === "percent" &&
          /penetration|market share|percentage/i.test(item.name));
      if (!isPercent) return item;
      return {
        ...item,
        values: item.values.map((point) => ({
          ...point,
          value:
            typeof point.value === "number" &&
            Math.abs(point.value) > 0 &&
            Math.abs(point.value) <= 1.5
              ? point.value * 100
              : point.value,
        })),
      };
    });

  const primary = parseGroup(chart.series);
  const shareSeries = chart.shareSeries.map((share) => {
    const source = primary.series.find((item) => item.name === share.name);
    if (!source) return share;
    return {
      ...share,
      values: source.values.map((point) => {
        const total = primary.series.reduce((sum, item) => {
          const value = item.values.find((candidate) => candidate.period === point.period)?.value;
          return sum + (typeof value === "number" ? value : 0);
        }, 0);
        return {
          period: point.period,
          value:
            typeof point.value === "number" && total > 0
              ? (point.value / total) * 100
              : null,
        };
      }),
    };
  });
  return {
    series: normalizePercentSeries(primary.series),
    shareSeries,
    updated: primary.updated + (primary.updated ? shareSeries.length : 0),
  };
}

export async function parseIndustryWorkbook(
  file: File,
  dataset: IndustryDashboardDataset
): Promise<WorkbookPreview> {
  if (file.size > MAX_FILE_BYTES) {
    throw new Error("The workbook exceeds the 20 MB browser upload limit.");
  }
  if (!file.name.toLowerCase().endsWith(".xlsx")) {
    throw new Error("Choose an .xlsx workbook.");
  }

  const ExcelJS = await import("exceljs");
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(await file.arrayBuffer());

  const recognizedSheets = new Set<string>();
  const chartOverrides: WorkbookPreview["chartOverrides"] = {};
  const warnings: string[] = [];
  let updatedSeries = 0;

  for (const chart of dataset.charts.filter((item) => !item.isSupporting)) {
    const sheet = workbook.worksheets.find((candidate) =>
      sheetMatches(chart.sourceSheet, candidate.name)
    );
    if (!sheet) continue;
    recognizedSheets.add(sheet.name);
    const parsed = parseChartSheet(sheet, chart);
    if (parsed.updated) {
      chartOverrides[chart.id] = {
        series: parsed.series,
        shareSeries: parsed.shareSeries,
      };
      updatedSeries += parsed.updated;
    } else {
      warnings.push(
        `${sheet.name}: recognized for ${chart.title}, but no matching quarterly series rows were found.`
      );
    }
  }

  if (!recognizedSheets.size) {
    throw new Error(
      "No recognized source sheets were found. Use the NCA workbook sheet names listed in Coverage & Sources."
    );
  }
  if (!Object.keys(chartOverrides).length) {
    throw new Error(
      "The workbook sheets were recognized, but no chart values could be mapped."
    );
  }

  const totalPrimaryCharts = dataset.charts.filter((chart) => !chart.isSupporting).length;
  if (Object.keys(chartOverrides).length < totalPrimaryCharts) {
    warnings.unshift(
      `${Object.keys(chartOverrides).length} of ${totalPrimaryCharts} analytical charts can be updated; unmatched charts will retain baseline values and remain labeled accordingly.`
    );
  }

  const periods = [
    ...new Set(
      Object.values(chartOverrides).flatMap((override) =>
        [...override.series, ...override.shareSeries].flatMap((series) =>
          series.values.map((point) => point.period)
        )
      )
    ),
  ].sort((a, b) => periodIndex(a) - periodIndex(b));

  return {
    fileName: file.name,
    recognizedSheets: [...recognizedSheets],
    updatedChartIds: Object.keys(chartOverrides),
    updatedSeries,
    periods,
    latestObservedPeriod: periods.at(-1) ?? dataset.metadata.latestObservedPeriod,
    warnings,
    chartOverrides,
  };
}
