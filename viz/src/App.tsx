import { useEffect, useMemo, useState } from 'react';
import { loadBundle, loadManifest } from './data';
import { buildCentroidIndex, columnsFromDamage } from './geo';
import { rasterizeWind, rasterizeWindFrames } from './wind';
import type { Bundle, ManifestEntry } from './types';
import ScenarioPicker from './components/ScenarioPicker';
import Scene3D, { COLUMN_SCALE_LABEL, type TrackMarker } from './components/Scene3D';
import Legend from './components/Legend';
import Timeline from './components/Timeline';
import Tooltip, { type HoverInfo } from './components/Tooltip';
import Footer from './components/Footer';

const FRAME_MS = 150; // fixed playback cadence, ~150ms/frame (no speed selector)

export default function App() {
  const [manifest, setManifest] = useState<ManifestEntry[]>([]);
  const [selectedHash, setSelectedHash] = useState<string | null>(null);
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [hover, setHover] = useState<HoverInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

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
    // Reset replay to frame 0, paused, on every storm switch (mirrors the
    // full-remount-on-switch pattern — Scene3D is keyed on the hash).
    setCurrentFrame(0);
    setIsPlaying(false);
    let cancelled = false;
    loadBundle(entry)
      .then((b) => {
        if (!cancelled) {
          setBundle(b);
          // Re-assert the reset here too: it resolves strictly after any in-flight
          // 150ms playback timer from the PREVIOUS bundle, so it wins that race and
          // the new storm can never inherit a stale mid-play frame index (reviewed
          // Phase 4 finding — the two resets above alone left a rare timing gap).
          setCurrentFrame(0);
          setIsPlaying(false);
        }
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

  // Precomputed once per bundle load: the centroid+population join (expensive) and
  // the static max-swath raster whose domainMax anchors the fixed color scale.
  const centroidIndex = useMemo(
    () => (bundle ? buildCentroidIndex(bundle.boundaries, bundle.damage) : null),
    [bundle],
  );
  const staticWindRaster = useMemo(
    () => (bundle ? rasterizeWind(bundle.wind) : null),
    [bundle],
  );
  // One raster per replay frame, all colored against the fixed max-swath domain.
  const frameRasters = useMemo(
    () =>
      bundle?.windFrames && staticWindRaster
        ? rasterizeWindFrames(bundle.windFrames, staticWindRaster.domainMax)
        : null,
    [bundle, staticWindRaster],
  );

  const hasTimeseries = !!(
    bundle?.meta.timeseries?.available &&
    bundle.timeseries &&
    frameRasters
  );
  const frameCount = hasTimeseries ? bundle!.timeseries!.frames.length : 0;
  // Clamp so a stale currentFrame (mid-switch) never indexes out of range.
  const frameIdx = hasTimeseries ? Math.min(currentFrame, frameCount - 1) : 0;

  // Playback: each active frame schedules the next tick; stop at the final frame
  // (which equals the reconciled single-pass total). setTimeout is cleared on every
  // frame change / pause / unmount, so nothing leaks.
  useEffect(() => {
    if (!isPlaying || !hasTimeseries) return;
    if (frameIdx >= frameCount - 1) {
      setIsPlaying(false);
      return;
    }
    const id = setTimeout(() => setCurrentFrame(frameIdx + 1), FRAME_MS);
    return () => clearTimeout(id);
  }, [isPlaying, hasTimeseries, frameIdx, frameCount]);

  // Current-frame render data. Falls back to the static (final) state for
  // Tier-1-only bundles, so rendering works with no timeseries.
  const columns = useMemo(() => {
    if (!bundle || !centroidIndex) return [];
    if (hasTimeseries) {
      return columnsFromDamage(
        centroidIndex,
        bundle.timeseries!.frames[frameIdx].cumulative_damage_by_municipality,
      );
    }
    return columnsFromDamage(centroidIndex, bundle.damage.damage_by_municipality);
  }, [bundle, centroidIndex, hasTimeseries, frameIdx]);

  const windRaster = hasTimeseries ? frameRasters![frameIdx] : staticWindRaster;

  // "Traveled so far" path + current-position marker — snapped to each frame's
  // exact reported track point (no interpolation), null when no timeseries.
  const traveledPath = useMemo<[number, number][] | null>(() => {
    if (!hasTimeseries) return null;
    return bundle!.timeseries!.frames
      .slice(0, frameIdx + 1)
      .map((f) => [f.track_lon, f.track_lat]);
  }, [bundle, hasTimeseries, frameIdx]);

  const marker = useMemo<TrackMarker | null>(() => {
    if (!hasTimeseries) return null;
    const f = bundle!.timeseries!.frames[frameIdx];
    return { lon: f.track_lon, lat: f.track_lat, vmax_kn: f.track_vmax_kn };
  }, [bundle, hasTimeseries, frameIdx]);

  const zeroDamageCount = useMemo(
    () =>
      bundle
        ? bundle.damage.damage_by_municipality.filter((d) => d.damage_usd <= 0).length
        : 0,
    [bundle],
  );

  const onSelect = (entry: ManifestEntry) => setSelectedHash(entry.scenario_hash);

  const onTogglePlay = () => {
    // Replaying from the end restarts at frame 0.
    if (!isPlaying && frameIdx >= frameCount - 1) setCurrentFrame(0);
    setIsPlaying((p) => !p);
  };
  const onScrub = (frame: number) => {
    setIsPlaying(false);
    setCurrentFrame(frame);
  };

  return (
    <>
      {bundle && windRaster && (
        <Scene3D
          key={bundle.meta.scenario_hash}
          bundle={bundle}
          columns={columns}
          windRaster={windRaster}
          onHover={setHover}
          traveledPath={traveledPath}
          marker={marker}
        />
      )}

      <ScenarioPicker
        manifest={manifest}
        selectedHash={selectedHash}
        onSelect={onSelect}
        meta={bundle?.meta ?? null}
      />

      {bundle && staticWindRaster && (
        <Legend
          windDomainMin={staticWindRaster.domainMin}
          windDomainMax={staticWindRaster.domainMax}
          windUnits={bundle.wind.units}
          columnScaleLabel={COLUMN_SCALE_LABEL}
          zeroDamageCount={zeroDamageCount}
          animated={hasTimeseries}
        />
      )}

      {bundle && hasTimeseries && (
        <Timeline
          frameCount={frameCount}
          currentFrame={frameIdx}
          isPlaying={isPlaying}
          time={bundle.timeseries!.frames[frameIdx].time}
          onTogglePlay={onTogglePlay}
          onScrub={onScrub}
        />
      )}

      {bundle && <Tooltip hover={hover} sourceCacheKey={bundle.meta.source_cache_key} />}

      {loading && <div className="loading">Loading scenario…</div>}
      {error && <div className="loading error">{error}</div>}

      {bundle && <Footer meta={bundle.meta} />}
    </>
  );
}
