import type { Boundaries, Damage, DamageColumn, MuniDamage } from './types';

// Shoelace area + centroid of a single ring (assumed closed or not; handles both).
// Returns null for degenerate rings (zero area) so callers can fall back.
function ringCentroid(ring: number[][]): { cx: number; cy: number; area: number } | null {
  let area = 0;
  let cx = 0;
  let cy = 0;
  const n = ring.length;
  for (let i = 0; i < n - 1; i++) {
    const [x0, y0] = ring[i];
    const [x1, y1] = ring[i + 1];
    const cross = x0 * y1 - x1 * y0;
    area += cross;
    cx += (x0 + x1) * cross;
    cy += (y0 + y1) * cross;
  }
  area *= 0.5;
  if (Math.abs(area) < 1e-12) return null;
  cx /= 6 * area;
  cy /= 6 * area;
  return { cx, cy, area: Math.abs(area) };
}

// Average of ring vertices — fallback for degenerate (zero-area) rings.
function ringMean(ring: number[][]): [number, number] {
  let sx = 0;
  let sy = 0;
  for (const [x, y] of ring) {
    sx += x;
    sy += y;
  }
  return [sx / ring.length, sy / ring.length];
}

// Centroid of a municipality feature. For MultiPolygon, use the largest-area
// polygon's exterior ring so a tiny outlying island doesn't drag the marker offshore.
function featureCentroid(
  geometry: Boundaries['features'][number]['geometry'],
): [number, number] {
  let exteriorRings: number[][][];
  if (geometry.type === 'Polygon') {
    exteriorRings = [geometry.coordinates[0]];
  } else {
    exteriorRings = geometry.coordinates.map((poly) => poly[0]);
  }
  let best: { cx: number; cy: number; area: number } | null = null;
  for (const ring of exteriorRings) {
    const c = ringCentroid(ring);
    if (c && (!best || c.area > best.area)) best = c;
  }
  if (best) return [best.cx, best.cy];
  return ringMean(exteriorRings[0]);
}

const key = (province: string, municipality: string) =>
  `${province.trim().toLowerCase()}||${municipality.trim().toLowerCase()}`;

// The expensive part of the join — polygon centroids and the affected-population
// lookup — precomputed ONCE per bundle. During replay, columns for each frame come
// from mapping that frame's damage list through this index (columnsFromDamage), so
// centroids are never recomputed per frame.
export interface CentroidIndex {
  centroids: Map<string, [number, number]>;
  popByKey: Map<string, number>;
}

export function buildCentroidIndex(boundaries: Boundaries, damage: Damage): CentroidIndex {
  const centroids = new Map<string, [number, number]>();
  for (const f of boundaries.features) {
    centroids.set(
      key(f.properties.province, f.properties.municipality),
      featureCentroid(f.geometry),
    );
  }
  const popByKey = new Map<string, number>();
  for (const p of damage.affected_population_by_municipality) {
    popByKey.set(key(p.province, p.municipality), p.affected_population);
  }
  return { centroids, popByKey };
}

// Map a damage-by-municipality list (final or a frame's cumulative snapshot) to
// renderable columns via a precomputed index. Same key convention and $0/unmatched
// drop rules as the static path — a $0 (or not-yet-damaged) municipality yields no
// column, so during playback columns appear/grow as cumulative damage crosses zero.
export function columnsFromDamage(
  index: CentroidIndex,
  damageByMunicipality: MuniDamage[],
): DamageColumn[] {
  const columns: DamageColumn[] = [];
  for (const d of damageByMunicipality) {
    if (d.damage_usd <= 0) continue; // $0 modeled damage — no column (a flat disk
    // at ground level says nothing; the footer/tooltip totals are unaffected)
    const k = key(d.province, d.municipality);
    const pos = index.centroids.get(k);
    if (!pos) continue; // no polygon to place it — skip rather than invent a location
    columns.push({
      position: pos,
      province: d.province,
      municipality: d.municipality,
      damage_usd: d.damage_usd,
      affected_population: index.popByKey.get(k) ?? null,
    });
  }
  return columns;
}

// Join municipality polygons (for centroids) to damage_by_municipality by
// (province, municipality) — the same name key the engine uses. Only municipalities
// present in the damage table produce a column; unmatched polygons are dropped.
export function buildDamageColumns(boundaries: Boundaries, damage: Damage): DamageColumn[] {
  return columnsFromDamage(buildCentroidIndex(boundaries, damage), damage.damage_by_municipality);
}
