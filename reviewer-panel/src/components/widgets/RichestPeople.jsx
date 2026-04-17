import { Row, num } from './_shared.jsx';

export default function RichestPeople({ data: p }) {
  return (
    <div>{(p.rows || []).slice(0, 8).map((r, i) => {
      const w = r.wealth_usd_b ?? r.worth;
      return (
        <Row key={i} label={`${r.rank}. ${r.name_or || r.name}`}
             value={<span className="text-emerald-700">${num(w, 1)}B</span>}
             right={<span className="text-xs text-gray-500 truncate max-w-[100px]">{r.src_or || r.src}</span>} />
      );
    })}</div>
  );
}
