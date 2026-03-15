import { useEffect, useState, type ReactNode } from 'react';
import { I18nContext, getDirection, getInitialLocale, messages, type Locale } from './i18n';

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() => getInitialLocale());
  const direction = getDirection(locale);

  useEffect(() => {
    window.localStorage.setItem('djamp.locale', locale);
    document.documentElement.lang = locale;
    document.documentElement.dir = direction;
    document.body.dir = direction;
  }, [direction, locale]);

  return (
    <I18nContext.Provider
      value={{
        locale,
        direction,
        setLocale,
        toggleLocale: () => setLocale((current) => (current === 'en' ? 'ar' : 'en')),
        t: messages[locale],
      }}
    >
      {children}
    </I18nContext.Provider>
  );
}
