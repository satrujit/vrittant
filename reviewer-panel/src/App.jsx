import { useEffect, useRef } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { I18nProvider, useI18n } from './i18n';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import AppLayout from './components/layout/AppLayout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import AllStoriesPage from './pages/AllStoriesPage';
import ReportersPage from './pages/ReportersPage';
import ReporterDetailPage from './pages/ReporterDetailPage';
import BucketsListPage from './pages/BucketsListPage';
import BucketDetailPage from './pages/BucketDetailPage';
import SettingsPage from './pages/SettingsPage';
import LeaderboardPage from './pages/LeaderboardPage';
import NewsFeedPage from './pages/NewsFeedPage';
import ReviewPage from './pages/ReviewPage';
import WidgetsPage from './pages/WidgetsPage';
import PrivacyPolicyPage from './pages/PrivacyPolicyPage';

const LANG_MAP = { odia: 'or', english: 'en', hindi: 'hi' };

/** Apply org default language ONCE on first login — never override user's localStorage choice */
function LocaleSync() {
  const { user } = useAuth();
  const { setLocale } = useI18n();
  const didSync = useRef(false);
  useEffect(() => {
    if (didSync.current) return;
    const saved = localStorage.getItem('vrittant_locale');
    if (saved) { didSync.current = true; return; }
    const lang = user?.org?.default_language;
    if (lang && LANG_MAP[lang]) {
      setLocale(LANG_MAP[lang]);
      didSync.current = true;
    }
  }, [user?.org?.default_language, setLocale]);
  return null;
}

function App() {
  return (
    <I18nProvider defaultLocale="en">
      <AuthProvider>
        <LocaleSync />
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/privacy-policy" element={<PrivacyPolicyPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<AppLayout />}>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/stories" element={<AllStoriesPage />} />
                <Route path="/reporters" element={<ReportersPage />} />
                <Route path="/reporters/:id" element={<ReporterDetailPage />} />
                <Route path="/leaderboard" element={<LeaderboardPage />} />
                <Route path="/buckets" element={<BucketsListPage />} />
                <Route path="/buckets/:editionId" element={<BucketDetailPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/news-feed" element={<NewsFeedPage />} />
                <Route path="/widgets" element={<WidgetsPage />} />
              </Route>
              <Route path="/review/:id" element={<ReviewPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </I18nProvider>
  );
}

export default App;
