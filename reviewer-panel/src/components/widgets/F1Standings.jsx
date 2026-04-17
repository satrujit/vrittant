import { Row } from './_shared.jsx';

export default function F1Standings({ data: p }) {
  return (
    <div>{(p.rows || []).slice(0, 8).map((r, i) => (
      <Row key={i} label={`${r.pos}. ${r.name}`} value={`${r.points} pts`}
           right={<span className="text-xs text-gray-500 truncate max-w-[80px]">{r.team}</span>} />
    ))}</div>
  );
}
