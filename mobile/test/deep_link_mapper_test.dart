import 'package:flutter_test/flutter_test.dart';
import 'package:newsflow/core/router/deep_link_mapper.dart';

void main() {
  group('mapUniversalLinkToLocation', () {
    test('maps /r/<id> to /create?storyId=<id>', () {
      final loc = mapUniversalLinkToLocation(
        Uri.parse('https://vrittant.in/r/abc-123'),
      );
      expect(loc, '/create?storyId=abc-123');
    });

    test('maps /r/today to /home', () {
      final loc = mapUniversalLinkToLocation(
        Uri.parse('https://vrittant.in/r/today'),
      );
      expect(loc, '/home');
    });

    test('returns null for non-vrittant.in domain', () {
      final loc = mapUniversalLinkToLocation(
        Uri.parse('https://example.com/r/abc'),
      );
      expect(loc, null);
    });

    test('returns null for vrittant.in without /r prefix', () {
      final loc = mapUniversalLinkToLocation(
        Uri.parse('https://vrittant.in/some/other/path'),
      );
      expect(loc, null);
    });

    test('falls back to /home for bare /r/', () {
      final loc = mapUniversalLinkToLocation(
        Uri.parse('https://vrittant.in/r/'),
      );
      expect(loc, '/home');
    });

    test('handles UUID-style story ids', () {
      final loc = mapUniversalLinkToLocation(
        Uri.parse('https://vrittant.in/r/550e8400-e29b-41d4-a716-446655440000'),
      );
      expect(loc, '/create?storyId=550e8400-e29b-41d4-a716-446655440000');
    });
  });
}
