import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load("C:/Users/dozzl/Downloads/NCA_Monthly_Report.xlsx"));
const excelDate = (serial) => typeof serial === "number"
  ? new Date(Date.UTC(1899, 11, 30) + serial * 86400000).toISOString().slice(0, 10)
  : serial;
const columnName = (index) => {
  let name = "";
  for (let n = index + 1; n > 0; n = Math.floor((n - 1) / 26)) name = String.fromCharCode(65 + ((n - 1) % 26)) + name;
  return name;
};

for (const sheetName of ["Subscriptions", "Device Brands", "Consumer Behaviour", "Network Parameters", "SMS Counts", "Pricing ARPU", "Domestic Traffic", "International Traffic", "West Africa", "Top10 Intl", "OTT Data", "Mobile Money"]) {
  const sheet = workbook.worksheets.getItem(sheetName);
  const values = sheet.getRange("A1:AT432").values;
  const dateRows = [];
  for (let row = 0; row < 6; row += 1) {
    const count = values[row]?.slice(5).filter((v) => typeof v === "number" && v > 40000 && v < 60000).length ?? 0;
    if (count >= 3) dateRows.push(row);
  }
  const dateRow = dateRows[0] ?? 1;
  const columns = [];
  for (let col = 5; col < 46; col += 1) {
    const rawHeader = values[dateRow]?.[col];
    let populated = 0;
    let numeric = 0;
    for (let row = dateRow + 1; row < values.length; row += 1) {
      const value = values[row]?.[col];
      if (value !== null && value !== "") populated += 1;
      if (typeof value === "number" || typeof value === "boolean") numeric += 1;
    }
    columns.push({ col: columnName(col), header: excelDate(rawHeader), populated, numeric });
  }
  console.log(JSON.stringify({ sheetName, dateRow: dateRow + 1, columns }));
}
