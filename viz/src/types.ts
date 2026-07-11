export interface ManifestEntry {
  scenario_hash: string;
  storm_key: string;
  label: string;
  is_baseline: boolean;
  path: string;
}

// Present when the bundle was exported with per-timestep replay data. Absent or
// { available: false } for Tier-1-only bundles (export CLI --no-timeseries) —
// code must feature-detect via meta.timeseries?.available, never assume presence.
export interface TimeseriesMeta {
  available: boolean;
  frame_count: number;
}

export interface Meta {
  storm_key: string;
  storm_name: string;
  ibtracs_name: string;
  year: number;
  scenario: Record<string, number | string>;
  scenario_hash: string;
  source_cache_key: string;
  hazard_model: string;
  units: { damage: string; wind: string };
  landfall_version: string;
  disclaimer: string;
  provenance: string;
  timeseries?: TimeseriesMeta;
}

export interface TrackPoint {
  time: string;
  lat: number;
  lon: number;
  max_sustained_wind_kn: number;
  central_pressure: number;
  radius_max_wind: number;
}

export interface WindSwath {
  bounds: [number, number, number, number]; // [lon_min, lat_min, lon_max, lat_max]
  res_deg: number;
  shape: [number, number]; // [rows, cols]
  units: string;
  row_order: string;
  col_order: string;
  value_rounding: number;
  values: number[][]; // row 0 = north edge, col 0 = west edge
}

export interface MuniDamage {
  province: string;
  municipality: string;
  damage_usd: number;
}

export interface MuniPop {
  province: string;
  municipality: string;
  affected_population: number;
}

export interface Damage {
  total_damage_usd: number;
  total_damage_usd_range: { low: number; high: number };
  affected_population: number;
  damage_by_municipality: MuniDamage[];
  affected_population_by_municipality: MuniPop[];
}

export interface BoundaryProps {
  gid_2: string;
  province: string;
  municipality: string;
}

export interface Boundaries {
  type: 'FeatureCollection';
  features: Array<{
    type: 'Feature';
    properties: BoundaryProps;
    geometry:
      | { type: 'Polygon'; coordinates: number[][][] }
      | { type: 'MultiPolygon'; coordinates: number[][][][] };
  }>;
}

// One replay frame: cumulative damage state + the storm's reported track position
// at that timestep. Damage values are cumulative (running max/accumulation), so the
// final frame equals the single-pass baseline exactly (final_frame_reconciles...).
export interface TimeseriesFrame {
  frame_index: number;
  time: string; // ISO8601, e.g. "2020-10-31T14:30:00Z" — the real UTC timestamp
  cumulative_total_damage_usd: number;
  cumulative_damage_by_municipality: MuniDamage[];
  track_lat: number;
  track_lon: number;
  track_vmax_kn: number;
}

export interface Timeseries {
  scenario_hash: string;
  wind_timestep_h: number;
  frame_count: number;
  frames: TimeseriesFrame[];
}

// wind/frames.json — per-frame wind grids sharing one bounds/shape/res (the same
// grid geometry as max_swath.json). Each frame's `values` is a 2D grid, same format
// as WindSwath.values. Array order aligns 1:1 with Timeseries.frames by index.
export interface WindFrame {
  frame_index: number;
  values: number[][];
}

export interface WindFrames {
  bounds: [number, number, number, number];
  res_deg: number;
  shape: [number, number];
  units: string;
  row_order: string;
  col_order: string;
  value_rounding: number;
  frames: WindFrame[];
}

export interface Bundle {
  meta: Meta;
  track: TrackPoint[];
  wind: WindSwath;
  damage: Damage;
  boundaries: Boundaries;
  // Populated only when meta.timeseries?.available; null otherwise (Tier-1 fallback).
  timeseries: Timeseries | null;
  windFrames: WindFrames | null;
}

// A damage column ready to render: centroid + joined damage + provenance for tooltip.
export interface DamageColumn {
  position: [number, number];
  province: string;
  municipality: string;
  damage_usd: number;
  affected_population: number | null;
}
