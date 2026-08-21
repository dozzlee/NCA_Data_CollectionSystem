export type SectorId = "mobile" | "fixed" | "bwa";
export type DashboardViewId = "industry" | SectorId;
export type ChartKind = "line" | "area" | "bar" | "combo";
export type DashboardVisualKind =
  | "gradientArea"
  | "stackedArea"
  | "groupedBar"
  | "stackedBar"
  | "ranking"
  | "trendShare"
  | "combo"
  | "radialShare"
  | "lineBand";
export type ChartEmphasis = "hero" | "wide" | "standard" | "compact";
export type AggregationMode = "yearEnd" | "sum" | "average";
export type Granularity = "monthly" | "quarterly" | "yearly";
export type TrendMode = "absolute" | "qoq" | "yoy" | "index";
export type SortMode = "source" | "title" | "latest";
export type Provenance = "baseline" | "uploaded";

export type Observation = {
  period: string;
  value: number | null;
};

export type IndicatorSeries = {
  name: string;
  aggregation: AggregationMode;
  values: Observation[];
};

export type ChartAnnotation = {
  quarter: string;
  label: string;
  detail: string;
};

export type PlacementContext = {
  sourceOrder: number;
  sectorId: SectorId;
  sector: string;
  section: string;
  sourceBlock: number;
};

export type ChartPresentation = {
  kind: DashboardVisualKind;
  emphasis: ChartEmphasis;
  showComposition: boolean;
  showRanking: boolean;
  averageBand: boolean;
};

export type IndustryChart = {
  id: string;
  title: string;
  wordGraphTitle: string;
  sectorId: SectorId;
  type: ChartKind;
  presentation: ChartPresentation;
  unit: string;
  unitLabel: string;
  axisLabel: string;
  secondaryUnit: string | null;
  secondaryAxisLabel: string | null;
  sourceSheet: string;
  sourceWorkbook: string;
  note: string;
  annotations: ChartAnnotation[];
  series: IndicatorSeries[];
  shareSeries: IndicatorSeries[];
  coverageIds: string[];
  placementContexts: PlacementContext[];
  isSupporting: boolean;
  parentId: string | null;
  supportingChartIds: string[];
  hasTargets: false;
  provenance?: Provenance;
};

export type SectionDefinition = {
  id: string;
  label: string;
  chartIds: string[];
};

export type SectorDefinition = {
  id: SectorId;
  label: string;
  dashboardTitle: string;
  scope: string;
  defaultRange: string;
  defaultForecastMetric: string;
  indicatorSections: string[];
  sections: SectionDefinition[];
};

export type CoveragePlacement = {
  id: string;
  sourceOrder: number;
  sourceBlock: number;
  sectorId: SectorId;
  sector: string;
  section: string;
  chartLabel: string;
  graph: string;
  series: string[];
  sourceSheet: string;
  unit: string | null;
  periodValuesAvailable: boolean;
  targetsAvailable: boolean;
  sourceStatus: string;
  duplicatePlacement: boolean;
  placementContexts: string[];
  chartIds: string[];
};

export type IndustryDashboardDataset = {
  metadata: {
    title: string;
    sourceDocument: string;
    definitionAuthority: string;
    datasetOrigin: string;
    generatedFrom: string;
    reviewedAt: string;
    latestObservedPeriod: string;
    targetsAvailable: false;
    monthlyDataAvailable: false;
    sourceWorkbooks: Record<SectorId, string>;
  };
  summary: {
    chartPlacements: number;
    distinctWordGraphs: number;
    referenceChartRecords: number;
    supportingMetrics: number;
    indicatorSections: number;
    seriesMentions: number;
  };
  periods: string[];
  operators: {
    name: string;
    color: string;
    note?: string;
    activeFrom?: string;
    activeTo?: string;
    successor?: string;
  }[];
  industryOverview: {
    id: "industry";
    label: string;
    title: string;
    scope: string;
    defaultRange: number;
    chartIds: string[];
  };
  sectors: SectorDefinition[];
  charts: IndustryChart[];
  coverage: CoveragePlacement[];
  commonElements: { field: string; details: string }[];
  dataQualityNotes: string[];
};

export type ChartDatum = {
  period: string;
  [seriesName: string]: string | number | null;
};

export type HeadlineMetric = {
  value: number | null;
  previous: number | null;
  yearAgo: number | null;
  period: string | null;
  seriesName: string;
  derivedFromSum: boolean;
};

export type WorkbookPreview = {
  fileName: string;
  recognizedSheets: string[];
  updatedChartIds: string[];
  updatedSeries: number;
  periods: string[];
  latestObservedPeriod: string;
  warnings: string[];
  chartOverrides: Record<
    string,
    {
      series: IndicatorSeries[];
      shareSeries: IndicatorSeries[];
    }
  >;
};

export type CustomChart = {
  id: string;
  title: string;
  sourceChartId: string;
  seriesNames: string[];
  type: ChartKind;
};
