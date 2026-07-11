import type { ManifestEntry, Meta } from '../types';

interface Props {
  manifest: ManifestEntry[];
  selectedHash: string | null;
  onSelect: (entry: ManifestEntry) => void;
  meta: Meta | null;
}

export default function ScenarioPicker({ manifest, selectedHash, onSelect, meta }: Props) {
  return (
    <div className="panel picker">
      <h1>Landfall Viz — 3D scenario replay</h1>
      <div className="storm-buttons">
        {manifest.map((entry) => (
          <button
            key={entry.scenario_hash}
            className={entry.scenario_hash === selectedHash ? 'active' : ''}
            onClick={() => onSelect(entry)}
          >
            {entry.label}
          </button>
        ))}
      </div>
      {meta && (
        <div className="storm-meta">
          {meta.storm_name} ({meta.year}) · IBTrACS {meta.ibtracs_name}
          <br />
          hazard model {meta.hazard_model} · {meta.landfall_version}
        </div>
      )}
    </div>
  );
}
