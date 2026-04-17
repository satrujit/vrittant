import { num, weatherIcon, weatherBg } from './_shared.jsx';

export default function Weather({ data: p }) {
  const cur = p.current || {};
  return (
    <div>
      <div className={`flex items-center gap-3 p-3 rounded-lg mb-3 ${weatherBg(cur.label)}`}>
        <span className="text-4xl">{weatherIcon(cur.label)}</span>
        <div>
          <div className="text-2xl font-bold text-gray-900">{num(cur.temp_c, 1)}°C</div>
          <div className="text-xs text-gray-600">{p.city} · {cur.label}</div>
          {cur.humidity != null && <div className="text-xs text-gray-500">Humidity {cur.humidity}%</div>}
        </div>
      </div>
      {(p.days || []).slice(0, 5).map((d, i) => (
        <div key={i} className="flex items-center gap-2 py-1 text-sm border-b border-gray-100 last:border-0">
          <span className="text-lg">{weatherIcon(d.label)}</span>
          <span className="text-gray-600 w-24">{d.date}</span>
          <span className="flex-1 text-gray-500 text-xs truncate">{d.label}</span>
          <span className="font-medium text-gray-900">{num(d.min_c, 0)}–{num(d.max_c, 0)}°</span>
        </div>
      ))}
    </div>
  );
}
