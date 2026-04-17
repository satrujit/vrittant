export default function QuoteOfDay({ data: p }) {
  return (
    <div className="bg-amber-50/50 rounded-lg p-3">
      <div className="text-2xl text-amber-600 leading-none mb-1">"</div>
      <div className="text-sm italic text-gray-800 -mt-1">{p.text}</div>
      <div className="text-xs text-gray-500 mt-2 text-right">— {p.author}</div>
    </div>
  );
}
