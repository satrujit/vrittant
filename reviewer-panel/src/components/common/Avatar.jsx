import { cn } from '@/lib/utils';

const SIZE_CLASSES = {
  // xs is for dense table rows where the avatar is metadata, not focal.
  // Sized to roughly match the surrounding ~11px reporter-name text.
  xs: 'size-[18px] text-[9px]',
  sm: 'size-7 text-xs',
  md: 'size-9 text-sm',
  lg: 'size-12 text-base',
};

function Avatar({ initials, color, size = 'md', className }) {
  return (
    <div
      className={cn(
        'inline-flex shrink-0 select-none items-center justify-center rounded-full font-semibold leading-none text-white',
        SIZE_CLASSES[size] || SIZE_CLASSES.md,
        className
      )}
      style={{ backgroundColor: color || 'hsl(var(--primary))' }}
    >
      {initials}
    </div>
  );
}

export default Avatar;
