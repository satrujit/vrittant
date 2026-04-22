import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../../core/theme/app_colors.dart';

/// Branded splash screen shown while the app checks stored auth.
///
/// Matches the native splash (white background) so the transition
/// from Android/iOS native splash → this widget is seamless.
class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: 64,
              height: 64,
              child: SvgPicture.asset(
                'assets/images/v_logo.svg',
                fit: BoxFit.contain,
              ),
            ),
            const SizedBox(height: 14),
            RichText(
              text: TextSpan(
                children: [
                  TextSpan(
                    text: 'V',
                    style: GoogleFonts.plusJakartaSans(
                      fontSize: 32,
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
                      fontSize: 32,
                      fontWeight: FontWeight.w800,
                      color: AppColors.vrHeading,
                      letterSpacing: -1.5,
                      height: 1,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
