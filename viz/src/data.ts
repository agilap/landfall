import type { Bundle, ManifestEntry } from './types';

const DATA_ROOT = 'data';

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load ${url}: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export async function loadManifest(): Promise<ManifestEntry[]> {
  return getJSON<ManifestEntry[]>(`${DATA_ROOT}/manifest.json`);
}

// Load one committed bundle. The 5 Tier-1 files always load; the 2 replay files
// (timeseries.json, wind/frames.json) load only when meta.timeseries.available, so
// Tier-1-only bundles still render. `path` comes from the manifest.
export async function loadBundle(entry: ManifestEntry): Promise<Bundle> {
  const base = entry.path;
  const [meta, track, wind, damage, boundaries] = await Promise.all([
    getJSON<Bundle['meta']>(`${base}/meta.json`),
    getJSON<Bundle['track']>(`${base}/track.json`),
    getJSON<Bundle['wind']>(`${base}/wind/max_swath.json`),
    getJSON<Bundle['damage']>(`${base}/damage.json`),
    getJSON<Bundle['boundaries']>(`${base}/boundaries.json`),
  ]);

  let timeseries: Bundle['timeseries'] = null;
  let windFrames: Bundle['windFrames'] = null;
  if (meta.timeseries?.available) {
    [timeseries, windFrames] = await Promise.all([
      getJSON<NonNullable<Bundle['timeseries']>>(`${base}/timeseries.json`),
      getJSON<NonNullable<Bundle['windFrames']>>(`${base}/wind/frames.json`),
    ]);
  }

  return { meta, track, wind, damage, boundaries, timeseries, windFrames };
}
