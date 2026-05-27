import * as XLSX from "xlsx";
import type { ExcelRow, MappedPlot, PlotWithDetails } from "./types";

const EXPECTED_COLUMNS = [
  "Plot Number",
  "Size (sq.yd)",
  "Facing",
  "Dimensions",
  "Road Width",
  "Price/sqyd",
  "Total Price",
  "Type",
  "Status",
];

function normalizeKey(s: string): string {
  return s.toUpperCase().replace(/[\s\-_]/g, "");
}

export function parseExcel(file: File): Promise<ExcelRow[]> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target!.result as ArrayBuffer);
        const workbook = XLSX.read(data, { type: "array" });
        const sheet = workbook.Sheets[workbook.SheetNames[0]];
        const rows: Record<string, unknown>[] = XLSX.utils.sheet_to_json(sheet, {
          defval: "",
        });

        const parsed: ExcelRow[] = rows.map((row) => {
          const get = (key: string): string => {
            const found = Object.keys(row).find(
              (k) => normalizeKey(k) === normalizeKey(key)
            );
            return found ? String(row[found]).trim() : "";
          };

          const plotNum = get("Plot Number");
          if (!plotNum) return null;

          return {
            plot_number: plotNum.toUpperCase().replace(/\s+/g, ""),
            size_sqyd: parseFloat(get("Size (sq.yd)")) || undefined,
            facing: get("Facing") || undefined,
            dimensions: get("Dimensions") || undefined,
            road_width: get("Road Width") || undefined,
            price_per_sqyd: parseFloat(get("Price/sqyd")) || undefined,
            total_price: parseFloat(get("Total Price")) || undefined,
            plot_type: get("Type") || undefined,
            status: (get("Status") || "available").toLowerCase() as ExcelRow["status"],
          };
        }).filter(Boolean) as ExcelRow[];

        resolve(parsed);
      } catch (err) {
        reject(new Error("Failed to parse Excel file: " + (err as Error).message));
      }
    };
    reader.onerror = () => reject(new Error("Failed to read file"));
    reader.readAsArrayBuffer(file);
  });
}

function normalizePlotNumber(n: string): string {
  return n.toUpperCase().replace(/[\s\-_]/g, "");
}

export function mapExcelToPlots(
  plots: PlotWithDetails[],
  excelRows: ExcelRow[]
): { mapped: MappedPlot[]; unmatchedExcel: ExcelRow[] } {
  const excelMap = new Map<string, ExcelRow>();
  for (const row of excelRows) {
    excelMap.set(normalizePlotNumber(row.plot_number), row);
  }

  const usedKeys = new Set<string>();

  const mapped: MappedPlot[] = plots.map((plot) => {
    const key = normalizePlotNumber(plot.plot_number ?? "");
    const excelRow = key ? excelMap.get(key) : undefined;

    if (excelRow) {
      usedKeys.add(key);
      return {
        ...plot,
        size_sqyd: excelRow.size_sqyd,
        facing: excelRow.facing,
        dimensions: excelRow.dimensions,
        road_width: excelRow.road_width,
        price_per_sqyd: excelRow.price_per_sqyd,
        total_price: excelRow.total_price,
        plot_type: excelRow.plot_type,
        status: (excelRow.status as PlotWithDetails["status"]) ?? "available",
        match_status: "matched",
      };
    }

    return { ...plot, match_status: "missing_excel" };
  });

  const unmatchedExcel = excelRows.filter(
    (r) => !usedKeys.has(normalizePlotNumber(r.plot_number))
  );

  return { mapped, unmatchedExcel };
}

export function generateExcelTemplate(): void {
  const templateData = [
    EXPECTED_COLUMNS,
    ["A-1", 150, "East", "22x44ft", "40ft", 15000, 2250000, "Residential", "Available"],
    ["A-2", 120, "West", "18x40ft", "30ft", 15000, 1800000, "Residential", "Available"],
    ["B-1", 200, "North", "25x48ft", "40ft", 15000, 3000000, "Commercial", "Sold"],
  ];

  const ws = XLSX.utils.aoa_to_sheet(templateData);
  ws["!cols"] = EXPECTED_COLUMNS.map(() => ({ wch: 18 }));

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Plot Data");

  XLSX.writeFile(wb, "plot-data-template.xlsx");
}
