import { useEffect, useRef, useState } from 'react';
import { useI18n } from '../i18n';

/**
 * WidgetsPage — embeds the standalone widget microservice in a sandboxed iframe.
 *
 * Security:
 *   - sandbox="allow-scripts allow-popups" blocks parent storage/cookie access,
 *     top-navigation, form submission, and same-origin assumptions.
 *   - The widget service additionally sets `Content-Security-Policy:
 *     frame-ancestors` so only this origin can embed it.
 *   - We only honour `vrittant-widget-resize` postMessages from the trusted origin.
 */

const WIDGETS_URL =
  import.meta.env.VITE_WIDGETS_URL || 'https://widgets.vrittant.in';
const WIDGETS_ORIGIN = (() => {
  try {
    return new URL(WIDGETS_URL).origin;
  } catch {
    return null;
  }
})();

export default function WidgetsPage() {
  const { t } = useI18n();
  const iframeRef = useRef(null);
  const [height, setHeight] = useState(800);

  useEffect(() => {
    function onMessage(ev) {
      // 1. Origin allow-list
      if (!WIDGETS_ORIGIN || ev.origin !== WIDGETS_ORIGIN) return;
      // 2. Source must be our iframe
      if (iframeRef.current && ev.source !== iframeRef.current.contentWindow) return;
      // 3. Typed message
      const { type, height: h } = ev.data || {};
      if (type !== 'vrittant-widget-resize') return;
      const n = Number(h);
      if (!Number.isFinite(n) || n < 100 || n > 10000) return;
      setHeight(Math.ceil(n));
    }
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);

  return (
    <div className="p-6">
      <div className="mb-4">
        <h1 className="text-2xl font-bold tracking-tight">
          {t('widgets.title') || 'Daily Widgets'}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {t('widgets.subtitle') ||
            'Auto-refreshed daily at 12:30 AM IST. Pulled from public sources, translated to Odia.'}
        </p>
      </div>
      <iframe
        ref={iframeRef}
        title="Vrittant Widgets"
        src={`${WIDGETS_URL}/render/all`}
        sandbox="allow-scripts allow-popups"
        referrerPolicy="no-referrer"
        loading="lazy"
        style={{
          width: '100%',
          height: `${height}px`,
          border: 0,
          background: 'transparent',
          display: 'block',
        }}
      />
    </div>
  );
}
