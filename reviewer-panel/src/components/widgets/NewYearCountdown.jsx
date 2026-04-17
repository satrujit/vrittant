export default function NewYearCountdown({ data: p }) {
  return (
    <div className="bg-gradient-to-br from-rose-50 to-orange-50 rounded-lg p-4 text-center">
      <div className="text-xs text-gray-500 uppercase tracking-wide">Until {p.next_year}</div>
      <div className="text-4xl font-bold text-rose-600 my-1">{p.days}</div>
      <div className="text-xs text-gray-600">days · {p.hours}h {p.minutes}m</div>
    </div>
  );
}
