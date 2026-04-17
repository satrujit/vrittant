import { useEffect, useMemo, useState } from 'react';

// Same host-routing as the rest of the app: UAT site → UAT backend
const API_BASE = (typeof window !== 'undefined' && window.location.hostname === 'vrittant-uat.web.app')
  ? 'https://vrittant-api-uat-829303072442.asia-south1.run.app'
  : import.meta.env.VITE_API_BASE;

/* ────────── Catalog: title (English) + category + source label ────────── */
const CATALOG = {
  // Markets
  stock_indices:        { title: 'Stock Indices',         category: 'Markets', source: 'Yahoo Finance' },
  fii_dii_activity:     { title: 'FII / DII Activity',    category: 'Markets', source: 'Moneycontrol' },
  commodities:          { title: 'Commodities',           category: 'Markets', source: 'Yahoo Finance' },
  crypto_prices:        { title: 'Crypto Prices',         category: 'Markets', source: 'CoinGecko' },
  currency_rates:       { title: 'Currency Rates (INR)',  category: 'Markets', source: 'ECB' },
  richest_people:       { title: 'Richest People',        category: 'Markets', source: 'Forbes' },
  upi_stats:            { title: 'UPI Stats',             category: 'Markets', source: 'NPCI' },

  // Local
  fuel_combined:           { title: 'Fuel — Bhubaneswar',    category: 'Local', source: 'CarDekho', virtual: ['fuel_petrol_bhubaneswar', 'fuel_diesel_bhubaneswar', 'fuel_cng_bhubaneswar'] },
  hundi_collection:        { title: 'Jagannath Temple Hundi', category: 'Local', source: 'Shree Jagannatha' },
  odisha_temps:            { title: 'Odisha Temperatures', category: 'Local', source: 'Open-Meteo' },

  // Weather & Environment
  weather:        { title: 'Weather Forecast',     category: 'Weather', source: 'Open-Meteo' },
  metro_weather:  { title: 'Metro Weather',        category: 'Weather', source: 'Open-Meteo' },
  air_quality:    { title: 'Air Quality',          category: 'Weather', source: 'Open-Meteo' },
  sun_moon:       { title: 'Sun & Moon',           category: 'Weather', source: 'Sunrise-Sunset' },
  earthquakes:    { title: 'Recent Earthquakes',   category: 'Weather', source: 'USGS' },
  nasa_eonet:     { title: 'Natural Events',       category: 'Weather', source: 'NASA EONET' },

  // Sports
  ipl_next:         { title: 'IPL — Next Match',    category: 'Sports', source: 'iplt20.com' },
  ipl_recent:       { title: 'IPL — Recent Result', category: 'Sports', source: 'iplt20.com' },
  ipl_points_table: { title: 'IPL — Points Table',  category: 'Sports', source: 'iplt20.com' },
  icc_fixtures:     { title: 'ICC Fixtures',        category: 'Sports', source: 'icc-cricket.com' },
  epl_next:         { title: 'Premier League — Next', category: 'Sports', source: 'football-data.org' },
  f1_last_race:     { title: 'F1 — Last Race',      category: 'Sports', source: 'Ergast' },
  f1_standings:     { title: 'F1 — Standings',      category: 'Sports', source: 'Ergast' },

  // Space
  iss_now:        { title: 'ISS Position',          category: 'Space', source: 'Open Notify' },
  people_in_space:{ title: 'People in Space',       category: 'Space', source: 'Open Notify' },
  spacex_next:    { title: 'SpaceX — Next Launch',  category: 'Space', source: 'SpaceX API' },
  nasa_apod:      { title: 'NASA Picture of the Day', category: 'Space', source: 'NASA APOD' },

  // Knowledge
  gita_verse:        { title: 'Gita Verse of the Day', category: 'Knowledge', source: 'Vedic Scriptures' },
  quote_of_day:      { title: 'Quote of the Day',      category: 'Knowledge', source: 'ZenQuotes' },
  word_of_day:       { title: 'Word of the Day',       category: 'Knowledge', source: 'Wordnik' },
  today_in_history:  { title: 'Today in History',      category: 'Knowledge', source: 'Wikipedia' },
  wiki_featured:     { title: 'Wikipedia — Featured',  category: 'Knowledge', source: 'Wikipedia' },
  wiki_on_this_day:  { title: 'Wikipedia — On This Day', category: 'Knowledge', source: 'Wikipedia' },
  trivia_question:   { title: 'Trivia',                category: 'Knowledge', source: 'Open Trivia DB' },

  // Puzzles & Entertainment
  chess_puzzle:    { title: 'Chess Puzzle',     category: 'Puzzles', source: 'Lichess' },
  sudoku_puzzle:   { title: 'Sudoku',           category: 'Puzzles', source: 'Sugoku' },
  upcoming_movies: { title: 'Upcoming Movies',  category: 'Entertainment', source: 'district.in' },
  new_year_countdown: { title: 'New Year Countdown', category: 'Entertainment', source: 'Calendar' },
};

const CATEGORY_ORDER = ['Markets', 'Local', 'Weather', 'Sports', 'Space', 'Knowledge', 'Puzzles', 'Entertainment'];

const CATEGORY_THEME = {
  Markets:       { dot: 'bg-blue-500',     pillBg: 'bg-blue-50',     pillText: 'text-blue-700' },
  Local:         { dot: 'bg-orange-500',   pillBg: 'bg-orange-50',   pillText: 'text-orange-700' },
  Weather:       { dot: 'bg-sky-500',      pillBg: 'bg-sky-50',      pillText: 'text-sky-700' },
  Sports:        { dot: 'bg-emerald-500',  pillBg: 'bg-emerald-50',  pillText: 'text-emerald-700' },
  Space:         { dot: 'bg-violet-500',   pillBg: 'bg-violet-50',   pillText: 'text-violet-700' },
  Knowledge:     { dot: 'bg-amber-500',    pillBg: 'bg-amber-50',    pillText: 'text-amber-700' },
  Puzzles:       { dot: 'bg-pink-500',     pillBg: 'bg-pink-50',     pillText: 'text-pink-700' },
  Entertainment: { dot: 'bg-rose-500',     pillBg: 'bg-rose-50',     pillText: 'text-rose-700' },
};

/* ────────── Helpers ────────── */
const inr = (n) => '₹' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 });
const num = (n, d = 2) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: d });
const pct = (n) => {
  const v = Number(n);
  const cls = v >= 0 ? 'text-emerald-600' : 'text-red-600';
  return <span className={cls + ' font-medium'}>{v >= 0 ? '+' : ''}{v.toFixed(2)}%</span>;
};

/** Pick a weather emoji from a textual label */
function weatherIcon(label = '') {
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
function weatherBg(label = '') {
  const s = label.toLowerCase();
  if (/thunder|storm/.test(s)) return 'bg-purple-50';
  if (/rain|shower/.test(s)) return 'bg-blue-50';
  if (/cloud|overcast/.test(s)) return 'bg-slate-50';
  if (/clear|sunny/.test(s)) return 'bg-yellow-50';
  if (/snow/.test(s)) return 'bg-cyan-50';
  return 'bg-sky-50';
}

const Row = ({ label, value, right }) => (
  <div className="flex items-baseline justify-between gap-3 py-1 border-b border-gray-100 last:border-0">
    <span className="text-sm text-gray-700 truncate">{label}</span>
    <span className="text-sm font-medium text-gray-900 shrink-0 flex items-center gap-2">
      {value}
      {right}
    </span>
  </div>
);

/* ────────── Per-widget renderers ────────── */
const RENDERERS = {
  stock_indices: (p) => (
    <div>{(p.rows || []).map((r, i) => (
      <Row key={i} label={r.label_or || r.label_en} value={num(r.price)} right={pct(r.pct)} />
    ))}</div>
  ),

  crypto_prices: (p) => (
    <div>{(p.rows || []).map((r, i) => (
      <Row key={i} label={r.name_or || r.name_en} value={inr(r.price)} right={pct(r.change_pct)} />
    ))}</div>
  ),

  commodities: (p) => (
    <div>{(p.rows || []).map((r, i) => (
      <Row key={i} label={r.label_or || r.label_en}
           value={r.inr != null ? inr(r.inr) : <span className="text-gray-500">${num(r.usd, 2)}</span>}
           right={r.inr != null ? <span className="text-xs text-gray-500">${num(r.usd, 0)}</span> : null} />
    ))}</div>
  ),

  currency_rates: (p) => (
    <div>{(p.rates || []).map((r, i) => (
      <Row key={i} label={r.code} value={inr(r.inr)} />
    ))}</div>
  ),

  fii_dii_activity: (p) => (
    <div>
      <div className="text-xs text-gray-500 mb-2">{p.date}</div>
      {(p.rows || []).map((r, i) => (
        <Row key={i} label={r.label_or || r.label_en} value={`Net: ${num(r.net)} Cr`}
             right={<span className={`text-xs font-semibold ${r.net >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{r.net >= 0 ? 'BUY' : 'SELL'}</span>} />
      ))}
    </div>
  ),

  richest_people: (p) => (
    <div>{(p.rows || []).slice(0, 8).map((r, i) => {
      const w = r.wealth_usd_b ?? r.worth;
      return (
        <Row key={i} label={`${r.rank}. ${r.name_or || r.name}`}
             value={<span className="text-emerald-700">${num(w, 1)}B</span>}
             right={<span className="text-xs text-gray-500 truncate max-w-[100px]">{r.src_or || r.src}</span>} />
      );
    })}</div>
  ),

  upi_stats: (p) => (
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
  ),

  // Combined fuel widget — composed from 3 separate snapshots
  fuel_combined: (_, all) => {
    const p = all?.fuel_petrol_bhubaneswar;
    const d = all?.fuel_diesel_bhubaneswar;
    const c = all?.fuel_cng_bhubaneswar;
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
  },

  hundi_collection: (p) => (
    <div>{(p.rows || []).map((r, i) => (
      <Row key={i} label={r.type} value={r.amount_label} />
    ))}</div>
  ),

  odisha_temps: (p) => (
    <div>{(p.cities || []).slice(0, 10).map((c, i) => (
      <Row key={i} label={c.name_or || c.name_en} value={`${num(c.now, 1)}°C`}
           right={<span className="text-xs text-gray-500">{num(c.min, 0)}–{num(c.max, 0)}°</span>} />
    ))}</div>
  ),

  metro_weather: (p) => (
    <div>{(p.rows || []).map((r, i) => (
      <Row key={i} label={r.name_or || r.name_en} value={`${num(r.temp, 1)}°C`}
           right={<span className="text-xs text-gray-500">{num(r.tmin, 0)}–{num(r.tmax, 0)}°</span>} />
    ))}</div>
  ),

  weather: (p) => {
    const cur = p.current || {};
    return (
      <div>
        <div className={`flex items-center gap-3 p-3 rounded-lg mb-3 ${weatherBg(cur.label)}`}>
          <span className="text-4xl">{weatherIcon(cur.label)}</span>
          <div>
            <div className="text-2xl font-bold text-gray-900">{num(cur.temp_c, 1)}°C</div>
            <div className="text-xs text-gray-600">{p.city} · {cur.label}</div>
            {cur.humidity != null && <div className="text-xs text-gray-500">Humidity {cur.humidity}%</div>}
          </div>
        </div>
        {(p.days || []).slice(0, 5).map((d, i) => (
          <div key={i} className="flex items-center gap-2 py-1 text-sm border-b border-gray-100 last:border-0">
            <span className="text-lg">{weatherIcon(d.label)}</span>
            <span className="text-gray-600 w-24">{d.date}</span>
            <span className="flex-1 text-gray-500 text-xs truncate">{d.label}</span>
            <span className="font-medium text-gray-900">{num(d.min_c, 0)}–{num(d.max_c, 0)}°</span>
          </div>
        ))}
      </div>
    );
  },

  air_quality: (p) => {
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
  },

  sun_moon: (p) => (
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
  ),

  earthquakes: (p) => (
    <div>{(p.rows || []).slice(0, 6).map((r, i) => {
      const sevColor = r.mag >= 6 ? 'bg-red-100 text-red-700' : r.mag >= 5 ? 'bg-orange-100 text-orange-700' : 'bg-yellow-100 text-yellow-700';
      return (
        <Row key={i} label={r.place}
             value={<span className={`px-1.5 py-0.5 text-xs rounded font-semibold ${sevColor}`}>M{r.mag}</span>}
             right={<span className="text-xs text-gray-500">{r.time}</span>} />
      );
    })}</div>
  ),

  nasa_eonet: (p) => (
    <ul className="space-y-1.5 text-sm text-gray-700">
      {(p.rows || []).slice(0, 6).map((r, i) => (
        <li key={i} className="flex items-start gap-2">
          <span>🔥</span>
          <span className="flex-1"><span className="text-gray-900">{r.title}</span> <span className="text-xs text-gray-400">({r.category})</span></span>
        </li>
      ))}
    </ul>
  ),

  ipl_next: (p) => p.rows?.length ? (
    <div>{p.rows.slice(0, 3).map((m, i) => (
      <Row key={i} label={`${m.home} vs ${m.away}`} value={m.date}
           right={<span className="text-xs text-gray-500">{m.time}</span>} />
    ))}</div>
  ) : <div className="text-sm text-gray-400 italic">No upcoming matches</div>,

  ipl_recent: (p) => (
    <div>{(p.rows || []).slice(0, 3).map((m, i) => (
      <Row key={i} label={`${m.home} vs ${m.away}`} value={m.date} />
    ))}</div>
  ),

  ipl_points_table: (p) => (
    <div className="text-sm">
      <div className="grid grid-cols-[max-content_1fr_max-content_max-content] gap-x-3 text-xs text-gray-500 border-b border-gray-200 pb-1 mb-1">
        <span>#</span><span>Team</span><span>P</span><span>Pts</span>
      </div>
      {(p.rows || []).map((r, i) => (
        <div key={i} className={`grid grid-cols-[max-content_1fr_max-content_max-content] gap-x-3 py-0.5 ${i < 4 ? 'text-gray-900' : 'text-gray-600'}`}>
          <span className="text-gray-500">{r.pos}</span>
          <span className="font-medium">{r.team}</span>
          <span>{r.played}</span>
          <span className="font-semibold">{r.points}</span>
        </div>
      ))}
    </div>
  ),

  icc_fixtures: (p) => (
    <div>{(p.rows || []).slice(0, 6).map((m, i) => (
      <Row key={i} label={m.match} value={m.date}
           right={<span className="text-xs text-gray-500 truncate max-w-[120px]">{m.tournament}</span>} />
    ))}</div>
  ),

  epl_next: (p) => (
    <div>{(p.rows || []).slice(0, 6).map((m, i) => (
      <Row key={i} label={`${m.home} vs ${m.away}`} value={m.date}
           right={<span className="text-xs text-gray-500">{m.time}</span>} />
    ))}</div>
  ),

  f1_last_race: (p) => (
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
  ),

  f1_standings: (p) => (
    <div>{(p.rows || []).slice(0, 8).map((r, i) => (
      <Row key={i} label={`${r.pos}. ${r.name}`} value={`${r.points} pts`}
           right={<span className="text-xs text-gray-500 truncate max-w-[80px]">{r.team}</span>} />
    ))}</div>
  ),

  iss_now: (p) => (
    <div className="bg-gradient-to-br from-violet-50 to-blue-50 rounded-lg p-4 text-center">
      <div className="text-3xl mb-2">🛰️</div>
      <div className="text-2xl font-bold text-gray-900">{num(p.lat, 2)}° {p.lat_dir}</div>
      <div className="text-2xl font-bold text-gray-900 mb-2">{num(p.lon, 2)}° {p.lon_dir}</div>
      <div className="text-xs text-gray-500">~7.66 km/s</div>
    </div>
  ),

  people_in_space: (p) => (
    <div>
      <div className="bg-violet-50 rounded-lg p-3 text-center mb-3">
        <div className="text-3xl font-bold text-violet-700">{p.count}</div>
        <div className="text-xs text-gray-600 uppercase tracking-wide">Astronauts in orbit</div>
      </div>
      {(p.crafts || []).map((c, i) => (
        <div key={i} className="mb-2">
          <div className="text-sm font-semibold text-gray-900 flex items-center gap-1">🚀 {c.name}</div>
          <div className="text-xs text-gray-600 leading-relaxed">{(c.people || []).join(', ')}</div>
        </div>
      ))}
    </div>
  ),

  spacex_next: (p) => (
    <div>
      <div className="text-2xl mb-1">🚀</div>
      <div className="text-sm font-medium">{p.name}</div>
      <div className="text-xs text-gray-500 mt-1">{new Date(p.date_utc).toLocaleString()}</div>
      {p.details && <div className="text-sm text-gray-700 mt-2">{p.details}</div>}
    </div>
  ),

  nasa_apod: (p) => (
    <div>
      {p.image_url && <img src={p.image_url} alt="" loading="lazy" className="w-full h-44 object-cover rounded mb-2" />}
      <div className="text-sm font-medium text-gray-900">{p.title}</div>
      <div className="text-xs text-gray-500 mt-1">{p.date}{p.copyright ? ` · © ${p.copyright}` : ''}</div>
    </div>
  ),

  gita_verse: (p) => (
    <div>
      <div className="text-xs text-gray-500 mb-2 uppercase tracking-wide">Chapter {p.chapter} · Verse {p.verse}</div>
      <div className="text-sm italic text-gray-800 border-l-2 border-orange-500 pl-3 whitespace-pre-line bg-orange-50/30 py-2 rounded-r">
        {p.sanskrit}
      </div>
      {p.english_meaning && <div className="text-sm text-gray-700 mt-3 whitespace-pre-line leading-relaxed">{p.english_meaning}</div>}
    </div>
  ),

  quote_of_day: (p) => (
    <div className="bg-amber-50/50 rounded-lg p-3">
      <div className="text-2xl text-amber-600 leading-none mb-1">"</div>
      <div className="text-sm italic text-gray-800 -mt-1">{p.text}</div>
      <div className="text-xs text-gray-500 mt-2 text-right">— {p.author}</div>
    </div>
  ),

  word_of_day: (p) => (
    <div>
      <div className="text-2xl font-bold text-gray-900">{p.word}</div>
      <div className="text-xs text-gray-500 mb-2">{p.phonetic} · <span className="italic">{p.part}</span></div>
      <div className="text-sm text-gray-700">{p.definition}</div>
      {p.example && <div className="text-sm italic text-gray-500 mt-2 border-l-2 border-amber-400 pl-2">{p.example}</div>}
    </div>
  ),

  today_in_history: (p) => (
    <div>
      <div className="text-xs text-gray-500 mb-2 uppercase tracking-wide">{p.label}</div>
      <ul className="space-y-2 text-sm text-gray-700">
        {(p.events || []).slice(0, 5).map((e, i) => <li key={i} className="flex gap-2"><span className="text-amber-500">•</span><span>{e.text}</span></li>)}
      </ul>
    </div>
  ),

  wiki_featured: (p) => (
    <div>
      {p.image && <img src={p.image} alt="" loading="lazy" className="w-full h-36 object-cover rounded mb-2" />}
      <a href={p.url} target="_blank" rel="noreferrer" className="text-sm font-semibold text-orange-600 hover:underline">{p.title || 'Read on Wikipedia →'}</a>
      {p.extract && <div className="text-sm text-gray-700 mt-1 line-clamp-5">{p.extract}</div>}
    </div>
  ),

  wiki_on_this_day: (p) => (
    <div>
      <div className="text-xs text-gray-500 mb-2 uppercase tracking-wide">{p.label}</div>
      <ul className="space-y-2 text-sm text-gray-700">
        {(p.events || []).slice(0, 5).map((e, i) => <li key={i} className="flex gap-2"><span className="text-amber-500">•</span><span>{e.text}</span></li>)}
      </ul>
    </div>
  ),

  trivia_question: (p) => (
    <div>
      <div className="text-xs uppercase tracking-wide text-amber-600 font-semibold mb-1">{p.category}</div>
      <div className="text-sm text-gray-900 mb-2">{p.question}</div>
      <ul className="text-sm space-y-1">
        {(p.options || []).map((o, i) => (
          <li key={i} className={o === p.answer ? 'text-emerald-700 font-semibold flex items-center gap-1' : 'text-gray-700'}>
            {o === p.answer && '✓ '}{o}
          </li>
        ))}
      </ul>
    </div>
  ),

  chess_puzzle: (p) => (
    <div className="text-center py-2">
      <div className="text-3xl mb-2">♟️</div>
      <div className="text-sm font-semibold text-gray-900">Rating: {p.rating}</div>
      {p.themes && <div className="text-xs text-gray-500 mt-1 mb-3">{(p.themes || []).slice(0, 3).join(' · ')}</div>}
      <a href={p.url} target="_blank" rel="noreferrer" className="inline-block text-sm text-white bg-pink-500 hover:bg-pink-600 px-4 py-1.5 rounded">Solve on Lichess →</a>
    </div>
  ),

  sudoku_puzzle: (p) => (
    <div>
      <div className="text-xs text-gray-500 mb-2">{p.date}</div>
      <table className="border-collapse text-xs mx-auto">
        <tbody>
          {(p.value || []).map((row, i) => (
            <tr key={i}>{row.map((c, j) => (
              <td key={j} className={`w-7 h-7 text-center border border-gray-300 ${(i % 3 === 2 && i < 8) ? 'border-b-gray-700 border-b-2' : ''} ${(j % 3 === 2 && j < 8) ? 'border-r-gray-700 border-r-2' : ''} ${c ? 'font-semibold text-gray-900' : ''}`}>
                {c || ''}
              </td>
            ))}</tr>
          ))}
        </tbody>
      </table>
    </div>
  ),

  // Movies — group by date, show ALL
  upcoming_movies: (p) => {
    const grouped = {};
    (p.rows || []).forEach(m => {
      const d = m.release_date;
      (grouped[d] ||= []).push(m);
    });
    return (
      <div className="space-y-3">
        {Object.entries(grouped).map(([date, movies]) => (
          <div key={date}>
            <div className="text-xs uppercase tracking-wide text-rose-600 font-semibold mb-1">🎬 {date}</div>
            <div className="flex flex-wrap gap-1.5">
              {movies.map((m, i) => (
                <span key={i} className="text-xs bg-rose-50 text-rose-900 px-2 py-1 rounded-full border border-rose-100">{m.title}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  },

  new_year_countdown: (p) => (
    <div className="bg-gradient-to-br from-rose-50 to-orange-50 rounded-lg p-4 text-center">
      <div className="text-xs text-gray-500 uppercase tracking-wide">Until {p.next_year}</div>
      <div className="text-4xl font-bold text-rose-600 my-1">{p.days}</div>
      <div className="text-xs text-gray-600">days · {p.hours}h {p.minutes}m</div>
    </div>
  ),
};

function FallbackRenderer({ value }) {
  return <pre className="text-xs text-gray-600 whitespace-pre-wrap break-words">{JSON.stringify(value, null, 2).slice(0, 400)}</pre>;
}

/* ────────── Card ────────── */
function WidgetCard({ id, payload, allWidgets }) {
  const meta = CATALOG[id];
  const title = meta?.title || id;
  const Renderer = RENDERERS[id];
  const theme = CATEGORY_THEME[meta?.category] || {};
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4 mb-4 break-inside-avoid">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-2">
          <span className={`inline-block w-1.5 h-1.5 rounded-full ${theme.dot || 'bg-gray-400'}`} />
          {title}
        </h3>
        {meta && <span className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full ${theme.pillBg} ${theme.pillText}`}>{meta.category}</span>}
      </div>
      <div className="text-gray-800">
        {Renderer ? Renderer(payload, allWidgets) : <FallbackRenderer value={payload} />}
      </div>
      {meta?.source && (
        <div className="mt-3 pt-2 border-t border-dashed border-gray-200 text-[10px] text-gray-400 text-right">
          Source: {meta.source}
        </div>
      )}
    </div>
  );
}

/* ────────── Page ────────── */
export default function WidgetsPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [activeCat, setActiveCat] = useState('All');

  useEffect(() => {
    fetch(`${API_BASE}/api/widgets/all`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(setData)
      .catch(e => setError(e.message));
  }, []);

  const ordered = useMemo(() => {
    if (!data) return [];
    // Build list of catalog IDs that have data (or are virtual composites)
    const w = data.widgets || {};
    const all = Object.keys(CATALOG).filter(id => {
      const meta = CATALOG[id];
      if (meta.virtual) return meta.virtual.some(vid => w[vid]); // composite needs at least one source
      return id in w;
    });
    const q = search.trim().toLowerCase();
    return all
      .filter(id => activeCat === 'All' || CATALOG[id].category === activeCat)
      .filter(id => !q || CATALOG[id].title.toLowerCase().includes(q) || id.includes(q))
      .sort((a, b) => {
        const ca = CATEGORY_ORDER.indexOf(CATALOG[a].category);
        const cb = CATEGORY_ORDER.indexOf(CATALOG[b].category);
        if (ca !== cb) return ca - cb;
        return CATALOG[a].title.localeCompare(CATALOG[b].title);
      });
  }, [data, search, activeCat]);

  if (error) return <div className="p-8 text-red-600">Failed to load widgets: {error}</div>;
  if (!data) return <div className="p-8 text-gray-500">Loading…</div>;

  const categories = ['All', ...CATEGORY_ORDER];

  return (
    <div className="px-6 py-6">
      <div className="mb-5">
        <div className="flex items-center justify-between gap-4 mb-3">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Newspaper Widgets</h1>
            <p className="text-xs text-gray-500">As of {data.as_of || '—'} · {ordered.length} widgets</p>
          </div>
          <input
            type="search"
            placeholder="Search widgets…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md w-64 focus:outline-none focus:ring-2 focus:ring-orange-500"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {categories.map(c => (
            <button
              key={c}
              onClick={() => setActiveCat(c)}
              className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                activeCat === c
                  ? 'bg-orange-500 text-white border-orange-500'
                  : 'bg-white text-gray-700 border-gray-300 hover:border-orange-400'
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="columns-1 md:columns-2 lg:columns-3 gap-4">
        {ordered.map(id => <WidgetCard key={id} id={id} payload={data.widgets[id]} allWidgets={data.widgets} />)}
      </div>
    </div>
  );
}
