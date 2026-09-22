import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load("C:/Users/dozzl/Downloads/NCA_Monthly_Report.xlsx"));
for (const sheet of workbook.worksheets.items) {
  const values = sheet.getRange("AS1:AT432").values;
  const nonblank = [];
  for (let row = 0; row < values.length; row += 1) {
    for (let col = 0; col < 2; col += 1) {
      const value = values[row]?.[col];
      if (value !== null && value !== "") nonblank.push({cell:`${col === 0 ? "AS" : "AT"}${row + 1}`,value});
    }
  }
  console.log(JSON.stringify({sheet:sheet.name, tail:nonblank.slice(-15)}));
}
