import { num } from './_shared.jsx';

export default function UpiStats({ data: p }) {
  return (
    <div>
      {(p.rows || []).slice(0, 4).map((r, i) => (
        <div key={i} className="py-2 border-b border-gray-100 last:border-0">
          <div className="flex items-baseline justify-between mb-1">
            <span className="text-sm font-medium text-gray-900">{r.label_or || r.label_en}</span>
            <span className="text-xs text-gray-500">{r.banks} banks</span>
          </div>
          <div className="grid grid-cols-2 gap-x-3 text-xs">
            <div><span className="text-gray-500">Total:</span> <span className="text-gray-900 font-medium">{num(r.volume_mn, 0)}M txn</span></div>
            <div><span className="text-gray-500">Value:</span> <span className="text-gray-900 font-medium">₹{num(r.value_lakh_cr ?? (r.value_cr / 100000), 2)} L Cr</span></div>
            {r.daily_volume_mn != null && <div><span className="text-gray-500">Daily avg:</span> <span className="text-gray-900 font-medium">{num(r.daily_volume_mn, 0)}M</span></div>}
            {r.daily_value_cr != null && <div><span className="text-gray-500">₹/day:</span> <span className="text-gray-900 font-medium">₹{num(r.daily_value_cr, 0)} Cr</span></div>}
          </div>
        </div>
      ))}
    </div>
  );
}
