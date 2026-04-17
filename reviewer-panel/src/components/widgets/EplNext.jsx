import { Row } from './_shared.jsx';

export default function EplNext({ data: p }) {
  return (
    <div>{(p.rows || []).slice(0, 6).map((m, i) => (
      <Row key={i} label={`${m.home} vs ${m.away}`} value={m.date}
           right={<span className="text-xs text-gray-500">{m.time}</span>} />
    ))}</div>
  );
}
