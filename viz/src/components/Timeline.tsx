interface Props {
  frameCount: number;
  currentFrame: number;
  isPlaying: boolean;
  time: string; // ISO8601 timestamp of the current frame
  onTogglePlay: () => void;
  onScrub: (frame: number) => void;
}

// Format the frame's real UTC timestamp as "YYYY-MM-DD HH:MM UTC" — the storm's
// actual clock from the data, not a synthetic playback counter.
function formatUTC(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, '0');
  return (
    `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())} ` +
    `${p(d.getUTCHours())}:${p(d.getUTCMinutes())} UTC`
  );
}

export default function Timeline({
  frameCount,
  currentFrame,
  isPlaying,
  time,
  onTogglePlay,
  onScrub,
}: Props) {
  return (
    <div className="panel timeline">
      <button
        className="play-btn"
        onClick={onTogglePlay}
        aria-label={isPlaying ? 'Pause' : 'Play'}
      >
        {isPlaying ? '❚❚' : '▶'}
      </button>
      <div className="timeline-body">
        <div className="timeline-time">{formatUTC(time)}</div>
        <input
          className="scrub"
          type="range"
          min={0}
          max={frameCount - 1}
          step={1}
          value={currentFrame}
          onChange={(e) => onScrub(Number(e.target.value))}
        />
        <div className="timeline-frame">
          frame {currentFrame + 1} / {frameCount}
        </div>
      </div>
    </div>
  );
}
