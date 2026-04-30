import 'package:audioplayers/audioplayers.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';

import '../../../core/services/api_config.dart';
import '../../../core/services/api_service.dart';
import '../../../core/services/story_image_cache_manager.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/l10n/app_strings.dart';
import '../../../core/theme/theme_extensions.dart';
import '../../auth/providers/auth_provider.dart';
import '../providers/files_provider.dart';

// ═══════════════════════════════════════════════════════════════════════════
// Files Screen — Vrittant reporter file manager (dynamic)
// ═══════════════════════════════════════════════════════════════════════════

class FilesScreen extends ConsumerStatefulWidget {
  const FilesScreen({super.key});

  @override
  ConsumerState<FilesScreen> createState() => _FilesScreenState();
}

class _FilesScreenState extends ConsumerState<FilesScreen> {
  AppStrings get s => AppStrings.of(ref);

  @override
  void initState() {
    super.initState();

    // Fetch files on init
    Future.microtask(
      () => ref.read(filesProvider.notifier).fetchFiles(),
    );
  }

  @override
  void dispose() {
    super.dispose();
  }

  Widget _buildOrgLogo(ReporterProfile? reporter, {double height = 32}) {
    final logoUrl = reporter?.org?.logoUrl;
    if (logoUrl != null && logoUrl.isNotEmpty) {
      final fullUrl =
          logoUrl.startsWith('http') ? logoUrl : '${ApiConfig.baseUrl}$logoUrl';
      return CachedNetworkImage(
        imageUrl: fullUrl,
        cacheManager: StoryImageCacheManager.instance,
        height: height,
        fit: BoxFit.contain,
        errorWidget: (_, __, ___) => Text(
          reporter?.org?.name ?? '',
          style: GoogleFonts.plusJakartaSans(
            fontSize: 14,
            fontWeight: FontWeight.w700,
            color: AppColors.vrHeading,
          ),
        ),
        placeholder: (_, __) => SizedBox(height: height),
      );
    }
    return Text(
      reporter?.org?.name ?? reporter?.organization ?? '',
      style: GoogleFonts.plusJakartaSans(
        fontSize: 14,
        fontWeight: FontWeight.w700,
        color: AppColors.vrHeading,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    final filesState = ref.watch(filesProvider);
    final reporter = ref.watch(authProvider).reporter;

    return Scaffold(
      backgroundColor: t.scaffoldBg,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            // ── Header (consistent with HOME) ──────────────────────
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
              child: Row(
                children: [
                  SizedBox(
                    width: 32,
                    height: 32,
                    child: SvgPicture.asset(
                      'assets/images/v_logo.svg',
                      fit: BoxFit.contain,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: RichText(
                      text: TextSpan(
                        children: [
                          TextSpan(
                            text: 'V',
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 26,
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
                              fontSize: 26,
                              fontWeight: FontWeight.w800,
                              color: AppColors.vrHeading,
                              letterSpacing: -1.5,
                              height: 1,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  // ── Partner org logo (dynamic) ─────────
                  _buildOrgLogo(reporter),
                ],
              ),
            ),

            // ── Content (single grouped view) ────────────────────
            Expanded(
              child: filesState.isLoading
                  ? const Center(
                      child: CircularProgressIndicator(
                        color: AppColors.vrCoral,
                        strokeWidth: 2.5,
                      ),
                    )
                  : filesState.error != null
                      ? _ErrorView(
                          message: filesState.error!,
                          retryLabel: s.retry,
                          onRetry: () =>
                              ref.read(filesProvider.notifier).fetchFiles(),
                        )
                      : _GroupedFilesView(
                          voiceNotes: filesState.voiceNotes,
                          photos: filesState.photos,
                          documents: filesState.documents,
                          noFilesTitle: s.noFilesYet,
                          noFilesSubtitle: s.noFilesDesc,
                          voiceNotesLabel: s.voiceNotes,
                          aiSortedLabel: s.aiSorted,
                          scenePhotosLabel: s.scenePhotos,
                          viewAllLabel: s.viewAll,
                          documentsLabel: s.documents,
                        ),
            ),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Error view with retry
// ═══════════════════════════════════════════════════════════════════════════

class _ErrorView extends StatelessWidget {
  final String message;
  final String retryLabel;
  final VoidCallback onRetry;

  const _ErrorView({
    required this.message,
    required this.retryLabel,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(LucideIcons.alertCircle, size: 48, color: AppColors.vrCoral),
          const SizedBox(height: 12),
          Text(
            message,
            style: AppTypography.bodyMedium.copyWith(color: t.mutedColor),
          ),
          const SizedBox(height: 16),
          TextButton.icon(
            onPressed: onRetry,
            icon: const Icon(LucideIcons.refreshCw, size: 16),
            label: Text(retryLabel),
            style: TextButton.styleFrom(foregroundColor: AppColors.vrCoral),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Grouped View — the default, matching the mockup
// ═══════════════════════════════════════════════════════════════════════════

class _GroupedFilesView extends StatelessWidget {
  final List<Map<String, dynamic>> voiceNotes;
  final List<Map<String, dynamic>> photos;
  final List<Map<String, dynamic>> documents;
  final String noFilesTitle;
  final String noFilesSubtitle;
  final String voiceNotesLabel;
  final String aiSortedLabel;
  final String scenePhotosLabel;
  final String viewAllLabel;
  final String documentsLabel;

  const _GroupedFilesView({
    required this.voiceNotes,
    required this.photos,
    required this.documents,
    required this.noFilesTitle,
    required this.noFilesSubtitle,
    required this.voiceNotesLabel,
    required this.aiSortedLabel,
    required this.scenePhotosLabel,
    required this.viewAllLabel,
    required this.documentsLabel,
  });

  @override
  Widget build(BuildContext context) {
    // Show empty state if no files at all
    if (voiceNotes.isEmpty && photos.isEmpty && documents.isEmpty) {
      return _EmptyView(
        icon: LucideIcons.folderOpen,
        title: noFilesTitle,
        subtitle: noFilesSubtitle,
      );
    }

    return ListView(
      padding: const EdgeInsets.only(top: AppSpacing.lg, bottom: 100),
      children: [
        if (voiceNotes.isNotEmpty) ...[
          _SectionHeader(
            title: voiceNotesLabel,
            trailing: _AiBadge(label: aiSortedLabel),
          ),
          const SizedBox(height: AppSpacing.md),
          _HorizontalFileList(
            files: voiceNotes,
            cardBuilder: (file) => _VoiceNoteCard(file: file),
            cardWidth: 160,
            height: 195,
          ),
          const SizedBox(height: AppSpacing.xxl),
        ],

        if (photos.isNotEmpty) ...[
          _SectionHeader(
            title: scenePhotosLabel,
          ),
          const SizedBox(height: AppSpacing.md),
          _HorizontalFileList(
            files: photos,
            cardBuilder: (file) => _ScenePhotoCard(file: file),
            cardWidth: 170,
            height: 195,
          ),
          const SizedBox(height: AppSpacing.xxl),
        ],

        if (documents.isNotEmpty) ...[
          _SectionHeader(title: documentsLabel),
          const SizedBox(height: AppSpacing.md),
          _HorizontalFileList(
            files: documents,
            cardBuilder: (file) => _DocumentCard(file: file),
            cardWidth: 170,
            height: 210,
          ),
        ],
      ],
    );
  }
}

// ─── Section header ──────────────────────────────────────────────────────

class _SectionHeader extends StatelessWidget {
  final String title;
  final Widget? trailing;

  const _SectionHeader({required this.title, this.trailing});

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.base),
      child: Row(
        children: [
          Text(
            title,
            style: AppTypography.titleLarge.copyWith(
              color: t.headingColor,
              fontWeight: FontWeight.w700,
            ),
          ),
          const Spacer(),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}

// ─── AI badge ────────────────────────────────────────────────────────────

class _AiBadge extends StatelessWidget {
  final String label;
  const _AiBadge({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
        border: Border.all(color: AppColors.vrCoral.withValues(alpha: 0.3)),
        color: AppColors.vrCoralLight,
      ),
      child: Text(
        label,
        style: GoogleFonts.plusJakartaSans(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: AppColors.vrCoral,
          letterSpacing: 0.8,
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Reusable horizontal file list
// ═══════════════════════════════════════════════════════════════════════════

class _HorizontalFileList extends StatelessWidget {
  final List<Map<String, dynamic>> files;
  final Widget Function(Map<String, dynamic>) cardBuilder;
  final double cardWidth;
  final double height;

  const _HorizontalFileList({
    required this.files,
    required this.cardBuilder,
    required this.cardWidth,
    required this.height,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: height,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.base),
        itemCount: files.length,
        separatorBuilder: (_, __) => const SizedBox(width: AppSpacing.md),
        itemBuilder: (_, i) => SizedBox(
          width: cardWidth,
          child: cardBuilder(files[i]),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Voice Note Card
// ═══════════════════════════════════════════════════════════════════════════

class _VoiceNoteCard extends StatefulWidget {
  final Map<String, dynamic> file;
  const _VoiceNoteCard({required this.file});

  @override
  State<_VoiceNoteCard> createState() => _VoiceNoteCardState();
}

class _VoiceNoteCardState extends State<_VoiceNoteCard> {
  AudioPlayer? _player;
  bool _isPlaying = false;
  Duration _position = Duration.zero;
  Duration _duration = Duration.zero;

  Map<String, dynamic> get file => widget.file;

  @override
  void dispose() {
    _player?.dispose();
    super.dispose();
  }

  Future<void> _togglePlay() async {
    final url = file['url'] as String? ?? '';
    if (url.isEmpty) return;

    if (_player == null) {
      _player = AudioPlayer();
      _player!.onPlayerStateChanged.listen((s) {
        if (mounted) setState(() => _isPlaying = s == PlayerState.playing);
      });
      _player!.onDurationChanged.listen((d) {
        if (mounted) setState(() => _duration = d);
      });
      _player!.onPositionChanged.listen((p) {
        if (mounted) setState(() => _position = p);
      });
      _player!.onPlayerComplete.listen((_) {
        if (mounted) setState(() {
          _isPlaying = false;
          _position = Duration.zero;
        });
      });
    }

    if (_isPlaying) {
      await _player!.pause();
    } else {
      final fullUrl = _fullUrl(url);
      if (_position > Duration.zero && _position < _duration) {
        await _player!.resume();
      } else {
        await _player!.play(UrlSource(fullUrl));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    final filename = file['filename'] as String? ?? 'Untitled';
    final size = _formatSize(file['size'] as int? ?? 0);
    final storyHeadline = file['story_headline'] as String? ?? '';

    return GestureDetector(
      onTap: _togglePlay,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Waveform thumbnail with play overlay
          Container(
            height: 130,
            width: 160,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Color(0xFFFFF2EE),
                  Color(0xFFFEE4D9),
                  Color(0xFFFDD6C6),
                ],
              ),
            ),
            child: Stack(
              alignment: Alignment.center,
              children: [
                _WaveformIcon(),
                // Play/pause overlay
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: AppColors.vrCoral.withValues(alpha: 0.9),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    _isPlaying ? LucideIcons.pause : LucideIcons.play,
                    size: 20,
                    color: Colors.white,
                  ),
                ),
                // Progress indicator at bottom
                if (_duration > Duration.zero)
                  Positioned(
                    bottom: 0,
                    left: 0,
                    right: 0,
                    child: ClipRRect(
                      borderRadius: const BorderRadius.only(
                        bottomLeft: Radius.circular(12),
                        bottomRight: Radius.circular(12),
                      ),
                      child: LinearProgressIndicator(
                        value: _duration.inMilliseconds > 0
                            ? _position.inMilliseconds / _duration.inMilliseconds
                            : 0,
                        minHeight: 3,
                        backgroundColor: AppColors.vrCoral.withValues(alpha: 0.15),
                        valueColor: const AlwaysStoppedAnimation(AppColors.vrCoral),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            filename,
            style: GoogleFonts.plusJakartaSans(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: t.headingColor,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 2),
          Text(
            storyHeadline.isNotEmpty ? '$size · $storyHeadline' : size,
            style: GoogleFonts.plusJakartaSans(
              fontSize: 11,
              fontWeight: FontWeight.w400,
              color: t.mutedColor,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

// ─── Waveform icon (simple painted bars) ─────────────────────────────────

class _WaveformIcon extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: const Size(50, 40),
      painter: _WaveformPainter(),
    );
  }
}

class _WaveformPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppColors.vrCoral.withValues(alpha: 0.7)
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 3.5;

    final barHeights = [0.3, 0.6, 1.0, 0.85, 0.55, 0.9, 0.4];
    final totalBars = barHeights.length;
    final spacing = size.width / (totalBars + 1);

    for (var i = 0; i < totalBars; i++) {
      final x = spacing * (i + 1);
      final barH = size.height * barHeights[i];
      final top = (size.height - barH) / 2;
      canvas.drawLine(Offset(x, top), Offset(x, top + barH), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

// ═══════════════════════════════════════════════════════════════════════════
// Scene Photo Card
// ═══════════════════════════════════════════════════════════════════════════

class _ScenePhotoCard extends StatelessWidget {
  final Map<String, dynamic> file;
  const _ScenePhotoCard({required this.file});

  void _openFullScreen(BuildContext context) {
    final url = file['url'] as String? ?? '';
    final filename = file['filename'] as String? ?? 'Photo';
    if (url.isEmpty) return;
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => _FilesFullScreenImage(
          url: _fullUrl(url),
          title: filename,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    final filename = file['filename'] as String? ?? 'Untitled';
    final size = _formatSize(file['size'] as int? ?? 0);
    final url = file['url'] as String? ?? '';
    final createdAt = file['created_at'] as String?;
    final dateStr = createdAt != null ? _shortDate(createdAt) : '';

    return GestureDetector(
      onTap: () => _openFullScreen(context),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Photo thumbnail or placeholder
          Container(
            height: 130,
            width: 170,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
              color: const Color(0xFFFAC8A0),
            ),
            clipBehavior: Clip.antiAlias,
            child: url.isNotEmpty
                ? CachedNetworkImage(
                    imageUrl: _fullUrl(url),
                    cacheManager: StoryImageCacheManager.instance,
                    fit: BoxFit.cover,
                    width: 170,
                    height: 130,
                    errorWidget: (_, __, ___) => Center(
                      child: Icon(
                        LucideIcons.image,
                        size: 32,
                        color: AppColors.vrCoral.withValues(alpha: 0.6),
                      ),
                    ),
                    placeholder: (_, __) => const SizedBox(
                      width: 170,
                      height: 130,
                    ),
                  )
                : Center(
                    child: Icon(
                      LucideIcons.image,
                      size: 32,
                      color: AppColors.vrCoral.withValues(alpha: 0.6),
                    ),
                  ),
          ),
          const SizedBox(height: 8),
          Text(
            filename,
            style: GoogleFonts.plusJakartaSans(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: t.headingColor,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 2),
          Text(
            dateStr.isNotEmpty ? '$dateStr · $size' : size,
            style: GoogleFonts.plusJakartaSans(
              fontSize: 11,
              fontWeight: FontWeight.w400,
              color: t.mutedColor,
            ),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Document Card
// ═══════════════════════════════════════════════════════════════════════════

class _DocumentCard extends ConsumerWidget {
  final Map<String, dynamic> file;
  const _DocumentCard({required this.file});

  String get _extension {
    final name = file['filename'] as String? ?? '';
    final dotIdx = name.lastIndexOf('.');
    if (dotIdx >= 0 && dotIdx < name.length - 1) {
      return name.substring(dotIdx + 1).toUpperCase();
    }
    return 'FILE';
  }

  Color get _typeColor {
    switch (_extension) {
      case 'PDF':
        return AppColors.vrCoral;
      case 'DOCX':
      case 'DOC':
        return AppColors.vrAccentIndigo;
      default:
        return AppColors.vrSection;
    }
  }

  Color get _typeBgColor {
    switch (_extension) {
      case 'PDF':
        return AppColors.vrCoralLight;
      case 'DOCX':
      case 'DOC':
        return const Color(0xFFEEF2FF);
      default:
        return AppColors.neutral100;
    }
  }

  Future<void> _openDocument(BuildContext context, WidgetRef ref) async {
    final url = file['url'] as String? ?? '';
    if (url.isEmpty) return;
    final filename = file['filename'] as String? ?? 'document';
    await _downloadAndOpen(context, ref, _fullUrl(url), filename);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = context.t;
    final filename = file['filename'] as String? ?? 'Untitled';
    final size = _formatSize(file['size'] as int? ?? 0);
    final storyHeadline = file['story_headline'] as String? ?? '';

    return GestureDetector(
      onTap: () => _openDocument(context, ref),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Document icon card
          Container(
            height: 140,
            width: 170,
            decoration: BoxDecoration(
              color: _typeBgColor,
              borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
              border: Border.all(color: t.dividerColor, width: 0.5),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(LucideIcons.fileText, size: 32, color: _typeColor),
                const SizedBox(height: 8),
                Text(
                  _extension,
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: _typeColor,
                    letterSpacing: 0.5,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            filename,
            style: GoogleFonts.plusJakartaSans(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: t.headingColor,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 2),
          Text(
            storyHeadline.isNotEmpty ? '$size · $storyHeadline' : size,
            style: GoogleFonts.plusJakartaSans(
              fontSize: 11,
              fontWeight: FontWeight.w400,
              color: t.mutedColor,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Empty view — reusable placeholder
// ═══════════════════════════════════════════════════════════════════════════

class _EmptyView extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;

  const _EmptyView({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 48, color: t.mutedColor),
          const SizedBox(height: 12),
          Text(
            title,
            style: AppTypography.titleMedium.copyWith(color: t.headingColor),
          ),
          const SizedBox(height: 4),
          Text(
            subtitle,
            style: AppTypography.bodySmall.copyWith(color: t.mutedColor),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Full-screen image viewer (Files tab)
// ═══════════════════════════════════════════════════════════════════════════

class _FilesFullScreenImage extends StatelessWidget {
  final String url;
  final String title;

  const _FilesFullScreenImage({required this.url, required this.title});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: Text(
          title,
          style: AppTypography.bodyMedium.copyWith(color: Colors.white),
        ),
        leading: IconButton(
          icon: const Icon(LucideIcons.x),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: Center(
        child: InteractiveViewer(
          minScale: 0.5,
          maxScale: 4.0,
          child: CachedNetworkImage(
            imageUrl: url,
            cacheManager: StoryImageCacheManager.instance,
            fit: BoxFit.contain,
            errorWidget: (_, __, ___) => Icon(
              LucideIcons.imageOff,
              size: 48,
              color: Colors.white.withValues(alpha: 0.5),
            ),
            placeholder: (_, __) => const SizedBox.shrink(),
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Download + Open Natively helper
// ═══════════════════════════════════════════════════════════════════════════

/// Download a remote file to temp storage and open with the native app.
/// Shows a small progress overlay during download.
Future<void> _downloadAndOpen(
  BuildContext context,
  WidgetRef ref,
  String url,
  String filename,
) async {
  final s = AppStrings.of(ref);
  final overlay = Overlay.of(context);
  final progress = ValueNotifier<double>(0);
  late OverlayEntry entry;

  entry = OverlayEntry(
    builder: (_) => _DownloadProgressOverlay(
      progress: progress,
      filename: filename,
    ),
  );
  overlay.insert(entry);

  try {
    final dir = await getTemporaryDirectory();
    // Sanitise filename for filesystem
    final safeName = filename.replaceAll(RegExp(r'[^\w\s\-.]'), '_');
    final savePath = '${dir.path}/$safeName';

    await Dio().download(
      url,
      savePath,
      onReceiveProgress: (received, total) {
        if (total > 0) progress.value = received / total;
      },
    );

    entry.remove();

    final result = await OpenFilex.open(savePath);
    if (result.type != ResultType.done && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('${s.couldNotOpenFile}: ${result.message}'),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  } catch (e) {
    entry.remove();
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('${s.downloadFailed}: $e'),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }
}

/// Compact download-progress overlay shown at the top of the screen.
class _DownloadProgressOverlay extends StatelessWidget {
  final ValueNotifier<double> progress;
  final String filename;

  const _DownloadProgressOverlay({
    required this.progress,
    required this.filename,
  });

  @override
  Widget build(BuildContext context) {
    return Positioned(
      top: MediaQuery.of(context).padding.top + 12,
      left: 24,
      right: 24,
      child: Material(
        elevation: 8,
        borderRadius: BorderRadius.circular(14),
        color: Colors.white,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            children: [
              const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2.5,
                  color: AppColors.vrCoral,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Opening $filename…',
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppColors.vrHeading,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 6),
                    ValueListenableBuilder<double>(
                      valueListenable: progress,
                      builder: (_, p, __) => ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: p > 0 ? p : null,
                          minHeight: 4,
                          backgroundColor:
                              AppColors.vrCoral.withValues(alpha: 0.12),
                          valueColor: const AlwaysStoppedAnimation(
                              AppColors.vrCoral),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Utility helpers
// ═══════════════════════════════════════════════════════════════════════════

/// Build full URL from a server-relative path like `/uploads/xxx.jpg`.
String _fullUrl(String path) {
  if (path.startsWith('http')) return path;
  return '${ApiConfig.baseUrl}$path';
}

/// Format byte size to human-readable string.
String _formatSize(int bytes) {
  if (bytes <= 0) return '0 B';
  if (bytes < 1024) return '$bytes B';
  if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
  return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
}

/// Parse ISO date string to short display format.
String _shortDate(String iso) {
  try {
    final dt = DateTime.parse(iso);
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    return '${months[dt.month - 1]} ${dt.day}';
  } catch (_) {
    return '';
  }
}
