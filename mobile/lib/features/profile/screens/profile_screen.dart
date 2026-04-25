import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../core/services/api_config.dart';
import '../../../core/services/api_service.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_theme_data.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/theme_extensions.dart';
import '../../../core/theme/theme_provider.dart';
import '../../../core/l10n/app_strings.dart';
import '../../../core/l10n/language_provider.dart';
import '../../../core/providers/auto_polish_provider.dart';
import '../../auth/providers/auth_provider.dart';
import '../../home/providers/stories_provider.dart';
import '../providers/voice_enrollment_provider.dart';

/// App version (e.g. "1.0.4") read from native package metadata.
/// Returns empty string on the rare failure path so the About row
/// just shows "Vrittant" without a misleading hardcoded version.
final _appVersionProvider = FutureProvider<String>((ref) async {
  try {
    final info = await PackageInfo.fromPlatform();
    return info.version;
  } catch (_) {
    return '';
  }
});

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.watch(themeProvider);
    final authState = ref.watch(authProvider);
    final storiesState = ref.watch(storiesProvider);
    final reporter = authState.reporter;
    final t = context.t;
    final s = AppStrings.of(ref);

    return Scaffold(
      backgroundColor: t.scaffoldBg,
      body: CustomScrollView(
        slivers: [
          SliverToBoxAdapter(child: _buildHeader(context, reporter, s)),
          SliverToBoxAdapter(child: _buildStats(context, storiesState, s)),
          SliverToBoxAdapter(child: _buildSettings(context, ref)),
          const SliverToBoxAdapter(child: SizedBox(height: 100)),
        ],
      ),
    );
  }

  Widget _buildOrgLogo(dynamic reporter, {double height = 32}) {
    final ReporterProfile? rp =
        reporter is ReporterProfile ? reporter : null;
    final logoUrl = rp?.org?.logoUrl;
    if (logoUrl != null && logoUrl.isNotEmpty) {
      final fullUrl =
          logoUrl.startsWith('http') ? logoUrl : '${ApiConfig.baseUrl}$logoUrl';
      return Image.network(
        fullUrl,
        height: height,
        fit: BoxFit.contain,
        errorBuilder: (_, __, ___) => Text(
          rp?.org?.name ?? '',
          style: GoogleFonts.plusJakartaSans(
            fontSize: 14,
            fontWeight: FontWeight.w700,
            color: AppColors.vrHeading,
          ),
        ),
      );
    }
    return Text(
      rp?.org?.name ?? rp?.organization ?? '',
      style: GoogleFonts.plusJakartaSans(
        fontSize: 14,
        fontWeight: FontWeight.w700,
        color: AppColors.vrHeading,
      ),
    );
  }

  Widget _buildHeader(BuildContext context, dynamic reporter, AppStrings s) {
    final name = reporter?.name ?? s.reporter;
    final phone = reporter?.phone ?? '';

    return Container(
      color: AppColors.neutral0,
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 24),
          child: Column(
            children: [
              // Avatar circle with coral accent
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: AppColors.vrCoralLight,
                  border: Border.all(color: AppColors.vrCardBorder, width: 2),
                ),
                child: Center(
                  child: Text(
                    name.isNotEmpty ? name[0].toUpperCase() : 'R',
                    style: GoogleFonts.plusJakartaSans(
                      fontSize: 32,
                      fontWeight: FontWeight.w700,
                      color: AppColors.vrCoral,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              Text(
                name,
                style: GoogleFonts.plusJakartaSans(
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                  color: AppColors.vrHeading,
                ),
              ),
              if (phone.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(
                  phone,
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 14,
                    color: AppColors.vrMuted,
                  ),
                ),
              ],
              const SizedBox(height: 14),
              _buildOrgLogo(reporter, height: 28),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStats(BuildContext context, StoriesState storiesState, AppStrings s) {
    final t = context.t;
    final stories = storiesState.stories;
    final total = stories.length;
    final drafts = stories.where((s) => s.status == 'draft').length;
    final published = stories.where((s) => s.status != 'draft').length;

    return Padding(
      padding: const EdgeInsets.all(AppSpacing.xl),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: t.cardBg,
          borderRadius: BorderRadius.circular(AppSpacing.radiusXl),
          border: Border.all(color: AppColors.vrCardBorder),
        ),
        child: Row(
          children: [
            _StatItem(
                value: '$total', label: s.total, color: AppColors.vrCoral),
            _divider(),
            _StatItem(
                value: '$drafts', label: s.drafts, color: AppColors.vrSection),
            _divider(),
            _StatItem(
                value: '$published',
                label: s.published,
                color: AppColors.vrAccentIndigo),
          ],
        ),
      ),
    );
  }

  Widget _divider() {
    return Container(
      width: 1,
      height: 40,
      color: AppColors.vrCardBorder,
    );
  }

  Widget _buildSettings(BuildContext context, WidgetRef ref) {
    final t = context.t;
    final s = AppStrings.of(ref);
    final lang = ref.watch(languageProvider);
    final langSubtitle = lang == AppLanguage.odia
        ? '\u0B13\u0B21\u0B3C\u0B3F\u0B06 (\u0B13\u0B21\u0B3C\u0B3F\u0B06)' // ଓଡ଼ିଆ
        : 'English';
    final enrollmentState = ref.watch(voiceEnrollmentProvider);
    final voiceSubtitle = enrollmentState.isEnrolled ? s.enrolled : s.notEnrolled;
    final autoPolish = ref.watch(autoPolishProvider);
    // Resolve dynamically — falls back to "Vrittant" alone if the
    // platform call hasn't returned yet or fails.
    final appVersion = ref.watch(_appVersionProvider).asData?.value ?? '';
    final aboutSubtitle =
        appVersion.isEmpty ? 'Vrittant' : 'Version $appVersion';
    final items = [
      (LucideIcons.languages, s.language, langSubtitle, 'language'),
      (LucideIcons.mic, s.voiceEnrollment, voiceSubtitle, 'voice_enrollment'),
      (LucideIcons.shield, s.privacyPolicy, s.privacyPolicySubtitle, 'privacy_policy'),
      (LucideIcons.info, s.about, aboutSubtitle, 'about'),
      (LucideIcons.logOut, s.logout, s.signOut, 'logout'),
    ];

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xl),
      child: Column(
        children: [
          // Auto-polish toggle
          Container(
            margin: const EdgeInsets.only(bottom: AppSpacing.md),
            decoration: BoxDecoration(
              color: t.cardBg,
              borderRadius: BorderRadius.circular(AppSpacing.radiusXl),
              border: Border.all(color: AppColors.vrCardBorder),
            ),
            child: SwitchListTile(
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 20,
                vertical: 4,
              ),
              secondary: Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: AppColors.vrCoralLight,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  LucideIcons.sparkles,
                  size: 18,
                  color: AppColors.vrCoral,
                ),
              ),
              title: Text(
                s.autoPolish,
                style: GoogleFonts.plusJakartaSans(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppColors.vrHeading,
                ),
              ),
              subtitle: Text(
                s.autoPolishDesc,
                style: GoogleFonts.plusJakartaSans(
                  fontSize: 12,
                  color: AppColors.vrBody,
                ),
              ),
              value: autoPolish,
              activeTrackColor: AppColors.vrCoral,
              onChanged: (_) => ref.read(autoPolishProvider.notifier).toggle(),
            ),
          ),
          // Settings list
          Container(
            decoration: BoxDecoration(
              color: t.cardBg,
              borderRadius: BorderRadius.circular(AppSpacing.radiusXl),
              border: Border.all(color: AppColors.vrCardBorder),
            ),
            child: Column(
              children: items.asMap().entries.map((entry) {
                final (icon, title, subtitle, action) = entry.value;
                final isLast = entry.key == items.length - 1;
                final isLogout = action == 'logout';

                return Column(
                  children: [
                    ListTile(
                      onTap: () =>
                          _handleSettingsTap(context, ref, action),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 20,
                        vertical: 4,
                      ),
                      leading: Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          color: isLogout
                              ? AppColors.error.withValues(alpha: 0.1)
                              : AppColors.vrCoralLight,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(
                          icon,
                          size: 18,
                          color: isLogout ? AppColors.error : AppColors.vrCoral,
                        ),
                      ),
                      title: Text(
                        title,
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: isLogout
                              ? AppColors.error
                              : AppColors.vrHeading,
                        ),
                      ),
                      subtitle: Text(
                        subtitle,
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 12,
                          color: AppColors.vrBody,
                        ),
                      ),
                      trailing: Icon(
                        LucideIcons.chevronRight,
                        size: 16,
                        color: AppColors.vrMuted,
                      ),
                    ),
                    if (!isLast)
                      Divider(
                        height: 1,
                        indent: 72,
                        color: AppColors.vrCardBorder,
                      ),
                  ],
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  void _handleSettingsTap(
      BuildContext context, WidgetRef ref, String action) {
    switch (action) {
      case 'theme':
        _showThemePicker(context, ref);
        break;
      case 'logout':
        _showLogoutConfirmation(context, ref);
        break;
      case 'about':
        _showAboutDialog(
          context,
          s: AppStrings.of(ref),
          version: ref.read(_appVersionProvider).asData?.value ?? '',
        );
        break;
      case 'language':
        _showLanguagePicker(context, ref);
        break;
      case 'voice_enrollment':
        context.push('/voice-enrollment');
        break;
      case 'privacy_policy':
        _openPrivacyPolicy(context, ref);
        break;
      case 'notifications':
      case 'help':
        final s = AppStrings.of(ref);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(s.comingSoon),
            backgroundColor: AppColors.vrCoral,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        );
        break;
    }
  }

  void _showLogoutConfirmation(BuildContext context, WidgetRef ref) {
    final s = AppStrings.of(ref);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(
          s.logout,
          style: GoogleFonts.plusJakartaSans(
            fontWeight: FontWeight.w700,
            color: AppColors.vrHeading,
          ),
        ),
        content: Text(
          s.logoutConfirm,
          style: GoogleFonts.plusJakartaSans(
            color: AppColors.vrBody,
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(
              s.cancel,
              style: GoogleFonts.plusJakartaSans(
                fontWeight: FontWeight.w600,
                color: AppColors.vrSection,
              ),
            ),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              ref.read(authProvider.notifier).logout();
              context.go('/login');
            },
            child: Text(
              s.logout,
              style: GoogleFonts.plusJakartaSans(
                fontWeight: FontWeight.w600,
                color: AppColors.error,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _openPrivacyPolicy(BuildContext context, WidgetRef ref) async {
    final s = AppStrings.of(ref);
    final uri = Uri.parse('https://vrittant.in/privacy');
    final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!ok && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(s.couldNotOpenLink),
          backgroundColor: AppColors.error,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      );
    }
  }

  void _showAboutDialog(
    BuildContext context, {
    required AppStrings s,
    required String version,
  }) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(
          'Vrittant',
          style: GoogleFonts.plusJakartaSans(
            fontWeight: FontWeight.w700,
            color: AppColors.vrHeading,
          ),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (version.isNotEmpty)
              Text(
                'Version $version',
                style: GoogleFonts.plusJakartaSans(
                  fontSize: 14,
                  color: AppColors.vrBody,
                ),
              ),
            if (version.isNotEmpty) const SizedBox(height: 8),
            Text(
              s.isOdia
                  ? '\u0B2C\u0B43\u0B24\u0B4D\u0B24\u0B3E\u0B28\u0B4D\u0B24 \u0B39\u0B47\u0B09\u0B1B\u0B3F \u0B0F\u0B15 \u0B38\u0B4D\u0B2E\u0B3E\u0B30\u0B4D\u0B1F \u0B28\u0B4D\u0B5F\u0B41\u0B1C\u0B4D \u0B30\u0B3F\u0B2A\u0B4B\u0B30\u0B4D\u0B1F\u0B3F\u0B02 \u0B1F\u0B41\u0B32\u0B4D \u0B2F\u0B3E\u0B39\u0B3E \u0B38\u0B3E\u0B2E\u0B4D\u0B2C\u0B3E\u0B26\u0B3F\u0B15\u0B2E\u0B3E\u0B28\u0B19\u0B4D\u0B15\u0B41 \u0B16\u0B2C\u0B30 \u0B38\u0B02\u0B17\u0B4D\u0B30\u0B39, \u0B38\u0B2E\u0B4D\u0B2A\u0B3E\u0B26\u0B28\u0B3E \u0B0F\u0B2C\u0B02 \u0B2A\u0B4D\u0B30\u0B15\u0B3E\u0B36\u0B28\u0B3E\u0B30\u0B47 \u0B38\u0B3E\u0B39\u0B3E\u0B2F\u0B4D\u0B5F \u0B15\u0B30\u0B47\u0964'  // ବୃତ୍ତାନ୍ତ ହେଉଛି ଏକ ସ୍ମାର୍ଟ ନ୍ୟୁଜ୍ ରିପୋର୍ଟିଂ ଟୁଲ୍ ଯାହା ସାମ୍ବାଦିକମାନଙ୍କୁ ଖବର ସଂଗ୍ରହ, ସମ୍ପାଦନା ଏବଂ ପ୍ରକାଶନାରେ ସାହାଯ୍ୟ କରେ।
                  : 'Vrittant is a smart news reporting tool that helps journalists with news gathering, editing, and publishing.',
              style: GoogleFonts.plusJakartaSans(
                fontSize: 14,
                color: AppColors.vrBody,
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(
              s.ok,
              style: GoogleFonts.plusJakartaSans(
                fontWeight: FontWeight.w600,
                color: AppColors.vrCoral,
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showLanguagePicker(BuildContext context, WidgetRef ref) {
    final current = ref.read(languageProvider);
    showModalBottomSheet(
      context: context,
      backgroundColor: context.t.cardBg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppColors.vrCardBorder,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  AppStrings.of(ref).language,
                  style: AppTypography.odiaTitleLarge
                      .copyWith(color: AppColors.vrHeading),
                ),
                const SizedBox(height: 16),
                _LanguageOption(
                  label: 'English',
                  isActive: current == AppLanguage.english,
                  onTap: () {
                    ref
                        .read(languageProvider.notifier)
                        .setLanguage(AppLanguage.english);
                    Navigator.pop(ctx);
                  },
                ),
                const SizedBox(height: 10),
                _LanguageOption(
                  label: '\u0B13\u0B21\u0B3C\u0B3F\u0B06 (Odia)',
                  isActive: current == AppLanguage.odia,
                  onTap: () {
                    ref
                        .read(languageProvider.notifier)
                        .setLanguage(AppLanguage.odia);
                    Navigator.pop(ctx);
                  },
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  void _showThemePicker(BuildContext context, WidgetRef ref) {
    final s = AppStrings.of(ref);
    final current = ref.read(themeProvider);
    showModalBottomSheet(
      context: context,
      backgroundColor: current.cardBg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppColors.vrCardBorder,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  s.selectTheme,
                  style: AppTypography.odiaTitleLarge
                      .copyWith(color: AppColors.vrHeading),
                ),
                const SizedBox(height: 16),
                Row(
                  children: appThemePresets.values.map((theme) {
                    final isActive = theme.key == current.key;
                    return Expanded(
                      child: GestureDetector(
                        onTap: () {
                          ref
                              .read(themeProvider.notifier)
                              .setTheme(theme.key);
                          Navigator.pop(ctx);
                        },
                        child: Container(
                          margin:
                              const EdgeInsets.symmetric(horizontal: 4),
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: theme.scaffoldBg,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: isActive
                                  ? theme.primary
                                  : theme.dividerColor,
                              width: isActive ? 2 : 1,
                            ),
                          ),
                          child: Column(
                            children: [
                              Container(
                                height: 48,
                                decoration: BoxDecoration(
                                  color: theme.cardBg,
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Row(
                                  children: [
                                    Container(
                                      width: 4,
                                      decoration: BoxDecoration(
                                        color: theme.primary,
                                        borderRadius:
                                            const BorderRadius.horizontal(
                                          left: Radius.circular(8),
                                        ),
                                      ),
                                    ),
                                    const Spacer(),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 8),
                              Text(
                                theme.odiaLabel,
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: isActive
                                      ? FontWeight.w700
                                      : FontWeight.w400,
                                  color: theme.headingColor,
                                ),
                              ),
                              if (isActive) ...[
                                const SizedBox(height: 4),
                                Icon(Icons.check_circle,
                                    size: 16, color: theme.primary),
                              ],
                            ],
                          ),
                        ),
                      ),
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _LanguageOption extends StatelessWidget {
  final String label;
  final bool isActive;
  final VoidCallback onTap;

  const _LanguageOption({
    required this.label,
    required this.isActive,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        decoration: BoxDecoration(
          color: isActive
              ? AppColors.vrCoral.withValues(alpha: 0.08)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: isActive ? AppColors.vrCoral : AppColors.vrCardBorder,
            width: isActive ? 2 : 1,
          ),
        ),
        child: Row(
          children: [
            Text(
              label,
              style: GoogleFonts.plusJakartaSans(
                fontSize: 16,
                fontWeight: isActive ? FontWeight.w700 : FontWeight.w500,
                color: isActive ? AppColors.vrCoral : AppColors.vrHeading,
              ),
            ),
            const Spacer(),
            if (isActive)
              Icon(Icons.check_circle, size: 20, color: AppColors.vrCoral),
          ],
        ),
      ),
    );
  }
}

class _StatItem extends StatelessWidget {
  final String value;
  final String label;
  final Color color;

  const _StatItem({
    required this.value,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Text(
            value,
            style: GoogleFonts.plusJakartaSans(
              fontSize: 28,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: GoogleFonts.plusJakartaSans(
              fontSize: 12,
              color: AppColors.vrBody,
            ),
          ),
        ],
      ),
    );
  }
}
