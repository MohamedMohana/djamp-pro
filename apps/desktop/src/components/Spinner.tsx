import { Loader2 } from 'lucide-react';
import { cn } from '../utils';

export default function Spinner({ size = 16, className }: { size?: number; className?: string }) {
  return <Loader2 size={size} aria-hidden className={cn('animate-spin', className)} />;
}
