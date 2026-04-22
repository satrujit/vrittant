import { createContext, useContext, useState, useCallback } from 'react';
import en from './locales/en.json';
import or from './locales/or.json';
import hi from './locales/hi.json';

const locales = { en, or, hi };

const I18nContext = createContext(null);

function getNestedValue(obj, path) {
  return path.split('.').reduce((acc, key) => acc?.[key], obj);
}

export function I18nProvider({ children, defaultLocale = 'en' }) {
  const [locale, setLocale] = useState(() => {
    try {
      const saved = localStorage.getItem('vrittant_locale');
      if (saved && locales[saved]) return saved;
    } catch {}
    return defaultLocale;
  });

  const setAndPersistLocale = useCallback((loc) => {
    setLocale(loc);
    try { localStorage.setItem('vrittant_locale', loc); } catch {}
  }, []);

  const t = useCallback(
    (key, paramsOrFallback = {}) => {
      // Support t('key', 'fallback') and t('key', { param: value })
      const isParams = typeof paramsOrFallback === 'object' && paramsOrFallback !== null;
      const fallback = !isParams ? paramsOrFallback : null;
      const params = isParams ? paramsOrFallback : {};

      let value = getNestedValue(locales[locale], key) || getNestedValue(locales.en, key) || fallback || key;
      if (isParams) {
        Object.entries(params).forEach(([k, v]) => {
          value = value.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
        });
      }
      return value;
    },
    [locale]
  );

  return (
    <I18nContext.Provider value={{ locale, setLocale: setAndPersistLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within I18nProvider');
  return ctx;
}
