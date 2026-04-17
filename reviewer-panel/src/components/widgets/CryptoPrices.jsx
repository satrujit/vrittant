import { Row, inr, pct } from './_shared.jsx';

export default function CryptoPrices({ data: p }) {
  return (
    <div>{(p.rows || []).map((r, i) => (
      <Row key={i} label={r.name_or || r.name_en} value={inr(r.price)} right={pct(r.change_pct)} />
    ))}</div>
  );
}
