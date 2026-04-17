export default function SpacexNext({ data: p }) {
  return (
    <div>
      <div className="text-2xl mb-1">🚀</div>
      <div className="text-sm font-medium">{p.name}</div>
      <div className="text-xs text-gray-500 mt-1">{new Date(p.date_utc).toLocaleString()}</div>
      {p.details && <div className="text-sm text-gray-700 mt-2">{p.details}</div>}
    </div>
  );
}
