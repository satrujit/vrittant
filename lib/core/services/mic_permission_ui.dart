// Glue between MicPermissionService and the UI.
//
// `ensureMicPermission(context, ref)` is the one entry point callers should
// use. It does the right thing for every state:
//
//   granted              → returns true immediately, no UI
//   denied               → shows rationale dialog, then re-requests; returns
//                          true if user approved on the OS prompt
//   permanentlyDenied    → shows "Open Settings" dialog (only recovery path);
//                          returns false
//   restricted           → shows restricted dialog; returns false
//
// Returning a bool keeps caller code simple — no need to branch on enums in
// every record-button handler.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../l10n/app_strings.dart';
import '../theme/app_colors.dart';
import 'mic_permission_service.dart';

/// Returns true if recording can now proceed, false otherwise.
///
/// All UI is shown via the supplied [context]. Caller must check
/// `context.mounted` before doing anything visual after this returns — the
/// dialogs are async.
Future<bool> ensureMicPermission(BuildContext context, WidgetRef ref) async {
  final s = AppStrings.of(ref);

  // First: cheap status check, no prompt.
  final current = await micPermissionService.check();
  if (current == MicPermissionResult.granted) return true;

  if (current == MicPermissionResult.permanentlyDenied) {
    if (!context.mounted) return false;
    await _showBlockedDialog(context, s);
    return false;
  }

  if (current == MicPermissionResult.restricted) {
    if (!context.mounted) return false;
    await _showRestrictedDialog(context, s);
    return false;
  }

  // Status is `denied` and the OS will still let us prompt. Show our own
  // rationale first so the user understands what they're consenting to —
  // then trigger the system prompt only if they tap Allow.
  if (!context.mounted) return false;
  final wantsToProceed = await _showRationaleDialog(context, s);
  if (!wantsToProceed) return false;

  final after = await micPermissionService.request();
  if (after == MicPermissionResult.granted) return true;

  // They saw our explanation, then declined the OS prompt. If that flipped
  // them into permanent denial (Android: 2nd refusal = "Don't ask again"
  // implicit on some OEMs), surface the Settings path now.
  if (after == MicPermissionResult.permanentlyDenied) {
    if (!context.mounted) return false;
    await _showBlockedDialog(context, s);
  }
  return false;
}

Future<bool> _showRationaleDialog(BuildContext context, AppStrings s) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      title: Text(
        s.micPermissionTitle,
        style: GoogleFonts.plusJakartaSans(
          fontWeight: FontWeight.w700,
          color: AppColors.vrHeading,
        ),
      ),
      content: Text(
        s.micPermissionRationale,
        style: GoogleFonts.plusJakartaSans(color: AppColors.vrBody),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx, false),
          child: Text(
            s.notNow,
            style: GoogleFonts.plusJakartaSans(
              fontWeight: FontWeight.w600,
              color: AppColors.vrSection,
            ),
          ),
        ),
        TextButton(
          onPressed: () => Navigator.pop(ctx, true),
          child: Text(
            s.micPermissionAllow,
            style: GoogleFonts.plusJakartaSans(
              fontWeight: FontWeight.w600,
              color: AppColors.vrCoral,
            ),
          ),
        ),
      ],
    ),
  );
  return result ?? false;
}

Future<void> _showBlockedDialog(BuildContext context, AppStrings s) async {
  await showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      title: Text(
        s.micPermissionBlockedTitle,
        style: GoogleFonts.plusJakartaSans(
          fontWeight: FontWeight.w700,
          color: AppColors.vrHeading,
        ),
      ),
      content: Text(
        s.micPermissionBlockedBody,
        style: GoogleFonts.plusJakartaSans(color: AppColors.vrBody),
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
          onPressed: () async {
            Navigator.pop(ctx);
            await micPermissionService.openSystemSettings();
          },
          child: Text(
            s.openSettings,
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

Future<void> _showRestrictedDialog(BuildContext context, AppStrings s) async {
  await showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      title: Text(
        s.micPermissionBlockedTitle,
        style: GoogleFonts.plusJakartaSans(
          fontWeight: FontWeight.w700,
          color: AppColors.vrHeading,
        ),
      ),
      content: Text(
        s.micPermissionRestricted,
        style: GoogleFonts.plusJakartaSans(color: AppColors.vrBody),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx),
          child: Text(
            'OK',
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
