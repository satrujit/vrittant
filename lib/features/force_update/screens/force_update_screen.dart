// Non-dismissable "Update required" screen.
//
// Shown when the version-check service reports the current install is below
// the server-configured minimum. The router redirects here BEFORE auth, so an
// unauthenticated user with an old client still sees the prompt instead of
// an opaquely-broken login flow.
//
// PopScope blocks back-button (Android) and the swipe-back gesture (iOS).
// There is no "Skip" or "Later" button — the entire point of force-update is
// that the user genuinely cannot continue.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/l10n/app_strings.dart';
import '../../../core/services/version_check_service.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';

class ForceUpdateScreen extends ConsumerWidget {
  const ForceUpdateScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = AppStrings.of(ref);

    // The version check has already run by the time we land here — read its
    // cached value to extract the store URL. If for some reason the check
    // hasn't completed yet (shouldn't happen via the router path, but
    // belt-and-suspenders), fall back to no URL → button hidden.
    final outcomeAsync = ref.watch(versionCheckProvider);
    final storeUrl = outcomeAsync.maybeWhen(
      data: (o) => o.storeUrl,
      orElse: () => '',
    );

    return PopScope(
      canPop: false,
      child: Scaffold(
        backgroundColor: Colors.white,
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.xxl),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  width: 96,
                  height: 96,
                  decoration: BoxDecoration(
                    color: AppColors.vrCoralLight,
                    borderRadius: BorderRadius.circular(28),
                  ),
                  child: Icon(
                    LucideIcons.downloadCloud,
                    size: 48,
                    color: AppColors.vrCoral,
                  ),
                ),
                const SizedBox(height: AppSpacing.xl),
                Text(
                  s.forceUpdateTitle,
                  textAlign: TextAlign.center,
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                    color: AppColors.vrHeading,
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
                Text(
                  s.forceUpdateBody,
                  textAlign: TextAlign.center,
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 15,
                    color: AppColors.vrBody,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: AppSpacing.xxl),
                if (storeUrl.isNotEmpty)
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: () => _openStore(context, ref, storeUrl),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.vrCoral,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                      child: Text(
                        s.forceUpdateButton,
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _openStore(
    BuildContext context,
    WidgetRef ref,
    String url,
  ) async {
    final s = AppStrings.of(ref);
    final ok = await launchUrl(
      Uri.parse(url),
      mode: LaunchMode.externalApplication,
    );
    if (!ok && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(s.couldNotOpenLink),
          backgroundColor: AppColors.error,
          behavior: SnackBarBehavior.floating,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      );
    }
  }
}
