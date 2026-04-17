// Movies — group by date, show ALL
export default function UpcomingMovies({ data: p }) {
  const grouped = {};
  (p.rows || []).forEach(m => {
    const d = m.release_date;
    (grouped[d] ||= []).push(m);
  });
  return (
    <div className="space-y-3">
      {Object.entries(grouped).map(([date, movies]) => (
        <div key={date}>
          <div className="text-xs uppercase tracking-wide text-rose-600 font-semibold mb-1">🎬 {date}</div>
          <div className="flex flex-wrap gap-1.5">
            {movies.map((m, i) => (
              <span key={i} className="text-xs bg-rose-50 text-rose-900 px-2 py-1 rounded-full border border-rose-100">{m.title}</span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
