import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';
import { useI18n } from '../i18n';
import { ToastContext, type ToastApi, type ToastVariant } from '../toast';
import { cn } from '../utils';

interface ToastItem {
  id: number;
  variant: ToastVariant;
  title: string;
  description?: string;
  leaving?: boolean;
}

const DURATIONS: Record<ToastVariant, number> = {
  success: 5000,
  info: 6500,
  warning: 8000,
  error: 9000,
};

const ICONS: Record<ToastVariant, typeof CheckCircle2> = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const ICON_CLASSES: Record<ToastVariant, string> = {
  success: 'text-emerald-400',
  error: 'text-red-400',
  warning: 'text-amber-400',
  info: 'text-sky-400',
};

const MAX_VISIBLE = 4;
const LEAVE_MS = 180;

function ToastCard({ toast, onDismiss }: { toast: ToastItem; onDismiss: () => void }) {
  const { t } = useI18n();
  const Icon = ICONS[toast.variant];

  return (
    <div
      role={toast.variant === 'error' ? 'alert' : 'status'}
      className={cn('toast-card', toast.leaving && 'toast-leave')}
    >
      <Icon size={19} className={cn('mt-0.5 shrink-0', ICON_CLASSES[toast.variant])} />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold leading-snug text-[var(--mamp-text)]">
          {toast.title}
        </div>
        {toast.description && (
          <div className="mt-1 whitespace-pre-wrap break-words text-xs leading-relaxed text-[var(--mamp-text-muted)]">
            {toast.description}
          </div>
        )}
      </div>
      <button
        onClick={onDismiss}
        aria-label={t.common.dismiss}
        className="shrink-0 rounded-md p-1 text-[var(--mamp-text-dim)] transition hover:bg-white/10 hover:text-white"
      >
        <X size={15} />
      </button>
    </div>
  );
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const idRef = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.map((item) => (item.id === id ? { ...item, leaving: true } : item)));
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((item) => item.id !== id));
    }, LEAVE_MS);
  }, []);

  const push = useCallback(
    (variant: ToastVariant, title: string, description?: string) => {
      const id = ++idRef.current;
      setToasts((prev) => [...prev.slice(-(MAX_VISIBLE - 1)), { id, variant, title, description }]);
      window.setTimeout(() => dismiss(id), DURATIONS[variant]);
    },
    [dismiss],
  );

  const api = useMemo<ToastApi>(
    () => ({
      success: (title, description) => push('success', title, description),
      error: (title, description) => push('error', title, description),
      warning: (title, description) => push('warning', title, description),
      info: (title, description) => push('info', title, description),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-viewport" aria-live="polite">
        {toasts.map((toast) => (
          <ToastCard key={toast.id} toast={toast} onDismiss={() => dismiss(toast.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}
