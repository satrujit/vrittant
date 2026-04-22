import 'package:flutter/material.dart';
import '../theme/app_spacing.dart';
import '../theme/theme_extensions.dart';

class GradientButton extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  final LinearGradient? gradient;
  final IconData? icon;
  final bool pill;
  final bool loading;
  final bool expand;

  const GradientButton({
    super.key,
    required this.label,
    required this.onTap,
    this.gradient,
    this.icon,
    this.pill = false,
    this.loading = false,
    this.expand = false,
  });

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    final grad = gradient ?? t.primaryGradient;
    final radius = pill ? AppSpacing.radiusFull : 14.0;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: loading ? null : onTap,
        borderRadius: BorderRadius.circular(radius),
        child: Ink(
          decoration: BoxDecoration(
            gradient: grad,
            borderRadius: BorderRadius.circular(radius),
            boxShadow: [
              BoxShadow(
                color: grad.colors.first.withValues(alpha: 0.3),
                blurRadius: 20,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 14),
            child: Row(
              mainAxisSize: expand ? MainAxisSize.max : MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (icon != null && !loading) ...[
                  Icon(icon, color: t.onPrimary, size: 18),
                  const SizedBox(width: 8),
                ],
                if (loading)
                  SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: t.onPrimary,
                    ),
                  )
                else
                  Text(
                    label,
                    style: TextStyle(
                      color: t.onPrimary,
                      fontWeight: FontWeight.w600,
                      fontSize: 14,
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
