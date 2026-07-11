import type { Meta } from '../types';

interface Props {
  meta: Meta;
}

// Always-visible provenance footer — PRD §4.4 "the disclaimer travels";
// hash + source cache key are shown unconditionally, not gated behind hover.
export default function Footer({ meta }: Props) {
  return (
    <div className="footer">
      <span className="disclaimer">{meta.disclaimer}</span>
      <span className="hashes">
        scenario {meta.scenario_hash} · source cache {meta.source_cache_key} ·{' '}
        {meta.landfall_version}
      </span>
    </div>
  );
}
