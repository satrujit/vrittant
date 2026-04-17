import { Row } from './_shared.jsx';

export default function HundiCollection({ data: p }) {
  return (
    <div>{(p.rows || []).map((r, i) => (
      <Row key={i} label={r.type} value={r.amount_label} />
    ))}</div>
  );
}
