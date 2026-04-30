import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';

import '../../../core/services/api_config.dart';
import '../../../core/services/api_service.dart';
import '../../../core/services/stt_service.dart';
import '../../../core/services/mic_permission_ui.dart';
import '../../auth/providers/auth_provider.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/theme/theme_extensions.dart';
import '../../../core/l10n/app_strings.dart';
import '../providers/all_news_provider.dart';

class AllNewsScreen extends ConsumerStatefulWidget {
  const AllNewsScreen({super.key});

  @override
  ConsumerState<AllNewsScreen> createState() => _AllNewsScreenState();
}

class _AllNewsScreenState extends ConsumerState<AllNewsScreen>
    with WidgetsBindingObserver {
  final _scrollController = ScrollController();
  final _searchController = TextEditingController();
  bool _showFilters = false;

  // Voice search via Sarvam STT (same engine as notepad)
  StreamingSttService? _stt;
  StreamSubscription<SttSegment>? _sttSub;
  bool _isListening = false;

  AppStrings get s => AppStrings.of(ref);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _scrollController.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(allNewsProvider.notifier).fetchStories();
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Release the mic when the app loses focus. Holding the mic open in the
    // background can trigger OS warnings (the recording indicator stays lit)
    // and on Android may be killed silently anyway, leaving us in an
    // inconsistent _isListening=true state when we resume.
    if (state != AppLifecycleState.resumed && _isListening) {
      _stopListening();
    }
  }

  void _toggleListening() async {
    if (_isListening) {
      await _stopListening();
      return;
    }
    // Permission gate before opening the WS — otherwise the recorder throws
    // a generic exception and the user sees nothing change.
    final ok = await ensureMicPermission(context, ref);
    if (!ok) return;
    // Start recording with Sarvam STT
    try {
      _stt = StreamingSttService();
      _stt!.authToken = ref.read(apiServiceProvider).token;
      final stream = await _stt!.start();
      setState(() => _isListening = true);

      _sttSub = stream.listen(
        (segment) {
          if (!mounted) return;
          _searchController.text = segment.text;
          // Live-update search as user speaks
          ref.read(allNewsProvider.notifier).setSearch(segment.text);
        },
        onError: (_) {
          if (mounted) _stopListening();
        },
        onDone: () {
          if (mounted) setState(() => _isListening = false);
        },
      );
    } catch (_) {
      if (mounted) {
        setState(() => _isListening = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(s.voiceSearchUnavailable)),
        );
      }
    }
  }

  Future<void> _stopListening() async {
    await _sttSub?.cancel();
    _sttSub = null;
    await _stt?.stop();
    _stt?.dispose();
    _stt = null;
    if (mounted) setState(() => _isListening = false);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    _searchController.dispose();
    _sttSub?.cancel();
    _stt?.stop();
    _stt?.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 200) {
      ref.read(allNewsProvider.notifier).loadMore();
    }
  }

  String _dateHeader(DateTime dt) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final storyDate = DateTime(dt.year, dt.month, dt.day);
    if (storyDate == today) return s.today;
    if (storyDate == today.subtract(const Duration(days: 1))) {
      return s.yesterday;
    }
    return '${dt.day}/${dt.month}/${dt.year}';
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(allNewsProvider);

    return Scaffold(
      backgroundColor: context.t.scaffoldBg,
      body: Column(
        children: [
          _buildHeader(),
          _buildSearchRow(state),
          _buildFilterSection(state),
          Expanded(
            child: state.isLoading && state.stories.isEmpty
                ? Center(
                    child: CircularProgressIndicator(
                      color: context.t.primary,
                    ),
                  )
                : RefreshIndicator(
                    color: context.t.primary,
                    onRefresh: () =>
                        ref.read(allNewsProvider.notifier).fetchStories(),
                    child: state.stories.isEmpty
                        ? _buildEmptyOrError(state)
                        : _buildStoryList(state),
                  ),
          ),
        ],
      ),
    );
  }

  // ── Header ──────────────────────────────────────────────────────────────────

  Widget _buildOrgLogo(ReporterProfile? reporter, {double height = 32}) {
    final logoUrl = reporter?.org?.logoUrl;
    if (logoUrl != null && logoUrl.isNotEmpty) {
      final fullUrl =
          logoUrl.startsWith('http') ? logoUrl : '${ApiConfig.baseUrl}$logoUrl';
      return CachedNetworkImage(
        imageUrl: fullUrl,
        height: height,
        fit: BoxFit.contain,
        errorWidget: (_, __, ___) => Text(
          reporter?.org?.name ?? '',
          style: GoogleFonts.plusJakartaSans(
            fontSize: 14,
            fontWeight: FontWeight.w700,
            color: AppColors.vrHeading,
          ),
        ),
        placeholder: (_, __) => SizedBox(height: height),
      );
    }
    return Text(
      reporter?.org?.name ?? reporter?.organization ?? '',
      style: GoogleFonts.plusJakartaSans(
        fontSize: 14,
        fontWeight: FontWeight.w700,
        color: AppColors.vrHeading,
      ),
    );
  }

  Widget _buildHeader() {
    final reporter = ref.watch(authProvider).reporter;

    return Container(
      color: AppColors.neutral0,
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
          child: Row(
            children: [
              SizedBox(
                width: 32,
                height: 32,
                child: SvgPicture.asset(
                  'assets/images/v_logo.svg',
                  fit: BoxFit.contain,
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: RichText(
                  text: TextSpan(
                    children: [
                      TextSpan(
                        text: 'V',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 26,
                          fontWeight: FontWeight.w800,
                          fontStyle: FontStyle.italic,
                          color: AppColors.vrCoral,
                          letterSpacing: -2.0,
                          height: 1,
                        ),
                      ),
                      TextSpan(
                        text: 'rittant',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 26,
                          fontWeight: FontWeight.w800,
                          color: AppColors.vrHeading,
                          letterSpacing: -1.5,
                          height: 1,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              // ── Partner org logo (dynamic) ─────────
              _buildOrgLogo(reporter),
            ],
          ),
        ),
      ),
    );
  }

  // ── Search bar + filter toggle ──────────────────────────────────────────────

  Widget _buildSearchRow(AllNewsState state) {
    final hasActive = state.filters.hasActiveFilters;

    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.base,
        AppSpacing.sm,
        AppSpacing.base,
        AppSpacing.xs,
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _searchController,
              onChanged: (q) => ref.read(allNewsProvider.notifier).setSearch(q),
              style: AppTypography.odiaBodyMedium
                  .copyWith(color: context.t.headingColor),
              decoration: InputDecoration(
                hintText: s.searchStories,
                hintStyle: AppTypography.odiaBodyMedium
                    .copyWith(color: context.t.mutedColor),
                prefixIcon: Icon(
                  LucideIcons.search,
                  size: 18,
                  color: context.t.mutedColor,
                ),
                suffixIcon: IconButton(
                  onPressed: _toggleListening,
                  icon: Icon(
                    _isListening ? LucideIcons.micOff : LucideIcons.mic,
                    size: 20,
                    color: _isListening ? AppColors.vrCoral : context.t.mutedColor,
                  ),
                ),
                filled: true,
                fillColor: context.t.cardBg,
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.base,
                  vertical: AppSpacing.md,
                ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                  borderSide: BorderSide.none,
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                  borderSide: _isListening
                      ? BorderSide(color: AppColors.vrCoral, width: 1.5)
                      : BorderSide.none,
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                  borderSide:
                      BorderSide(color: context.t.primary, width: 1.5),
                ),
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          Stack(
            children: [
              IconButton(
                onPressed: () => setState(() => _showFilters = !_showFilters),
                style: IconButton.styleFrom(
                  backgroundColor: context.t.cardBg,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                  ),
                ),
                icon: Icon(
                  LucideIcons.slidersHorizontal,
                  size: 20,
                  color: context.t.bodyColor,
                ),
              ),
              if (hasActive)
                Positioned(
                  right: 8,
                  top: 8,
                  child: Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: context.t.primary,
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }

  // ── Filter section (collapsible) ────────────────────────────────────────────

  Widget _buildFilterSection(AllNewsState state) {
    return AnimatedCrossFade(
      firstChild: const SizedBox.shrink(),
      secondChild: _buildFilterContent(state),
      crossFadeState:
          _showFilters ? CrossFadeState.showSecond : CrossFadeState.showFirst,
      duration: const Duration(milliseconds: 250),
    );
  }

  Widget _buildFilterContent(AllNewsState state) {
    final filters = state.filters;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.base,
        AppSpacing.sm,
        AppSpacing.base,
        AppSpacing.md,
      ),
      color: context.t.cardBg,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Status row
          Text(
            s.statusFilter,
            style: AppTypography.labelLarge,
          ),
          const SizedBox(height: AppSpacing.sm),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: () {
                final statusEntries = <MapEntry<String?, String>>[
                  MapEntry(null, s.all),
                  MapEntry('draft', s.statusDraft),
                  MapEntry('submitted', s.statusSubmitted),
                ];
                return statusEntries.map((entry) {
                  final isActive = filters.status == entry.key;
                  return Padding(
                    padding: const EdgeInsets.only(right: AppSpacing.sm),
                    child: _buildFilterChip(
                      label: entry.value,
                      isActive: isActive,
                      onTap: () => ref
                          .read(allNewsProvider.notifier)
                          .setStatus(entry.key),
                    ),
                  );
                }).toList();
              }(),
            ),
          ),

          const SizedBox(height: AppSpacing.md),

          // Category row
          Text(
            s.categoryFilter,
            style: AppTypography.labelLarge,
          ),
          const SizedBox(height: AppSpacing.sm),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: () {
                final categoryEntries = <MapEntry<String?, String>>[
                  MapEntry(null, s.all),
                  ...['politics', 'sports', 'crime', 'business', 'entertainment', 'education', 'health', 'technology', 'disaster', 'other']
                    .map((k) => MapEntry<String?, String>(k, s.categoryLabel(k))),
                ];
                return categoryEntries.map((entry) {
                  final isActive = filters.category == entry.key;
                  return Padding(
                    padding: const EdgeInsets.only(right: AppSpacing.sm),
                    child: _buildFilterChip(
                      label: entry.value,
                      isActive: isActive,
                      onTap: () => ref
                          .read(allNewsProvider.notifier)
                          .setCategory(entry.key),
                    ),
                  );
                }).toList();
              }(),
            ),
          ),

          const SizedBox(height: AppSpacing.md),

          // Date range row
          Text(
            s.dateRange,
            style: AppTypography.labelLarge,
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              _buildDateChip(
                label: filters.dateFrom != null
                    ? '${filters.dateFrom!.day}/${filters.dateFrom!.month}/${filters.dateFrom!.year}'
                    : s.dateFrom,
                isActive: filters.dateFrom != null,
                onTap: () => _pickDate(isFrom: true),
              ),
              const SizedBox(width: AppSpacing.sm),
              _buildDateChip(
                label: filters.dateTo != null
                    ? '${filters.dateTo!.day}/${filters.dateTo!.month}/${filters.dateTo!.year}'
                    : s.dateTo,
                isActive: filters.dateTo != null,
                onTap: () => _pickDate(isFrom: false),
              ),
            ],
          ),

          // Clear all button
          if (filters.hasActiveFilters) ...[
            const SizedBox(height: AppSpacing.md),
            GestureDetector(
              onTap: () {
                ref.read(allNewsProvider.notifier).clearAllFilters();
                _searchController.clear();
              },
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.md,
                  vertical: AppSpacing.sm,
                ),
                decoration: BoxDecoration(
                  color: AppColors.coral50,
                  borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(LucideIcons.x,
                        size: 14, color: AppColors.coral500),
                    const SizedBox(width: 4),
                    Text(
                      s.clearAll,
                      style: AppTypography.labelSmall.copyWith(
                        color: AppColors.coral500,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildFilterChip({
    required String label,
    required bool isActive,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
        decoration: BoxDecoration(
          color: isActive ? context.t.primary : context.t.scaffoldBg,
          borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
          border: isActive
              ? null
              : Border.all(
                  color: context.t.dividerColor,
                  width: 1,
                ),
        ),
        child: Text(
          label,
          style: AppTypography.odiaBodySmall.copyWith(
            color: isActive ? context.t.onPrimary : context.t.headingColor,
            fontWeight: isActive ? FontWeight.w600 : FontWeight.w400,
          ),
        ),
      ),
    );
  }

  Widget _buildDateChip({
    required String label,
    required bool isActive,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
        decoration: BoxDecoration(
          color: isActive ? context.t.primaryLight : context.t.cardBg,
          borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
          border: isActive
              ? Border.all(color: context.t.primary, width: 1)
              : null,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              LucideIcons.calendar,
              size: 14,
              color: isActive ? context.t.primary : context.t.mutedColor,
            ),
            const SizedBox(width: 4),
            Text(
              label,
              style: AppTypography.bodySmall.copyWith(
                color: isActive ? context.t.primary : context.t.bodyColor,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _pickDate({required bool isFrom}) async {
    final filters = ref.read(allNewsProvider).filters;
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: isFrom
          ? (filters.dateFrom ?? now)
          : (filters.dateTo ?? now),
      firstDate: DateTime(2020),
      lastDate: now,
    );
    if (picked != null) {
      ref.read(allNewsProvider.notifier).setDateRange(
            isFrom ? picked : filters.dateFrom,
            isFrom ? filters.dateTo : picked,
          );
    }
  }

  // ── Story list ──────────────────────────────────────────────────────────────

  Widget _buildStoryList(AllNewsState state) {
    final widgets = _buildGroupedStoryWidgets(state.stories);

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.all(AppSpacing.base),
      physics: const AlwaysScrollableScrollPhysics(),
      itemCount: widgets.length + (state.isLoading ? 1 : 0),
      itemBuilder: (context, index) {
        if (index < widgets.length) return widgets[index];
        // Loading indicator at bottom
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: AppSpacing.lg),
          child: Center(
            child: CircularProgressIndicator(color: context.t.primary),
          ),
        );
      },
    );
  }

  List<Widget> _buildGroupedStoryWidgets(List<dynamic> stories) {
    // Sort by createdAt DESC to fix duplicate date sections
    final sorted = List<dynamic>.from(stories)
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));

    final widgets = <Widget>[];
    String? lastHeader;

    for (final story in sorted) {
      final header = _dateHeader(story.createdAt);
      if (header != lastHeader) {
        lastHeader = header;
        final isSpecialDate = header == s.today || header == s.yesterday;
        final labelColor = isSpecialDate ? AppColors.vrCoral : AppColors.vrSection;
        widgets.add(
          Padding(
            padding: EdgeInsets.only(
              top: widgets.isEmpty ? 0 : AppSpacing.lg,
              bottom: AppSpacing.sm,
            ),
            child: Row(
              children: [
                Icon(
                  LucideIcons.calendar,
                  size: 13,
                  color: labelColor,
                ),
                const SizedBox(width: 6),
                Text(
                  header.toUpperCase(),
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: labelColor,
                    letterSpacing: 1.0,
                  ),
                ),
              ],
            ),
          ),
        );
      }
      widgets.add(_buildStoryCard(story));
    }

    return widgets;
  }

  /// Format date as "Oct 24" style.
  String _shortDate(DateTime dt) {
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    return '${months[dt.month - 1]} ${dt.day}';
  }

  Widget _buildStoryCard(dynamic story) {
    final headline = story.headline.isNotEmpty
        ? story.headline
        : s.untitledDraft;
    final t = context.t;
    final category = story.category != null
        ? s.categoryLabel(story.category)
        : null;

    return InkWell(
      onTap: () => context.push('/create?storyId=${story.id}'),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.base),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(color: t.dividerColor, width: 0.5),
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            // ── Left content ──
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    headline,
                    style: GoogleFonts.plusJakartaSans(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: story.headline.isEmpty
                          ? t.mutedColor
                          : t.headingColor,
                      height: 1.35,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      Text(
                        _shortDate(story.createdAt),
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 12,
                          color: AppColors.vrCoral,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      if (category != null && category.isNotEmpty) ...[
                        _dot(),
                        Text(
                          category,
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 12,
                            color: t.mutedColor,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                      const SizedBox(width: 8),
                      _statusIcon(story.status),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            // ── Chevron ──
            Icon(
              LucideIcons.chevronRight,
              size: 18,
              color: t.mutedColor,
            ),
          ],
        ),
      ),
    );
  }

  Widget _dot() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6),
      child: Container(
        width: 3, height: 3,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: AppColors.vrMuted,
        ),
      ),
    );
  }



  Widget _statusIcon(String status) {
    final IconData icon;
    final Color color;

    switch (status) {
      case 'draft':
        icon = LucideIcons.pencil;
        color = AppColors.vrCoral;
      case 'submitted':
        icon = LucideIcons.checkCircle2;
        color = AppColors.success;
      case 'published':
        icon = LucideIcons.globe;
        color = AppColors.success;
      case 'review':
        icon = LucideIcons.eye;
        color = AppColors.info;
      case 'archived':
        icon = LucideIcons.archive;
        color = AppColors.vrSection;
      default:
        icon = LucideIcons.fileText;
        color = AppColors.vrSection;
    }

    return Icon(icon, size: 14, color: color);
  }

  // ── Empty state ─────────────────────────────────────────────────────────────

  // Single scrollable wrapper so RefreshIndicator works when the list is
  // empty — without AlwaysScrollable physics the pull gesture is swallowed.
  Widget _buildEmptyOrError(AllNewsState state) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        SizedBox(
          height: MediaQuery.of(context).size.height * 0.6,
          child: state.error != null
              ? _buildErrorState(state.error!)
              : _buildEmptyState(),
        ),
      ],
    );
  }

  Widget _buildErrorState(String message) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(LucideIcons.cloudOff, size: 40, color: context.t.mutedColor),
          const SizedBox(height: AppSpacing.md),
          Text(
            message,
            textAlign: TextAlign.center,
            style: AppTypography.odiaBodyMedium
                .copyWith(color: context.t.mutedColor),
          ),
          const SizedBox(height: AppSpacing.md),
          OutlinedButton.icon(
            onPressed: () =>
                ref.read(allNewsProvider.notifier).fetchStories(),
            icon: const Icon(LucideIcons.refreshCw, size: 16),
            label: Text(s.retry),
            style: OutlinedButton.styleFrom(
              foregroundColor: context.t.primary,
              side: BorderSide(color: context.t.primary),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(LucideIcons.newspaper,
              size: 40, color: context.t.mutedColor),
          const SizedBox(height: AppSpacing.md),
          Text(
            s.noNewsFound,
            style: AppTypography.odiaBodyMedium
                .copyWith(color: context.t.mutedColor),
          ),
        ],
      ),
    );
  }
}
