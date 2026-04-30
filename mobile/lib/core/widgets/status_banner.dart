import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';

/// A compact persistent banner shown at the top of a screen for status alerts.
class StatusBanner extends StatelessWidget {
  final IconData icon;
  final String message;
  final Color backgroundColor;
  final Color foregroundColor;

  const StatusBanner({
    super.key,
    required this.icon,
    required this.message,
    this.backgroundColor = const Color(0xFFFEF3C7), // warm yellow
    this.foregroundColor = const Color(0xFF92400E), // amber-800
  });

  /// No internet connection banner.
  factory StatusBanner.noInternet() {
    return const StatusBanner(
      icon: LucideIcons.wifiOff,
      message: 'No internet connection',
      backgroundColor: Color(0xFFFEE2E2), // red-100
      foregroundColor: Color(0xFFB91C1C), // red-700
    );
  }

  /// Mic occupied by phone call banner.
  factory StatusBanner.micBusy() {
    return const StatusBanner(
      icon: LucideIcons.phoneCall,
      message: 'Mic unavailable during phone call',
      backgroundColor: Color(0xFFFEF3C7), // amber-100
      foregroundColor: Color(0xFF92400E), // amber-800
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      color: backgroundColor,
      child: Row(
        children: [
          Icon(icon, size: 16, color: foregroundColor),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: GoogleFonts.plusJakartaSans(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: foregroundColor,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
