import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:newsflow/app.dart';

void main() {
  testWidgets('App loads and shows home screen', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: NewsFlowApp()),
    );
    await tester.pumpAndSettle();
    expect(find.text('Good Morning'), findsOneWidget);
  });
}
