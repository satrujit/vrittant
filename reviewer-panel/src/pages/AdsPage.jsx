import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Plus, Loader2, Megaphone, IndianRupee, CalendarDays, ClipboardList, Paperclip,
} from 'lucide-react';
import { fetchAds, fetchReporters, fetchAdvertisers } from '../services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { useI18n } from '../i18n';

const ALL_SENTINEL = '__all__';

const STATUS_COLORS = {
  draft:      'bg-gray-100 text-gray-700',
  submitted:  'bg-amber-100 text-amber-800',
  in_review:  'bg-blue-100 text-blue-800',
  approved:   'bg-emerald-100 text-emerald-800',
  scheduled:  'bg-violet-100 text-violet-800',
  published:  'bg-green-100 text-green-800',
  rejected:   'bg-rose-100 text-rose-800',
  cancelled:  'bg-zinc-100 text-zinc-600',
};

const STATUSES = ['draft','submitted','in_review','approved','scheduled','published','rejected','cancelled'];
const AD_TYPES = ['display','classified','jacket','supplement','govt_tender','obituary','matrimonial','public_notice'];

const SIZE_LABELS = {
  full_page: 'Full page', half_page: 'Half page', quarter_page: 'Quarter page',
  eighth_page: '⅛ page', strip: 'Strip', skybox: 'Skybox', ear_panel: 'Ear panel',
  single_col: 'Single col', double_col: 'Double col', custom: 'Custom',
};

function formatINR(n) {
  if (n === null || n === undefined || isNaN(n)) return '—';
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)}Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)}L`;
  if (n >= 1e3) return `₹${(n / 1e3).toFixed(1)}k`;
  return `₹${Math.round(n)}`;
}

function fmtDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
}

function KpiCard({ icon: Icon, label, value, accent = 'text-foreground' }) {
  return (
    <div className="bg-card border border-border rounded-xl p-4 flex items-center gap-3">
      <div className="size-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
        <Icon size={18} />
      </div>
      <div className="min-w-0">
        <div className="text-[11px] uppercase tracking-wide text-muted-foreground font-medium">{label}</div>
        <div className={`text-lg font-bold ${accent}`}>{value}</div>
      </div>
    </div>
  );
}

export default function AdsPage() {
  const { t } = useI18n();
  const navigate = useNavigate();

  const [ads, setAds] = useState([]);
  const [kpis, setKpis] = useState(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const [reporters, setReporters] = useState([]);
  const [advertisers, setAdvertisers] = useState([]);

  const [statusFilter, setStatusFilter] = useState('');
  const [adTypeFilter, setAdTypeFilter] = useState('');
  const [advertiserFilter, setAdvertiserFilter] = useState('');
  const [reporterFilter, setReporterFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [search, setSearch] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        status: statusFilter || undefined,
        ad_type: adTypeFilter || undefined,
        advertiser_id: advertiserFilter || undefined,
        brought_by: reporterFilter || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        search: search || undefined,
        limit: 100,
      };
      const data = await fetchAds(params);
      setAds(data.ads || []);
      setTotal(data.total || 0);
      setKpis(data.kpis || null);
    } catch (e) {
      console.error('Failed to load ads', e);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, adTypeFilter, advertiserFilter, reporterFilter, dateFrom, dateTo, search]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    fetchReporters().then((d) => setReporters(d.reporters || [])).catch(() => {});
    fetchAdvertisers({ limit: 200 }).then(setAdvertisers).catch(() => {});
  }, []);

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Advertisement Tracker</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Create, review and schedule ads. Submitted ads appear in the editorial review queue on their target dates.
          </p>
        </div>
        <Button onClick={() => navigate('/ads/new')} className="gap-2">
          <Plus size={16} /> New ad
        </Button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <KpiCard icon={ClipboardList} label="Pending review" value={kpis?.pending_review ?? '—'} accent="text-amber-600" />
        <KpiCard icon={CalendarDays}  label="Scheduled"      value={kpis?.scheduled ?? '—'}      accent="text-violet-600" />
        <KpiCard icon={Megaphone}     label="Published"      value={kpis?.published ?? '—'}      accent="text-emerald-600" />
        <KpiCard icon={IndianRupee}   label="Booked value"   value={formatINR(kpis?.total_booked_value || 0)} />
      </div>

      {/* Filters */}
      <div className="bg-card border border-border rounded-xl p-4 mb-4 grid grid-cols-1 md:grid-cols-6 gap-3">
        <div className="md:col-span-2">
          <Label className="text-xs">Search</Label>
          <Input placeholder="Title or advertiser…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div>
          <Label className="text-xs">Status</Label>
          <Select value={statusFilter || ALL_SENTINEL} onValueChange={(v) => setStatusFilter(v === ALL_SENTINEL ? '' : v)}>
            <SelectTrigger><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_SENTINEL}>All</SelectItem>
              {STATUSES.map((s) => <SelectItem key={s} value={s}>{s.replace('_',' ')}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">Type</Label>
          <Select value={adTypeFilter || ALL_SENTINEL} onValueChange={(v) => setAdTypeFilter(v === ALL_SENTINEL ? '' : v)}>
            <SelectTrigger><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_SENTINEL}>All</SelectItem>
              {AD_TYPES.map((s) => <SelectItem key={s} value={s}>{s.replace('_',' ')}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">Advertiser</Label>
          <Select value={advertiserFilter || ALL_SENTINEL} onValueChange={(v) => setAdvertiserFilter(v === ALL_SENTINEL ? '' : v)}>
            <SelectTrigger><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_SENTINEL}>All</SelectItem>
              {advertisers.map((a) => <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">Brought by</Label>
          <Select value={reporterFilter || ALL_SENTINEL} onValueChange={(v) => setReporterFilter(v === ALL_SENTINEL ? '' : v)}>
            <SelectTrigger><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_SENTINEL}>All</SelectItem>
              {reporters.map((r) => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">Publish from</Label>
          <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div>
          <Label className="text-xs">Publish to</Label>
          <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-muted-foreground">
            <Loader2 className="inline animate-spin mr-2" size={16} /> Loading…
          </div>
        ) : ads.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground">
            No ads match these filters. <Link to="/ads/new" className="text-primary underline">Create one →</Link>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Advertiser</TableHead>
                <TableHead>Type / Size</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Next date</TableHead>
                <TableHead>Editions</TableHead>
                <TableHead className="text-right">Value</TableHead>
                <TableHead>Brought by</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {ads.map((a) => (
                <TableRow
                  key={a.id}
                  className="cursor-pointer hover:bg-muted/30"
                  onClick={() => navigate(`/ads/${a.id}`)}
                >
                  <TableCell>
                    <div className="font-medium flex items-center gap-2">
                      {a.priority === 'urgent' && <span className="size-1.5 rounded-full bg-rose-500 shrink-0" />}
                      {a.title || <span className="text-muted-foreground italic">(untitled)</span>}
                      {a.attachment_count > 0 && (
                        <span className="text-muted-foreground inline-flex items-center gap-0.5 text-[11px]">
                          <Paperclip size={11} />{a.attachment_count}
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-muted-foreground">RC: {fmtDate(a.received_date)}</div>
                  </TableCell>
                  <TableCell>{a.advertiser_name}</TableCell>
                  <TableCell>
                    <div className="text-sm">{a.ad_type.replace('_',' ')}</div>
                    <div className="text-[11px] text-muted-foreground">{SIZE_LABELS[a.size_preset] || a.size_preset}</div>
                  </TableCell>
                  <TableCell>
                    <Badge className={`${STATUS_COLORS[a.status]} font-medium`}>{a.status.replace('_',' ')}</Badge>
                  </TableCell>
                  <TableCell>
                    <div>{fmtDate(a.next_publish_date)}</div>
                    {a.publish_dates.length > 1 && (
                      <div className="text-[11px] text-muted-foreground">+{a.publish_dates.length - 1} more</div>
                    )}
                  </TableCell>
                  <TableCell>
                    <span className="text-sm">{a.edition_count}</span>
                  </TableCell>
                  <TableCell className="text-right font-medium">{formatINR(a.negotiated_value)}</TableCell>
                  <TableCell className="text-sm">{a.brought_by_name}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <div className="text-[11px] text-muted-foreground mt-3">{total} ad{total === 1 ? '' : 's'} total</div>
    </div>
  );
}
