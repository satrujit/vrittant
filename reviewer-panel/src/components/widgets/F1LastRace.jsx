import { Row } from './_shared.jsx';

export default function F1LastRace({ data: p }) {
  return (
    <div>
      <div className="text-sm font-medium mb-1">{p.name}</div>
      <div className="text-xs text-gray-500 mb-2">{p.date}</div>
      {(p.rows || []).slice(0, 5).map((r, i) => {
        const podium = ['🥇', '🥈', '🥉'][i];
        return (
          <Row key={i}
               label={<span>{podium ? `${podium} ` : `${r.pos}. `}{r.name}</span>}
               value={r.team} />
        );
      })}
    </div>
  );
}
