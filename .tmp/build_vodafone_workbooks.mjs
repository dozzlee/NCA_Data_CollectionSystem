import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const sourcePath = "C:/Users/dozzl/Downloads/NCA_Monthly_Report.xlsx";
const manifestPath = "C:/Users/dozzl/OneDrive/Documents/testing and fixing/.tmp/vodafone_values_manifest.json";
const outputDir = "C:/Users/dozzl/OneDrive/Documents/testing and fixing/outputs/vodafone-monthly-2026";
const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(sourcePath));

const sheetNames = workbook.worksheets.items.map((sheet) => sheet.name);
const entriesBySheet = new Map(sheetNames.map((name) => [name, []]));
for (const entry of manifest.entries) {
  if (!entriesBySheet.has(entry.sheet)) throw new Error(`Unknown worksheet ${entry.sheet}`);
  entriesBySheet.get(entry.sheet).push(entry);
}

function dateHeaderRow(sheet) {
  const values = sheet.getRange("A1:AS6").values;
  for (let row = 0; row < values.length; row += 1) {
    const dateCount = values[row].slice(5).filter((value) => typeof value === "number" && value > 40000 && value < 60000).length;
    if (dateCount >= 3) return row;
  }
  throw new Error(`Could not locate date header row for ${sheet.name}`);
}

function buildColumn(sheet, periodDate, valueKey, selectedOnly = false) {
  const rows = Array.from({ length: 432 }, () => [null]);
  rows[dateHeaderRow(sheet)][0] = periodDate;
  for (const entry of entriesBySheet.get(sheet.name)) {
    if (selectedOnly && !entry.selected_half) continue;
    rows[entry.row - 1][0] = entry[valueKey];
  }
  return rows;
}

function formatPeriodColumn(sheet, column) {
  sheet.getRange(`${column}1:${column}432`).format.numberFormat = "#,##0.00";
  sheet.getCell(dateHeaderRow(sheet), column === "AT" ? 45 : 46).setNumberFormat("mmm-yy");
}

function countPopulated(valueKey, selectedOnly = false) {
  return manifest.entries.filter((entry) => (!selectedOnly || entry.selected_half) && entry[valueKey] !== null && entry[valueKey] !== "").length;
}

await fs.mkdir(outputDir, { recursive: true });

for (const sheet of workbook.worksheets.items) {
  sheet.getRange("AT1:AT432").copyFrom(sheet.getRange("AS1:AS432"), "all");
  sheet.getRange("AT1:AT432").values = buildColumn(sheet, new Date(Date.UTC(2026, 8, 23)), "september");
  formatPeriodColumn(sheet, "AT");
}

if (countPopulated("september") !== 281) throw new Error("September does not contain all 281 requested indicators.");
let output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/NCA_Monthly_Report_Vodafone_September_2026.xlsx`);

for (const sheet of workbook.worksheets.items) {
  sheet.getRange("AU1:AU432").copyFrom(sheet.getRange("AT1:AT432"), "all");
  sheet.getRange("AU1:AU432").values = buildColumn(sheet, new Date(Date.UTC(2026, 9, 23)), "october", true);
  formatPeriodColumn(sheet, "AU");
}
if (countPopulated("october", true) !== 141) throw new Error("October half-filled variant does not contain 141 indicators.");
output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/NCA_Monthly_Report_Vodafone_October_2026_Half_Filled.xlsx`);

for (const sheet of workbook.worksheets.items) {
  sheet.getRange("AU1:AU432").values = buildColumn(sheet, new Date(Date.UTC(2026, 9, 23)), "october_absurd");
  formatPeriodColumn(sheet, "AU");
}
if (countPopulated("october_absurd") !== 281) throw new Error("October absurd-growth variant does not contain all 281 requested indicators.");

const mobileChecks = manifest.entries
  .filter((entry) => entry.is_mobile_subscription)
  .map((entry) => ({ code: entry.field_code, september: entry.september, october: entry.october_absurd, ratio: entry.october_absurd / entry.september }));
if (!mobileChecks.length || mobileChecks.some((item) => item.ratio < 1000)) {
  throw new Error("Absurd-growth mobile subscription values were not applied consistently.");
}

const subscriptionCheck = await workbook.inspect({
  kind: "table",
  sheetId: "Subscriptions",
  range: "C1:AU70",
  include: "values,formulas",
  tableMaxRows: 70,
  tableMaxCols: 47,
  tableMaxCellChars: 80,
  maxChars: 18000,
});
console.log("SUBSCRIPTION_CHECK");
console.log(subscriptionCheck.ndjson);

const deviceCheck = await workbook.inspect({
  kind: "table",
  sheetId: "Device Brands",
  range: "C75:AU130",
  include: "values,formulas",
  tableMaxRows: 56,
  tableMaxCols: 47,
  tableMaxCellChars: 80,
  maxChars: 14000,
});
console.log("DEVICE_CHECK");
console.log(deviceCheck.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log("FORMULA_ERRORS");
console.log(errors.ndjson);

const previewSubscriptions = await workbook.render({ sheetName: "Subscriptions", range: "C1:AU70", scale: 1.25, format: "png" });
await fs.writeFile(`${outputDir}/preview_subscriptions.png`, new Uint8Array(await previewSubscriptions.arrayBuffer()));
const previewDevices = await workbook.render({ sheetName: "Device Brands", range: "C75:AU130", scale: 1.25, format: "png" });
await fs.writeFile(`${outputDir}/preview_device_brands.png`, new Uint8Array(await previewDevices.arrayBuffer()));

output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/NCA_Monthly_Report_Vodafone_October_2026_Absurd_Growth.xlsx`);

console.log(JSON.stringify({
  outputDir,
  septemberCount: countPopulated("september"),
  octoberHalfCount: countPopulated("october", true),
  octoberFullCount: countPopulated("october_absurd"),
  mobileChecks,
}, null, 2));
