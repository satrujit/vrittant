export default function IplPointsTable({ data: p }) {
  return (
    <div className="text-sm">
      <div className="grid grid-cols-[max-content_1fr_max-content_max-content] gap-x-3 text-xs text-gray-500 border-b border-gray-200 pb-1 mb-1">
        <span>#</span><span>Team</span><span>P</span><span>Pts</span>
      </div>
      {(p.rows || []).map((r, i) => (
        <div key={i} className={`grid grid-cols-[max-content_1fr_max-content_max-content] gap-x-3 py-0.5 ${i < 4 ? 'text-gray-900' : 'text-gray-600'}`}>
          <span className="text-gray-500">{r.pos}</span>
          <span className="font-medium">{r.team}</span>
          <span>{r.played}</span>
          <span className="font-semibold">{r.points}</span>
        </div>
      ))}
    </div>
  );
}
