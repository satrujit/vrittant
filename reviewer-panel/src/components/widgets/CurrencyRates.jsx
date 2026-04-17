import { Row, inr } from './_shared.jsx';

export default function CurrencyRates({ data: p }) {
  return (
    <div>{(p.rates || []).map((r, i) => (
      <Row key={i} label={r.code} value={inr(r.inr)} />
    ))}</div>
  );
}
