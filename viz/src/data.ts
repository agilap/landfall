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

// Load the 5 JSON files of one committed bundle. `path` comes from the manifest
// (e.g. "data/289d30ecbb27bc03") and is relative to the app base.
export async function loadBundle(entry: ManifestEntry): Promise<Bundle> {
  const base = entry.path;
  const [meta, track, wind, damage, boundaries] = await Promise.all([
    getJSON<Bundle['meta']>(`${base}/meta.json`),
    getJSON<Bundle['track']>(`${base}/track.json`),
    getJSON<Bundle['wind']>(`${base}/wind/max_swath.json`),
    getJSON<Bundle['damage']>(`${base}/damage.json`),
    getJSON<Bundle['boundaries']>(`${base}/boundaries.json`),
  ]);
  return { meta, track, wind, damage, boundaries };
}
