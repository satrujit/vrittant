import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';

import '../../../core/l10n/app_strings.dart';
import '../../../core/services/mic_permission_ui.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/theme_extensions.dart';
import '../../../core/theme/theme_provider.dart';
import '../../../core/widgets/voice_button.dart';
import '../providers/voice_enrollment_provider.dart';

class VoiceEnrollmentScreen extends ConsumerStatefulWidget {
  const VoiceEnrollmentScreen({super.key});

  @override
  ConsumerState<VoiceEnrollmentScreen> createState() =>
      _VoiceEnrollmentScreenState();
}

class _VoiceEnrollmentScreenState
    extends ConsumerState<VoiceEnrollmentScreen>
    with TickerProviderStateMixin, WidgetsBindingObserver {
  Timer? _recordingTimer;
  int _recordingSeconds = 0;
  bool _isTesting = false;

  // Audio level bar animation
  Timer? _audioLevelTimer;
  final _barHeights = List<double>.filled(5, 0.15);
  final _random = Random();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _recordingTimer?.cancel();
    _audioLevelTimer?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) return;
    final enrollment = ref.read(voiceEnrollmentProvider);
    if (enrollment.isRecording) {
      ref.read(voiceEnrollmentProvider.notifier).stopRecording();
      _stopTimer();
    }
  }

  void _startTimer() {
    _recordingSeconds = 0;
    _recordingTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      setState(() => _recordingSeconds++);
    });
    // Start audio level animation
    _audioLevelTimer =
        Timer.periodic(const Duration(milliseconds: 120), (_) {
      setState(() {
        for (var i = 0; i < _barHeights.length; i++) {
          _barHeights[i] = 0.15 + _random.nextDouble() * 0.85;
        }
      });
    });
  }

  void _stopTimer() {
    _recordingTimer?.cancel();
    _recordingTimer = null;
    _audioLevelTimer?.cancel();
    _audioLevelTimer = null;
    setState(() {
      for (var i = 0; i < _barHeights.length; i++) {
        _barHeights[i] = 0.15;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    ref.watch(themeProvider);
    final t = context.t;
    final s = AppStrings.of(ref);
    final enrollment = ref.watch(voiceEnrollmentProvider);

    return Scaffold(
      backgroundColor: t.scaffoldBg,
      appBar: AppBar(
        backgroundColor: t.scaffoldBg,
        surfaceTintColor: Colors.transparent,
        leading: IconButton(
          icon: const Icon(LucideIcons.arrowLeft),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: Text(
          s.voiceEnrollment,
          style: GoogleFonts.plusJakartaSans(
            fontSize: 18,
            fontWeight: FontWeight.w700,
            color: AppColors.vrHeading,
          ),
        ),
        centerTitle: true,
      ),
      body: enrollment.isLoading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.vrCoral))
          : SingleChildScrollView(
              padding: const EdgeInsets.all(AppSpacing.xl),
              child: Column(
                children: [
                  if (!enrollment.isEnrolled)
                    _buildEnrollmentFlow(s, enrollment),
                  if (enrollment.isEnrolled) _buildEnrolledView(s, enrollment),
                  if (enrollment.error != null) ...[
                    const SizedBox(height: 16),
                    _buildErrorCard(enrollment.error!),
                  ],
                ],
              ),
            ),
    );
  }

  // ---------------------------------------------------------------------------
  // Enrollment flow
  // ---------------------------------------------------------------------------

  Widget _buildEnrollmentFlow(AppStrings s, VoiceEnrollmentState enrollment) {
    final isRecording = enrollment.isRecording && !_isTesting;

    return Column(
      children: [
        // Header
        Container(
          width: 80,
          height: 80,
          decoration: BoxDecoration(
            color: AppColors.vrCoralLight,
            borderRadius: BorderRadius.circular(24),
          ),
          child:
              const Icon(LucideIcons.mic, size: 36, color: AppColors.vrCoral),
        ),
        const SizedBox(height: 20),
        Text(
          s.enrollYourVoice,
          style: GoogleFonts.plusJakartaSans(
            fontSize: 22,
            fontWeight: FontWeight.w700,
            color: AppColors.vrHeading,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          s.enrollDescription,
          textAlign: TextAlign.center,
          style: GoogleFonts.plusJakartaSans(
            fontSize: 14,
            color: AppColors.vrSection,
            height: 1.5,
          ),
        ),
        const SizedBox(height: 32),

        // Connected step indicator
        _ConnectedStepIndicator(
          current: enrollment.sampleCount,
          total: enrollment.targetSamples,
          labels: List.generate(
              enrollment.targetSamples, (i) => '${s.sample} ${i + 1}'),
        ),
        const SizedBox(height: 40),

        // Voice button (animated circular)
        VoiceButton(
          isRecording: isRecording,
          onTap: () async {
            if (isRecording) {
              _stopTimer();
              await ref
                  .read(voiceEnrollmentProvider.notifier)
                  .stopRecording();
            } else {
              // Permission gate: show rationale or Settings prompt before
              // touching the recorder. Without this, a denied user just sees
              // the mic button do nothing.
              final ok = await ensureMicPermission(context, ref);
              if (!ok) return;
              _isTesting = false;
              _startTimer();
              await ref
                  .read(voiceEnrollmentProvider.notifier)
                  .startRecording();
            }
          },
          size: 80,
        ),

        // Audio level bars (visible during recording)
        AnimatedSize(
          duration: const Duration(milliseconds: 200),
          child: isRecording
              ? Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: _AudioLevelBars(heights: _barHeights),
                )
              : const SizedBox.shrink(),
        ),

        const SizedBox(height: 12),

        // Timer / status text
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 200),
          child: isRecording
              ? Text(
                  _formatTime(_recordingSeconds),
                  key: ValueKey('timer-$_recordingSeconds'),
                  style: GoogleFonts.jetBrainsMono(
                    fontSize: 28,
                    fontWeight: FontWeight.w600,
                    color: AppColors.vrCoral,
                  ),
                )
              : Text(
                  '${s.recordSample} ${enrollment.sampleCount + 1}/${enrollment.targetSamples}',
                  key: const ValueKey('label'),
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: AppColors.vrHeading,
                  ),
                ),
        ),

        const SizedBox(height: 8),
        Text(
          isRecording
              ? 'Tap to stop'
              : s.recordInstruction,
          textAlign: TextAlign.center,
          style: GoogleFonts.plusJakartaSans(
            fontSize: 12,
            color: AppColors.vrMuted,
          ),
        ),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Enrolled view
  // ---------------------------------------------------------------------------

  Widget _buildEnrolledView(AppStrings s, VoiceEnrollmentState enrollment) {
    final t = context.t;
    final isTestRecording = enrollment.isRecording && _isTesting;

    return Column(
      children: [
        // Success card
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0.8, end: 1.0),
          duration: const Duration(milliseconds: 500),
          curve: Curves.elasticOut,
          builder: (context, scale, child) =>
              Transform.scale(scale: scale, child: child),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 32, horizontal: 24),
            decoration: BoxDecoration(
              color: const Color(0xFFECFDF5),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: const Color(0xFFA7F3D0)),
            ),
            child: Column(
              children: [
                Container(
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    color: const Color(0xFF10B981).withValues(alpha: 0.15),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    LucideIcons.shieldCheck,
                    size: 36,
                    color: Color(0xFF10B981),
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  s.voiceEnrolled,
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 20,
                    fontWeight: FontWeight.w700,
                    color: const Color(0xFF065F46),
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  '${enrollment.sampleCount} ${s.samplesRecorded}',
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 13,
                    color: const Color(0xFF047857),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),

        // Test section
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: t.cardBg,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.vrCardBorder),
          ),
          child: Column(
            children: [
              Text(
                s.testYourVoice,
                style: GoogleFonts.plusJakartaSans(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: AppColors.vrHeading,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                s.testDescription,
                textAlign: TextAlign.center,
                style: GoogleFonts.plusJakartaSans(
                  fontSize: 13,
                  color: AppColors.vrSection,
                ),
              ),
              const SizedBox(height: 20),

              // Test voice button
              VoiceButton(
                isRecording: isTestRecording,
                onTap: () {
                  if (isTestRecording) {
                    _stopTimer();
                    ref
                        .read(voiceEnrollmentProvider.notifier)
                        .stopTestRecording();
                  } else {
                    _isTesting = true;
                    _startTimer();
                    ref
                        .read(voiceEnrollmentProvider.notifier)
                        .startTestRecording();
                  }
                },
                size: 56,
              ),

              // Audio bars during test
              AnimatedSize(
                duration: const Duration(milliseconds: 200),
                child: isTestRecording
                    ? Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: _AudioLevelBars(heights: _barHeights),
                      )
                    : const SizedBox.shrink(),
              ),

              if (isTestRecording) ...[
                const SizedBox(height: 8),
                Text(
                  _formatTime(_recordingSeconds),
                  style: GoogleFonts.jetBrainsMono(
                    fontSize: 22,
                    fontWeight: FontWeight.w600,
                    color: AppColors.vrCoral,
                  ),
                ),
              ],

              // Test result
              if (enrollment.testResult != null) ...[
                const SizedBox(height: 20),
                _ScoreIndicator(result: enrollment.testResult!, strings: s),
              ],
            ],
          ),
        ),
        const SizedBox(height: 16),

        // Re-enroll (text button)
        TextButton.icon(
          onPressed: () {
            ref.read(voiceEnrollmentProvider.notifier).deleteEnrollment();
          },
          icon: const Icon(LucideIcons.refreshCw, size: 14),
          label: Text(s.reEnroll),
          style: TextButton.styleFrom(
            foregroundColor: AppColors.vrMuted,
            textStyle: GoogleFonts.plusJakartaSans(
              fontSize: 14,
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Error card
  // ---------------------------------------------------------------------------

  Widget _buildErrorCard(String error) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFEF2F2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFFECACA)),
      ),
      child: Row(
        children: [
          const Icon(LucideIcons.alertCircle,
              size: 18, color: Color(0xFFEF4444)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              error,
              style: GoogleFonts.plusJakartaSans(
                fontSize: 13,
                color: const Color(0xFF991B1B),
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _formatTime(int seconds) {
    final m = seconds ~/ 60;
    final s = seconds % 60;
    return '${m.toString().padLeft(1, '0')}:${s.toString().padLeft(2, '0')}';
  }
}

// =============================================================================
// Connected step indicator
// =============================================================================

class _ConnectedStepIndicator extends StatelessWidget {
  final int current;
  final int total;
  final List<String> labels;

  const _ConnectedStepIndicator({
    required this.current,
    required this.total,
    required this.labels,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: List.generate(total * 2 - 1, (i) {
        // Even indices = circles, odd = connecting lines
        if (i.isOdd) {
          final stepBefore = i ~/ 2;
          final done = stepBefore < current;
          return Expanded(
            child: Container(
              height: 3,
              decoration: BoxDecoration(
                color: done ? const Color(0xFF10B981) : AppColors.vrCardBorder,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          );
        }

        final step = i ~/ 2;
        final done = step < current;
        final active = step == current;

        return Column(
          children: [
            TweenAnimationBuilder<double>(
              tween: Tween(begin: 1.0, end: active ? 1.1 : 1.0),
              duration: const Duration(milliseconds: 300),
              builder: (context, scale, child) =>
                  Transform.scale(scale: scale, child: child),
              child: Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: done
                      ? const Color(0xFF10B981)
                      : active
                          ? AppColors.vrCoral
                          : Colors.transparent,
                  border: Border.all(
                    color: done
                        ? const Color(0xFF10B981)
                        : active
                            ? AppColors.vrCoral
                            : AppColors.vrCardBorder,
                    width: 2,
                  ),
                ),
                child: Center(
                  child: done
                      ? const Icon(LucideIcons.check,
                          size: 18, color: Colors.white)
                      : Text(
                          '${step + 1}',
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 16,
                            fontWeight: FontWeight.w700,
                            color: active ? Colors.white : AppColors.vrMuted,
                          ),
                        ),
                ),
              ),
            ),
            const SizedBox(height: 6),
            Text(
              labels[step],
              style: GoogleFonts.plusJakartaSans(
                fontSize: 11,
                fontWeight: active ? FontWeight.w600 : FontWeight.w400,
                color: done
                    ? const Color(0xFF10B981)
                    : active
                        ? AppColors.vrCoral
                        : AppColors.vrMuted,
              ),
            ),
          ],
        );
      }),
    );
  }
}

// =============================================================================
// Audio level bars
// =============================================================================

class _AudioLevelBars extends StatelessWidget {
  final List<double> heights;

  const _AudioLevelBars({required this.heights});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 32,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: List.generate(heights.length, (i) {
          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 3),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 100),
              width: 4,
              height: 32 * heights[i],
              decoration: BoxDecoration(
                color: AppColors.vrCoral.withValues(alpha: 0.6 + 0.4 * heights[i]),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          );
        }),
      ),
    );
  }
}

// =============================================================================
// Circular score indicator
// =============================================================================

class _ScoreIndicator extends StatelessWidget {
  final ({bool passed, double score}) result;
  final AppStrings strings;

  const _ScoreIndicator({required this.result, required this.strings});

  @override
  Widget build(BuildContext context) {
    final pct = (result.score * 100).toStringAsFixed(0);
    final color =
        result.passed ? const Color(0xFF10B981) : const Color(0xFFEF4444);
    final bgColor = result.passed
        ? const Color(0xFFECFDF5)
        : const Color(0xFFFEF2F2);
    final textColor = result.passed
        ? const Color(0xFF065F46)
        : const Color(0xFF991B1B);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          // Circular progress
          SizedBox(
            width: 56,
            height: 56,
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: result.score),
              duration: const Duration(milliseconds: 800),
              curve: Curves.easeOutCubic,
              builder: (context, value, _) {
                return Stack(
                  alignment: Alignment.center,
                  children: [
                    SizedBox(
                      width: 56,
                      height: 56,
                      child: CircularProgressIndicator(
                        value: value,
                        strokeWidth: 5,
                        strokeCap: StrokeCap.round,
                        backgroundColor: color.withValues(alpha: 0.15),
                        valueColor: AlwaysStoppedAnimation(color),
                      ),
                    ),
                    Text(
                      '$pct%',
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: color,
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      result.passed
                          ? LucideIcons.shieldCheck
                          : LucideIcons.shieldOff,
                      size: 18,
                      color: color,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      result.passed
                          ? strings.voiceVerified
                          : strings.voiceNotRecognized,
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: textColor,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  '${strings.matchScore}: $pct%',
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 12,
                    color: textColor.withValues(alpha: 0.7),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
