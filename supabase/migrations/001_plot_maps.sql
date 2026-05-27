-- Run this in your Supabase SQL editor

-- Plot Maps: one per project/upload session
CREATE TABLE IF NOT EXISTS plot_maps (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id          UUID,                          -- reference your projects table
  org_id              UUID,                          -- reference your organizations table
  original_image_url  TEXT,
  processed_image_url TEXT,
  total_plots         INT DEFAULT 0,
  plots_with_numbers  INT DEFAULT 0,
  status              VARCHAR(50) DEFAULT 'draft',   -- draft | published
  created_at          TIMESTAMP DEFAULT NOW(),
  updated_at          TIMESTAMP DEFAULT NOW()
);

-- Plots: each individual plot detected on the map
CREATE TABLE IF NOT EXISTS plots (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  map_id               UUID REFERENCES plot_maps(id) ON DELETE CASCADE,
  project_id           UUID,
  plot_number          VARCHAR(50),
  ocr_detected_number  VARCHAR(50),
  -- Details from Excel
  size_sqyd            NUMERIC,
  facing               VARCHAR(50),
  dimensions           VARCHAR(100),
  road_width           VARCHAR(50),
  price_per_sqyd       NUMERIC,
  total_price          NUMERIC,
  plot_type            VARCHAR(100),
  status               VARCHAR(50) DEFAULT 'available',  -- available | sold | reserved | held
  created_at           TIMESTAMP DEFAULT NOW(),
  updated_at           TIMESTAMP DEFAULT NOW()
);

-- Plot Coordinates: polygon points for each plot
CREATE TABLE IF NOT EXISTS plot_coordinates (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  plot_id           UUID REFERENCES plots(id) ON DELETE CASCADE,
  map_id            UUID REFERENCES plot_maps(id) ON DELETE CASCADE,
  normalized_points JSONB NOT NULL,   -- [{x: 0.12, y: 0.34}, ...]
  detection_method  VARCHAR(50) DEFAULT 'auto',   -- auto | manual
  confidence_score  FLOAT DEFAULT 0,
  verified          BOOLEAN DEFAULT FALSE,
  created_at        TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_plots_map_id ON plots(map_id);
CREATE INDEX IF NOT EXISTS idx_plots_project_id ON plots(project_id);
CREATE INDEX IF NOT EXISTS idx_plot_coordinates_map_id ON plot_coordinates(map_id);
CREATE INDEX IF NOT EXISTS idx_plot_coordinates_plot_id ON plot_coordinates(plot_id);
