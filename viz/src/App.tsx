import { useEffect, useMemo, useState } from 'react';
import { loadBundle, loadManifest } from './data';
import { buildDamageColumns } from './geo';
import { rasterizeWind } from './wind';
import type { Bundle, ManifestEntry } from './types';
import ScenarioPicker from './components/ScenarioPicker';
import Scene3D, { COLUMN_SCALE_LABEL } from './components/Scene3D';
import Legend from './components/Legend';
import Tooltip, { type HoverInfo } from './components/Tooltip';
import Footer from './components/Footer';

export default function App() {
  const [manifest, setManifest] = useState<ManifestEntry[]>([]);
  const [selectedHash, setSelectedHash] = useState<string | null>(null);
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [hover, setHover] = useState<HoverInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadManifest()
      .then((m) => {
        setManifest(m);
        if (m.length > 0) setSelectedHash(m[0].scenario_hash);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!selectedHash) return;
    const entry = manifest.find((m) => m.scenario_hash === selectedHash);
    if (!entry) return;
    setLoading(true);
    setError(null);
    setHover(null);
    let cancelled = false;
    loadBundle(entry)
      .then((b) => {
        if (!cancelled) setBundle(b);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedHash, manifest]);

  const columns = useMemo(
    () => (bundle ? buildDamageColumns(bundle.boundaries, bundle.damage) : []),
    [bundle],
  );

  const windRaster = useMemo(
    () => (bundle ? rasterizeWind(bundle.wind) : null),
    [bundle],
  );

  // Municipalities the engine modeled at $0 damage — filtered out of the columns
  // (buildDamageColumns) since a flat disk conveys nothing; surfaced honestly in
  // the legend so their absence isn't mistaken for missing data.
  const zeroDamageCount = useMemo(
    () =>
      bundle
        ? bundle.damage.damage_by_municipality.filter((d) => d.damage_usd <= 0).length
        : 0,
    [bundle],
  );

  const onSelect = (entry: ManifestEntry) => setSelectedHash(entry.scenario_hash);

  return (
    <>
      {bundle && windRaster && (
        <Scene3D
          key={bundle.meta.scenario_hash}
          bundle={bundle}
          columns={columns}
          windRaster={windRaster}
          onHover={setHover}
        />
      )}

      <ScenarioPicker
        manifest={manifest}
        selectedHash={selectedHash}
        onSelect={onSelect}
        meta={bundle?.meta ?? null}
      />

      {bundle && windRaster && (
        <Legend
          windDomainMin={windRaster.domainMin}
          windDomainMax={windRaster.domainMax}
          windUnits={bundle.wind.units}
          columnScaleLabel={COLUMN_SCALE_LABEL}
          zeroDamageCount={zeroDamageCount}
        />
      )}

      {bundle && <Tooltip hover={hover} sourceCacheKey={bundle.meta.source_cache_key} />}

      {loading && <div className="loading">Loading scenario…</div>}
      {error && <div className="loading error">{error}</div>}

      {bundle && <Footer meta={bundle.meta} />}
    </>
  );
}
