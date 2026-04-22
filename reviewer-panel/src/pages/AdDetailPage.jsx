import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, Loader2, Paperclip, Upload, X, Calendar, Send, Check, XCircle,
  CalendarCheck, BookOpen, RotateCcw, History, Trash2, ExternalLink, Building2, User, IndianRupee,
} from 'lucide-react';
import {
  fetchAd, changeAdStatus, uploadAdAttachment, deleteAdAttachment, deleteAd, updateAd,
  getMediaUrl,
} from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

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

const TRANSITIONS = {
  draft:      [{ to: 'submitted', icon: Send, label: 'Submit for review' }, { to: 'cancelled', icon: XCircle, label: 'Cancel', variant: 'outline' }],
  submitted:  [{ to: 'in_review', icon: BookOpen, label: 'Start review' }, { to: 'approved', icon: Check, label: 'Approve' }, { to: 'rejected', icon: XCircle, label: 'Reject', variant: 'destructive' }],
  in_review:  [{ to: 'approved', icon: Check, label: 'Approve' }, { to: 'rejected', icon: XCircle, label: 'Reject', variant: 'destructive' }],
  approved:   [{ to: 'scheduled', icon: CalendarCheck, label: 'Mark scheduled' }, { to: 'published', icon: Check, label: 'Mark published' }],
  scheduled:  [{ to: 'published', icon: Check, label: 'Mark published' }, { to: 'cancelled', icon: XCircle, label: 'Cancel', variant: 'outline' }],
  published:  [],
  rejected:   [{ to: 'submitted', icon: RotateCcw, label: 'Re-submit' }],
  cancelled:  [],
};

const SIZE_LABELS = {
  full_page: 'Full page', half_page: 'Half page', quarter_page: 'Quarter page',
  eighth_page: '⅛ page', strip: 'Strip', skybox: 'Skybox', ear_panel: 'Ear panel',
  single_col: 'Single col', double_col: 'Double col', custom: 'Custom',
};

function formatINR(n) {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return `₹${Number(n).toLocaleString('en-IN')}`;
}

function fmt(d) {
  if (!d) return '—';
  return new Date(d).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}
function fmtDateTime(d) {
  if (!d) return '—';
  return new Date(d).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export default function AdDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isReviewer = user && (user.user_type === 'reviewer' || user.user_type === 'org_admin');

  const [ad, setAd] = useState(null);
  const [loading, setLoading] = useState(true);
  const [transitioning, setTransitioning] = useState(false);
  const [transitionNote, setTransitionNote] = useState('');
  const [pendingTransition, setPendingTransition] = useState(null); // { to, label }

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAd(id);
      setAd(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const doTransition = async (to, note) => {
    setTransitioning(true);
    try {
      const updated = await changeAdStatus(ad.id, to, note);
      setAd(updated);
      setPendingTransition(null);
      setTransitionNote('');
    } catch (e) {
      alert(e.message || 'Transition failed');
    } finally {
      setTransitioning(false);
    }
  };

  const onUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = '';
    for (const f of files) {
      try { await uploadAdAttachment(ad.id, f, ''); } catch (err) { alert(err.message); }
    }
    load();
  };

  const onDeleteAttachment = async (attId) => {
    if (!confirm('Delete this attachment?')) return;
    try { await deleteAdAttachment(ad.id, attId); load(); } catch (e) { alert(e.message); }
  };

  const onDeleteAd = async () => {
    if (!confirm('Delete this advertisement permanently?')) return;
    try { await deleteAd(ad.id); navigate('/ads'); } catch (e) { alert(e.message); }
  };

  if (loading || !ad) {
    return <div className="p-12 text-center text-muted-foreground"><Loader2 className="inline animate-spin mr-2" size={16} /> Loading…</div>;
  }

  const transitions = TRANSITIONS[ad.status] || [];
  const sqcm = ad.size_cols && ad.size_cm ? Math.round(ad.size_cols * ad.size_cm * 100) / 100 : null;

  return (
    <div className="p-6 max-w-[1200px] mx-auto">
      <button onClick={() => navigate('/ads')} className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-4">
        <ArrowLeft size={14} /> Back to ads
      </button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Badge className={`${STATUS_COLORS[ad.status]} font-medium`}>{ad.status.replace('_',' ')}</Badge>
            {ad.priority === 'urgent' && <Badge className="bg-rose-100 text-rose-800">Urgent</Badge>}
          </div>
          <h1 className="text-2xl font-bold tracking-tight truncate">{ad.title || '(untitled)'}</h1>
          <div className="text-sm text-muted-foreground mt-1 flex items-center flex-wrap gap-x-3 gap-y-1">
            <span className="inline-flex items-center gap-1"><Building2 size={13} /> {ad.advertiser?.name}</span>
            <span className="inline-flex items-center gap-1"><User size={13} /> Brought by {ad.brought_by?.name}</span>
            <span>RC: {fmt(ad.received_date)}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 justify-end">
          {transitions.map((t) => {
            const reviewerOnly = ['in_review','approved','rejected','scheduled','published'].includes(t.to);
            if (reviewerOnly && !isReviewer) return null;
            const Icon = t.icon;
            return (
              <Button
                key={t.to}
                variant={t.variant || 'default'}
                size="sm"
                onClick={() => setPendingTransition(t)}
                disabled={transitioning}
                className="gap-1.5"
              >
                <Icon size={14} /> {t.label}
              </Button>
            );
          })}
          {ad.status === 'draft' && (
            <Button variant="ghost" size="sm" onClick={onDeleteAd} className="text-rose-600 hover:text-rose-700 gap-1.5">
              <Trash2 size={14} /> Delete
            </Button>
          )}
        </div>
      </div>

      {/* Transition modal (inline strip) */}
      {pendingTransition && (
        <div className="bg-card border border-border rounded-xl p-4 mb-4">
          <div className="text-sm font-medium mb-2">Add a note for "{pendingTransition.label}" (optional)</div>
          <Textarea rows={2} value={transitionNote} onChange={(e) => setTransitionNote(e.target.value)} placeholder="Reason / context…" />
          <div className="flex justify-end gap-2 mt-2">
            <Button variant="ghost" size="sm" onClick={() => { setPendingTransition(null); setTransitionNote(''); }}>Cancel</Button>
            <Button size="sm" onClick={() => doTransition(pendingTransition.to, transitionNote)} disabled={transitioning}>
              {transitioning ? <Loader2 size={14} className="animate-spin" /> : 'Confirm'}
            </Button>
          </div>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-4">
        {/* Left col: details */}
        <div className="lg:col-span-2 space-y-4">
          {/* Spec */}
          <section className="bg-card border border-border rounded-xl p-5">
            <h2 className="font-semibold mb-3">Specification</h2>
            <dl className="grid grid-cols-2 md:grid-cols-3 gap-y-3 gap-x-6 text-sm">
              <div><dt className="text-[11px] uppercase text-muted-foreground">Type</dt><dd>{ad.ad_type.replace('_',' ')}</dd></div>
              <div><dt className="text-[11px] uppercase text-muted-foreground">Size</dt><dd>{SIZE_LABELS[ad.size_preset] || ad.size_preset}</dd></div>
              <div><dt className="text-[11px] uppercase text-muted-foreground">Color</dt><dd>{ad.color === 'bw' ? 'Black & White' : 'Color'}</dd></div>
              <div><dt className="text-[11px] uppercase text-muted-foreground">Cols × cm</dt><dd>{ad.size_cols && ad.size_cm ? `${ad.size_cols} × ${ad.size_cm}` : '—'}</dd></div>
              <div><dt className="text-[11px] uppercase text-muted-foreground">Area</dt><dd>{sqcm ? `${sqcm} sq cm` : '—'}</dd></div>
              <div><dt className="text-[11px] uppercase text-muted-foreground">Position</dt><dd>{ad.position_pref || '—'}</dd></div>
            </dl>
          </section>

          {/* Commercial */}
          <section className="bg-card border border-border rounded-xl p-5">
            <h2 className="font-semibold mb-3">Commercial</h2>
            <dl className="grid grid-cols-2 md:grid-cols-3 gap-y-3 gap-x-6 text-sm">
              <div><dt className="text-[11px] uppercase text-muted-foreground">Negotiated</dt><dd className="font-semibold text-emerald-700">{formatINR(ad.negotiated_value)}</dd></div>
              <div><dt className="text-[11px] uppercase text-muted-foreground">Rate card</dt><dd>{formatINR(ad.rate_card_value)}</dd></div>
              <div><dt className="text-[11px] uppercase text-muted-foreground">Payment</dt><dd>{ad.payment_terms || '—'}</dd></div>
              <div><dt className="text-[11px] uppercase text-muted-foreground">RO #</dt><dd>{ad.ro_number || '—'}</dd></div>
              <div><dt className="text-[11px] uppercase text-muted-foreground">Currency</dt><dd>{ad.currency}</dd></div>
            </dl>
          </section>

          {/* Schedule */}
          <section className="bg-card border border-border rounded-xl p-5">
            <h2 className="font-semibold mb-3">Schedule</h2>
            {ad.publish_dates.length === 0 ? (
              <div className="text-sm text-muted-foreground">No publication dates scheduled.</div>
            ) : (
              <div className="flex flex-wrap gap-1.5 mb-3">
                {ad.publish_dates.map((p) => (
                  <span key={p.publish_date} className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-violet-50 text-violet-800 text-xs">
                    <Calendar size={11} /> {p.publish_date}
                  </span>
                ))}
              </div>
            )}
            <div>
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground mb-1.5">Editions</div>
              {ad.editions.length === 0 ? (
                <div className="text-sm text-muted-foreground">All editions (none specifically targeted).</div>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {ad.editions.map((e) => (
                    <span key={e.id} className="px-2 py-1 rounded-md bg-blue-50 text-blue-800 text-xs">{e.title || e.publication_date}</span>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Brief */}
          {ad.creative_brief && (
            <section className="bg-card border border-border rounded-xl p-5">
              <h2 className="font-semibold mb-2">Creative brief</h2>
              <p className="text-sm whitespace-pre-wrap">{ad.creative_brief}</p>
            </section>
          )}

          {/* Attachments */}
          <section className="bg-card border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold">Attachments</h2>
              <label className="flex items-center gap-1.5 text-sm cursor-pointer text-primary hover:underline">
                <Upload size={14} /> Add file
                <input type="file" multiple className="hidden" onChange={onUpload} />
              </label>
            </div>
            {ad.attachments.length === 0 ? (
              <div className="text-sm text-muted-foreground">No attachments yet.</div>
            ) : (
              <div className="space-y-1.5">
                {ad.attachments.map((a) => (
                  <div key={a.id} className="flex items-center gap-2 text-sm border border-border rounded-md px-3 py-2">
                    <Paperclip size={13} className="text-muted-foreground" />
                    <a href={getMediaUrl(a.url)} target="_blank" rel="noreferrer" className="text-foreground hover:underline truncate flex-1">
                      {a.filename}
                    </a>
                    {a.label && <span className="text-[11px] text-muted-foreground">{a.label}</span>}
                    <span className="text-[11px] text-muted-foreground">{(a.size_bytes / 1024).toFixed(0)} KB</span>
                    <a href={getMediaUrl(a.url)} target="_blank" rel="noreferrer" className="text-muted-foreground hover:text-foreground"><ExternalLink size={13} /></a>
                    <button onClick={() => onDeleteAttachment(a.id)} className="text-muted-foreground hover:text-rose-600"><X size={14} /></button>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        {/* Right col: status / history / advertiser */}
        <div className="space-y-4">
          <section className="bg-card border border-border rounded-xl p-5">
            <h2 className="font-semibold mb-3">Advertiser</h2>
            <div className="text-sm space-y-1.5">
              <div className="font-medium">{ad.advertiser?.name}</div>
              {ad.advertiser?.contact_person && <div className="text-muted-foreground">{ad.advertiser.contact_person}</div>}
              {ad.advertiser?.phone && <div>{ad.advertiser.phone}</div>}
              {ad.advertiser?.email && <div>{ad.advertiser.email}</div>}
              {ad.advertiser?.gst_number && <div className="text-[11px] text-muted-foreground">GST: {ad.advertiser.gst_number}</div>}
            </div>
          </section>

          {(ad.review_notes || ad.rejection_reason) && (
            <section className="bg-card border border-border rounded-xl p-5">
              <h2 className="font-semibold mb-2">Reviewer feedback</h2>
              {ad.review_notes && <p className="text-sm whitespace-pre-wrap mb-2">{ad.review_notes}</p>}
              {ad.rejection_reason && <p className="text-sm text-rose-700 whitespace-pre-wrap">Rejected: {ad.rejection_reason}</p>}
              {ad.reviewer && <div className="text-[11px] text-muted-foreground mt-1">— {ad.reviewer.name}</div>}
            </section>
          )}

          <section className="bg-card border border-border rounded-xl p-5">
            <h2 className="font-semibold mb-3 flex items-center gap-1.5"><History size={14} /> History</h2>
            {ad.history.length === 0 ? (
              <div className="text-sm text-muted-foreground">No transitions yet.</div>
            ) : (
              <ol className="space-y-2.5">
                {ad.history.slice().reverse().map((h, i) => (
                  <li key={i} className="text-sm border-l-2 border-border pl-3">
                    <div className="font-medium text-xs">
                      {h.from_status ? `${h.from_status} → ${h.to_status}` : h.to_status}
                    </div>
                    <div className="text-[11px] text-muted-foreground">{fmtDateTime(h.created_at)}{h.actor ? ` · ${h.actor.name}` : ''}</div>
                    {h.note && <div className="text-xs mt-1 text-muted-foreground italic">"{h.note}"</div>}
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
