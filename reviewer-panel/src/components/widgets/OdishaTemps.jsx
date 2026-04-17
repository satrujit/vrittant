import { Row, num } from './_shared.jsx';

export default function OdishaTemps({ data: p }) {
  return (
    <div>{(p.cities || []).slice(0, 10).map((c, i) => (
      <Row key={i} label={c.name_or || c.name_en} value={`${num(c.now, 1)}°C`}
           right={<span className="text-xs text-gray-500">{num(c.min, 0)}–{num(c.max, 0)}°</span>} />
    ))}</div>
  );
}
