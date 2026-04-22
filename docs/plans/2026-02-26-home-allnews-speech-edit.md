# Home Redesign, All News Page & Speech-Edit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the home screen with a create button and today's stories, add an All News page with search/filter, and add select-text-then-speak-to-replace editing in the notepad.

**Architecture:** Three features implemented bottom-up: (1) backend filter API, (2) Flutter API client + providers, (3) UI screens. The bottom nav changes from Home|+|Profile to Home|AllNews|Profile, with the create action moving to a button atop the home screen. The speech-edit feature uses Flutter's TextEditingController.selection to detect highlighted text and shows an overlay button to trigger a short STT recording whose output replaces the selection.

**Tech Stack:** Flutter 3.41, Riverpod 3.x, GoRouter, FastAPI, SQLAlchemy, Sarvam STT WebSocket

---

### Task 1: Backend — Add filter/search/pagination to GET /stories

**Files:**
- Modify: `/Users/admin/Desktop/newsflow-api/app/routers/stories.py` (lines 32-47)

**Step 1: Update the list_stories endpoint with query parameters**

Replace the existing `list_stories` function (lines 32-47) with:

```python
@router.get("/stories", response_model=list[StoryResponse])
async def list_stories(
    db: Session = Depends(get_db),
    reporter: Reporter = Depends(current_reporter),
    status: str | None = Query(None, description="Filter by status: draft, submitted, approved, published, rejected"),
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search in headline text"),
    date_from: str | None = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Filter to date (YYYY-MM-DD)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Pagination limit"),
):
    query = db.query(Story).filter(Story.reporter_id == reporter.id)

    if status:
        query = query.filter(Story.status == status)
    if category:
        query = query.filter(Story.category == category)
    if search:
        query = query.filter(Story.headline.ilike(f"%{search}%"))
    if date_from:
        from datetime import datetime
        try:
            dt = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(Story.created_at >= dt)
        except ValueError:
            pass
    if date_to:
        from datetime import datetime
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(Story.created_at <= dt)
        except ValueError:
            pass

    stories = (
        query
        .order_by(Story.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return stories
```

Add `Query` import at top of file if not present:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
```

**Step 2: Verify backend starts and endpoints respond**

Run:
```bash
cd /Users/admin/Desktop/newsflow-api && python -m uvicorn app.main:app --reload --port 8000
```

Test with curl:
```bash
# Get token first
TOKEN=$(curl -s -X POST http://localhost:8000/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"phone":"+919876543210","otp":"123456"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Test filter params
curl -s "http://localhost:8000/stories?status=draft&limit=5" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Test search
curl -s "http://localhost:8000/stories?search=test&offset=0&limit=10" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: 200 OK with filtered story arrays.

**Step 3: Commit**

```bash
cd /Users/admin/Desktop/newsflow-api
git add app/routers/stories.py
git commit -m "feat: add filter/search/pagination params to GET /stories"
```

---

### Task 2: Flutter API client — Add filter params to listStories

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/lib/core/services/api_service.dart` (lines 169-174)

**Step 1: Update the listStories method**

Replace the existing `listStories` method (lines 169-174) with:

```dart
  /// Lists stories with optional filters and pagination.
  Future<List<StoryDto>> listStories({
    String? status,
    String? category,
    String? search,
    String? dateFrom,
    String? dateTo,
    int offset = 0,
    int limit = 50,
  }) async {
    final queryParams = <String, dynamic>{
      'offset': offset,
      'limit': limit,
    };
    if (status != null) queryParams['status'] = status;
    if (category != null) queryParams['category'] = category;
    if (search != null && search.isNotEmpty) queryParams['search'] = search;
    if (dateFrom != null) queryParams['date_from'] = dateFrom;
    if (dateTo != null) queryParams['date_to'] = dateTo;

    final response = await _dio.get(
      '/stories',
      queryParameters: queryParams,
    );
    return (response.data as List)
        .map((json) => StoryDto.fromJson(json as Map<String, dynamic>))
        .toList();
  }
```

**Step 2: Build to verify compilation**

```bash
cd /Users/admin/Desktop/newsflow && flutter build web --release 2>&1 | tail -5
```

Expected: `✓ Built build/web`

**Step 3: Commit**

```bash
cd /Users/admin/Desktop/newsflow
git add lib/core/services/api_service.dart
git commit -m "feat: add filter/search/pagination params to listStories API"
```

---

### Task 3: Bottom nav — Replace center FAB with All News tab

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/lib/core/widgets/app_bottom_nav.dart` (full rewrite of nav items)

**Step 1: Rewrite AppShell to have 3 equal tabs: Home | All News | Profile**

The current file has Home (index 0), center FAB (+), and Profile (index 1). Replace the entire nav structure with three equal `_NavItem` widgets. Remove the elevated circular gradient FAB.

Update `_currentIndex` to handle 3 routes:
```dart
int _currentIndex(BuildContext context) {
  final uri = GoRouterState.of(context).uri.toString();
  if (uri.startsWith('/all-news')) return 1;
  if (uri.startsWith('/profile')) return 2;
  return 0; // /home
}
```

Replace the nav `Row` children (currently lines 33-76) with:
```dart
Row(
  mainAxisAlignment: MainAxisAlignment.spaceAround,
  children: [
    _NavItem(
      icon: LucideIcons.home,
      label: '\u0B18\u0B30', // ଘର
      isActive: currentIndex == 0,
      onTap: () => context.go('/home'),
    ),
    _NavItem(
      icon: LucideIcons.newspaper,
      label: '\u0B38\u0B2C\u0B41 \u0B16\u0B2C\u0B30', // ସବୁ ଖବର
      isActive: currentIndex == 1,
      onTap: () => context.go('/all-news'),
    ),
    _NavItem(
      icon: LucideIcons.user,
      label: '\u0B2E\u0B41\u0B01', // ମୁଁ
      isActive: currentIndex == 2,
      onTap: () => context.go('/profile'),
    ),
  ],
),
```

Remove the old gradient FAB container (the center child in the current Row). The `_NavItem` widget class can stay largely the same.

**Step 2: Update router to add /all-news route inside the ShellRoute**

File: `/Users/admin/Desktop/newsflow/lib/core/router/app_router.dart` (lines 31-39)

Add `/all-news` as a child of the ShellRoute alongside `/home` and `/profile`. For now, use a placeholder widget:

```dart
ShellRoute(
  navigatorKey: _shellNavigatorKey,
  builder: (context, state, child) => AppShell(child: child),
  routes: [
    GoRoute(path: '/home', builder: (_, __) => const HomeScreen()),
    GoRoute(path: '/all-news', builder: (_, __) => const AllNewsScreen()),
    GoRoute(path: '/profile', builder: (_, __) => const ProfileScreen()),
  ],
),
```

Create a minimal placeholder `/Users/admin/Desktop/newsflow/lib/features/all_news/screens/all_news_screen.dart`:

```dart
import 'package:flutter/material.dart';

class AllNewsScreen extends StatelessWidget {
  const AllNewsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: Text('All News — coming soon')),
    );
  }
}
```

Add the import to `app_router.dart`.

**Step 3: Build and verify**

```bash
cd /Users/admin/Desktop/newsflow && flutter build web --release 2>&1 | tail -5
```

Expected: `✓ Built build/web`

**Step 4: Commit**

```bash
cd /Users/admin/Desktop/newsflow
git add lib/core/widgets/app_bottom_nav.dart lib/core/router/app_router.dart lib/features/all_news/screens/all_news_screen.dart
git commit -m "feat: replace center FAB with All News tab in bottom nav"
```

---

### Task 4: Home screen redesign — Create button + today's stories

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/lib/features/home/screens/home_screen.dart` (full rework of body)

**Step 1: Replace the story sections logic**

The current `_buildSections` (lines 151-193) splits stories into drafts vs submitted. Replace with date-based logic:

In the `_HomeScreenState`, add a helper to check if a story is from today:

```dart
bool _isToday(DateTime dt) {
  final now = DateTime.now();
  return dt.year == now.year && dt.month == now.month && dt.day == now.day;
}
```

Replace `_buildSections` with a new method that:
1. Filters `stories` to only today's stories (by `createdAt`)
2. If today's stories exist: shows header "ଆଜି" (Today) + count + story cards
3. If no today's stories: shows header "ସାମ୍ପ୍ରତିକ" (Recent) + up to 5 latest stories from full list

**Step 2: Add the create button below the header**

Add a full-width button after `_buildHeader()` and before the story list. Use the primary gradient style:

```dart
Widget _buildCreateButton() {
  return Padding(
    padding: const EdgeInsets.symmetric(
      horizontal: AppSpacing.base,
      vertical: AppSpacing.sm,
    ),
    child: Material(
      borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
        onTap: () => context.push('/create'),
        child: Ink(
          decoration: BoxDecoration(
            gradient: AppGradients.primaryButton,
            borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(
              vertical: AppSpacing.md,
              horizontal: AppSpacing.lg,
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(LucideIcons.plus, color: Colors.white, size: 20),
                const SizedBox(width: AppSpacing.sm),
                Text(
                  '\u0B28\u0B42\u0B06 \u0B16\u0B2C\u0B30 \u0B32\u0B47\u0B16\u0B28\u0B4D\u0B24\u0B41',
                  // ନୂଆ ଖବର ଲେଖନ୍ତୁ (Write New News)
                  style: AppTypography.odiaTitleLarge.copyWith(
                    color: Colors.white,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}
```

**Step 3: Update the build method body**

In the main `build()` method, restructure the body Column to:
1. `_buildHeader()` — existing header
2. `_buildCreateButton()` — new create button
3. Expanded → RefreshIndicator → story list (today's or recent)

Replace the section headers from "ମୋ ଡ୍ରାଫ୍ଟ" / "ଦାଖଲ ହୋଇଛି" to "ଆଜି" / "ସାମ୍ପ୍ରତିକ". Each story card still shows its Draft/Submitted status badge — the grouping just changes from status-based to date-based.

**Step 4: Update the empty state**

When there are zero stories total, show the existing `_buildFullEmptyState()` but without the microphone icon (since the create button is already visible above). Simplify to a short message like "ଆଜି କିଛି ଖବର ନାହିଁ" (No news today).

**Step 5: Build and verify**

```bash
cd /Users/admin/Desktop/newsflow && flutter build web --release 2>&1 | tail -5
```

**Step 6: Visually verify in browser**

Restart dev server and check:
- Create button visible at top
- Today's stories shown under "ଆଜି" header
- Status badges (Draft/Submitted) visible on each card
- Tapping create button navigates to `/create`

**Step 7: Commit**

```bash
cd /Users/admin/Desktop/newsflow
git add lib/features/home/screens/home_screen.dart
git commit -m "feat: redesign home with create button and today's stories"
```

---

### Task 5: All News provider — Filterable stories state

**Files:**
- Create: `/Users/admin/Desktop/newsflow/lib/features/all_news/providers/all_news_provider.dart`

**Step 1: Create the provider with filter state**

```dart
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/api_service.dart';

class AllNewsFilters {
  final String? status;
  final String? category;
  final String? search;
  final DateTime? dateFrom;
  final DateTime? dateTo;

  const AllNewsFilters({
    this.status,
    this.category,
    this.search,
    this.dateFrom,
    this.dateTo,
  });

  AllNewsFilters copyWith({
    String? status,
    bool clearStatus = false,
    String? category,
    bool clearCategory = false,
    String? search,
    bool clearSearch = false,
    DateTime? dateFrom,
    bool clearDateFrom = false,
    DateTime? dateTo,
    bool clearDateTo = false,
  }) {
    return AllNewsFilters(
      status: clearStatus ? null : (status ?? this.status),
      category: clearCategory ? null : (category ?? this.category),
      search: clearSearch ? null : (search ?? this.search),
      dateFrom: clearDateFrom ? null : (dateFrom ?? this.dateFrom),
      dateTo: clearDateTo ? null : (dateTo ?? this.dateTo),
    );
  }

  /// Format dateFrom for API query param.
  String? get dateFromStr => dateFrom != null
      ? '${dateFrom!.year}-${dateFrom!.month.toString().padLeft(2, '0')}-${dateFrom!.day.toString().padLeft(2, '0')}'
      : null;

  /// Format dateTo for API query param.
  String? get dateToStr => dateTo != null
      ? '${dateTo!.year}-${dateTo!.month.toString().padLeft(2, '0')}-${dateTo!.day.toString().padLeft(2, '0')}'
      : null;

  bool get hasActiveFilters =>
      status != null || category != null || dateFrom != null || dateTo != null;
}

class AllNewsState {
  final List<StoryDto> stories;
  final bool isLoading;
  final bool hasMore;
  final String? error;
  final AllNewsFilters filters;

  const AllNewsState({
    this.stories = const [],
    this.isLoading = false,
    this.hasMore = true,
    this.error,
    this.filters = const AllNewsFilters(),
  });

  AllNewsState copyWith({
    List<StoryDto>? stories,
    bool? isLoading,
    bool? hasMore,
    String? error,
    bool clearError = false,
    AllNewsFilters? filters,
  }) {
    return AllNewsState(
      stories: stories ?? this.stories,
      isLoading: isLoading ?? this.isLoading,
      hasMore: hasMore ?? this.hasMore,
      error: clearError ? null : (error ?? this.error),
      filters: filters ?? this.filters,
    );
  }
}

class AllNewsNotifier extends Notifier<AllNewsState> {
  static const _pageSize = 20;

  Timer? _searchDebounce;

  @override
  AllNewsState build() => const AllNewsState();

  ApiService get _api => ref.read(apiServiceProvider);

  /// Fetch first page of stories with current filters.
  Future<void> fetchStories() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final f = state.filters;
      final stories = await _api.listStories(
        status: f.status,
        category: f.category,
        search: f.search,
        dateFrom: f.dateFromStr,
        dateTo: f.dateToStr,
        offset: 0,
        limit: _pageSize,
      );
      state = AllNewsState(
        stories: stories,
        hasMore: stories.length >= _pageSize,
        filters: f,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: 'Failed to load stories');
    }
  }

  /// Load next page (infinite scroll).
  Future<void> loadMore() async {
    if (state.isLoading || !state.hasMore) return;
    state = state.copyWith(isLoading: true);
    try {
      final f = state.filters;
      final moreStories = await _api.listStories(
        status: f.status,
        category: f.category,
        search: f.search,
        dateFrom: f.dateFromStr,
        dateTo: f.dateToStr,
        offset: state.stories.length,
        limit: _pageSize,
      );
      state = state.copyWith(
        stories: [...state.stories, ...moreStories],
        isLoading: false,
        hasMore: moreStories.length >= _pageSize,
      );
    } catch (_) {
      state = state.copyWith(isLoading: false);
    }
  }

  /// Update filters and re-fetch.
  void setFilters(AllNewsFilters filters) {
    state = state.copyWith(filters: filters);
    fetchStories();
  }

  /// Debounced search — waits 500ms after last keystroke.
  void setSearch(String query) {
    _searchDebounce?.cancel();
    final newFilters = query.isEmpty
        ? state.filters.copyWith(clearSearch: true)
        : state.filters.copyWith(search: query);
    state = state.copyWith(filters: newFilters);
    _searchDebounce = Timer(const Duration(milliseconds: 500), () {
      fetchStories();
    });
  }

  void setStatus(String? status) {
    setFilters(status == null
        ? state.filters.copyWith(clearStatus: true)
        : state.filters.copyWith(status: status));
  }

  void setCategory(String? category) {
    setFilters(category == null
        ? state.filters.copyWith(clearCategory: true)
        : state.filters.copyWith(category: category));
  }

  void setDateRange(DateTime? from, DateTime? to) {
    setFilters(state.filters.copyWith(
      dateFrom: from,
      clearDateFrom: from == null,
      dateTo: to,
      clearDateTo: to == null,
    ));
  }

  void clearAllFilters() {
    setFilters(const AllNewsFilters());
  }
}

final allNewsProvider =
    NotifierProvider<AllNewsNotifier, AllNewsState>(AllNewsNotifier.new);
```

**Step 2: Build to verify**

```bash
cd /Users/admin/Desktop/newsflow && flutter build web --release 2>&1 | tail -5
```

**Step 3: Commit**

```bash
cd /Users/admin/Desktop/newsflow
git add lib/features/all_news/providers/all_news_provider.dart
git commit -m "feat: add AllNewsNotifier with filter/search/pagination state"
```

---

### Task 6: All News screen — Search bar, filter panel, story list

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/lib/features/all_news/screens/all_news_screen.dart` (replace placeholder)

**Step 1: Build the full All News screen**

The screen layout (top to bottom):
1. **AppBar-like header**: Title "ସବୁ ଖବର" (All News)
2. **Search bar** (persistent): TextField with search icon, calls `notifier.setSearch(query)`
3. **Filter icon** (right of search): Toggles visibility of filter section
4. **Filter section** (collapsed by default, animated):
   - Status chips: ସବୁ (All) / ଡ୍ରାଫ୍ଟ / ଦାଖଲ / ଅନୁମୋଦିତ / ପ୍ରତ୍ୟାଖ୍ୟାତ
   - Category chips: ସବୁ + known categories (politics, sports, crime, business, entertainment, education, health, technology, disaster, other)
   - Date range: Two tappable date display chips → `showDatePicker()`
   - "Clear all" button when filters are active
5. **Story list**: ListView.builder with scroll listener for infinite scroll
   - Stories grouped by date headers: "ଆଜି" (Today), "ଗତକାଲି" (Yesterday), or formatted date
   - Each card identical to home screen story cards
   - Loading indicator at bottom when fetching more
6. **Empty state**: When no stories match filters

Key implementation details:
- Use `ConsumerStatefulWidget` with `ref.watch(allNewsProvider)`
- Add `ScrollController` with listener for infinite scroll: when `position.pixels >= position.maxScrollExtent - 200`, call `notifier.loadMore()`
- The filter section uses `AnimatedCrossFade` or `AnimatedSize` to expand/collapse
- Status chips use `ChoiceChip` or custom chip widgets matching the app's existing style
- Category labels should be displayed in Odia where possible, else English lowercase
- Date headers computed by grouping stories by `createdAt` date

Category label map (Odia):
```dart
const categoryLabels = {
  'politics': '\u0B30\u0B3E\u0B1C\u0B28\u0B40\u0B24\u0B3F', // ରାଜନୀତି
  'sports': '\u0B15\u0B4D\u0B30\u0B40\u0B21\u0B3C\u0B3E', // କ୍ରୀଡ଼ା
  'crime': '\u0B05\u0B2A\u0B30\u0B3E\u0B27', // ଅପରାଧ
  'business': '\u0B2C\u0B4D\u0B5F\u0B2C\u0B38\u0B3E\u0B5F', // ବ୍ୟବସାୟ
  'entertainment': '\u0B2E\u0B28\u0B4B\u0B30\u0B1E\u0B4D\u0B1C\u0B28', // ମନୋରଞ୍ଜନ
  'education': '\u0B36\u0B3F\u0B15\u0B4D\u0B37\u0B3E', // ଶିକ୍ଷା
  'health': '\u0B38\u0B4D\u0B2C\u0B3E\u0B38\u0B4D\u0B25\u0B4D\u0B5F', // ସ୍ୱାସ୍ଥ୍ୟ
  'technology': '\u0B2A\u0B4D\u0B30\u0B5F\u0B41\u0B15\u0B4D\u0B24\u0B3F', // ପ୍ରଯୁକ୍ତି
  'disaster': '\u0B2C\u0B3F\u0B2A\u0B26', // ବିପଦ
  'other': '\u0B05\u0B28\u0B4D\u0B5F\u0B3E\u0B28\u0B4D\u0B5F', // ଅନ୍ୟାନ୍ୟ
};
```

Date header helper:
```dart
String _dateHeader(DateTime dt) {
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final storyDate = DateTime(dt.year, dt.month, dt.day);

  if (storyDate == today) return '\u0B06\u0B1C\u0B3F'; // ଆଜି
  if (storyDate == today.subtract(const Duration(days: 1))) {
    return '\u0B17\u0B24\u0B15\u0B3E\u0B32\u0B3F'; // ଗତକାଲି
  }
  return '${dt.day}/${dt.month}/${dt.year}';
}
```

**Step 2: Build and verify**

```bash
cd /Users/admin/Desktop/newsflow && flutter build web --release 2>&1 | tail -5
```

**Step 3: Visual test in browser**

Restart dev server, navigate to All News tab:
- Search bar visible at top
- Filter icon toggles filter panel
- Stories listed with date headers
- Scroll to bottom loads more
- Filters update the list

**Step 4: Commit**

```bash
cd /Users/admin/Desktop/newsflow
git add lib/features/all_news/screens/all_news_screen.dart
git commit -m "feat: build All News screen with search, filters, and infinite scroll"
```

---

### Task 7: Speech-edit — Text selection detection + overlay button

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/lib/features/create_news/screens/notepad_screen.dart`

**Step 1: Add selection state tracking**

In `_NotepadScreenState` (around line 29), add state for tracking text selection:

```dart
// Speech-edit state
bool _hasTextSelection = false;
TextSelection? _currentSelection;
```

**Step 2: Add a selection change listener to the inline edit TextField**

In the `_ParagraphBlock` widget (around line 943), the TextField (lines 978-994) needs an `onSelectionChanged` callback. Since `TextField` doesn't have a direct `onSelectionChanged`, we need to wrap it or use a `TextEditingController` listener.

Add a callback parameter to `_ParagraphBlock`:
```dart
final ValueChanged<TextSelection>? onSelectionChanged;
```

In the parent `_NotepadBody`, pass a callback that updates `_hasTextSelection` and `_currentSelection` in the top-level state. Since `_NotepadBody` is a StatelessWidget and `_ParagraphBlock` is also stateless, we need to pass callbacks up.

The approach:
1. Add `onSelectionChanged` callback to `_NotepadBody` → `_ParagraphBlock`
2. In `_NotepadScreenState._startInlineEdit()`, add a listener on `_inlineEditController`:
```dart
_inlineEditController!.addListener(() {
  final sel = _inlineEditController!.selection;
  final hasSelection = sel.isValid && sel.start != sel.end;
  if (hasSelection != _hasTextSelection) {
    setState(() {
      _hasTextSelection = hasSelection;
      _currentSelection = hasSelection ? sel : null;
    });
  }
});
```

**Step 3: Show floating edit button when text is selected**

In the `build()` method of `_NotepadScreenState`, add a `Stack` around the body content. When `_hasTextSelection` is true and `_inlineEditingIndex != null`, show a positioned button:

```dart
if (_hasTextSelection && _inlineEditingIndex != null)
  Positioned(
    bottom: 80, // above the bottom action bar
    left: 0,
    right: 0,
    child: Center(
      child: Material(
        elevation: 4,
        borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
          onTap: () => _startSpeechEdit(),
          child: Ink(
            decoration: BoxDecoration(
              gradient: AppGradients.primaryButton,
              borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
            ),
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.lg,
              vertical: AppSpacing.md,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(LucideIcons.mic, color: Colors.white, size: 18),
                const SizedBox(width: AppSpacing.sm),
                Text(
                  '\u0B38\u0B2E\u0B4D\u0B2A\u0B3E\u0B26\u0B28\u0B3E',
                  // ସମ୍ପାଦନା (Edit)
                  style: AppTypography.odiaTitleLarge.copyWith(
                    color: Colors.white,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  ),
```

**Step 4: Build and verify**

```bash
cd /Users/admin/Desktop/newsflow && flutter build web --release 2>&1 | tail -5
```

**Step 5: Commit**

```bash
cd /Users/admin/Desktop/newsflow
git add lib/features/create_news/screens/notepad_screen.dart
git commit -m "feat: add text selection detection and floating speech-edit button"
```

---

### Task 8: Speech-edit — Record and replace selected text

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/lib/features/create_news/screens/notepad_screen.dart`
- Modify: `/Users/admin/Desktop/newsflow/lib/features/create_news/providers/create_news_provider.dart`

**Step 1: Add speech-edit recording method to the provider**

In `NotepadNotifier`, add a method for short recording that returns the transcript:

```dart
/// Starts a short speech-edit recording session.
/// Returns the transcribed text, or null if nothing detected.
Future<String?> recordSpeechEdit() async {
  final stt = StreamingSttService();
  String lastTranscript = '';

  try {
    final stream = await stt.start();
    final completer = Completer<String?>();

    final sub = stream.listen(
      (segment) {
        lastTranscript = segment.text;
      },
      onError: (_) {
        if (!completer.isCompleted) completer.complete(null);
      },
    );

    // Wait for user to stop (this is controlled by the UI calling stopSpeechEdit)
    // Store references so UI can stop it
    _speechEditStt = stt;
    _speechEditSubscription = sub;
    _speechEditCompleter = completer;

    return completer.future;
  } catch (e) {
    stt.dispose();
    return null;
  }
}

StreamingSttService? _speechEditStt;
StreamSubscription<SttSegment>? _speechEditSubscription;
Completer<String?>? _speechEditCompleter;
String _speechEditTranscript = '';

/// Stops speech-edit recording and returns the result.
Future<String?> stopSpeechEdit() async {
  final transcript = _speechEditTranscript;
  _speechEditSubscription?.cancel();
  await _speechEditStt?.stop();
  _speechEditStt?.dispose();
  _speechEditStt = null;
  _speechEditSubscription = null;

  if (!(_speechEditCompleter?.isCompleted ?? true)) {
    _speechEditCompleter!.complete(
      transcript.trim().isEmpty ? null : transcript.trim(),
    );
  }
  _speechEditCompleter = null;
  _speechEditTranscript = '';
  return transcript.trim().isEmpty ? null : transcript.trim();
}
```

Actually, a simpler approach — since the STT service already accumulates text, we can use a simpler flow:

Add to `NotepadNotifier`:
```dart
// --- Speech edit support ---
StreamingSttService? _speechEditStt;
StreamSubscription<SttSegment>? _speechEditSub;

/// Start a short speech-edit recording. The live text is exposed via
/// state.speechEditTranscript so the UI can show it.
Future<void> startSpeechEdit() async {
  _speechEditStt = StreamingSttService();
  final stream = await _speechEditStt!.start();
  state = state.copyWith(isSpeechEditing: true, speechEditTranscript: '');
  _speechEditSub = stream.listen(
    (segment) {
      state = state.copyWith(speechEditTranscript: segment.text);
    },
    onError: (_) {},
  );
}

/// Stop speech-edit and return the transcript.
Future<String> stopSpeechEdit() async {
  final transcript = state.speechEditTranscript;
  _speechEditSub?.cancel();
  _speechEditSub = null;
  await _speechEditStt?.stop();
  _speechEditStt?.dispose();
  _speechEditStt = null;
  state = state.copyWith(isSpeechEditing: false, speechEditTranscript: '');
  return transcript;
}
```

Add two new fields to `NotepadState`:
```dart
final bool isSpeechEditing;
final String speechEditTranscript;
```

With defaults `false` and `''` in the constructor. Update `copyWith` to include them.

**Step 2: Add the _startSpeechEdit and _stopSpeechEdit methods to the screen**

In `_NotepadScreenState`:

```dart
Future<void> _startSpeechEdit() async {
  if (_currentSelection == null || _inlineEditingIndex == null) return;

  final notifier = ref.read(notepadProvider.notifier);
  await notifier.startSpeechEdit();
}

Future<void> _stopSpeechEdit() async {
  final notifier = ref.read(notepadProvider.notifier);
  final replacement = await notifier.stopSpeechEdit();

  if (replacement.isNotEmpty &&
      _inlineEditController != null &&
      _currentSelection != null) {
    final controller = _inlineEditController!;
    final sel = _currentSelection!;
    final text = controller.text;

    // Replace the selected range with the spoken text
    final newText = text.replaceRange(sel.start, sel.end, replacement);
    controller.text = newText;

    // Move cursor to end of replacement
    controller.selection = TextSelection.collapsed(
      offset: sel.start + replacement.length,
    );

    // Commit the edit
    _commitInlineEdit(_inlineEditingIndex!);
  }

  setState(() {
    _hasTextSelection = false;
    _currentSelection = null;
  });
}
```

**Step 3: Update the floating button to toggle start/stop**

When the user taps the speech-edit button:
- If not recording: call `_startSpeechEdit()`, button changes to a stop button
- If recording (isSpeechEditing): call `_stopSpeechEdit()`, button disappears

The button shows:
- "🎙 ସମ୍ପାଦନା" when not recording → starts recording
- "⏹ ବନ୍ଦ କରନ୍ତୁ" (Stop) + live transcript preview when recording → stops and replaces

Watch `state.isSpeechEditing` and `state.speechEditTranscript` to update the button UI.

**Step 4: Build and verify**

```bash
cd /Users/admin/Desktop/newsflow && flutter build web --release 2>&1 | tail -5
```

**Step 5: Visual test in browser**

1. Open a story with text paragraphs
2. Tap a paragraph to enter inline edit
3. Select some text by tap-and-drag
4. Floating "ସମ୍ପାଦନା" button should appear
5. Tap it → button changes to stop button with live transcript
6. Speak replacement text
7. Tap stop → selected text is replaced with spoken text

**Step 6: Commit**

```bash
cd /Users/admin/Desktop/newsflow
git add lib/features/create_news/screens/notepad_screen.dart lib/features/create_news/providers/create_news_provider.dart
git commit -m "feat: speech-edit — record replacement text for selected paragraph text"
```

---

### Task 9: Polish and integration test

**Files:**
- All modified files from Tasks 1-8

**Step 1: Full build verification**

```bash
cd /Users/admin/Desktop/newsflow && flutter build web --release 2>&1 | tail -5
```

**Step 2: Restart dev server and backend**

```bash
# Backend
cd /Users/admin/Desktop/newsflow-api && python -m uvicorn app.main:app --reload --port 8000

# Flutter dev server
cd /Users/admin/Desktop/newsflow && flutter run -d chrome --web-port=8080
```

**Step 3: End-to-end test checklist**

1. **Login**: Enter phone + OTP → land on home screen
2. **Home screen**:
   - Create button visible at top
   - Today's stories under "ଆଜି" header
   - Status badges (Draft/Submitted) on each card
   - Tap create button → navigates to notepad
3. **Bottom nav**:
   - Three tabs: ଘର | ସବୁ ଖବର | ମୁଁ
   - Each tab navigates correctly
   - Active tab highlighted
4. **All News page**:
   - Search bar at top, type to filter
   - Filter icon expands filter section
   - Status/category chips filter stories
   - Date range picker works
   - Stories grouped by date headers
   - Scroll to load more
5. **Speech edit**:
   - Open a story, tap a paragraph
   - Select text, floating edit button appears
   - Tap → record → stop → text replaced
6. **Navigation**:
   - Home → Create → Back → Home
   - Home → All News → tap story → opens in notepad
   - All tabs preserve their state

**Step 4: Fix any issues found during testing**

**Step 5: Commit all remaining changes**

```bash
cd /Users/admin/Desktop/newsflow
git add -A
git commit -m "feat: complete home redesign, all news page, and speech-edit feature"
```
