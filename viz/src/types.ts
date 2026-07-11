export interface ManifestEntry {
  scenario_hash: string;
  storm_key: string;
  label: string;
  is_baseline: boolean;
  path: string;
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

export interface Bundle {
  meta: Meta;
  track: TrackPoint[];
  wind: WindSwath;
  damage: Damage;
  boundaries: Boundaries;
}

// A damage column ready to render: centroid + joined damage + provenance for tooltip.
export interface DamageColumn {
  position: [number, number];
  province: string;
  municipality: string;
  damage_usd: number;
  affected_population: number | null;
}
