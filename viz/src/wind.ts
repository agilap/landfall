import type { WindSwath } from './types';

// Sequential color stops for wind magnitude, normalized [0,1] over the swath's
// own value range. Multi-hue so magnitude differences read clearly; the legend
// states the actual m/s span so no false precision is implied.
const STOPS: Array<{ t: number; rgb: [number, number, number] }> = [
  { t: 0.0, rgb: [69, 117, 180] }, // blue — weak
  { t: 0.25, rgb: [116, 173, 209] },
  { t: 0.45, rgb: [171, 217, 233] },
  { t: 0.6, rgb: [254, 224, 144] }, // yellow
  { t: 0.75, rgb: [253, 174, 97] }, // orange
  { t: 0.88, rgb: [244, 109, 67] },
  { t: 1.0, rgb: [165, 0, 38] }, // deep red — strongest
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
// rather than painting a blue wash implying wind where the model has ~none.
const MIN_VISIBLE_MS = 17.0; // ~tropical-storm force; below this we don't color

// Rasterize the native-resolution grid to a canvas one texel per grid cell.
// No interpolation here; the BitmapLayer must also use nearest-neighbour
// sampling (see Scene3D) so cells stay crisp — honest rendering per PRD §4.3.
export function rasterizeWind(swath: WindSwath): WindRaster {
  const [rows, cols] = swath.shape;
  let domainMax = 0;
  for (const row of swath.values) {
    for (const v of row) if (v > domainMax) domainMax = v;
  }
  const domainMin = MIN_VISIBLE_MS;

  const canvas = document.createElement('canvas');
  canvas.width = cols;
  canvas.height = rows;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(cols, rows);

  // swath row 0 is the NORTH edge; canvas row 0 is the TOP — same orientation,
  // so no vertical flip is needed. col 0 is the WEST edge = canvas left. Good.
  const span = Math.max(domainMax - domainMin, 1e-6);
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const v = swath.values[r][c];
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
      img.data[idx + 3] = 200; // semi-opaque so terrain relief still reads
    }
  }
  ctx.putImageData(img, 0, 0);

  const [lonMin, latMin, lonMax, latMax] = swath.bounds;
  return {
    canvas,
    bounds: [lonMin, latMin, lonMax, latMax],
    domainMin,
    domainMax,
  };
}
