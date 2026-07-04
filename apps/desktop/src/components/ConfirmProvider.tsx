import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { AlertTriangle, ShieldQuestion } from 'lucide-react';
import { useI18n } from '../i18n';
import { ConfirmContext, type ConfirmFn, type ConfirmOptions } from '../confirm';
import { cn } from '../utils';

interface PendingConfirm {
  options: ConfirmOptions;
  resolve: (confirmed: boolean) => void;
}

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [pending, setPending] = useState<PendingConfirm | null>(null);
  const confirmButtonRef = useRef<HTMLButtonElement | null>(null);

  const confirm = useCallback<ConfirmFn>((options) => {
    return new Promise<boolean>((resolve) => {
      setPending({ options, resolve });
    });
  }, []);

  const settle = useCallback(
    (confirmed: boolean) => {
      pending?.resolve(confirmed);
      setPending(null);
    },
    [pending],
  );

  useEffect(() => {
    if (!pending) {
      return;
    }
    confirmButtonRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        settle(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [pending, settle]);

  const danger = pending?.options.tone === 'danger';

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {pending && (
        <div
          className="fixed inset-0 z-[90] flex items-center justify-center bg-[var(--scrim)] p-4 backdrop-blur-sm"
          onClick={() => settle(false)}
        >
          <div
            role="alertdialog"
            aria-modal="true"
            aria-label={pending.options.title}
            onClick={(event) => event.stopPropagation()}
            className={cn(
              'mamp-modal confirm-pop w-full max-w-md p-5',
              danger && 'border-red-500/30',
            )}
          >
            <div className="flex items-start gap-3">
              <div
                className={cn(
                  'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border',
                  danger
                    ? 'border-transparent bg-red-500/12 text-[var(--danger-text)]'
                    : 'border-transparent bg-[var(--accent-tint)] text-[var(--accent-hover)]',
                )}
              >
                {danger ? <AlertTriangle size={19} /> : <ShieldQuestion size={19} />}
              </div>
              <div className="min-w-0">
                <h3 className="text-[16px] font-semibold text-[var(--text-1)]">{pending.options.title}</h3>
                <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-2)]">
                  {pending.options.message}
                </p>
              </div>
            </div>

            <div className="mt-5 flex items-center justify-end gap-2">
              <button onClick={() => settle(false)} className="mamp-button-neutral">
                {t.common.cancel}
              </button>
              <button
                ref={confirmButtonRef}
                onClick={() => settle(true)}
                className={danger ? 'mamp-button-danger' : 'mamp-button-primary'}
              >
                {pending.options.confirmLabel || t.common.confirm}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}
