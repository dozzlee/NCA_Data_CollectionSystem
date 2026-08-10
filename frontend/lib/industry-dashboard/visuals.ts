export const CHART_COLORS = {
  blue: "#1677ff",
  indigo: "#4f5bd5",
  violet: "#8b4ad8",
  teal: "#00a39b",
  amber: "#f4ad00",
  coral: "#e25555",
  green: "#4b9f45",
  slate: "#617384",
  ink: "#18354f",
  grid: "#e8edf2",
  muted: "#73808c",
};

export const OPERATOR_COLORS: Record<string, string> = {
  mtn: "#f4ad00",
  telecel: "#e5484d",
  vodafone: "#e5484d",
  at: "#11a1b5",
  airteltigo: "#11a1b5",
  airtel: "#d052a7",
  tigo: "#7b55d9",
  glo: "#4b9f45",
  expresso: "#e67f22",
  telesol: "#1677ff",
};

const GENERAL_PALETTE = [
  CHART_COLORS.blue,
  CHART_COLORS.violet,
  CHART_COLORS.teal,
  CHART_COLORS.amber,
  CHART_COLORS.coral,
  CHART_COLORS.green,
  CHART_COLORS.indigo,
  CHART_COLORS.slate,
];

const DASH_PATTERNS = [undefined, "7 4", "2 3", "10 4 2 4"];

function normalizeKey(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

export function seriesColor(name: string, index = 0) {
  const normalized = normalizeKey(name);
  if (/industrytotal|totaltraffic|totalsubscriptions|^total$/.test(normalized)) {
    return CHART_COLORS.ink;
  }
  const operator = Object.entries(OPERATOR_COLORS).find(([key]) =>
    normalized.includes(key)
  );
  return operator?.[1] ?? GENERAL_PALETTE[index % GENERAL_PALETTE.length];
}

export function seriesDash(index: number) {
  return DASH_PATTERNS[index % DASH_PATTERNS.length];
}

export function chartAccent(index: number) {
  return GENERAL_PALETTE[index % GENERAL_PALETTE.length];
}

export const RECHARTS_AXIS = {
  tick: { fill: CHART_COLORS.muted, fontSize: 10 },
  axisLine: { stroke: "#dce3e9" },
  tickLine: false,
};

