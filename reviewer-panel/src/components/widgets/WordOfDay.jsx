export default function WordOfDay({ data: p }) {
  return (
    <div>
      <div className="text-2xl font-bold text-gray-900">{p.word}</div>
      <div className="text-xs text-gray-500 mb-2">{p.phonetic} · <span className="italic">{p.part}</span></div>
      <div className="text-sm text-gray-700">{p.definition}</div>
      {p.example && <div className="text-sm italic text-gray-500 mt-2 border-l-2 border-amber-400 pl-2">{p.example}</div>}
    </div>
  );
}
