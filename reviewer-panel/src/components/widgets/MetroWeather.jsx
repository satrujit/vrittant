import { Row, num } from './_shared.jsx';

export default function MetroWeather({ data: p }) {
  return (
    <div>{(p.rows || []).map((r, i) => (
      <Row key={i} label={r.name_or || r.name_en} value={`${num(r.temp, 1)}°C`}
           right={<span className="text-xs text-gray-500">{num(r.tmin, 0)}–{num(r.tmax, 0)}°</span>} />
    ))}</div>
  );
}
