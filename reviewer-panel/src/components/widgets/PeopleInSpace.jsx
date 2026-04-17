export default function PeopleInSpace({ data: p }) {
  return (
    <div>
      <div className="bg-violet-50 rounded-lg p-3 text-center mb-3">
        <div className="text-3xl font-bold text-violet-700">{p.count}</div>
        <div className="text-xs text-gray-600 uppercase tracking-wide">Astronauts in orbit</div>
      </div>
      {(p.crafts || []).map((c, i) => (
        <div key={i} className="mb-2">
          <div className="text-sm font-semibold text-gray-900 flex items-center gap-1">🚀 {c.name}</div>
          <div className="text-xs text-gray-600 leading-relaxed">{(c.people || []).join(', ')}</div>
        </div>
      ))}
    </div>
  );
}
