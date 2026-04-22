import 'package:flutter/material.dart';
import '../../models/category.dart';
import '../theme/app_colors.dart';

class StatusChip extends StatelessWidget {
  final NewsStatus status;
  const StatusChip({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    final (bg, textColor, dotColor) = switch (status) {
      NewsStatus.draft => (
        AppColors.neutral100,
        AppColors.neutral600,
        AppColors.neutral400,
      ),
      NewsStatus.submitted => (
        const Color(0xFFFEF3C7),
        const Color(0xFF92400E),
        AppColors.gold500,
      ),
      NewsStatus.approved => (
        const Color(0xFFDCFCE7),
        const Color(0xFF166534),
        AppColors.success,
      ),
      NewsStatus.rejected => (
        const Color(0xFFFEE2E2),
        const Color(0xFF991B1B),
        AppColors.error,
      ),
      NewsStatus.published => (
        AppColors.indigo100,
        AppColors.indigo700,
        AppColors.indigo500,
      ),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: dotColor, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(
            status.name[0].toUpperCase() + status.name.substring(1),
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: textColor,
            ),
          ),
        ],
      ),
    );
  }
}
