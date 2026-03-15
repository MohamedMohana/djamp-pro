import { cn } from '../utils';
import { useI18n } from '../i18n';

interface ProjectAvatarProps {
  name: string;
  size?: 'sm' | 'md';
  className?: string;
}

function hashName(input: string): number {
  let hash = 0;
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash * 31 + input.charCodeAt(i)) >>> 0;
  }
  return hash;
}

function initials(name: string): string {
  const words = name
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (words.length === 0) {
    return 'DJ';
  }

  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase();
  }

  return `${words[0][0]}${words[1][0]}`.toUpperCase();
}

export default function ProjectAvatar({ name, size = 'sm', className }: ProjectAvatarProps) {
  const { t } = useI18n();
  const hash = hashName(name || 'project');
  const hue1 = hash % 360;
  const hue2 = (hue1 + 28) % 360;
  const style = {
    background: `linear-gradient(135deg, hsl(${hue1} 70% 50%), hsl(${hue2} 70% 38%))`,
  };

  const sizeClass = size === 'md' ? 'h-12 w-12 text-base' : 'h-9 w-9 text-xs';

  return (
    <div
      className={cn(
        'shrink-0 rounded-lg font-semibold text-white shadow-md ring-1 ring-white/10',
        'flex items-center justify-center',
        sizeClass,
        className,
      )}
      style={style}
      aria-label={t.projectAvatar.label(name)}
      title={name}
    >
      {initials(name)}
    </div>
  );
}
