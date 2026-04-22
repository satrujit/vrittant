import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Save, Send, Plus, X, Upload, Loader2, Paperclip, Calendar, Check,
} from 'lucide-react';
import {
  fetchAdvertisers, createAdvertiser,
  createAd, changeAdStatus, uploadAdAttachment,
  fetchReporters, fetchEditions,
} from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

const AD_TYPES = [
  { v: 'display',       l: 'Display' },
  { v: 'classified',    l: 'Classified' },
  { v: 'jacket',        l: 'Jacket' },
  { v: 'supplement',    l: 'Supplement' },
  { v: 'govt_tender',   l: 'Govt tender' },
  { v: 'obituary',      l: 'Obituary' },
  { v: 'matrimonial',   l: 'Matrimonial' },
  { v: 'public_notice', l: 'Public notice' },
];

// Standard Indian newspaper presets — 8-col broadsheet baseline.
const SIZE_PRESETS = [
  { v: 'full_page',    l: 'Full page',    cols: 8, cm: 50 },
  { v: 'half_page',    l: 'Half page',    cols: 8, cm: 25 },
  { v: 'quarter_page', l: 'Quarter page', cols: 4, cm: 25 },
  { v: 'eighth_page',  l: 'Eighth page',  cols: 4, cm: 12.5 },
  { v: 'strip',        l: 'Strip',        cols: 8, cm: 5 },
  { v: 'skybox',       l: 'Skybox',       cols: 2, cm: 5 },
  { v: 'ear_panel',    l: 'Ear panel',    cols: 1, cm: 4 },
  { v: 'single_col',   l: 'Single col',   cols: 1, cm: null },
  { v: 'double_col',   l: 'Double col',   cols: 2, cm: null },
  { v: 'custom',       l: 'Custom',       cols: null, cm: null },
];

const POSITION_OPTIONS = [
  'front', 'back', 'p3', 'sports', 'business', 'inside', 'general',
];

const PAYMENT_TERMS = [
  { v: 'advance',   l: 'Advance' },
  { v: 'credit_30', l: 'Credit 30 days' },
  { v: 'credit_60', l: 'Credit 60 days' },
];

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

/** Type-ahead advertiser picker. Lets the user select an existing one or
 *  type a new name (server creates inline on save). */
function AdvertiserPicker({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchAdvertisers({ q: query, limit: 20 })
      .then((rows) => { if (!cancelled) setItems(rows); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [query]);

  const display = value?.id ? value.name : (value?.name || '');

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="w-full flex items-center justify-between px-3 py-2 border border-input rounded-md text-sm bg-transparent hover:bg-muted/30"
        >
          <span className={cn(display ? '' : 'text-muted-foreground')}>{display || 'Pick or type advertiser…'}</span>
          {value?.id && <Check size={14} className="text-emerald-600" />}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[380px] p-0">
        <div className="p-2 border-b">
          <Input
            autoFocus
            placeholder="Search or add new…"
            value={query}
            onChange={(e) => { setQuery(e.target.value); onChange({ name: e.target.value }); }}
          />
        </div>
        <div className="max-h-[260px] overflow-y-auto">
          {loading && (
            <div className="p-3 text-sm text-muted-foreground"><Loader2 size={12} className="inline animate-spin mr-1" /> Loading…</div>
          )}
          {!loading && items.length === 0 && query.trim() && (
            <button
              type="button"
              className="w-full text-left px-3 py-2.5 hover:bg-muted text-sm flex items-center gap-2"
              onClick={() => { onChange({ name: query.trim() }); setOpen(false); }}
            >
              <Plus size={14} /> Use new: <strong>{query.trim()}</strong>
            </button>
          )}
          {items.map((a) => (
            <button
              key={a.id}
              type="button"
              className="w-full text-left px-3 py-2 hover:bg-muted flex items-center justify-between text-sm"
              onClick={() => { onChange(a); setOpen(false); }}
            >
              <span>{a.name}</span>
              {a.ad_count > 0 && (
                <span className="text-[11px] text-muted-foreground">{a.ad_count} ad{a.ad_count === 1 ? '' : 's'}</span>
              )}
            </button>
          ))}
          {items.length > 0 && query.trim() && !items.some(i => i.name.toLowerCase() === query.trim().toLowerCase()) && (
            <button
              type="button"
              className="w-full text-left px-3 py-2 hover:bg-muted text-sm border-t flex items-center gap-2"
              onClick={() => { onChange({ name: query.trim() }); setOpen(false); }}
            >
              <Plus size={14} /> Or use new: <strong>{query.trim()}</strong>
            </button>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function DateChips({ dates, onChange }) {
  const [draft, setDraft] = useState('');
  const add = () => {
    if (!draft) return;
    if (dates.includes(draft)) { setDraft(''); return; }
    onChange([...dates, draft].sort());
    setDraft('');
  };
  return (
    <div>
      <div className="flex gap-2">
        <Input type="date" value={draft} onChange={(e) => setDraft(e.target.value)} />
        <Button type="button" variant="outline" onClick={add}>Add date</Button>
      </div>
      {dates.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {dates.map((d) => (
            <span key={d} className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-violet-50 text-violet-800 text-xs">
              <Calendar size={11} /> {d}
              <button type="button" onClick={() => onChange(dates.filter((x) => x !== d))} className="hover:bg-violet-100 rounded-sm">
                <X size={11} />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AdNewPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [form, setForm] = useState({
    advertiser: null, // {id?, name}
    brought_by_user_id: '',
    received_date: todayISO(),
    title: '',
    ad_type: 'display',
    size_preset: 'quarter_page',
    size_cols: 4,
    size_cm: 25,
    color: 'color',
    position_pref: 'general',
    rate_card_value: '',
    negotiated_value: '',
    currency: 'INR',
    ro_number: '',
    payment_terms: 'advance',
    creative_brief: '',
    priority: 'normal',
    publish_dates: [],
    edition_ids: [],
  });
  const [reporters, setReporters] = useState([]);
  const [editions, setEditions] = useState([]);
  const [pendingFiles, setPendingFiles] = useState([]); // [{file, label}]
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchReporters().then((d) => setReporters(d.reporters || [])).catch(() => {});
    fetchEditions().then((d) => setEditions(d.editions || d || [])).catch(() => {});
  }, []);

  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const onSizePreset = (preset) => {
    const def = SIZE_PRESETS.find((p) => p.v === preset);
    setForm((f) => ({
      ...f,
      size_preset: preset,
      size_cols: def?.cols ?? f.size_cols,
      size_cm:   def?.cm   ?? f.size_cm,
    }));
  };

  const sqcm = useMemo(() => {
    if (form.size_cols && form.size_cm) return Math.round(form.size_cols * form.size_cm * 100) / 100;
    return null;
  }, [form.size_cols, form.size_cm]);

  const validate = () => {
    if (!form.advertiser?.id && !form.advertiser?.name?.trim()) return 'Pick or enter an advertiser';
    if (!form.brought_by_user_id) return 'Choose who brought this ad in';
    if (!form.received_date) return 'Receive date is required';
    if (!form.title.trim()) return 'Give the ad a short title';
    if (form.publish_dates.length === 0) return 'Add at least one publication date';
    return '';
  };

  const buildPayload = () => ({
    advertiser_id: form.advertiser?.id || null,
    advertiser_name: form.advertiser?.id ? null : form.advertiser?.name?.trim(),
    brought_by_user_id: form.brought_by_user_id,
    received_date: form.received_date,
    title: form.title.trim(),
    ad_type: form.ad_type,
    size_preset: form.size_preset,
    size_cols: form.size_cols ? Number(form.size_cols) : null,
    size_cm: form.size_cm ? Number(form.size_cm) : null,
    color: form.color,
    position_pref: form.position_pref || null,
    rate_card_value: form.rate_card_value ? Number(form.rate_card_value) : null,
    negotiated_value: form.negotiated_value ? Number(form.negotiated_value) : 0,
    currency: form.currency,
    ro_number: form.ro_number || null,
    payment_terms: form.payment_terms || null,
    creative_brief: form.creative_brief || null,
    priority: form.priority,
    publish_dates: form.publish_dates,
    edition_ids: form.edition_ids,
  });

  const submit = async (sendForReview) => {
    const err = validate();
    if (err) { setError(err); return; }
    setError('');
    setSaving(true);
    try {
      const ad = await createAd(buildPayload());
      // upload pending files (best-effort; failures don't block save)
      for (const pf of pendingFiles) {
        try { await uploadAdAttachment(ad.id, pf.file, pf.label); } catch (e) { console.warn('attach failed', e); }
      }
      if (sendForReview) {
        try { await changeAdStatus(ad.id, 'submitted', 'Submitted from create form'); } catch (e) { console.warn(e); }
      }
      navigate(`/ads/${ad.id}`);
    } catch (e) {
      setError(e.message || 'Failed to create');
    } finally {
      setSaving(false);
    }
  };

  const onPickFiles = (e) => {
    const files = Array.from(e.target.files || []);
    setPendingFiles((prev) => [...prev, ...files.map((f) => ({ file: f, label: '' }))]);
    e.target.value = '';
  };

  return (
    <div className="p-6 max-w-[960px] mx-auto">
      <button onClick={() => navigate('/ads')} className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-4">
        <ArrowLeft size={14} /> Back to ads
      </button>

      <h1 className="text-2xl font-bold mb-1">New advertisement</h1>
      <p className="text-sm text-muted-foreground mb-6">Once submitted it goes to the editorial review queue on the selected publication dates.</p>

      {error && (
        <div className="mb-4 px-4 py-3 rounded-md bg-rose-50 border border-rose-200 text-sm text-rose-800">{error}</div>
      )}

      {/* Section: Who & when */}
      <div className="bg-card border border-border rounded-xl p-5 mb-4">
        <h2 className="font-semibold mb-3">Advertiser & sourcing</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <Label>Company name</Label>
            <AdvertiserPicker value={form.advertiser} onChange={(v) => update('advertiser', v)} />
            <p className="text-[11px] text-muted-foreground mt-1">
              Auto-suggest from past advertisers. New names create a record on save.
            </p>
          </div>
          <div>
            <Label>Brought by (reporter / sales)</Label>
            <Select value={form.brought_by_user_id} onValueChange={(v) => update('brought_by_user_id', v)}>
              <SelectTrigger><SelectValue placeholder="Pick a user…" /></SelectTrigger>
              <SelectContent>
                {reporters.map((r) => <SelectItem key={r.id} value={r.id}>{r.name}{r.area_name ? ` · ${r.area_name}` : ''}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Receive date</Label>
            <Input type="date" value={form.received_date} onChange={(e) => update('received_date', e.target.value)} />
          </div>
          <div>
            <Label>Short title (for queue)</Label>
            <Input placeholder="e.g. Tata Motors – Diwali campaign" value={form.title} onChange={(e) => update('title', e.target.value)} />
          </div>
        </div>
      </div>

      {/* Section: Ad spec */}
      <div className="bg-card border border-border rounded-xl p-5 mb-4">
        <h2 className="font-semibold mb-3">Ad specification</h2>
        <div className="grid md:grid-cols-3 gap-4">
          <div>
            <Label>Type</Label>
            <Select value={form.ad_type} onValueChange={(v) => update('ad_type', v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{AD_TYPES.map((t) => <SelectItem key={t.v} value={t.v}>{t.l}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label>Size preset</Label>
            <Select value={form.size_preset} onValueChange={onSizePreset}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{SIZE_PRESETS.map((s) => <SelectItem key={s.v} value={s.v}>{s.l}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label>Color / B&W</Label>
            <Select value={form.color} onValueChange={(v) => update('color', v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="color">Color</SelectItem>
                <SelectItem value="bw">Black & White</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Columns</Label>
            <Input type="number" min={1} max={8} value={form.size_cols ?? ''} onChange={(e) => update('size_cols', e.target.value ? Number(e.target.value) : null)} />
          </div>
          <div>
            <Label>Height (cm)</Label>
            <Input type="number" min={1} step="0.5" value={form.size_cm ?? ''} onChange={(e) => update('size_cm', e.target.value ? Number(e.target.value) : null)} />
          </div>
          <div>
            <Label>Calculated</Label>
            <div className="px-3 py-2 border border-input rounded-md text-sm bg-muted/30">
              {sqcm ? `${sqcm} sq cm  ·  ${form.size_cols} col × ${form.size_cm} cm` : '—'}
            </div>
          </div>
          <div className="md:col-span-2">
            <Label>Position preference</Label>
            <Select value={form.position_pref} onValueChange={(v) => update('position_pref', v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {POSITION_OPTIONS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Priority</Label>
            <Select value={form.priority} onValueChange={(v) => update('priority', v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="normal">Normal</SelectItem>
                <SelectItem value="urgent">Urgent</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Section: Commercial */}
      <div className="bg-card border border-border rounded-xl p-5 mb-4">
        <h2 className="font-semibold mb-3">Commercial</h2>
        <div className="grid md:grid-cols-3 gap-4">
          <div>
            <Label>Negotiated value (₹)</Label>
            <Input type="number" min={0} value={form.negotiated_value} onChange={(e) => update('negotiated_value', e.target.value)} />
          </div>
          <div>
            <Label>Rate card value (₹)</Label>
            <Input type="number" min={0} value={form.rate_card_value} onChange={(e) => update('rate_card_value', e.target.value)} />
          </div>
          <div>
            <Label>Payment terms</Label>
            <Select value={form.payment_terms} onValueChange={(v) => update('payment_terms', v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{PAYMENT_TERMS.map((p) => <SelectItem key={p.v} value={p.v}>{p.l}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label>Release Order #</Label>
            <Input value={form.ro_number} onChange={(e) => update('ro_number', e.target.value)} placeholder="optional" />
          </div>
          <div>
            <Label>Currency</Label>
            <Select value={form.currency} onValueChange={(v) => update('currency', v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="INR">INR</SelectItem><SelectItem value="USD">USD</SelectItem></SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Section: Schedule */}
      <div className="bg-card border border-border rounded-xl p-5 mb-4">
        <h2 className="font-semibold mb-3">Publication schedule</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <Label>Target publication dates *</Label>
            <DateChips dates={form.publish_dates} onChange={(d) => update('publish_dates', d)} />
            <p className="text-[11px] text-muted-foreground mt-1">Add as many as needed — each becomes its own scheduled placement.</p>
          </div>
          <div>
            <Label>Editions</Label>
            <div className="border border-input rounded-md p-2 max-h-[180px] overflow-y-auto">
              {editions.length === 0 && <div className="text-xs text-muted-foreground p-2">No editions found.</div>}
              {editions.map((e) => {
                const checked = form.edition_ids.includes(e.id);
                return (
                  <label key={e.id} className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted/40 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        const next = checked ? form.edition_ids.filter((x) => x !== e.id) : [...form.edition_ids, e.id];
                        update('edition_ids', next);
                      }}
                    />
                    <span className="text-sm">{e.title || `Edition ${e.publication_date}`}</span>
                    <span className="ml-auto text-[11px] text-muted-foreground">{e.publication_date}</span>
                  </label>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Section: Brief + attachments */}
      <div className="bg-card border border-border rounded-xl p-5 mb-4">
        <h2 className="font-semibold mb-3">Creative brief & attachments</h2>
        <Label>Brief / notes (optional)</Label>
        <Textarea rows={3} value={form.creative_brief} onChange={(e) => update('creative_brief', e.target.value)} placeholder="Anything design / desk needs to know" />
        <div className="mt-3">
          <Label>Attachments (optional — any file type)</Label>
          <label className="flex items-center gap-2 px-3 py-2 border border-dashed border-input rounded-md text-sm cursor-pointer hover:bg-muted/30 w-fit">
            <Upload size={14} /> Pick files
            <input type="file" multiple className="hidden" onChange={onPickFiles} />
          </label>
          {pendingFiles.length > 0 && (
            <div className="mt-2 space-y-1.5">
              {pendingFiles.map((pf, i) => (
                <div key={i} className="flex items-center gap-2 text-sm border border-border rounded-md px-2 py-1.5">
                  <Paperclip size={12} className="text-muted-foreground" />
                  <span className="truncate">{pf.file.name}</span>
                  <Input
                    placeholder="label (optional)"
                    className="h-7 text-xs ml-auto max-w-[200px]"
                    value={pf.label}
                    onChange={(e) => setPendingFiles((arr) => arr.map((x, j) => j === i ? { ...x, label: e.target.value } : x))}
                  />
                  <button type="button" onClick={() => setPendingFiles((arr) => arr.filter((_, j) => j !== i))} className="text-muted-foreground hover:text-foreground"><X size={14} /></button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex justify-end gap-2 sticky bottom-0 bg-background py-3">
        <Button variant="outline" onClick={() => submit(false)} disabled={saving} className="gap-2">
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Save as draft
        </Button>
        <Button onClick={() => submit(true)} disabled={saving} className="gap-2">
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} Submit for review
        </Button>
      </div>
    </div>
  );
}
