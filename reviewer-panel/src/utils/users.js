/**
 * User-list filtering helpers shared across the panel.
 *
 * Centralises the "who can a story be assigned to" rule so the
 * assignee dropdowns on ReviewPage, AllStoriesPage, DashboardPage,
 * and the review side panel stay in sync.
 *
 * Rule: anyone whose `user_type` is reviewer or org_admin and who is
 * active. Sorted by display name (case-insensitive, locale-aware) so
 * the dropdown is scannable.
 */

const ASSIGNABLE_TYPES = new Set(['reviewer', 'org_admin']);

export function isAssignable(user) {
  if (!user) return false;
  if (!ASSIGNABLE_TYPES.has(user.user_type)) return false;
  return user.is_active ?? true;
}

export function sortByName(users) {
  return [...users].sort((a, b) =>
    String(a?.name || '').localeCompare(String(b?.name || ''), undefined, {
      sensitivity: 'base',
    })
  );
}

/**
 * Filter a raw user list (e.g. from `fetchReporters`) down to the
 * users that may be assigned a story for review, sorted alphabetically
 * by name.
 */
export function assignableReviewers(users) {
  if (!Array.isArray(users)) return [];
  return sortByName(users.filter(isAssignable));
}
