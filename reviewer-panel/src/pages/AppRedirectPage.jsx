/**
 * Universal Link fallback page.
 *
 * When a reporter taps a vrittant.in/r/<id> link in WhatsApp:
 *   - If the Vrittant app is installed: iOS / Android intercepts the
 *     URL via Universal Link / App Link and opens the app directly.
 *     This page never renders.
 *   - If the app isn't installed: the OS opens this page in a browser.
 *
 * Reporters do NOT have web panel access, so this page must NOT show
 * any story content, login form, or anything that suggests the panel
 * is for them. Just install-app badges. The brand stays minimal so
 * the page still feels like Vrittant.
 */
import { useEffect } from 'react';

// Google Play listing — live.
const PLAY_STORE_URL =
  'https://play.google.com/store/apps/details?id=com.attentionstack.vrittant';

// iOS App Store listing — pending review at time of writing. Once live,
// flip IOS_LIVE to true and replace the placeholder URL with the real one
// (typically https://apps.apple.com/in/app/vrittant/id<numeric-id>).
const IOS_LIVE = false;
const APP_STORE_URL = 'https://apps.apple.com/in/app/vrittant';

export default function AppRedirectPage() {
  useEffect(() => {
    // No JS-side redirect. The OS-level Universal Link handler should
    // already have opened the app if installed. If we got here, the
    // app isn't installed and the user picks their store manually.
    document.title = 'Open in Vrittant';
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-6 p-6 bg-background text-foreground">
      <div className="flex flex-col items-center gap-2">
        <span className="text-3xl font-bold tracking-tight text-foreground">
          <span className="text-[#FA6C38] italic font-extrabold -mr-px">V</span>rittant
        </span>
        <span className="text-sm text-muted-foreground">
          Editorial newsroom
        </span>
      </div>

      <p className="text-center text-sm text-muted-foreground max-w-xs">
        Install Vrittant to open this story.
      </p>

      <div className="flex flex-col gap-3 w-full max-w-xs">
        <a
          href={PLAY_STORE_URL}
          className="rounded-md border border-border bg-card px-4 py-3 text-center text-sm font-medium text-foreground hover:bg-accent transition-colors no-underline"
        >
          Get it on Google Play
        </a>
        {IOS_LIVE ? (
          <a
            href={APP_STORE_URL}
            className="rounded-md border border-border bg-card px-4 py-3 text-center text-sm font-medium text-foreground hover:bg-accent transition-colors no-underline"
          >
            Download on the App Store
          </a>
        ) : (
          <div className="rounded-md border border-dashed border-border/60 bg-muted/30 px-4 py-3 text-center text-xs text-muted-foreground">
            iOS app coming soon
          </div>
        )}
      </div>

      <p className="text-[11px] text-muted-foreground text-center max-w-xs mt-4">
        If you already have the app, tap the Vrittant link again to open it.
      </p>
    </div>
  );
}
