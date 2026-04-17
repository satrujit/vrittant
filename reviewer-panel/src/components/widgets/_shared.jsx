/* Shared helpers and primitives for widget renderers */

export const inr = (n) => '₹' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 });

export const num = (n, d = 2) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: d });

export const pct = (n) => {
  const v = Number(n);
  const cls = v >= 0 ? 'text-emerald-600' : 'text-red-600';
  return <span className={cls + ' font-medium'}>{v >= 0 ? '+' : ''}{v.toFixed(2)}%</span>;
};

/** Pick a weather emoji from a textual label */
export function weatherIcon(label = '') {
  const s = label.toLowerCase();
  if (/thunder|storm/.test(s)) return '⛈️';
  if (/snow|sleet/.test(s)) return '❄️';
  if (/shower|drizzle|rain/.test(s)) return '🌧️';
  if (/fog|mist|haze/.test(s)) return '🌫️';
  if (/overcast|cloud/.test(s)) return '☁️';
  if (/partly|few/.test(s)) return '⛅';
  if (/clear|sunny|fair/.test(s)) return '☀️';
  return '🌤️';
}

/** Background tint for a weather label */
export function weatherBg(label = '') {
  const s = label.toLowerCase();
  if (/thunder|storm/.test(s)) return 'bg-purple-50';
  if (/rain|shower/.test(s)) return 'bg-blue-50';
  if (/cloud|overcast/.test(s)) return 'bg-slate-50';
  if (/clear|sunny/.test(s)) return 'bg-yellow-50';
  if (/snow/.test(s)) return 'bg-cyan-50';
  return 'bg-sky-50';
}

export const Row = ({ label, value, right }) => (
  <div className="flex items-baseline justify-between gap-3 py-1 border-b border-gray-100 last:border-0">
    <span className="text-sm text-gray-700 truncate">{label}</span>
    <span className="text-sm font-medium text-gray-900 shrink-0 flex items-center gap-2">
      {value}
      {right}
    </span>
  </div>
);
