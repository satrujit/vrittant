import { Row, inr, num } from './_shared.jsx';

export default function Commodities({ data: p }) {
  return (
    <div>{(p.rows || []).map((r, i) => (
      <Row key={i} label={r.label_or || r.label_en}
           value={r.inr != null ? inr(r.inr) : <span className="text-gray-500">${num(r.usd, 2)}</span>}
           right={r.inr != null ? <span className="text-xs text-gray-500">${num(r.usd, 0)}</span> : null} />
    ))}</div>
  );
}
