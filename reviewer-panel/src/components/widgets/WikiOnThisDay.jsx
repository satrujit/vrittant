export default function WikiOnThisDay({ data: p }) {
  return (
    <div>
      <div className="text-xs text-gray-500 mb-2 uppercase tracking-wide">{p.label}</div>
      <ul className="space-y-2 text-sm text-gray-700">
        {(p.events || []).slice(0, 5).map((e, i) => <li key={i} className="flex gap-2"><span className="text-amber-500">•</span><span>{e.text}</span></li>)}
      </ul>
    </div>
  );
}
