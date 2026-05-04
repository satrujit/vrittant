import { Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useI18n } from '../../i18n';
import SearchableSelect from '../common/SearchableSelect';

// Status filter chips. We deliberately omit 'in_progress' — it's a
// transient state, not a bucket reviewers triage. They want to see what's
// reported, what they've approved, and what's flagged.
const STATUS_FILTERS = [
  { value: '',          labelKey: 'dashboard.filterAll' },
  { value: 'submitted', labelKey: 'status.submitted' },
  { value: 'approved',  labelKey: 'status.approved' },
  { value: 'flagged',   labelKey: 'status.flagged' },
];

export default function FilterBar({
  search, onSearchChange,
  status, onStatusChange,
  categories = [], category, onCategoryChange,
  reporters = [], reporter, onReporterChange,
}) {
  const { t } = useI18n();

  return (
    <div className="flex flex-wrap items-center gap-1.5 border-b border-border/60 px-1 py-2.5">
      {/* Search */}
      <div className="relative">
        <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder={t('dashboard.searchPlaceholder')}
          className="h-7 w-44 rounded-md border border-border/60 bg-card pl-7 pr-7 text-[11.5px] outline-none transition-colors focus:border-ring focus:shadow-[0_0_0_3px_rgba(250,108,56,0.08)]"
        />
        {search && (
          <button
            type="button"
            onClick={() => onSearchChange('')}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted-foreground hover:bg-accent"
            aria-label="Clear search"
          >
            <X size={12} />
          </button>
        )}
      </div>

      {/* Status chips */}
      <div className="flex items-center gap-0.5 rounded-md border border-border/60 bg-card p-0.5">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value || 'all'}
            type="button"
            onClick={() => onStatusChange(f.value)}
            aria-pressed={status === f.value}
            className={cn(
              'rounded-[5px] px-2 py-1 text-[11.5px] font-medium transition-colors',
              status === f.value
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground',
            )}
          >
            {t(f.labelKey) || f.value}
          </button>
        ))}
      </div>

      {/* Category — SearchableSelect so reviewers can typeahead through
          longer category lists rather than scrolling a native menu. */}
      {categories.length > 0 && (
        <SearchableSelect
          triggerClassName="h-7 text-[11.5px] border-border/60 px-2 min-w-[120px]"
          value={category || ''}
          onChange={onCategoryChange}
          placeholder={t('dashboard.filterAllCategories') || 'All categories'}
          allLabel={t('dashboard.filterAllCategories') || 'All categories'}
          options={categories.map((c) => ({ value: c, label: c }))}
        />
      )}

      {/* Reporter — same component. Auto-shows the inline search input
          when there are >6 reporters (typical for a real org). */}
      {reporters.length > 0 && (
        <SearchableSelect
          triggerClassName="h-7 text-[11.5px] border-border/60 px-2 min-w-[120px] max-w-[180px]"
          value={reporter || ''}
          onChange={onReporterChange}
          placeholder={t('dashboard.filterAllReporters') || 'All reporters'}
          allLabel={t('dashboard.filterAllReporters') || 'All reporters'}
          options={reporters.map((r) => ({ value: String(r.id), label: r.name }))}
        />
      )}
    </div>
  );
}
