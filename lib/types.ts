export interface NormalizedPoint {
  x: number;
  y: number;
}

export type PlotStatus = "available" | "sold" | "reserved" | "held";

export interface DetectedPlot {
  id: string;
  points: NormalizedPoint[];
  plot_number: string | null;
  number_detected: boolean;
  confidence: number;
  sides: number;
  area_ratio?: number;
  verified?: boolean;
}

export interface PlotWithDetails extends DetectedPlot {
  // Fields filled from Excel
  size_sqyd?: number;
  facing?: string;
  dimensions?: string;
  road_width?: string;
  price_per_sqyd?: number;
  total_price?: number;
  plot_type?: string;
  status?: PlotStatus;
  // DB fields
  db_id?: string;
  map_id?: string;
}

export interface MapBuilderSession {
  projectId: string;
  projectName: string;
  imageUrl: string;        // object URL or Supabase URL
  imageFile?: File;
  plots: PlotWithDetails[];
  mapId?: string;
}

export type MatchStatus = "matched" | "missing_excel" | "missing_map";

export interface ExcelRow {
  plot_number: string;
  size_sqyd?: number;
  facing?: string;
  dimensions?: string;
  road_width?: string;
  price_per_sqyd?: number;
  total_price?: number;
  plot_type?: string;
  status?: string;
}

export interface MappedPlot extends PlotWithDetails {
  match_status: MatchStatus;
}
