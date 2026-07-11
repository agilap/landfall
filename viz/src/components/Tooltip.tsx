import type { DamageColumn } from '../types';

export interface HoverInfo {
  column: DamageColumn;
  x: number;
  y: number;
}

interface Props {
  hover: HoverInfo | null;
  sourceCacheKey: string;
}

const usd = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
});

export default function Tooltip({ hover, sourceCacheKey }: Props) {
  if (!hover) return null;
  const { column, x, y } = hover;
  return (
    <div className="tooltip" style={{ left: x, top: y }}>
      <div className="muni">{column.municipality}</div>
      <div className="prov">{column.province}</div>
      <div className="dmg">{usd.format(column.damage_usd)}</div>
      {column.affected_population != null && (
        <div className="prov">
          {Math.round(column.affected_population).toLocaleString('en-US')} affected
        </div>
      )}
      <div className="prov-hash">source cache {sourceCacheKey}</div>
    </div>
  );
}
