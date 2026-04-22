import 'package:flutter/material.dart';
import '../../models/news_article.dart';
import '../../models/category.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../theme/app_spacing.dart';
import '../theme/theme_extensions.dart';
import 'status_chip.dart';
import 'category_chip.dart';

class NewsCard extends StatelessWidget {
  final NewsArticle article;
  final VoidCallback? onTap;

  const NewsCard({super.key, required this.article, this.onTap});

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(22),
        decoration: BoxDecoration(
          color: t.cardBg,
          borderRadius: BorderRadius.circular(AppSpacing.radiusXl),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.06),
              blurRadius: 12,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CategoryChip(category: article.category, selected: true),
                const Spacer(),
                StatusChip(status: article.status),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              article.titleOdia ?? article.title,
              style: AppTypography.odiaTitleLarge,
            ),
            const SizedBox(height: 6),
            Text(
              article.bodyOdia ?? article.body,
              style: AppTypography.odiaBodyMedium,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                if (article.priority == NewsPriority.breaking ||
                    article.priority == NewsPriority.urgent)
                  _PriorityBadge(priority: article.priority),
                const Spacer(),
                Text(_timeAgo(article.createdAt), style: AppTypography.caption),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _timeAgo(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }
}

class _PriorityBadge extends StatelessWidget {
  final NewsPriority priority;
  const _PriorityBadge({required this.priority});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppColors.gold400, AppColors.coral400],
        ),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        priority == NewsPriority.breaking ? 'BREAKING' : 'URGENT',
        style: TextStyle(
          color: context.t.onPrimary,
          fontSize: 10,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}
