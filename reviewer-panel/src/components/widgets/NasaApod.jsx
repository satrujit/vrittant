export default function NasaApod({ data: p }) {
  return (
    <div>
      {p.image_url && <img src={p.image_url} alt="" loading="lazy" className="w-full h-44 object-cover rounded mb-2" />}
      <div className="text-sm font-medium text-gray-900">{p.title}</div>
      <div className="text-xs text-gray-500 mt-1">{p.date}{p.copyright ? ` · © ${p.copyright}` : ''}</div>
    </div>
  );
}
