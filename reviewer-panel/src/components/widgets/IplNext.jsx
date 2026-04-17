import { Row } from './_shared.jsx';

export default function IplNext({ data: p }) {
  return p.rows?.length ? (
    <div>{p.rows.slice(0, 3).map((m, i) => (
      <Row key={i} label={`${m.home} vs ${m.away}`} value={m.date}
           right={<span className="text-xs text-gray-500">{m.time}</span>} />
    ))}</div>
  ) : <div className="text-sm text-gray-400 italic">No upcoming matches</div>;
}
