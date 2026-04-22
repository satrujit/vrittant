import 'category.dart';

class NewsArticle {
  final String id;
  final String title;
  final String body;
  final String? titleOdia;
  final String? bodyOdia;
  final NewsCategory category;
  final NewsPriority priority;
  final NewsStatus status;
  final String reporterId;
  final String? location;
  final List<String> mediaUrls;
  final DateTime createdAt;
  final DateTime updatedAt;
  final String? rejectionReason;

  const NewsArticle({
    required this.id,
    required this.title,
    required this.body,
    this.titleOdia,
    this.bodyOdia,
    required this.category,
    this.priority = NewsPriority.normal,
    this.status = NewsStatus.draft,
    required this.reporterId,
    this.location,
    this.mediaUrls = const [],
    required this.createdAt,
    required this.updatedAt,
    this.rejectionReason,
  });

  NewsArticle copyWith({
    String? id,
    String? title,
    String? body,
    String? titleOdia,
    String? bodyOdia,
    NewsCategory? category,
    NewsPriority? priority,
    NewsStatus? status,
    String? reporterId,
    String? location,
    List<String>? mediaUrls,
    DateTime? createdAt,
    DateTime? updatedAt,
    String? rejectionReason,
  }) {
    return NewsArticle(
      id: id ?? this.id,
      title: title ?? this.title,
      body: body ?? this.body,
      titleOdia: titleOdia ?? this.titleOdia,
      bodyOdia: bodyOdia ?? this.bodyOdia,
      category: category ?? this.category,
      priority: priority ?? this.priority,
      status: status ?? this.status,
      reporterId: reporterId ?? this.reporterId,
      location: location ?? this.location,
      mediaUrls: mediaUrls ?? this.mediaUrls,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      rejectionReason: rejectionReason ?? this.rejectionReason,
    );
  }
}
