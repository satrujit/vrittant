export default function ChessPuzzle({ data: p }) {
  return (
    <div className="text-center py-2">
      <div className="text-3xl mb-2">♟️</div>
      <div className="text-sm font-semibold text-gray-900">Rating: {p.rating}</div>
      {p.themes && <div className="text-xs text-gray-500 mt-1 mb-3">{(p.themes || []).slice(0, 3).join(' · ')}</div>}
      <a href={p.url} target="_blank" rel="noreferrer" className="inline-block text-sm text-white bg-pink-500 hover:bg-pink-600 px-4 py-1.5 rounded">Solve on Lichess →</a>
    </div>
  );
}
