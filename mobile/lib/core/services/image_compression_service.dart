import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';
import 'package:flutter_image_compress/flutter_image_compress.dart';

/// Compresses photo uploads when they exceed a size threshold.
///
/// Why this exists
/// ---------------
/// `image_picker` already applies `imageQuality: 85` when the
/// reporter taps "Photo from camera/gallery", which trims raw JPEG
/// bytes a bit. But modern phone cameras still produce 3–8 MB files
/// on a single shot, especially in good light. On a 3G newsroom
/// connection a 6 MB upload can take 30+ seconds and silently
/// timeout — the reporter then re-attaches and tries again, doubling
/// the work for the same outcome.
///
/// The shape of the compromise we want
/// -----------------------------------
///   - Photos already under [_thresholdBytes] (2 MB by default) pass
///     through untouched. There's no quality reason to recompress
///     a small file, and recompression is lossy — applying it to a
///     800 KB thumbnail would degrade for no payoff.
///   - Photos over the threshold get a single recompress pass aimed
///     at landing under it. We don't iterate quality bands or
///     resize — most over-threshold camera shots reduce by 60–80%
///     at quality 80 + a 2048px max edge, which is plenty for the
///     panel reviewer's screen and for the e-paper print pipeline.
///   - Non-image bytes (audio, video, PDFs) are explicitly excluded
///     by the [shouldCompress] predicate; the caller checks that
///     before invoking [compress] so we never accidentally feed a
///     PDF to libjpeg-turbo and corrupt it.
///
/// On platforms where flutter_image_compress isn't available (web
/// today), we no-op — the original bytes go up. The newsroom uses
/// the mobile app, so degraded web behaviour is fine.
class ImageCompressionService {
  ImageCompressionService._();

  /// 2 MB. Empirically this keeps a photo upload under ~5 s on a
  /// reasonable 4G link, and well under 15 s on a degraded 3G
  /// session. Files at or below the threshold skip compression.
  static const int _thresholdBytes = 2 * 1024 * 1024;

  /// Quality level passed to libjpeg-turbo on a compression pass.
  /// 80 is a good balance — visually indistinguishable from 95 for
  /// editorial photos, ~half the bytes.
  static const int _jpegQuality = 80;

  /// Maximum edge length (px) on either dimension after a compress
  /// pass. 2048 covers every reviewer screen we ship to (Vrittant
  /// panel maxes out around 1440 logical px) and survives a print
  /// page at 200 DPI for a typical 4-column photo. Phone cameras
  /// shoot at 4000+ px on the long edge, so this is a real
  /// reduction.
  static const int _maxEdgePx = 2048;

  /// Image extensions we know how to compress. Anything outside this
  /// set is excluded by [shouldCompress] — see the class doc for why
  /// running libjpeg-turbo on a PDF is a bad idea.
  static const _kImageExtensions = {
    'jpg', 'jpeg', 'png', 'webp', 'heic', 'heif',
  };

  /// Returns true when the file is large enough AND of a recognised
  /// image type to be worth compressing. Calls site:
  ///
  /// ```dart
  /// final outBytes = ImageCompressionService.shouldCompress(bytes, name)
  ///     ? await ImageCompressionService.compress(bytes, name)
  ///     : bytes;
  /// ```
  static bool shouldCompress(List<int> bytes, String filename) {
    if (bytes.length <= _thresholdBytes) return false;
    final lower = filename.toLowerCase();
    final dot = lower.lastIndexOf('.');
    if (dot < 0 || dot == lower.length - 1) return false;
    return _kImageExtensions.contains(lower.substring(dot + 1));
  }

  /// Compress [bytes] in a single pass. Returns the compressed bytes
  /// when the pass produced a smaller output; falls back to the
  /// original bytes on any error or if compression somehow grew the
  /// file (rare but possible with already-aggressive source JPEGs).
  ///
  /// The output format is JPEG regardless of input format. PNG /
  /// HEIC / WebP source images become JPEG on the wire; the panel /
  /// publish pipeline doesn't care about the source format and
  /// JPEG keeps the bytes-per-pixel ratio predictable.
  ///
  /// Filename is preserved at the call site (we return only bytes);
  /// the caller may want to swap the extension to `.jpg` if it
  /// matters for content-type sniffing on the server. Today our
  /// `/files/upload` endpoint sniffs from headers + filename and
  /// either is fine.
  static Future<Uint8List> compress(
    List<int> bytes,
    String filename,
  ) async {
    try {
      final asUint8 = Uint8List.fromList(bytes);
      final compressed = await FlutterImageCompress.compressWithList(
        asUint8,
        quality: _jpegQuality,
        minWidth: _maxEdgePx,
        minHeight: _maxEdgePx,
        // keepExif=false strips camera EXIF (location, timestamp,
        // device serial). Reporters' phones may have geotagging on
        // and we don't want to leak coordinates of crime / sensitive
        // sources via published photos. The print desk re-tags with
        // story-level metadata anyway.
        keepExif: false,
        format: CompressFormat.jpeg,
      );
      // Defensive: if the compression somehow inflated the bytes,
      // keep the original. flutter_image_compress occasionally does
      // this on already-tiny / pre-compressed inputs.
      if (compressed.length >= asUint8.length) {
        debugPrint(
          '[image_compress] no-shrink for $filename '
          '(orig=${asUint8.length}, out=${compressed.length}); '
          'keeping original',
        );
        return asUint8;
      }
      debugPrint(
        '[image_compress] $filename: '
        '${(asUint8.length / 1024).toStringAsFixed(0)} KB → '
        '${(compressed.length / 1024).toStringAsFixed(0)} KB '
        '(${(100 * compressed.length / asUint8.length).toStringAsFixed(0)}%)',
      );
      return compressed;
    } catch (e) {
      // Never block an upload because the compressor blew up. Worst
      // case the reporter waits longer for the upload — better than
      // losing the photo entirely.
      debugPrint('[image_compress] compression failed for $filename: $e — uploading original');
      return Uint8List.fromList(bytes);
    }
  }
}
