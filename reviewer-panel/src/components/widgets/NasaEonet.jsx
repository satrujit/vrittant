export default function NasaEonet({ data: p }) {
  return (
    <ul className="space-y-1.5 text-sm text-gray-700">
      {(p.rows || []).slice(0, 6).map((r, i) => (
        <li key={i} className="flex items-start gap-2">
          <span>🔥</span>
          <span className="flex-1"><span className="text-gray-900">{r.title}</span> <span className="text-xs text-gray-400">({r.category})</span></span>
        </li>
      ))}
    </ul>
  );
}
