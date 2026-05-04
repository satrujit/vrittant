import { useEffect, useMemo, useState } from 'react';
import { Search, X } from 'lucide-react';
import { CATALOG } from '../components/widgets';
import { cn } from '@/lib/utils';

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
  return <pre className="text-xs text-muted-foreground whitespace-pre-wrap break-words">{JSON.stringify(value, null, 2).slice(0, 400)}</pre>;
}

function WidgetCard({ id, payload, allWidgets }) {
  const meta = META[id];
  const title = meta?.title || id;
  const Renderer = CATALOG[id];
  const theme = CATEGORY_THEME[meta?.category] || {};
  return (
    <div className="mb-4 break-inside-avoid rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <span className={`inline-block size-1.5 rounded-full ${theme.dot || 'bg-muted-foreground'}`} />
          {title}
        </h3>
        {meta && <span className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide ${theme.pillBg} ${theme.pillText}`}>{meta.category}</span>}
      </div>
      <div className="text-foreground">
        {Renderer ? <Renderer data={payload} allWidgets={allWidgets} /> : <FallbackRenderer value={payload} />}
      </div>
      {meta?.source && (
        <div className="mt-3 border-t border-dashed border-border pt-2 text-right text-[10px] text-muted-foreground">
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

  const categories = ['All', ...CATEGORY_ORDER];

  return (
    <div className="flex h-full flex-col">
      {/* Header strip — same inline-title pattern as Dashboard / All
          Stories / News Feed / Reporters. The "as of" + widget count
          replaces the old PageHeader subtitle so the timestamp stays
          visible (it tells reviewers how stale the cached payloads
          are). */}
      <header className="shrink-0 flex flex-wrap items-center justify-between gap-4 px-6 pt-6">
        <div className="flex flex-col gap-0.5 min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-foreground truncate">
            Newspaper Widgets
          </h1>
          <p className="text-[12.5px] text-muted-foreground">
            As of {data?.as_of || '—'} · {data ? ordered.length : 0} widgets
          </p>
        </div>
      </header>

      {/* Filter strip — same chrome as the queue pages: h-7,
          text-[11.5px], gap-1.5, border-b underline. Search left,
          category chips next to it. The chip strip uses the same
          segmented-control pattern as Dashboard's status filter and
          Reporters' period toggle. */}
      <div className="shrink-0 px-6 pt-3 pb-2">
        <div className="flex flex-wrap items-center gap-1.5 border-b border-border/60 px-1 py-2.5">
          <div className="relative">
            <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search widgets…"
              className="h-7 w-44 rounded-md border border-border/60 bg-card pl-7 pr-7 text-[11.5px] outline-none transition-colors focus:border-ring focus:shadow-[0_0_0_3px_rgba(250,108,56,0.08)]"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted-foreground hover:bg-accent"
                aria-label="Clear search"
              >
                <X size={12} />
              </button>
            )}
          </div>

          {/* Category chips — 9 categories total. Wrapping is allowed
              (flex-wrap on the parent strip) so on narrow widths they
              flow to a second line rather than scroll horizontally. */}
          <div className="flex items-center gap-0.5 rounded-md border border-border/60 bg-card p-0.5">
            {categories.map(c => (
              <button
                key={c}
                type="button"
                onClick={() => setActiveCat(c)}
                aria-pressed={activeCat === c}
                className={cn(
                  'rounded-[5px] px-2 py-1 text-[11.5px] font-medium transition-colors',
                  activeCat === c
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                )}
              >
                {c}
              </button>
            ))}
          </div>

          {(search || activeCat !== 'All') && (
            <button
              type="button"
              onClick={() => { setSearch(''); setActiveCat('All'); }}
              className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-[11.5px] text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <X size={12} />
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Widget masonry — kept as-is (this surface is a different
          paradigm from the queue tables). The cards themselves now use
          theme tokens (border-border, bg-card, text-foreground) so
          they adapt to dark mode. */}
      <div className="flex-1 min-h-0 overflow-auto px-6 pb-6 pt-2">
        {error ? (
          <div className="flex h-32 items-center justify-center text-sm text-destructive">
            Failed to load widgets: {error}
          </div>
        ) : !data ? (
          <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
            Loading…
          </div>
        ) : ordered.length === 0 ? (
          <div className="flex h-40 flex-col items-center justify-center gap-1 text-sm text-muted-foreground">
            <span className="text-base font-medium text-foreground">No widgets match.</span>
          </div>
        ) : (
          <div className="columns-1 gap-4 md:columns-2 lg:columns-3">
            {ordered.map(id => <WidgetCard key={id} id={id} payload={data.widgets[id]} allWidgets={data.widgets} />)}
          </div>
        )}
      </div>
    </div>
  );
}
