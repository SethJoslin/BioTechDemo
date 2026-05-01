export default function RunList({ runs, onSelect }) {
  return (
    <div>
      {runs.map(r => (
        <button key={r.id} onClick={() => onSelect(r.id)}>
          {r.id} — {r.date}
        </button>
      ))}
    </div>
  );
}
