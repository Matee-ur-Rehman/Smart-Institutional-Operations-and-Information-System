import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/paged_list.dart';
import '../common/report_download.dart';
import '../dashboard/role_scope.dart';
import 'fee_invoice_dialogs.dart';
import 'fee_models.dart';

/// Parent: fee totals, invoice list (tap for the breakdown and receipts) and the fee statement PDF.
class FeesParentPage extends StatelessWidget {
  const FeesParentPage({super.key});

  @override
  Widget build(BuildContext context) {
    return PageFrame(
      title: 'Fees',
      subtitle: 'Invoices, payments and receipts',
      child: StudentScope(builder: (context, child) => _ChildFees(studentId: child.studentId)),
    );
  }
}

class _ChildFees extends StatefulWidget {
  const _ChildFees({required this.studentId});
  final String studentId;
  @override
  State<_ChildFees> createState() => _ChildFeesState();
}

class _ChildFeesState extends State<_ChildFees> {
  int _rev = 0;

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    final wide = isMedium(context);
    final cardW = wide ? 220.0 : (MediaQuery.sizeOf(context).width - 42) / 2;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      AsyncView<Map<String, dynamic>>(
        loadKey: _rev,
        loader: () async => asMap(asMap(await api.get('/students/${widget.studentId}/fee-statement'))['totals']),
        builder: (context, t, reload) {
          final balance = asDouble(t['balance']);
          final overdue = asDouble(t['overdue']);
          return Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Wrap(spacing: 10, runSpacing: 10, crossAxisAlignment: WrapCrossAlignment.center, children: [
              SizedBox(width: cardW, child: KpiCard(label: 'Total billed', value: formatMoney(asDouble(t['billed'])), icon: Icons.receipt_long, color: Brand.info)),
              SizedBox(width: cardW, child: KpiCard(label: 'Paid', value: formatMoney(asDouble(t['paid'])), icon: Icons.check_circle_outline, color: Brand.success)),
              SizedBox(width: cardW, child: KpiCard(label: 'Balance due', value: formatMoney(balance), icon: Icons.hourglass_bottom, color: balance > 0 ? Brand.warning : Brand.success)),
              if (overdue > 0) SizedBox(width: cardW, child: KpiCard(label: 'Overdue', value: formatMoney(overdue), icon: Icons.warning_amber, color: Brand.danger)),
              ReportButton(label: 'Fee statement', path: '/reports/fee-statement/${widget.studentId}', fallbackName: 'fee_statement.pdf'),
            ]),
          );
        },
      ),
      Expanded(
        child: PagedList<FeeInvoice>(
          path: '/fee-invoices',
          reloadKey: _rev,
          query: {'student_id': widget.studentId},
          parse: FeeInvoice.fromJson,
          emptyTitle: 'No invoices yet',
          emptyMessage: 'Fee invoices appear here once the school generates them.',
          emptyIcon: Icons.receipt_long,
          itemBuilder: (context, inv, reload) => InvoiceTile(
            invoice: inv,
            showStudent: false,
            onTap: () async {
              await showInvoiceDetail(context, invoiceId: inv.id, isAdmin: false);
              if (mounted) setState(() => _rev++);
            },
          ),
        ),
      ),
    ]);
  }
}
