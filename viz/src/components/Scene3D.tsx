import { useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { TerrainLayer } from '@deck.gl/geo-layers';
import { BitmapLayer, ColumnLayer, PathLayer, ScatterplotLayer } from '@deck.gl/layers';
import { _TerrainExtension as TerrainExtension } from '@deck.gl/extensions';
import type { TerrainExtensionProps } from '@deck.gl/extensions';
import type { Layer, PickingInfo } from '@deck.gl/core';
import type { Bundle, DamageColumn } from '../types';
import type { WindRaster } from '../wind';
import type { HoverInfo } from './Tooltip';

// Keyless public tile sources (PRD §5.1 — no paid keys anywhere).
const TERRAIN_URL = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png';
const BASEMAP_URL = 'https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png';

// Terrarium encoding: height(m) = (R*256 + G + B/256) - 32768.
const TERRARIUM_DECODER = {
  rScaler: 256,
  gScaler: 1,
  bScaler: 1 / 256,
  offset: -32768,
};

// Damage column height: log scale (damage spans several orders of magnitude).
// height(m) = max(0, log10(damage_usd) - LOG_FLOOR) * METERS_PER_DECADE.
// The scale is stated in the UI legend (PRD §4.3), not just here.
const LOG_FLOOR = 3; // $1,000 -> zero height
const METERS_PER_DECADE = 7000;
export const COLUMN_SCALE_LABEL = 'height ∝ log₁₀(USD), 7 km per decade above $1k';

function columnHeight(damageUsd: number): number {
  if (damageUsd <= 0) return 0;
  return Math.max(0, Math.log10(damageUsd) - LOG_FLOOR) * METERS_PER_DECADE;
}

// Current storm position during replay: snapped to a frame's reported track point
// (no interpolation) and sized by that frame's reported max wind.
export interface TrackMarker {
  lon: number;
  lat: number;
  vmax_kn: number;
}

interface Props {
  bundle: Bundle;
  columns: DamageColumn[];
  windRaster: WindRaster;
  onHover: (info: HoverInfo | null) => void;
  // Replay overlays — null in Tier-1 static rendering.
  traveledPath: [number, number][] | null;
  marker: TrackMarker | null;
}

export default function Scene3D({
  bundle,
  columns,
  windRaster,
  onHover,
  traveledPath,
  marker,
}: Props) {
  const hash = bundle.meta.scenario_hash;

  const initialViewState = useMemo(() => {
    const [lonMin, latMin, lonMax, latMax] = bundle.wind.bounds;
    return {
      longitude: (lonMin + lonMax) / 2,
      latitude: (latMin + latMax) / 2,
      zoom: 7,
      pitch: 50,
      bearing: 15,
    };
  }, [bundle.wind.bounds]);

  const trackPath = useMemo(
    () => [{ path: bundle.track.map((p) => [p.lon, p.lat] as [number, number]) }],
    [bundle.track],
  );

  const layers: Layer[] = [
    new TerrainLayer({
      id: `terrain-${hash}`,
      elevationData: TERRAIN_URL,
      texture: BASEMAP_URL,
      elevationDecoder: TERRARIUM_DECODER,
      minZoom: 0,
      maxZoom: 12,
      // 'terrain+draw': render the terrain mesh normally AND expose it as the
      // draping/height target the TerrainExtension on the wind and damage layers
      // reads from. Propagates to the mesh sublayer (composite-layer forwards
      // `operation`). Without this the extension finds no terrain and no-ops.
      operation: 'terrain+draw',
    }),
    new BitmapLayer({
      id: `wind-${hash}`,
      image: windRaster.canvas,
      bounds: windRaster.bounds,
      opacity: 0.75,
      // Nearest-neighbour sampling keeps each model cell crisp — no smoothing
      // that would imply spatial precision the model doesn't have (PRD §4.3).
      textureParameters: {
        minFilter: 'nearest',
        magFilter: 'nearest',
      },
      // Drape the flat raster onto the terrain surface instead of leaving it at
      // z=0 slicing through relief. Placement only — no value/cell change.
      extensions: [new TerrainExtension()],
      terrainDrawMode: 'drape',
    }),
    new ColumnLayer<DamageColumn>({
      id: `damage-columns-${hash}`,
      data: columns,
      diskResolution: 12,
      radius: 1400,
      extruded: true,
      pickable: true,
      elevationScale: 1,
      getPosition: (d) => d.position,
      getElevation: (d) => columnHeight(d.damage_usd),
      getFillColor: [255, 170, 40, 220],
      // Offset each column's base to the terrain height at its anchor so it rises
      // from the ground, not sea level. Heights (columnHeight) are unchanged.
      // Spread the typed extension prop so it isn't rejected as an unknown key on
      // ColumnLayerProps (the extension consumes it at runtime).
      extensions: [new TerrainExtension()],
      ...({ terrainDrawMode: 'offset' } as TerrainExtensionProps),
      onHover: (info: PickingInfo<DamageColumn>) => {
        if (info.object) {
          onHover({ column: info.object, x: info.x, y: info.y });
        } else {
          onHover(null);
        }
      },
    }),
    new PathLayer({
      id: `track-${hash}`,
      data: trackPath,
      getPath: (d: { path: [number, number][] }) => d.path,
      getColor: [77, 225, 255],
      getWidth: 3,
      widthUnits: 'pixels',
      widthMinPixels: 2,
      capRounded: true,
      jointRounded: true,
    }),
  ];

  // Replay overlays: the "traveled so far" segment (brighter, thicker) over the dim
  // full track, and a marker snapped to the current frame's exact reported position
  // (sized by its reported max wind — no interpolated in-between point).
  if (traveledPath && traveledPath.length >= 2) {
    layers.push(
      new PathLayer<{ path: [number, number][] }>({
        id: `track-traveled-${hash}`,
        data: [{ path: traveledPath }],
        getPath: (d) => d.path,
        getColor: [255, 255, 255],
        getWidth: 5,
        widthUnits: 'pixels',
        widthMinPixels: 3,
        capRounded: true,
        jointRounded: true,
      }),
    );
  }
  if (marker) {
    layers.push(
      new ScatterplotLayer<TrackMarker>({
        id: `track-marker-${hash}`,
        data: [marker],
        getPosition: (d) => [d.lon, d.lat],
        // Radius grows with reported max wind — bigger dot = stronger core.
        getRadius: (d) => 4 + d.vmax_kn / 8,
        radiusUnits: 'pixels',
        radiusMinPixels: 4,
        getFillColor: [255, 230, 120, 235],
        stroked: true,
        getLineColor: [40, 20, 0, 255],
        lineWidthUnits: 'pixels',
        getLineWidth: 1.5,
      }),
    );
  }

  return (
    <div id="deck-root">
      <DeckGL
        initialViewState={initialViewState}
        controller={true}
        layers={layers}
        onHover={(info) => {
          // Clear tooltip when the cursor leaves any pickable object.
          if (!info.object) onHover(null);
        }}
      />
    </div>
  );
}
