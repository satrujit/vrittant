import { useEffect, useMemo, useState } from 'react';
import { LayoutGrid } from 'lucide-react';
import { CATALOG } from '../components/widgets';
import { PageHeader } from '../components/common';

// Same host-routing as the rest of the app: UAT site → UAT backend
const API_BASE = (typeof window !== 'undefined' && window.location.hostname === 'vrittant-uat.web.app')
  ? 'https://vrittant-api-uat-829303072442.asia-south1.run.app'
  : import.meta.env.VITE_API_BASE;

/* ────────── Display metadata: title (English) + category + source label ────────── */
const META = {
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

function FallbackRenderer({ value }) {
  return <pre className="text-xs text-gray-600 whitespace-pre-wrap break-words">{JSON.stringify(value, null, 2).slice(0, 400)}</pre>;
}

function WidgetCard({ id, payload, allWidgets }) {
  const meta = META[id];
  const title = meta?.title || id;
  const Renderer = CATALOG[id];
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
        {Renderer ? <Renderer data={payload} allWidgets={allWidgets} /> : <FallbackRenderer value={payload} />}
      </div>
      {meta?.source && (
        <div className="mt-3 pt-2 border-t border-dashed border-gray-200 text-[10px] text-gray-400 text-right">
          Source: {meta.source}
        </div>
      )}
    </div>
  );
}

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
    const w = data.widgets || {};
    const all = Object.keys(META).filter(id => {
      const meta = META[id];
      if (meta.virtual) return meta.virtual.some(vid => w[vid]); // composite needs at least one source
      return id in w;
    });
    const q = search.trim().toLowerCase();
    return all
      .filter(id => activeCat === 'All' || META[id].category === activeCat)
      .filter(id => !q || META[id].title.toLowerCase().includes(q) || id.includes(q))
      .sort((a, b) => {
        const ca = CATEGORY_ORDER.indexOf(META[a].category);
        const cb = CATEGORY_ORDER.indexOf(META[b].category);
        if (ca !== cb) return ca - cb;
        return META[a].title.localeCompare(META[b].title);
      });
  }, [data, search, activeCat]);

  if (error) return <div className="p-8 text-red-600">Failed to load widgets: {error}</div>;
  if (!data) return <div className="p-8 text-gray-500">Loading…</div>;

  const categories = ['All', ...CATEGORY_ORDER];

  return (
    <div className="p-6 lg:p-8 max-w-[1400px]">
      <PageHeader
        icon={LayoutGrid}
        title="Newspaper Widgets"
        subtitle={`As of ${data.as_of || '—'} · ${ordered.length} widgets`}
        actions={
          <input
            type="search"
            placeholder="Search widgets…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="px-3 py-1.5 text-sm border border-input rounded-md w-64 focus:outline-none focus:ring-2 focus:ring-primary"
          />
        }
      />
      <div className="mb-5">
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
