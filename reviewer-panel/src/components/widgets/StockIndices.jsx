import { Row, num, pct } from './_shared.jsx';

export default function StockIndices({ data: p }) {
  return (
    <div>{(p.rows || []).map((r, i) => (
      <Row key={i} label={r.label_or || r.label_en} value={num(r.price)} right={pct(r.pct)} />
    ))}</div>
  );
}
