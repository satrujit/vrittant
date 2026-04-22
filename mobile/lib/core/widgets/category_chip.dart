import 'package:flutter/material.dart';
import '../../models/category.dart';
import '../theme/theme_extensions.dart';

class CategoryChip extends StatelessWidget {
  final NewsCategory category;
  final bool selected;
  final VoidCallback? onTap;

  const CategoryChip({
    super.key,
    required this.category,
    this.selected = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          gradient: selected ? category.gradient : null,
          color: selected ? null : t.cardBg,
          borderRadius: BorderRadius.circular(10),
          border: selected ? null : Border.all(color: t.dividerColor),
          boxShadow: selected
              ? [
                  BoxShadow(
                    color: category.gradient.colors.first.withValues(alpha: 0.3),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ]
              : null,
        ),
        child: Text(
          category.label,
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: selected ? t.onPrimary : t.mutedColor,
          ),
        ),
      ),
    );
  }
}
