import { Row } from './_shared.jsx';

export default function IplRecent({ data: p }) {
  return (
    <div>{(p.rows || []).slice(0, 3).map((m, i) => (
      <Row key={i} label={`${m.home} vs ${m.away}`} value={m.date} />
    ))}</div>
  );
}
