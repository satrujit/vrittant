import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';

import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/theme_extensions.dart';
import '../../../core/services/api_config.dart';
import '../../../core/services/api_service.dart';
import '../../../core/l10n/app_strings.dart';
import '../../../core/providers/connectivity_provider.dart';
import '../../../core/providers/phone_call_provider.dart';
import '../../../core/widgets/status_banner.dart';
import '../../auth/providers/auth_provider.dart';
import '../providers/stories_provider.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  AppStrings get s => AppStrings.of(ref);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(storiesProvider.notifier).fetchStories();
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        ref.read(storiesProvider.notifier).fetchStories();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);
    final storiesState = ref.watch(storiesProvider);
    final reporter = authState.reporter;
    final isConnected = ref.watch(connectivityProvider);
    final isInCall = ref.watch(phoneCallProvider);

    return Scaffold(
      backgroundColor: context.t.scaffoldBg,
      floatingActionButton: FloatingActionButton(
        onPressed: () => context.push('/create'),
        backgroundColor: AppColors.vrCoral,
        elevation: 4,
        child: const Icon(LucideIcons.plus, color: Colors.white, size: 24),
      ),
      body: Column(
        children: [
          _buildHeader(reporter),
          if (!isConnected) StatusBanner.noInternet(),
          if (isInCall) StatusBanner.micBusy(),
          Expanded(
            child: storiesState.isLoading && storiesState.stories.isEmpty
                ? Center(child: CircularProgressIndicator(color: context.t.primary))
                : RefreshIndicator(
                    color: context.t.primary,
                    onRefresh: () =>
                        ref.read(storiesProvider.notifier).fetchStories(),
                    child: storiesState.stories.isEmpty
                        ? _buildFullEmptyState()
                        : _buildContent(storiesState),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(ReporterProfile? reporter) {
    return Container(
      color: AppColors.neutral0,
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
          child: Row(
            children: [
              // ── V curved icon ──────────────────────
              SizedBox(
                width: 32,
                height: 32,
                child: SvgPicture.asset(
                  'assets/images/v_logo.svg',
                  fit: BoxFit.contain,
                ),
              ),
              const SizedBox(width: 6),
              // ── "Vrittant" text ────────────────────
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

  Widget _buildOrgLogo(ReporterProfile? reporter, {double height = 32}) {
    try {
      final logoUrl = reporter?.org?.logoUrl;
      if (logoUrl != null && logoUrl.isNotEmpty) {
        final fullUrl =
            logoUrl.startsWith('http') ? logoUrl : '${ApiConfig.baseUrl}$logoUrl';
        return ConstrainedBox(
          constraints: BoxConstraints(maxWidth: 160, maxHeight: height),
          child: Image.network(
            fullUrl,
            height: height,
            fit: BoxFit.contain,
            errorBuilder: (_, __, ___) => Text(
              reporter?.org?.name ?? '',
              style: GoogleFonts.plusJakartaSans(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: AppColors.vrHeading,
              ),
            ),
          ),
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
    } catch (e) {
      debugPrint('_buildOrgLogo error: $e');
      return const SizedBox.shrink();
    }
  }

  Widget _buildContent(StoriesState storiesState) {
    // Filter to only show today's stories
    final now = DateTime.now();
    final todayStart = DateTime(now.year, now.month, now.day);
    final stories = storiesState.stories
        .where((s) => s.createdAt.isAfter(todayStart))
        .toList();

    if (stories.isEmpty) {
      return _buildFullEmptyState();
    }

    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        _buildSectionLabel(
          s.latestStories,
          trailing: s.totalCount(stories.length),
        ),
        const SizedBox(height: 10),
        ...stories.map((story) => _buildStoryCard(story)),
        const SizedBox(height: 100), // space for FAB
      ],
    );
  }

  Widget _buildSectionLabel(String title, {String? trailing}) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          title,
          style: GoogleFonts.plusJakartaSans(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: AppColors.vrSection,
            letterSpacing: 1.0,
          ),
        ),
        if (trailing != null)
          Text(
            trailing,
            style: GoogleFonts.plusJakartaSans(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: AppColors.vrSection,
              letterSpacing: 0.5,
            ),
          ),
      ],
    );
  }

  /// Format date as "Oct 24" style.
  String _shortDate(DateTime dt) {
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    return '${months[dt.month - 1]} ${dt.day}';
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

  Widget _dot() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6),
      child: Container(
        width: 3, height: 3,
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          color: AppColors.vrMuted,
        ),
      ),
    );
  }

  Widget _buildStoryCard(StoryDto story) {
    final s = AppStrings.of(ref);
    final headline = story.headline.isNotEmpty
        ? story.headline
        : s.untitledDraft;
    final category = story.category != null
        ? s.categoryLabel(story.category)
        : null;

    return InkWell(
      onTap: () => context.push('/create?storyId=${story.id}'),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(color: AppColors.vrCardBorder, width: 0.5),
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
                          ? AppColors.vrMuted
                          : AppColors.vrHeading,
                      height: 1.35,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      Text(
                        _shortDate(story.updatedAt),
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
                            color: AppColors.vrMuted,
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
              color: AppColors.vrMuted,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFullEmptyState() {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        SizedBox(
          height: 300,
          child: Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(LucideIcons.newspaper,
                      size: 40, color: AppColors.vrMuted),
                  const SizedBox(height: AppSpacing.md),
                  Text(
                    s.noStoriesToday,
                    style: AppTypography.odiaBodyMedium
                        .copyWith(color: AppColors.vrMuted),
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}
