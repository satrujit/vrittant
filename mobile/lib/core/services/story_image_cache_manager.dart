import 'package:flutter_cache_manager/flutter_cache_manager.dart';

/// Long-lived on-disk image cache for story photos and org logos.
///
/// Why a custom manager instead of `DefaultCacheManager`:
/// the default cache manager honours each server's `Cache-Control`
/// header. `storage.googleapis.com` (where reporter-uploaded photos
/// and org logos live) emits `Cache-Control: max-age=2400` — about
/// 40 minutes. After that the file on disk is marked stale and the
/// next render triggers a re-download, even though the bytes behind
/// the URL could not have changed.
///
/// Stories change. Photos don't. Reporter uploads land at a UUID
/// path (`storage.googleapis.com/vrittant-uploads/<uuid>.jpg`) — the
/// URL is one-shot, never reused, never overwritten. Same with the
/// scraped-news thumbnails. So we treat image files as permanent
/// once on disk: `stalePeriod` is effectively forever (~100 years).
///
/// What still bounds the cache:
///   • `maxNrOfCacheObjects` (LRU eviction) — capped at 1000 so the
///     disk footprint stays bounded even as the reporter accumulates
///     stories over months. ~1 GB ceiling at 1 MB/photo.
///   • The OS may purge `Library/Caches/` on extreme low-disk
///     pressure (iOS) or via Android's cache-clear flow. That's the
///     contract for "Caches/" — totally fine for our purposes.
///
/// Pass `cacheManager: StoryImageCacheManager.instance` to every
/// `CachedNetworkImage` (and `CachedNetworkImageProvider`) call site.
class StoryImageCacheManager {
  StoryImageCacheManager._();

  static const _key = 'vr_story_images_v1';

  /// 100 years = effectively forever for the lifetime of the app
  /// install. Image bytes are immutable per URL so there's no
  /// correctness reason to ever expire by time.
  static const _forever = Duration(days: 365 * 100);

  static final CacheManager instance = CacheManager(
    Config(
      _key,
      stalePeriod: _forever,
      maxNrOfCacheObjects: 1000,
    ),
  );
}
