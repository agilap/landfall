import type { WindSwath, WindFrames } from './types';

// Sequential color stops for wind magnitude, normalized [0,1] over the swath's
// own value range. ColorBrewer YlOrRd — a single perceptually-ordered warm
// progression (pale yellow -> deep red) so "hotter = stronger wind" reads without
// implying a meaningful midpoint (wind speed has none). The legend states the
// actual m/s span so no false precision is implied.
const STOPS: Array<{ t: number; rgb: [number, number, number] }> = [
  { t: 0.0, rgb: [255, 255, 204] }, // pale yellow — weakest shown
  { t: 0.16, rgb: [255, 237, 160] },
  { t: 0.33, rgb: [254, 217, 118] },
  { t: 0.5, rgb: [254, 178, 76] }, // orange
  { t: 0.66, rgb: [253, 141, 60] },
  { t: 0.83, rgb: [252, 78, 42] },
  { t: 1.0, rgb: [189, 0, 38] }, // deep red — strongest
];

export function windColor(t: number): [number, number, number] {
  const c = Math.max(0, Math.min(1, t));
  for (let i = 0; i < STOPS.length - 1; i++) {
    const a = STOPS[i];
    const b = STOPS[i + 1];
    if (c >= a.t && c <= b.t) {
      const f = (c - a.t) / (b.t - a.t || 1);
      return [
        Math.round(a.rgb[0] + f * (b.rgb[0] - a.rgb[0])),
        Math.round(a.rgb[1] + f * (b.rgb[1] - a.rgb[1])),
        Math.round(a.rgb[2] + f * (b.rgb[2] - a.rgb[2])),
      ];
    }
  }
  return STOPS[STOPS.length - 1].rgb;
}

export interface WindRaster {
  canvas: HTMLCanvasElement;
  // BitmapLayer bounds: [left, bottom, right, top] in lon/lat.
  bounds: [number, number, number, number];
  domainMin: number;
  domainMax: number;
}

// Cells below this (m/s) render fully transparent so calm areas show terrain,
// rather than painting a wash implying wind where the model has ~none.
const MIN_VISIBLE_MS = 17.0; // ~tropical-storm force; below this we don't color

// Alpha ramps with magnitude so weak-but-shown cells stay faint (terrain, basemap,
// and place labels read through), strengthening to near-opaque at the peak. This
// only changes how visible a cell is, never whether it exists — every cell >= the
// 17 m/s cutoff is still drawn. t is the same normalized magnitude used for hue.
const ALPHA_MIN = 70; // near MIN_VISIBLE_MS — barely-there
const ALPHA_MAX = 230; // at the swath peak — near-opaque
function windAlpha(t: number): number {
  const c = Math.max(0, Math.min(1, t));
  return Math.round(ALPHA_MIN + c * (ALPHA_MAX - ALPHA_MIN));
}

// Peak wind (m/s) over a grid — the max-swath domain that anchors the color scale.
function gridMax(values: number[][]): number {
  let m = 0;
  for (const row of values) {
    for (const v of row) if (v > m) m = v;
  }
  return m;
}

// Rasterize a native-resolution grid to a canvas, one texel per grid cell, coloring
// against an EXPLICIT [domainMin, domainMax]. No interpolation; the BitmapLayer must
// also use nearest-neighbour sampling (see Scene3D) so cells stay crisp (PRD §4.3).
// Passing the domain in (rather than deriving it per grid) is what keeps an animation
// honest: every frame is colored against the storm's full max-swath range, so a given
// color means the same wind speed in every frame — no per-frame renormalization.
function rasterizeGrid(
  values: number[][],
  rows: number,
  cols: number,
  bounds: [number, number, number, number],
  domainMin: number,
  domainMax: number,
): WindRaster {
  const canvas = document.createElement('canvas');
  canvas.width = cols;
  canvas.height = rows;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(cols, rows);

  // grid row 0 is the NORTH edge; canvas row 0 is the TOP — same orientation,
  // so no vertical flip is needed. col 0 is the WEST edge = canvas left. Good.
  const span = Math.max(domainMax - domainMin, 1e-6);
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const v = values[r][c];
      const idx = (r * cols + c) * 4;
      if (v < MIN_VISIBLE_MS) {
        img.data[idx + 3] = 0; // transparent
        continue;
      }
      const t = (v - domainMin) / span;
      const [red, green, blue] = windColor(t);
      img.data[idx] = red;
      img.data[idx + 1] = green;
      img.data[idx + 2] = blue;
      img.data[idx + 3] = windAlpha(t); // faint where weak, near-opaque at peak
    }
  }
  ctx.putImageData(img, 0, 0);

  const [lonMin, latMin, lonMax, latMax] = bounds;
  return { canvas, bounds: [lonMin, latMin, lonMax, latMax], domainMin, domainMax };
}

// Static max-swath raster. Its domainMax (the swath peak) is the fixed color-scale
// anchor for the whole bundle — the Legend reads it, and the per-frame rasters below
// reuse it so their colors never rescale as you scrub.
export function rasterizeWind(swath: WindSwath): WindRaster {
  const [rows, cols] = swath.shape;
  return rasterizeGrid(swath.values, rows, cols, swath.bounds, MIN_VISIBLE_MS, gridMax(swath.values));
}

// One raster per replay frame, ALL colored against the same fixed domain
// [MIN_VISIBLE_MS, domainMax] where domainMax is the bundle's max-swath peak (pass in
// rasterizeWind(...).domainMax). Precomputed once at load; playback just swaps which
// canvas the BitmapLayer points at — no re-rasterization per frame, no per-frame
// rescaling. The frames share one bounds/shape, so those come from the top level.
export function rasterizeWindFrames(windFrames: WindFrames, domainMax: number): WindRaster[] {
  const [rows, cols] = windFrames.shape;
  return windFrames.frames.map((f) =>
    rasterizeGrid(f.values, rows, cols, windFrames.bounds, MIN_VISIBLE_MS, domainMax),
  );
}
