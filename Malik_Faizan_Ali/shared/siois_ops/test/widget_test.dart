import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:siois_ops/src/core/theme.dart';
import 'package:siois_ops/src/core/widgets.dart';
import 'package:siois_ops/src/features/common/quick_form.dart';

// Widget smoke tests that need no network. NOT executed in the authoring environment.
Widget _wrap(Widget child) => MaterialApp(theme: buildTheme(Brightness.light), home: Scaffold(body: SingleChildScrollView(child: child)));

void main() {
  testWidgets('StatusChip humanizes its label', (tester) async {
    await tester.pumpWidget(_wrap(const StatusChip('in_review')));
    expect(find.text('In review'), findsOneWidget);
  });

  testWidgets('EmptyState shows title and message', (tester) async {
    await tester.pumpWidget(_wrap(const EmptyState(icon: Icons.inbox, title: 'Nothing here', message: 'Add one')));
    expect(find.text('Nothing here'), findsOneWidget);
    expect(find.text('Add one'), findsOneWidget);
  });

  testWidgets('QuickForm blocks submit when a required field is empty', (tester) async {
    var submitted = false;
    await tester.pumpWidget(_wrap(QuickForm(
      fields: const [QField('name', 'Name', QType.text, required: true)],
      onSubmit: (v) async => submitted = true,
    )));
    await tester.tap(find.text('Save'));
    await tester.pump();
    expect(find.text('This field is required'), findsOneWidget);
    expect(submitted, isFalse);
  });

  testWidgets('QuickForm submits trimmed values and closes its dialog', (tester) async {
    Map<String, dynamic>? got;
    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (context) => Scaffold(
          body: TextButton(
            onPressed: () => showDialog<bool>(
              context: context,
              builder: (_) => Dialog(
                child: QuickForm(fields: const [QField('name', 'Name', QType.text, required: true)], onSubmit: (v) async => got = v),
              ),
            ),
            child: const Text('open'),
          ),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, '  Ali  ');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    expect(got?['name'], 'Ali');
    expect(find.byType(QuickForm), findsNothing); // popped with true
  });
}
