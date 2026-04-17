export default function TriviaQuestion({ data: p }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-amber-600 font-semibold mb-1">{p.category}</div>
      <div className="text-sm text-gray-900 mb-2">{p.question}</div>
      <ul className="text-sm space-y-1">
        {(p.options || []).map((o, i) => (
          <li key={i} className={o === p.answer ? 'text-emerald-700 font-semibold flex items-center gap-1' : 'text-gray-700'}>
            {o === p.answer && '✓ '}{o}
          </li>
        ))}
      </ul>
    </div>
  );
}
