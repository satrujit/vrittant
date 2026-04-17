export default function GitaVerse({ data: p }) {
  return (
    <div>
      <div className="text-xs text-gray-500 mb-2 uppercase tracking-wide">Chapter {p.chapter} · Verse {p.verse}</div>
      <div className="text-sm italic text-gray-800 border-l-2 border-orange-500 pl-3 whitespace-pre-line bg-orange-50/30 py-2 rounded-r">
        {p.sanskrit}
      </div>
      {p.english_meaning && <div className="text-sm text-gray-700 mt-3 whitespace-pre-line leading-relaxed">{p.english_meaning}</div>}
    </div>
  );
}
