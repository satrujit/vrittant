import { Row } from './_shared.jsx';

export default function IccFixtures({ data: p }) {
  return (
    <div>{(p.rows || []).slice(0, 6).map((m, i) => (
      <Row key={i} label={m.match} value={m.date}
           right={<span className="text-xs text-gray-500 truncate max-w-[120px]">{m.tournament}</span>} />
    ))}</div>
  );
}
