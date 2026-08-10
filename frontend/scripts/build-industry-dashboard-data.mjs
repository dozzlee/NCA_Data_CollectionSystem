import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(scriptDir, "..");
const workspaceDir = path.resolve(frontendDir, "..");
const referencePath = path.join(
  workspaceDir,
  ".analysis",
  "reference-zip",
  "statistical_dashboards-main-2",
  "data",
  "industry-dashboard-data.json"
);
const definitionPath = path.join(frontendDir, "data", "industry-indicators.json");
const outputPath = path.join(frontendDir, "public", "data", "industry-dashboard.json");
const coveragePath = path.join(
  frontendDir,
  "data",
  "INDUSTRY_DASHBOARD_COVERAGE.md"
);

const titleAliases = {
  "Average BWA Subscriptions": "BWA Data Usage per Subscription",
  "Average Mobile Internet Subscriptions": "Mobile Data Usage per Subscription",
  "Devices by Type": "Devices per Type",
  "Devices per Operator": "Devices per MNO",
  "Fibre Broadband Subscriptions and Market Share per Provider":
    "Fixed Broadband Subscriptions and Market Share per Operator",
  "Fibre Broadband Traffic per Provider": "Fixed Broadband Traffic per Operator",
  "Mobile Internet Data Traffic": "Mobile Data Traffic",
  "Mobile Internet Data Traffic per Operator": "Mobile Data Traffic per Operator",
  "Mobile Internet Prepaid and Postpaid Subscriptions":
    "Mobile Data Prepaid and Postpaid Subscriptions",
  "Mobile Internet Subscriptions and Market Share per Operator":
    "Mobile Data Subscriptions per Operator and Market Share",
  "Mobile Internet Subscriptions and Penetration Rate":
    "Mobile Data Subscriptions and Penetration Rate",
  "Mobile Internet Usage per Subscription": "Mobile Data Usage per Subscription",
  "Mobile Voice Minutes of Use per Subscription": "Minutes of Use per Subscription",
  "Off-Net Domestic Mobile Voice Traffic": "Off-Net Domestic Voice Traffic",
  "SMS per subscription": "SMS per Subscription",
  "Total Domestic Mobile Voice Traffic": "Total Domestic Voice Traffic",
  "Total Fibre Broadband Subscriptions": "Total Fixed Broadband Subscriptions",
};

const supportingParents = {
  "average-data-subscriptions": "mobile-data-usage-per-sub",
  "bwa-average-subscriptions": "bwa-data-usage-per-sub",
};

const overviewChartIds = [
  "voice-subs-market-share",
  "mobile-data-subs-penetration",
  "mobile-data-traffic",
  "fixed-bb-subs",
  "fixed-bb-traffic",
  "bwa-industry-total",
];

const presentation = (
  kind,
  emphasis = "standard",
  { showComposition = false, showRanking = false, averageBand = false } = {}
) => ({ kind, emphasis, showComposition, showRanking, averageBand });

const presentationMap = {
  "voice-subs-market-share": presentation("trendShare", "hero", {
    showComposition: true,
    showRanking: true,
  }),
  "voice-prepaid-postpaid": presentation("stackedArea", "wide", {
    showComposition: true,
  }),
  "domestic-voice-traffic": presentation("stackedArea", "hero"),
  "on-net-domestic-voice": presentation("gradientArea"),
  "off-net-domestic-voice": presentation("stackedBar", "wide"),
  "total-domestic-voice": presentation("gradientArea"),
  "domestic-voice-per-operator": presentation("ranking", "wide", {
    showRanking: true,
  }),
  "international-mobile-voice": presentation("groupedBar"),
  "minutes-of-use": presentation("lineBand", "wide", { averageBand: true }),
  sms: presentation("stackedArea", "hero"),
  "sms-per-subscription": presentation("lineBand", "wide", { averageBand: true }),
  "sms-off-net-per-mno": presentation("ranking", "wide", { showRanking: true }),
  "sms-on-net-per-mno": presentation("ranking", "wide", { showRanking: true }),
  "mobile-data-subs-penetration": presentation("combo", "hero"),
  "m2m-subscriptions": presentation("stackedBar", "wide"),
  "mobile-data-prepaid-postpaid": presentation("stackedArea", "wide", {
    showComposition: true,
  }),
  "mobile-data-subs-operator-share": presentation("trendShare", "hero", {
    showComposition: true,
    showRanking: true,
  }),
  "mobile-data-traffic": presentation("gradientArea", "hero"),
  "mobile-data-usage-per-sub": presentation("lineBand", "wide", {
    averageBand: true,
  }),
  "mobile-data-traffic-operator": presentation("stackedArea", "hero", {
    showRanking: true,
  }),
  "mobile-tariffs": presentation("lineBand", "hero", { averageBand: true }),
  "average-mobile-tariff-service": presentation("ranking", "wide", {
    showRanking: true,
  }),
  "devices-per-mno": presentation("ranking", "wide", { showRanking: true }),
  "device-types": presentation("stackedArea", "hero", {
    showComposition: true,
  }),
  "fixed-voice-subs-market-share": presentation("trendShare", "hero", {
    showComposition: true,
    showRanking: true,
  }),
  "fixed-voice-subs-penetration": presentation("combo", "wide"),
  "fixed-voice-traffic": presentation("stackedArea", "hero"),
  "fixed-voice-mou": presentation("lineBand", "wide", { averageBand: true }),
  "fixed-data-subs-market-share": presentation("trendShare", "hero", {
    showComposition: true,
    showRanking: true,
  }),
  "fixed-data-subs-penetration": presentation("combo", "wide"),
  "fixed-bb-subs": presentation("gradientArea", "hero"),
  "fixed-bb-per-operator": presentation("trendShare", "wide", {
    showComposition: true,
    showRanking: true,
  }),
  "fixed-bb-traffic": presentation("stackedArea", "hero", { showRanking: true }),
  "bwa-subs-penetration": presentation("combo", "hero"),
  "bwa-subs-operator": presentation("radialShare", "wide", {
    showComposition: true,
  }),
  "bwa-industry-total": presentation("groupedBar", "wide"),
  "bwa-traffic": presentation("gradientArea", "hero"),
  "bwa-traffic-operator": presentation("lineBand", "wide"),
  "bwa-data-usage-per-sub": presentation("lineBand", "wide", {
    averageBand: true,
  }),
};

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function slug(value) {
  return value
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function canonicalTitle(title) {
  return titleAliases[title] ?? title;
}

function seriesAggregation(chart, seriesName) {
  const label = `${chart.title} ${seriesName}`.toLowerCase();
  if (
    /penetration|market share|share|rate|per subscription|average|tariff|arpu|index/.test(
      label
    )
  ) {
    return "average";
  }
  if (
    chart.unit === "TB" ||
    chart.unit === "messages" ||
    (chart.unit === "minutes" && /traffic/.test(label))
  ) {
    return "sum";
  }
  return "yearEnd";
}

function normalizeSeries(chart, series) {
  const numericValues = series.values
    .map((point) => point.value)
    .filter((value) => typeof value === "number" && Number.isFinite(value));
  const percentSeries =
    chart.unit === "percent" ||
    /penetration|market share|share|rate/i.test(series.name);
  const percentMultiplier =
    percentSeries && numericValues.length && Math.max(...numericValues.map(Math.abs)) <= 1.5
      ? 100
      : 1;
  return {
    name: series.name,
    aggregation: seriesAggregation(chart, series.name),
    values: series.values.map((point) => ({
      period: point.quarter,
      value:
        typeof point.value === "number" && Number.isFinite(point.value)
          ? point.value * percentMultiplier
          : null,
    })),
  };
}

function mapChart(referenceChart, sourceWorkbooks, placements) {
  const wordTitle = canonicalTitle(referenceChart.title);
  const coverage = placements.filter((placement) => placement.graph === wordTitle);
  const isSupporting = Boolean(supportingParents[referenceChart.id]);

  return {
    id: referenceChart.id,
    title: isSupporting ? referenceChart.title.replace("Internet", "Data") : wordTitle,
    wordGraphTitle: wordTitle,
    sectorId: referenceChart.service,
    type: referenceChart.type,
    presentation:
      presentationMap[referenceChart.id] ??
      presentation(referenceChart.type === "bar" ? "groupedBar" : "gradientArea"),
    unit: referenceChart.unit,
    unitLabel: referenceChart.unitLabel ?? referenceChart.unit,
    axisLabel: referenceChart.axisLabel ?? referenceChart.unitLabel ?? referenceChart.unit,
    secondaryUnit: referenceChart.secondaryUnit ?? null,
    secondaryAxisLabel: referenceChart.secondaryAxisLabel ?? null,
    sourceSheet: referenceChart.sourceSheet,
    sourceWorkbook: sourceWorkbooks[referenceChart.service],
    note: referenceChart.note ?? "",
    annotations: referenceChart.annotations ?? [],
    series: (referenceChart.series ?? []).map((series) =>
      normalizeSeries(referenceChart, series)
    ),
    shareSeries: (referenceChart.shareSeries ?? []).map((series) => ({
      ...normalizeSeries({ ...referenceChart, unit: "percent" }, series),
      aggregation: "average",
    })),
    coverageIds: coverage.map((placement) => placement.id),
    placementContexts: coverage.map((placement) => ({
      sourceOrder: placement.sourceOrder,
      sectorId: placement.sectorId,
      sector: placement.sector,
      section: placement.section,
      sourceBlock: placement.sourceBlock,
    })),
    isSupporting,
    parentId: supportingParents[referenceChart.id] ?? null,
    supportingChartIds: [],
    hasTargets: false,
  };
}

function buildSections(definitions, charts) {
  return definitions.sectors.map((sector) => ({
    ...sector,
    sections: sector.indicatorSections.map((section) => {
      const graphTitles = new Set(
        definitions.placements
          .filter(
            (placement) =>
              placement.sectorId === sector.id && placement.section === section
          )
          .map((placement) => placement.graph)
      );
      return {
        id: `${sector.id}-${slug(section)}`,
        label: section,
        chartIds: charts
          .filter(
            (chart) =>
              chart.sectorId === sector.id &&
              !chart.isSupporting &&
              graphTitles.has(chart.wordGraphTitle)
          )
          .map((chart) => chart.id),
      };
    }),
  }));
}

function buildDataset() {
  const reference = readJson(referencePath);
  const definitions = readJson(definitionPath);

  if (reference.charts.length !== 41) {
    throw new Error(`Expected 41 reference chart records; found ${reference.charts.length}.`);
  }
  if (definitions.placements.length !== 50) {
    throw new Error(
      `Expected 50 Word-document placements; found ${definitions.placements.length}.`
    );
  }
  const distinctGraphs = new Set(
    definitions.placements.map((placement) => placement.graph)
  );
  if (distinctGraphs.size !== 39) {
    throw new Error(`Expected 39 distinct Word graphs; found ${distinctGraphs.size}.`);
  }

  const orderedPlacements = definitions.placements.map((placement, index) => ({
    ...placement,
    sourceOrder: index + 1,
  }));
  const charts = reference.charts.map((chart) =>
    mapChart(chart, reference.sourceWorkbooks, orderedPlacements)
  );
  const unmappedPresentations = charts
    .filter((chart) => !chart.isSupporting && !presentationMap[chart.id])
    .map((chart) => chart.id);
  if (unmappedPresentations.length) {
    throw new Error(
      `Missing presentation mapping for: ${unmappedPresentations.join(", ")}.`
    );
  }

  for (const chart of charts) {
    if (chart.parentId) {
      const parent = charts.find((candidate) => candidate.id === chart.parentId);
      if (!parent) throw new Error(`Missing parent chart ${chart.parentId}.`);
      parent.supportingChartIds.push(chart.id);
    }
  }

  for (const graph of distinctGraphs) {
    if (!charts.some((chart) => chart.wordGraphTitle === graph)) {
      throw new Error(`No workbook chart maps to Word graph "${graph}".`);
    }
  }

  const periodsWithData = new Set();
  for (const chart of charts) {
    for (const series of [...chart.series, ...chart.shareSeries]) {
      for (const point of series.values) {
        if (point.value !== null) periodsWithData.add(point.period);
      }
    }
  }
  const approvedEndIndex = reference.quarters.indexOf("Q4 2025");
  const periods = reference.quarters
    .slice(0, approvedEndIndex + 1)
    .filter((period) => periodsWithData.has(period));
  const latestObservedPeriod = periods.at(-1);
  if (latestObservedPeriod !== "Q4 2025") {
    throw new Error(
      `Expected latest observed period Q4 2025; found ${latestObservedPeriod}.`
    );
  }
  const approvedPeriods = new Set(periods);
  for (const chart of charts) {
    for (const series of [...chart.series, ...chart.shareSeries]) {
      series.values = series.values.filter((point) => approvedPeriods.has(point.period));
    }
  }

  const coverage = orderedPlacements.map((placement) => ({
    ...placement,
    chartIds: charts
      .filter((chart) => chart.wordGraphTitle === placement.graph)
      .map((chart) => chart.id),
  }));
  if (coverage.some((placement) => placement.chartIds.length === 0)) {
    throw new Error("At least one Word placement is not mapped to a workbook chart.");
  }

  return {
    metadata: {
      title: "NCA Industry Dashboard",
      sourceDocument: definitions.source.fileName,
      definitionAuthority: definitions.source.authority,
      datasetOrigin: "Workbook-derived history from the authorized ZIP reference",
      generatedFrom: reference.generatedFrom,
      reviewedAt: definitions.source.reviewedAt,
      latestObservedPeriod,
      targetsAvailable: false,
      monthlyDataAvailable: false,
      sourceWorkbooks: reference.sourceWorkbooks,
    },
    summary: {
      chartPlacements: definitions.summary.chartPlacements,
      distinctWordGraphs: definitions.summary.distinctGraphs,
      referenceChartRecords: charts.length,
      supportingMetrics: charts.filter((chart) => chart.isSupporting).length,
      indicatorSections: definitions.summary.indicatorSections,
      seriesMentions: definitions.summary.seriesMentions,
    },
    periods,
    operators: reference.operators,
    industryOverview: {
      id: "industry",
      label: "Industry Overview",
      title: "Telecommunications Industry Overview",
      scope:
        "A cross-sector view of mobile, fixed network, and broadband wireless access activity.",
      defaultRange: 12,
      chartIds: overviewChartIds,
    },
    sectors: buildSections(definitions, charts),
    charts,
    coverage,
    commonElements: definitions.commonElements,
    dataQualityNotes: [
      ...definitions.dataQualityNotes,
      "Historical observations are sourced from the authorized workbook-derived ZIP dataset, while indicator terminology and placement remain governed by the Word document.",
      "Targets were not supplied. Forecasts shown by the dashboard are model-derived planning estimates and are not official projections.",
      "Two workbook metrics (average mobile data subscriptions and average BWA subscriptions) are supporting series nested under their Word-defined usage-per-subscription indicators.",
    ],
  };
}

const dataset = buildDataset();
const serialized = `${JSON.stringify(dataset, null, 2)}\n`;
const coverageMarkdown = `# Industry Dashboard indicator coverage

Source definition authority: \`${dataset.metadata.sourceDocument}\`

- Chart placements mapped: ${dataset.summary.chartPlacements}/${dataset.summary.chartPlacements}
- Distinct Word-document graphs: ${dataset.summary.distinctWordGraphs}
- Workbook chart records: ${dataset.summary.referenceChartRecords} (${dataset.summary.supportingMetrics} supporting metrics)
- Historical observations: authorized workbook-derived dataset through ${dataset.metadata.latestObservedPeriod}
- Target data: not supplied

| # | Sector | Section | Source chart | Indicator graph | Source sheet | Dashboard location |
|---:|---|---|---|---|---|---|
${dataset.coverage
  .map(
    (item) =>
      `| ${item.sourceOrder} | ${item.sector} | ${item.section} | ${item.chartLabel} | ${item.graph} | ${item.sourceSheet} | Analytics → ${item.sector} → ${item.section} → ${item.graph}; Coverage & Sources row ${String(item.sourceOrder).padStart(2, "0")}${item.duplicatePlacement ? " (repeated placement)" : ""} |`
  )
  .join("\n")}
`;

if (process.argv.includes("--check")) {
  if (!fs.existsSync(outputPath)) {
    throw new Error(`Missing generated dataset: ${outputPath}`);
  }
  const existing = fs.readFileSync(outputPath, "utf8");
  if (existing !== serialized) {
    throw new Error(
      "Generated industry dashboard data is stale. Run the data build script."
    );
  }
  if (
    !fs.existsSync(coveragePath) ||
    fs.readFileSync(coveragePath, "utf8") !== coverageMarkdown
  ) {
    throw new Error(
      "Industry dashboard coverage checklist is stale. Run the data build script."
    );
  }
  console.log(
    `Industry data valid: ${dataset.summary.chartPlacements} placements, ${dataset.summary.distinctWordGraphs} Word graphs, ${dataset.summary.referenceChartRecords} reference charts.`
  );
} else {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, serialized);
  fs.writeFileSync(coveragePath, coverageMarkdown);
  console.log(`Wrote ${outputPath}`);
  console.log(`Wrote ${coveragePath}`);
}
