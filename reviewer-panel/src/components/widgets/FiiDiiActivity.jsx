import { Row, num } from './_shared.jsx';

export default function FiiDiiActivity({ data: p }) {
  return (
    <div>
      <div className="text-xs text-gray-500 mb-2">{p.date}</div>
      {(p.rows || []).map((r, i) => (
        <Row key={i} label={r.label_or || r.label_en} value={`Net: ${num(r.net)} Cr`}
             right={<span className={`text-xs font-semibold ${r.net >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{r.net >= 0 ? 'BUY' : 'SELL'}</span>} />
      ))}
    </div>
  );
}
