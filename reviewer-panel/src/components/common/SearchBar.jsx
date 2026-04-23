import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

function SearchBar({ placeholder = '', value, onChange, icon: Icon = Search, className }) {
  return (
    <div className={cn('relative flex w-full', className)}>
      <Icon
        size={14}
        className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
      />
      <Input
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        className="h-8 w-full rounded-md pl-8 pr-3 text-[13px]"
      />
    </div>
  );
}

export default SearchBar;
