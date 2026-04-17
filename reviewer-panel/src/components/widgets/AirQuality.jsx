export default function AirQuality({ data: p }) {
  const aqi = p.aqi;
  const aqiColor = aqi <= 50 ? 'text-emerald-600' : aqi <= 100 ? 'text-yellow-600' : aqi <= 150 ? 'text-orange-600' : aqi <= 200 ? 'text-red-600' : 'text-purple-700';
  const bgColor = aqi <= 50 ? 'bg-emerald-50' : aqi <= 100 ? 'bg-yellow-50' : aqi <= 150 ? 'bg-orange-50' : aqi <= 200 ? 'bg-red-50' : 'bg-purple-50';
  return (
    <div>
      <div className={`p-3 rounded-lg mb-3 ${bgColor} text-center`}>
        <div className={`text-4xl font-bold ${aqiColor}`}>{aqi}</div>
        <div className="text-xs uppercase tracking-wide text-gray-500">AQI</div>
        <div className="text-sm text-gray-700 mt-1">{p.band_or || p.band_en}</div>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600">
        <div>PM2.5: <span className="text-gray-900 font-medium">{p.pm2_5}</span></div>
        <div>PM10: <span className="text-gray-900 font-medium">{p.pm10}</span></div>
        <div>NO₂: <span className="text-gray-900 font-medium">{p.no2}</span></div>
        <div>SO₂: <span className="text-gray-900 font-medium">{p.so2}</span></div>
        <div>O₃: <span className="text-gray-900 font-medium">{p.ozone}</span></div>
        <div>CO: <span className="text-gray-900 font-medium">{p.co}</span></div>
      </div>
    </div>
  );
}
