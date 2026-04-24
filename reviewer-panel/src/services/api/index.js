/**
 * Public surface of the api/ services layer.
 * Consumers import from '../services/api' — Vite resolves to this file
 * because the api/ directory has an index.js.
 *
 * Re-exports are explicit (named, not export *) so each name is grep-able
 * to its owning module. Phase 2.1b swapped the legacy apiFetch (in
 * _internal.js) for apiGet/apiPost/apiPut/apiDelete from services/http.js —
 * none of the names in this file changed.
 */

// Auth — token storage + auth endpoints
export {
  getAuthToken,
  setAuthToken,
  clearAuthToken,
  checkPhone,
  msg91Login,
  requestOtp,
  verifyOtp,
  resendOtp,
  fetchCurrentUser,
} from './auth.js';

// Cache — SWR cache primitives
export { cachedGet, invalidateCache } from './cache.js';

// Stats — admin dashboard
export {
  fetchStats,
  fetchActivityHeatmap,
  fetchLeaderboard,
} from './stats.js';

// Stories — CRUD + search + image upload + related
export {
  semanticSearchStories,
  fetchStories,
  fetchStory,
  updateStoryStatus,
  updateStory,
  deleteStory,
  adminDeleteStory,
  createStory,
  uploadStoryImage,
  fetchRelatedStories,
  reassignStory,
  getAssignmentLog,
  fetchStoryComments,
  postStoryComment,
} from './stories.js';

// Reporters
export {
  fetchReporters,
  fetchReporterStories,
} from './reporters.js';

// Helpers — pure UI shape transforms
export {
  getAvatarColor,
  getInitialsFromName,
  getMediaUrl,
  transformStory,
  transformReporter,
} from './helpers.js';

// Editions — CRUD, page CRUD, story-to-page mapping
export {
  fetchEditions,
  fetchEdition,
  createEdition,
  updateEdition,
  deleteEdition,
  addEditionPage,
  updateEditionPage,
  deleteEditionPage,
  assignStoriesToPage,
  addStoryToPage,
  removeStoryFromPage,
  getStoryPlacements,
  setStoryPlacements,
  listTodaysEditions,
} from './editions.js';

// Org admin — users, roles, entitlements, org metadata + config
export {
  fetchOrgUsers,
  createUser,
  updateUser,
  updateUserRole,
  updateUserEntitlements,
  updateOrg,
  uploadOrgLogo,
  fetchOrgConfig,
  updateOrgConfig,
} from './org.js';

// Sarvam AI — STT websocket + LLM chat
export {
  getSTTWebSocketUrl,
  llmChat,
  translateText,
} from './sarvam.js';

// News articles ingestion + researched-story pipeline
export {
  fetchNewsArticles,
  fetchRelatedArticles,
  researchStoryFromArticle,
  searchNewsByTitle,
  confirmResearchedStory,
} from './news.js';
