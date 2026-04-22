import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

function SearchBar({ placeholder = '', value, onChange, icon: Icon = Search, className }) {
  return (
    <div className={cn('relative flex w-full', className)}>
      <Icon
        size={18}
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
      />
      <Input
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        className="h-10 w-full rounded-xl pl-[42px] pr-4"
      />
    </div>
  );
}

export default SearchBar;
