/// Maps an incoming Universal Link / App Link URI to a go_router location.
///
/// Pure function. No navigation, no Riverpod, no platform dependence.
/// Caller decides what to do with the returned location string (typically
/// router.go(...)).
///
/// Universal Links land here from app_links's getInitialAppLink() (cold
/// start) and uriLinkStream (runtime). We only respond to vrittant.in;
/// everything else returns null and the caller should ignore.
String? mapUniversalLinkToLocation(Uri uri) {
  if (uri.host != 'vrittant.in') return null;
  final segments = uri.pathSegments;
  if (segments.isEmpty || segments[0] != 'r') return null;
  if (segments.length < 2) return '/home'; // bare /r — fallback
  final tail = segments[1];
  if (tail.isEmpty) return '/home'; // bare /r/ (trailing slash) — fallback
  if (tail == 'today') {
    // No today-filter route yet; land on home. Follow-up ticket can wire
    // a /home?filter=today or a dedicated /today path.
    return '/home';
  }
  // Story ID — navigate to the notepad with the story preloaded.
  // A future "view-only story" route could replace this with /story/<id>.
  return '/create?storyId=$tail';
}
