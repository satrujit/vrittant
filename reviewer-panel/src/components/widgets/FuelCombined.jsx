// Combined fuel widget — composed from 3 separate snapshots in `allWidgets`
export default function FuelCombined({ allWidgets }) {
  const p = allWidgets?.fuel_petrol_bhubaneswar;
  const d = allWidgets?.fuel_diesel_bhubaneswar;
  const c = allWidgets?.fuel_cng_bhubaneswar;
  const Tile = ({ label, price, unit, color }) => (
    <div className="flex flex-col items-center py-3 px-2 rounded-lg flex-1 min-w-0" style={{ background: color }}>
      <div className="text-xs text-gray-600 uppercase tracking-wide mb-1">{label}</div>
      <div className="text-2xl font-bold text-gray-900">₹{price}</div>
      <div className="text-[10px] text-gray-500">per {unit}</div>
    </div>
  );
  return (
    <div className="flex gap-2">
      {p && <Tile label="Petrol" price={p.price_inr} unit="L" color="#FEF3C7" />}
      {d && <Tile label="Diesel" price={d.price_inr} unit="L" color="#DBEAFE" />}
      {c && <Tile label="CNG"    price={c.price_inr} unit="kg" color="#D1FAE5" />}
    </div>
  );
}
