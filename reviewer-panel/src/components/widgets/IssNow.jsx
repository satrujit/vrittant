import { num } from './_shared.jsx';

export default function IssNow({ data: p }) {
  return (
    <div className="bg-gradient-to-br from-violet-50 to-blue-50 rounded-lg p-4 text-center">
      <div className="text-3xl mb-2">🛰️</div>
      <div className="text-2xl font-bold text-gray-900">{num(p.lat, 2)}° {p.lat_dir}</div>
      <div className="text-2xl font-bold text-gray-900 mb-2">{num(p.lon, 2)}° {p.lon_dir}</div>
      <div className="text-xs text-gray-500">~7.66 km/s</div>
    </div>
  );
}
