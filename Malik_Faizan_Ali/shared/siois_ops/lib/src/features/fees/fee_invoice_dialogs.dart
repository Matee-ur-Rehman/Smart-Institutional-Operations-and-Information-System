import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/report_download.dart';
import 'fee_models.dart';

/// One invoice as a list row (admin and parent lists).
class InvoiceTile extends StatelessWidget {
  const InvoiceTile({super.key, required this.invoice, required this.onTap, this.showStudent = true});
  final FeeInvoice invoice;
  final VoidCallback onTap;
  final bool showStudent;

  @override
  Widget build(BuildContext context) {
    final inv = invoice;
    final title = showStudent && inv.studentName.isNotEmpty ? '${inv.studentName} · ${inv.periodLabel}' : inv.periodLabel;
    final sub = [
      inv.invoiceNo,
      if (showStudent && inv.sectionLabel.isNotEmpty) inv.sectionLabel,
      'Due ${formatDate(inv.dueDate)}',
    ].join(' · ');
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: AppCard(
        onTap: onTap,
        child: Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.w700), overflow: TextOverflow.ellipsis),
              const SizedBox(height: 2),
              Text(sub, style: const TextStyle(color: Brand.muted, fontSize: 12.5), overflow: TextOverflow.ellipsis),
            ]),
          ),
          const SizedBox(width: 12),
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text(formatMoney(inv.net), style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            StatusChip(inv.status),
          ]),
        ]),
      ),
    );
  }
}

/// Opens the invoice detail dialog. Returns true when something changed (payment, reversal, cancellation).
Future<bool> showInvoiceDetail(BuildContext context, {required String invoiceId, required bool isAdmin}) async {
  var changed = false;
  await showAppDialog<void>(
    context,
    title: 'Invoice',
    width: 620,
    builder: (ctx) => _InvoiceBody(invoiceId: invoiceId, isAdmin: isAdmin, onChanged: () => changed = true),
  );
  return changed;
}

class _InvoiceBody extends StatefulWidget {
  const _InvoiceBody({required this.invoiceId, required this.isAdmin, required this.onChanged});
  final String invoiceId;
  final bool isAdmin;
  final VoidCallback onChanged;

  @override
  State<_InvoiceBody> createState() => _InvoiceBodyState();
}

class _InvoiceBodyState extends State<_InvoiceBody> with BusyMixin {
  late Future<FeeInvoice> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<FeeInvoice> _load() async {
    final api = context.read<ApiClient>();
    return FeeInvoice.fromJson(asMap(await api.get('/fee-invoices/${widget.invoiceId}')));
  }

  void _refresh() => setState(() { _future = _load(); });

  Future<void> _record(FeeInvoice inv) async {
    final ok = await showAppDialog<bool>(context, title: 'Record payment', builder: (ctx) => _PaymentForm(invoice: inv));
    if (ok == true && mounted) {
      widget.onChanged();
      _refresh();
    }
  }

  Future<void> _reverse(FeePayment p) async {
    final ok = await showAppDialog<bool>(context, title: 'Reverse payment ${p.receiptNo}', builder: (ctx) => _ReverseForm(payment: p));
    if (ok == true && mounted) {
      widget.onChanged();
      _refresh();
    }
  }

  Future<void> _cancel(FeeInvoice inv) async {
    final yes = await confirmDialog(context,
        title: 'Cancel invoice?',
        message: 'Invoice ${inv.invoiceNo} will be cancelled. This cannot be undone.',
        confirmLabel: 'Cancel invoice',
        destructive: true);
    if (!yes || !mounted) return;
    final api = context.read<ApiClient>();
    final ok = await runBusy(() async {
      await api.post('/fee-invoices/${inv.id}/cancel');
    }, success: 'Invoice cancelled');
    if (ok && mounted) {
      widget.onChanged();
      _refresh();
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<FeeInvoice>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const SizedBox(height: 140, child: LoadingView());
        }
        if (snap.hasError) {
          return ErrorView(error: snap.error!, onRetry: _refresh);
        }
        final inv = snap.data!;
        final canRecord = widget.isAdmin && inv.balance > 0 && inv.status != 'cancelled';
        final canCancel = widget.isAdmin && inv.status != 'cancelled' && inv.payments.isEmpty;
        return Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
          Row(children: [
            Expanded(child: Text(inv.invoiceNo, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700))),
            StatusChip(inv.status),
          ]),
          const SizedBox(height: 8),
          if (inv.studentName.isNotEmpty) InfoRow('Student', '${inv.studentName} (${inv.rollNo})'),
          if (inv.sectionLabel.isNotEmpty) InfoRow('Section', inv.sectionLabel),
          InfoRow('Period', inv.periodLabel),
          InfoRow('Issued', formatDate(inv.issueDate)),
          InfoRow('Due date', formatDate(inv.dueDate)),
          const SectionTitle('Fee breakdown'),
          if (inv.items.isEmpty) const Text('No line items.', style: TextStyle(color: Brand.muted)),
          for (final it in inv.items)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(children: [
                Expanded(child: Text(it.description)),
                Text(formatMoney(it.amount)),
              ]),
            ),
          const Divider(height: 20),
          _amountRow('Total', inv.total),
          if (inv.discount > 0) _amountRow('Discount', -inv.discount),
          _amountRow('Net payable', inv.net, bold: true),
          _amountRow('Paid', inv.paid),
          _amountRow('Balance', inv.balance, bold: true, color: inv.balance > 0 ? Brand.danger : Brand.success),
          const SectionTitle('Payment history'),
          if (inv.payments.isEmpty) const Text('No payments recorded yet.', style: TextStyle(color: Brand.muted)),
          for (final p in inv.payments) _paymentRow(p),
          const SizedBox(height: 16),
          if (widget.isAdmin)
            Wrap(spacing: 8, runSpacing: 8, children: [
              if (canRecord)
                FilledButton.icon(
                  onPressed: busy ? null : () => _record(inv),
                  icon: const Icon(Icons.payments_outlined),
                  label: const Text('Record payment'),
                ),
              if (canCancel)
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(foregroundColor: Brand.danger),
                  onPressed: busy ? null : () => _cancel(inv),
                  icon: const Icon(Icons.block),
                  label: const Text('Cancel invoice'),
                ),
            ]),
        ]);
      },
    );
  }

  Widget _amountRow(String label, double v, {bool bold = false, Color? color}) {
    final style = TextStyle(fontWeight: bold ? FontWeight.w700 : FontWeight.w500, color: color);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(children: [
        Expanded(child: Text(label, style: style)),
        Text(v < 0 ? '- ${formatMoney(-v)}' : formatMoney(v), style: style),
      ]),
    );
  }

  Widget _paymentRow(FeePayment p) {
    final faded = p.isReversed;
    final style = TextStyle(decoration: faded ? TextDecoration.lineThrough : null, color: faded ? Brand.muted : null);
    final detail = [
      formatDate(p.paymentDate),
      humanize(p.method),
      if (p.reference != null && p.reference!.isNotEmpty) 'Ref ${p.reference}',
      if (p.recordedByName != null) 'by ${p.recordedByName}',
    ].join(' · ');
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Flexible(child: Text(p.receiptNo, style: style.copyWith(fontWeight: FontWeight.w600))),
              if (p.isReversal) ...[const SizedBox(width: 6), const StatusChip('reversal', color: Brand.warning)],
              if (p.isReversed) ...[const SizedBox(width: 6), const StatusChip('reversed', color: Brand.muted)],
            ]),
            Text(detail, style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
            if (p.remarks != null && p.remarks!.isNotEmpty) Text(p.remarks!, style: const TextStyle(fontSize: 12.5)),
          ]),
        ),
        Text(p.amount < 0 ? '- ${formatMoney(-p.amount)}' : formatMoney(p.amount), style: style.copyWith(fontWeight: FontWeight.w700)),
        if (!p.isReversal && !p.isReversed)
          IconButton(
            tooltip: 'Download receipt',
            visualDensity: VisualDensity.compact,
            icon: const Icon(Icons.picture_as_pdf_outlined, size: 20),
            onPressed: () => downloadReport(context, '/reports/fee-receipt/${p.id}', fallbackName: 'receipt.pdf'),
          ),
        if (widget.isAdmin && !p.isReversal && !p.isReversed)
          IconButton(
            tooltip: 'Reverse payment',
            visualDensity: VisualDensity.compact,
            icon: const Icon(Icons.undo, size: 20),
            onPressed: busy ? null : () => _reverse(p),
          ),
      ]),
    );
  }
}

class _PaymentForm extends StatefulWidget {
  const _PaymentForm({required this.invoice});
  final FeeInvoice invoice;

  @override
  State<_PaymentForm> createState() => _PaymentFormState();
}

class _PaymentFormState extends State<_PaymentForm> with BusyMixin {
  final _key = GlobalKey<FormState>();
  late final TextEditingController _amount;
  final _reference = TextEditingController();
  final _remarks = TextEditingController();
  DateTime _date = dateOnly(DateTime.now());
  String _method = 'cash';

  @override
  void initState() {
    super.initState();
    _amount = TextEditingController(text: widget.invoice.balance.toStringAsFixed(2));
  }

  @override
  void dispose() {
    _amount.dispose();
    _reference.dispose();
    _remarks.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_key.currentState?.validate() ?? false)) return;
    final api = context.read<ApiClient>();
    final amount = round2(double.parse(_amount.text.trim()));
    final ok = await runBusy(() async {
      await api.post('/fee-invoices/${widget.invoice.id}/payments', body: {
        'amount': amount,
        'payment_date': isoDate(_date),
        'method': _method,
        if (_reference.text.trim().isNotEmpty) 'reference': _reference.text.trim(),
        if (_remarks.text.trim().isNotEmpty) 'remarks': _remarks.text.trim(),
      });
    }, success: 'Payment recorded');
    if (ok && mounted) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _key,
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text('${widget.invoice.invoiceNo} · outstanding ${formatMoney(widget.invoice.balance)}', style: const TextStyle(color: Brand.muted)),
        const SizedBox(height: 12),
        TextFormField(
          controller: _amount,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: const InputDecoration(labelText: 'Amount (PKR)'),
          validator: (v) {
            final n = double.tryParse((v ?? '').trim());
            if (n == null) return 'Enter a valid amount';
            if (n <= 0) return 'Amount must be greater than zero';
            if (n > widget.invoice.balance + 0.004) return 'Cannot exceed the balance of ${formatMoney(widget.invoice.balance)}';
            return null;
          },
        ),
        const SizedBox(height: 12),
        DateField(label: 'Payment date', value: _date, onChanged: (d) => setState(() => _date = d ?? _date)),
        const SizedBox(height: 12),
        AppDropdown<String>(
          label: 'Method',
          value: _method,
          items: [for (final m in kPaymentMethods) DropdownMenuItem<String>(value: m, child: Text(humanize(m)))],
          onChanged: (v) => setState(() => _method = v ?? _method),
        ),
        const SizedBox(height: 12),
        TextFormField(controller: _reference, maxLength: 100, decoration: const InputDecoration(labelText: 'Reference (cheque / transaction no.)')),
        TextFormField(controller: _remarks, maxLength: 500, decoration: const InputDecoration(labelText: 'Remarks')),
        const SizedBox(height: 12),
        FilledButton(onPressed: busy ? null : _submit, child: Text(busy ? 'Saving…' : 'Record payment')),
      ]),
    );
  }
}

class _ReverseForm extends StatefulWidget {
  const _ReverseForm({required this.payment});
  final FeePayment payment;

  @override
  State<_ReverseForm> createState() => _ReverseFormState();
}

class _ReverseFormState extends State<_ReverseForm> with BusyMixin {
  final _key = GlobalKey<FormState>();
  final _reason = TextEditingController();

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_key.currentState?.validate() ?? false)) return;
    final api = context.read<ApiClient>();
    final ok = await runBusy(() async {
      await api.post('/fee-payments/${widget.payment.id}/reverse', body: {'reason': _reason.text.trim()});
    }, success: 'Payment reversed');
    if (ok && mounted) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _key,
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text('A reversal record of ${formatMoney(widget.payment.amount)} is created; the original payment is kept for audit.',
            style: const TextStyle(color: Brand.muted)),
        const SizedBox(height: 12),
        TextFormField(
          controller: _reason,
          maxLines: 3,
          maxLength: 500,
          decoration: const InputDecoration(labelText: 'Reason (required)'),
          validator: (v) => (v ?? '').trim().length < 5 ? 'Please give a reason (at least 5 characters)' : null,
        ),
        const SizedBox(height: 8),
        FilledButton(
          style: FilledButton.styleFrom(backgroundColor: Brand.danger),
          onPressed: busy ? null : _submit,
          child: Text(busy ? 'Saving…' : 'Reverse payment'),
        ),
      ]),
    );
  }
}
