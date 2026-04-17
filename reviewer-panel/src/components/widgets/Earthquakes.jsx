import { Row } from './_shared.jsx';

export default function Earthquakes({ data: p }) {
  return (
    <div>{(p.rows || []).slice(0, 6).map((r, i) => {
      const sevColor = r.mag >= 6 ? 'bg-red-100 text-red-700' : r.mag >= 5 ? 'bg-orange-100 text-orange-700' : 'bg-yellow-100 text-yellow-700';
      return (
        <Row key={i} label={r.place}
             value={<span className={`px-1.5 py-0.5 text-xs rounded font-semibold ${sevColor}`}>M{r.mag}</span>}
             right={<span className="text-xs text-gray-500">{r.time}</span>} />
      );
    })}</div>
  );
}
