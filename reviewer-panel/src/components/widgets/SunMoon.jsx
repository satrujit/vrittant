import { Row } from './_shared.jsx';

export default function SunMoon({ data: p }) {
  return (
    <div>
      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="bg-yellow-50 rounded-lg p-3 text-center">
          <div className="text-2xl">🌅</div>
          <div className="text-xs text-gray-600">Sunrise</div>
          <div className="text-lg font-bold text-gray-900">{p.sunrise}</div>
        </div>
        <div className="bg-orange-50 rounded-lg p-3 text-center">
          <div className="text-2xl">🌇</div>
          <div className="text-xs text-gray-600">Sunset</div>
          <div className="text-lg font-bold text-gray-900">{p.sunset}</div>
        </div>
      </div>
      <Row label="Daylight" value={p.daylight} />
      <Row label="Moon Phase" value={p.moon_phase_or || p.moon_phase_en} />
    </div>
  );
}
