export default function WikiFeatured({ data: p }) {
  return (
    <div>
      {p.image && <img src={p.image} alt="" loading="lazy" className="w-full h-36 object-cover rounded mb-2" />}
      <a href={p.url} target="_blank" rel="noreferrer" className="text-sm font-semibold text-orange-600 hover:underline">{p.title || 'Read on Wikipedia →'}</a>
      {p.extract && <div className="text-sm text-gray-700 mt-1 line-clamp-5">{p.extract}</div>}
    </div>
  );
}
