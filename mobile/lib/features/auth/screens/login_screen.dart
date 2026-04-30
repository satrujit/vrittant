import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';

import '../../../core/l10n/app_strings.dart';
import '../../../core/theme/app_colors.dart';
import '../providers/auth_provider.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _phoneController = TextEditingController();
  final _otpController = TextEditingController();

  /// Resend cooldown (seconds remaining).
  int _resendCooldown = 0;
  Timer? _resendTimer;

  void _startResendTimer() {
    _resendTimer?.cancel();
    setState(() => _resendCooldown = 60);
    _resendTimer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (_resendCooldown <= 1) {
        t.cancel();
        if (mounted) setState(() => _resendCooldown = 0);
      } else {
        if (mounted) setState(() => _resendCooldown--);
      }
    });
  }

  @override
  void dispose() {
    _resendTimer?.cancel();
    _phoneController.dispose();
    _otpController.dispose();
    super.dispose();
  }

  /// Format phone for display: "98765 43210"
  String get _formattedPhone {
    final raw = _phoneController.text.trim();
    if (raw.length >= 10) {
      return '${raw.substring(0, 5)} ${raw.substring(5, 10)}';
    }
    return raw;
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    final s = AppStrings.of(ref);

    return Scaffold(
      backgroundColor: AppColors.vrWarmBg,
      body: Stack(
        children: [
          // ── Watermark "V" background ───────────────────────────
          Positioned.fill(
            child: Center(
              child: Text(
                'V',
                style: GoogleFonts.plusJakartaSans(
                  fontSize: MediaQuery.of(context).size.height * 0.75,
                  fontWeight: FontWeight.w800,
                  fontStyle: FontStyle.italic,
                  color: AppColors.vrCoral.withValues(alpha: 0.03),
                ),
              ),
            ),
          ),

          // ── Main content ───────────────────────────────────────
          SafeArea(
            child: auth.otpSent
                ? _buildOtpScreen(auth, s)
                : _buildPhoneScreen(auth, s),
          ),

          // Language toggle removed — hardcoded to English
        ],
      ),
    );
  }

  // ╔══════════════════════════════════════════════════════════════╗
  // ║  PHONE INPUT SCREEN                                        ║
  // ╚══════════════════════════════════════════════════════════════╝
  Widget _buildPhoneScreen(AuthState auth, AppStrings s) {
    final notifier = ref.read(authProvider.notifier);

    return Column(
      children: [
        Expanded(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const SizedBox(height: 20),

                  // ── V Logo (concentric arcs) ────
                  SizedBox(
                    width: 240,
                    height: 160,
                    child: SvgPicture.asset(
                      'assets/images/v_logo.svg',
                      fit: BoxFit.contain,
                    ),
                  ),

                  // ── "Vrittant" title ─
                  RichText(
                    text: TextSpan(
                      children: [
                        TextSpan(
                          text: 'V',
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 52,
                            fontWeight: FontWeight.w800,
                            fontStyle: FontStyle.italic,
                            color: AppColors.vrCoral,
                            letterSpacing: -4.0,
                            height: 1,
                          ),
                        ),
                        TextSpan(
                          text: 'rittant',
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 52,
                            fontWeight: FontWeight.w800,
                            color: AppColors.vrHeading,
                            letterSpacing: -3.5,
                            height: 1,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 48),

                  // ── Phone input ─────────
                  _buildPhoneField(s),
                  const SizedBox(height: 16),

                  // ── Error text ────────────────────────────
                  if (auth.error != null) ...[
                    Padding(
                      padding: const EdgeInsets.only(bottom: 16),
                      child: Text(
                        auth.error!,
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 13,
                          color: AppColors.error,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ],

                  const SizedBox(height: 28),

                  // ── Send OTP button ──────────
                  _buildRoundedButton(
                    label: s.sendOtp,
                    isLoading: auth.isLoading,
                    onTap: () => _requestOtp(notifier),
                  ),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(height: 40),
      ],
    );
  }

  // ╔══════════════════════════════════════════════════════════════╗
  // ║  OTP VERIFICATION SCREEN                                   ║
  // ╚══════════════════════════════════════════════════════════════╝
  Widget _buildOtpScreen(AuthState auth, AppStrings s) {
    final notifier = ref.read(authProvider.notifier);

    return Column(
      children: [
        // ── Main scrollable content ────────────────────────
        Expanded(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 32),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const SizedBox(height: 20),

                  // ── Curved logo ─
                  Center(
                    child: SizedBox(
                      width: 240,
                      height: 160,
                      child: SvgPicture.asset(
                        'assets/images/v_logo.svg',
                        fit: BoxFit.contain,
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),

                  // ── "Verify Phone" title ─────────────────────
                  Text(
                    s.verifyPhone,
                    style: GoogleFonts.plusJakartaSans(
                      fontSize: 36,
                      fontWeight: FontWeight.w800,
                      color: AppColors.vrHeading,
                      letterSpacing: -1.0,
                      height: 1.2,
                    ),
                  ),
                  const SizedBox(height: 12),

                  // ── Subtitle with phone number ───────────────
                  RichText(
                    text: TextSpan(
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 16,
                        fontWeight: FontWeight.w400,
                        color: AppColors.vrSection,
                        height: 1.5,
                      ),
                      children: [
                        TextSpan(text: s.enterCodeSent),
                        TextSpan(
                          text: '+91 $_formattedPhone',
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 16,
                            fontWeight: FontWeight.w700,
                            color: AppColors.vrHeading,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),

                  // ── Edit number link ─────────────────────────
                  GestureDetector(
                    onTap: () {
                      ref.read(authProvider.notifier).resetOtpState();
                      _otpController.clear();
                    },
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(LucideIcons.pencil,
                            size: 14, color: AppColors.vrCoral),
                        const SizedBox(width: 6),
                        Text(
                          s.editNumber,
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: AppColors.vrCoral,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 40),

                  // ── Simple OTP input field ─────────────────
                  _buildOtpField(s),
                  const SizedBox(height: 28),

                  // ── Resend Code link with cooldown ────────────
                  Center(
                    child: _resendCooldown > 0
                        ? Text(
                            '${s.resendCode} ${_resendCooldown}s',
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: AppColors.vrSlate400,
                            ),
                          )
                        : GestureDetector(
                            onTap: () {
                              final phone = _phoneController.text.trim();
                              if (phone.isNotEmpty) {
                                notifier.resendOtp('+91$phone');
                                _startResendTimer();
                              }
                            },
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(
                                  s.resendCode,
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w700,
                                    color: AppColors.vrCoral,
                                  ),
                                ),
                                const SizedBox(width: 6),
                                Icon(LucideIcons.refreshCw,
                                    size: 16, color: AppColors.vrCoral),
                              ],
                            ),
                          ),
                  ),

                  // ── Error text ───────────────────────────────
                  if (auth.error != null) ...[
                    const SizedBox(height: 16),
                    Center(
                      child: Text(
                        auth.error!,
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 13,
                          color: AppColors.error,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ],

                  const SizedBox(height: 40),

                  // ── Verify & Continue button ─────────────────
                  _buildRoundedButton(
                    label: s.verifyAndContinue,
                    showArrow: true,
                    isLoading: auth.isLoading,
                    onTap: () => _verifyOtp(notifier),
                  ),
                ],
              ),
            ),
          ),
        ),

        // ── Terms of service pinned at bottom ──────────────
        Padding(
          padding: const EdgeInsets.only(bottom: 32, top: 16),
          child: RichText(
            textAlign: TextAlign.center,
            text: TextSpan(
              style: GoogleFonts.plusJakartaSans(
                fontSize: 13,
                fontWeight: FontWeight.w400,
                color: AppColors.vrSlate400,
                fontStyle: FontStyle.italic,
              ),
              children: [
                TextSpan(text: s.termsAgree),
                TextSpan(
                  text: s.termsOfService,
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: AppColors.vrSlate400,
                    fontStyle: FontStyle.italic,
                    decoration: TextDecoration.underline,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  // ╔══════════════════════════════════════════════════════════════╗
  // ║  SHARED WIDGETS                                            ║
  // ╚══════════════════════════════════════════════════════════════╝

  Widget _buildPhoneField(AppStrings s) {
    const double fontSize = 30.0;
    final baseStyle = GoogleFonts.plusJakartaSans(
      fontSize: fontSize,
      fontWeight: FontWeight.w700,
      color: AppColors.vrHeading,
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 1, bottom: 8),
          child: Text(
            s.phoneNumber,
            style: GoogleFonts.plusJakartaSans(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: AppColors.vrSlate400,
              letterSpacing: 3.0,
            ),
          ),
        ),
        LayoutBuilder(
          builder: (context, constraints) {
            final totalWidth = constraints.maxWidth;

            // Measure the +91 prefix width
            final prefixPainter = TextPainter(
              text: TextSpan(
                text: '+91',
                style: GoogleFonts.plusJakartaSans(
                  fontSize: fontSize,
                  fontWeight: FontWeight.w600,
                ),
              ),
              textDirection: TextDirection.ltr,
            )..layout();
            final prefixWidth = prefixPainter.width;
            const gap = 14.0;

            // Measure base width of 10 digits with zero letter-spacing
            final digitPainter = TextPainter(
              text: TextSpan(text: '0000000000', style: baseStyle),
              textDirection: TextDirection.ltr,
            )..layout();
            final baseDigitWidth = digitPainter.width;

            // Calculate spacing: distribute remaining space across chars
            final availableForDigits = totalWidth - prefixWidth - gap;
            final extraSpace = availableForDigits - baseDigitWidth;
            final letterSpacing = (extraSpace / 11).clamp(1.0, 20.0);

            return Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Text(
                  '+91',
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: fontSize,
                    fontWeight: FontWeight.w600,
                    color: AppColors.vrSlate400,
                  ),
                ),
                const SizedBox(width: gap),
                Expanded(
                  child: Stack(
                    alignment: Alignment.centerLeft,
                    children: [
                      // Custom placeholder
                      if (_phoneController.text.isEmpty)
                        ClipRect(
                          child: Text(
                            '0000000000',
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: fontSize,
                              fontWeight: FontWeight.w600,
                              color: AppColors.vrSlate400
                                  .withValues(alpha: 0.25),
                              letterSpacing: letterSpacing,
                            ),
                            maxLines: 1,
                            softWrap: false,
                            overflow: TextOverflow.clip,
                          ),
                        ),
                      // Actual text field
                      TextField(
                        controller: _phoneController,
                        keyboardType: TextInputType.phone,
                        inputFormatters: [
                          FilteringTextInputFormatter.digitsOnly,
                          LengthLimitingTextInputFormatter(10),
                        ],
                        style:
                            baseStyle.copyWith(letterSpacing: letterSpacing),
                        onChanged: (_) => setState(() {}),
                        decoration: const InputDecoration(
                          filled: true,
                          fillColor: Colors.transparent,
                          border: InputBorder.none,
                          enabledBorder: InputBorder.none,
                          focusedBorder: InputBorder.none,
                          disabledBorder: InputBorder.none,
                          errorBorder: InputBorder.none,
                          focusedErrorBorder: InputBorder.none,
                          contentPadding: EdgeInsets.zero,
                          isDense: true,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            );
          },
        ),
        const SizedBox(height: 8),
        Container(
          height: 1.5,
          color: AppColors.vrCardBorder,
        ),
      ],
    );
  }

  /// Simple single text field for OTP — easier for older users.
  Widget _buildOtpField(AppStrings s) {
    return TextField(
      controller: _otpController,
      keyboardType: TextInputType.number,
      textAlign: TextAlign.center,
      maxLength: 6,
      inputFormatters: [FilteringTextInputFormatter.digitsOnly],
      // OTP autofill from the SMS the user just received. Zero
      // permission required on either platform:
      //
      //   - iOS: oneTimeCode is a TextContentType that the keyboard
      //     bar surfaces as a one-tap suggestion when an SMS with a
      //     code arrives within the last ~3 minutes. No Info.plist
      //     entry, no entitlements, no SMS access. Works on every
      //     iPhone since iOS 12.
      //
      //   - Android: triggers Autofill Framework + Google's SMS code
      //     suggestion, again no permission needed (READ_SMS would
      //     be an absolute non-starter on Play Store review).
      //
      // No transparent-fill (the kind that pastes the code without a
      // tap): that needs SMS Retriever API + a server-side app hash
      // baked into the SMS body, or User Consent API + a per-message
      // dialog. Both are heavier — left as a follow-up. The keyboard
      // suggestion is one tap which is already a big win for older
      // reporters who used to switch apps to copy the code.
      autofillHints: const [AutofillHints.oneTimeCode],
      style: GoogleFonts.plusJakartaSans(
        fontSize: 32,
        fontWeight: FontWeight.w700,
        color: AppColors.vrHeading,
        letterSpacing: 16,
      ),
      decoration: InputDecoration(
        counterText: '',
        hintText: '------',
        hintStyle: GoogleFonts.plusJakartaSans(
          fontSize: 32,
          fontWeight: FontWeight.w400,
          color: AppColors.vrSlate400.withValues(alpha: 0.35),
          letterSpacing: 16,
        ),
        filled: true,
        fillColor: AppColors.vrWarmBg,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: AppColors.vrCardBorder, width: 1.5),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: AppColors.vrCardBorder, width: 1.5),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: AppColors.vrCoral, width: 2),
        ),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
      ),
    );
  }

  Widget _buildRoundedButton({
    required String label,
    required bool isLoading,
    required VoidCallback onTap,
    bool showArrow = false,
  }) {
    if (isLoading) {
      return Container(
        width: double.infinity,
        height: 60,
        decoration: BoxDecoration(
          color: AppColors.vrCoral,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: AppColors.vrCoral.withValues(alpha: 0.25),
              blurRadius: 24,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: const Center(
          child: SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(
              strokeWidth: 2.5,
              color: Colors.white,
            ),
          ),
        ),
      );
    }

    return SizedBox(
      width: double.infinity,
      height: 60,
      child: Material(
        color: AppColors.vrCoral,
        borderRadius: BorderRadius.circular(20),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(20),
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: AppColors.vrCoral.withValues(alpha: 0.25),
                  blurRadius: 24,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  label,
                  style: GoogleFonts.plusJakartaSans(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                    fontSize: 18,
                    letterSpacing: 0.5,
                  ),
                ),
                if (showArrow) ...[
                  const SizedBox(width: 10),
                  const Icon(LucideIcons.arrowRight,
                      color: Colors.white, size: 20),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ╔══════════════════════════════════════════════════════════════╗
  // ║  ACTIONS                                                   ║
  // ╚══════════════════════════════════════════════════════════════╝

  void _requestOtp(AuthNotifier notifier) {
    final phone = _phoneController.text.trim();
    if (phone.isEmpty || phone.length < 10) return;
    notifier.requestOtp('+91$phone');
    _startResendTimer();
  }

  Future<void> _verifyOtp(AuthNotifier notifier) async {
    final phone = _phoneController.text.trim();
    final otp = _otpController.text.trim();
    if (phone.isEmpty || otp.isEmpty) return;

    final success = await notifier.verifyOtp('+91$phone', otp);
    if (success && mounted) {
      context.go('/home');
    }
  }
}
