import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/dozzl/Downloads/NCA_Monthly_Report.xlsx";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));

const sheetInfo = await workbook.inspect({
  kind: "sheet",
  include: "id,name",
  maxChars: 20000,
});
console.log("SHEETS");
console.log(sheetInfo.ndjson);

for (let index = 0; index < workbook.worksheets.items.length; index += 1) {
  const sheet = workbook.worksheets.getItemAt(index);
  const used = sheet.getUsedRange(false);
  console.log(`SHEET ${index}: ${sheet.name} USED ${used?.address ?? "none"}`);
  if (!used) continue;
  const overview = await workbook.inspect({
    kind: "table",
    sheetId: sheet.name,
    range: used.address,
    include: "values,formulas",
    tableMaxRows: 18,
    tableMaxCols: 16,
    tableMaxCellChars: 120,
    maxChars: 9000,
  });
  console.log(overview.ndjson);
}

const excelDate = (serial) => {
  if (typeof serial !== "number") return serial;
  return new Date(Date.UTC(1899, 11, 30) + serial * 86400000).toISOString().slice(0, 10);
};
for (const sheetName of ["Subscriptions", "Network Parameters", "Mobile Money"]) {
  const sheet = workbook.worksheets.getItem(sheetName);
  const headerRows = sheet.getRange("A1:AT4").values;
  console.log(`HEADERS ${sheetName}`);
  headerRows.forEach((row, rowIndex) => {
    console.log(rowIndex + 1, row.map((value, colIndex) => ({ col: colIndex + 1, value: excelDate(value) })).filter((item) => item.value !== null && item.value !== ""));
  });
  const allValues = sheet.getRange("A1:AT432").values;
  const stats = [];
  for (let col = 5; col < 46; col += 1) {
    let populated = 0;
    let numeric = 0;
    for (let row = 4; row < allValues.length; row += 1) {
      const value = allValues[row]?.[col];
      if (value !== null && value !== "") populated += 1;
      if (typeof value === "number") numeric += 1;
    }
    stats.push({ col: col + 1, header: excelDate(headerRows.flat().find((_, i) => false)), row1: excelDate(allValues[0]?.[col]), row2: excelDate(allValues[1]?.[col]), row3: excelDate(allValues[2]?.[col]), populated, numeric });
  }
  console.log(`COLUMN_STATS ${sheetName}`, JSON.stringify(stats));
}
