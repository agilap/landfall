import { windColor } from '../wind';

interface Props {
  windDomainMin: number;
  windDomainMax: number;
  windUnits: string;
  columnScaleLabel: string;
}

// Build a CSS gradient matching the wind color ramp so the legend is faithful
// to what's drawn on the map.
function rampGradient(): string {
  const n = 12;
  const stops: string[] = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const [r, g, b] = windColor(t);
    stops.push(`rgb(${r},${g},${b}) ${(t * 100).toFixed(0)}%`);
  }
  return `linear-gradient(90deg, ${stops.join(', ')})`;
}

export default function Legend({
  windDomainMin,
  windDomainMax,
  windUnits,
  columnScaleLabel,
}: Props) {
  const mid = (windDomainMin + windDomainMax) / 2;
  return (
    <div className="panel legend">
      <h2>Max sustained wind ({windUnits})</h2>
      <div className="ramp" style={{ background: rampGradient() }} />
      <div className="ramp-labels">
        <span>{windDomainMin.toFixed(0)}</span>
        <span>{mid.toFixed(0)}</span>
        <span>{windDomainMax.toFixed(0)}</span>
      </div>
      <div className="scale-note">
        Grid drawn at native 150″ (0.0417°) resolution — one texel per model cell,
        no smoothing. Cells below {windDomainMin.toFixed(0)} {windUnits} are transparent.
      </div>
      <div className="scale-note">
        <span className="swatch" />
        Damage columns: {columnScaleLabel}
      </div>
      <div className="scale-note">
        <span className="swatch track-swatch" />
        Storm track (chronological)
      </div>
    </div>
  );
}
