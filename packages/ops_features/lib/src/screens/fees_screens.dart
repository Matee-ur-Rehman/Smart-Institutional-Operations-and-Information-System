import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/core.dart';
import '../data/ops_api.dart';
import '../models/models.dart';
import '../ui/ui.dart';

const List<MapEntry<String, String>> _methods = <MapEntry<String, String>>[
  MapEntry('cash', 'Cash'),
  MapEntry('bank_transfer', 'Bank transfer'),
  MapEntry('cheque', 'Cheque'),
  MapEntry('other', 'Other'),
];

const List<MapEntry<String, String>> _frequencies = <MapEntry<String, String>>[
  MapEntry('monthly', 'Monthly'),
  MapEntry('quarterly', 'Quarterly'),
  MapEntry('yearly', 'Yearly'),
  MapEntry('one_time', 'One time'),
];

String _methodLabel(String method) {
  for (final m in _methods) {
    if (m.key == method) return m.value;
  }
  return titleCase(method);
}

// ====================================================================== parent view

/// Fees of one child (parents only; students do not see fees by project decision).
class FeesScreen extends StatefulWidget {
  const FeesScreen({super.key, required this.studentId});

  final String studentId;

  @override
  State<FeesScreen> createState() => _FeesScreenState();
}

class _FeesScreenState extends State<FeesScreen> {
  late Future<Paged<Invoice>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<Paged<Invoice>> _load() => context.read<OpsApi>().invoices(studentId: widget.studentId);

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Fees'),
        actions: [IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _reload)],
      ),
      body: ContentWidth(
        maxWidth: 720,
        child: FutureView<Paged<Invoice>>(
          future: _future,
          onRetry: _reload,
          builder: (ctx, page) {
            final invoices = page.items.where((i) => i.status != 'cancelled').toList();
            if (invoices.isEmpty) return const EmptyView('No fee records yet', icon: Icons.receipt_long_outlined);
            final outstanding = invoices.fold<double>(0, (sum, i) => sum + i.balance);
            final paid = invoices.fold<double>(0, (sum, i) => sum + i.paidAmount);
            return ListView(
              padding: const EdgeInsets.all(12),
              children: [
                Row(
                  children: [
                    Expanded(
                      child: StatCard(
                        label: 'Outstanding',
                        value: fmtMoney(outstanding),
                        color: outstanding > 0 ? Colors.red.shade700 : Colors.green.shade700,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(child: StatCard(label: 'Paid so far', value: fmtMoney(paid))),
                  ],
                ),
                const SizedBox(height: 8),
                for (final inv in invoices)
                  _InvoiceCard(
                    invoice: inv,
                    onTap: () async {
                      await Navigator.of(context).push(MaterialPageRoute<void>(
                        builder: (_) => InvoiceDetailScreen(invoiceId: inv.id, isAdmin: false),
                      ));
                      _reload();
                    },
                  ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _InvoiceCard extends StatelessWidget {
  const _InvoiceCard({required this.invoice, required this.onTap, this.showStudent = false});

  final Invoice invoice;
  final VoidCallback onTap;
  final bool showStudent;

  @override
  Widget build(BuildContext context) {
    final title = showStudent ? '${invoice.studentName} - ${invoice.periodLabel}' : invoice.periodLabel;
    return Card(
      child: ListTile(
        onTap: onTap,
        isThreeLine: true,
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text(
            '${invoice.invoiceNo}'
            '${showStudent ? '  |  ${invoice.sectionName}' : ''}\n'
            'Due ${fmtDate(invoice.dueDate)}  |  Balance ${fmtMoney(invoice.balance)}',
          ),
        ),
        trailing: StatusChip(invoice.status),
      ),
    );
  }
}

// ====================================================================== invoice detail

/// One invoice with its items and payments. Admin ([isAdmin]) can also record and reverse
/// payments and cancel an unpaid invoice. Parents get a read-only view.
class InvoiceDetailScreen extends StatefulWidget {
  const InvoiceDetailScreen({super.key, required this.invoiceId, required this.isAdmin});

  final String invoiceId;
  final bool isAdmin;

  @override
  State<InvoiceDetailScreen> createState() => _InvoiceDetailScreenState();
}

class _InvoiceDetailScreenState extends State<InvoiceDetailScreen> {
  late Future<Invoice> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<Invoice> _load() => context.read<OpsApi>().invoice(widget.invoiceId);

  void _reload() => setState(() => _future = _load());

  Future<void> _recordPayment(Invoice inv) async {
    final api = context.read<OpsApi>();
    var amount = '';
    DateTime? date = DateTime.now();
    var method = 'cash';
    var reference = '';
    var remarks = '';
    final saved = await showFormDialog(
      context,
      title: 'Record payment',
      submitLabel: 'Record',
      builder: (ctx, set) => Column(
        mainAxisSize: MainAxisSize.min,
        children: spaced([
          Text('Outstanding balance: ${fmtMoney(inv.balance)}'),
          formText('Amount received (Rs)', amount, (v) => amount = v, number: true),
          DateField(
            label: 'Payment date',
            value: date,
            lastDate: DateTime.now(),
            onChanged: (d) => set(() => date = d),
          ),
          pickString('Method', method, _methods, (v) => set(() => method = v ?? method)),
          formText('Reference (optional)', reference, (v) => reference = v, hint: 'Receipt or transaction number'),
          formText('Remarks (optional)', remarks, (v) => remarks = v, maxLines: 2),
        ]),
      ),
      validate: () =>
          Validators.positiveAmount(amount, max: inv.balance) ?? Validators.notFutureDate(date, label: 'Payment date'),
      onSubmit: () => api.recordPayment(inv.id, <String, dynamic>{
        'amount': Validators.parseNumber(amount),
        'payment_date': ymd(date!),
        'method': method,
        'reference': reference.trim().isEmpty ? null : reference.trim(),
        'remarks': remarks.trim().isEmpty ? null : remarks.trim(),
      }),
    );
    if (saved) {
      _reload();
      if (mounted) showMessage(context, 'Payment recorded');
    }
  }

  Future<void> _reverse(Payment p) async {
    final api = context.read<OpsApi>();
    var reason = '';
    final saved = await showFormDialog(
      context,
      title: 'Reverse ${p.receiptNo}',
      submitLabel: 'Reverse payment',
      builder: (ctx, set) => Column(
        mainAxisSize: MainAxisSize.min,
        children: spaced([
          Text('This cancels ${fmtMoney(p.amount)} received on ${fmtDate(p.paymentDate)}. '
              'The original payment stays in the history.'),
          formText('Reason', reason, (v) => reason = v, maxLines: 2),
        ]),
      ),
      validate: () => Validators.minLength(reason, 5, 'Reason') ?? Validators.maxLength(reason, 500, 'Reason'),
      onSubmit: () => api.reversePayment(p.id, reason.trim()),
    );
    if (saved) {
      _reload();
      if (mounted) showMessage(context, 'Payment reversed');
    }
  }

  Future<void> _cancel(Invoice inv) async {
    final ok = await confirmDialog(
      context,
      'Cancel invoice?',
      '${inv.invoiceNo} will be marked cancelled. This only works while nothing has been paid.',
      yes: 'Cancel invoice',
    );
    if (!ok || !mounted) return;
    final done = await runAction(context, () => context.read<OpsApi>().cancelInvoice(inv.id), success: 'Invoice cancelled');
    if (done) _reload();
  }

  Widget _amountRow(String label, String value, {bool bold = false}) {
    final style = TextStyle(fontWeight: bold ? FontWeight.w700 : FontWeight.normal);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Expanded(child: Text(label, style: style)),
          Text(value, style: style),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Invoice'),
        actions: [IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _reload)],
      ),
      body: ContentWidth(
        maxWidth: 720,
        child: FutureView<Invoice>(
          future: _future,
          onRetry: _reload,
          builder: (ctx, inv) {
            final reversible = inv.reversiblePayments.map((p) => p.id).toSet();
            final canPay = widget.isAdmin && inv.balance > 0 && inv.status != 'cancelled';
            final canCancel = widget.isAdmin && inv.status != 'cancelled' && inv.paidAmount == 0 && inv.payments.isEmpty;
            return ListView(
              padding: const EdgeInsets.all(12),
              children: [
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(inv.invoiceNo, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                            ),
                            StatusChip(inv.status),
                          ],
                        ),
                        const SizedBox(height: 8),
                        if (widget.isAdmin) InfoRow('Student', '${inv.studentName} (${inv.rollNo}) - ${inv.sectionName}'),
                        InfoRow('Period', inv.periodLabel),
                        InfoRow('Issued', fmtDate(inv.issueDate)),
                        InfoRow('Due', fmtDate(inv.dueDate)),
                      ],
                    ),
                  ),
                ),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Fee details', style: TextStyle(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 6),
                        for (final item in inv.items) _amountRow(item.description, fmtMoney(item.amount)),
                        const Divider(),
                        _amountRow('Total', fmtMoney(inv.totalAmount)),
                        if (inv.discountAmount > 0) _amountRow('Discount', '- ${fmtMoney(inv.discountAmount)}'),
                        _amountRow('Net amount', fmtMoney(inv.netAmount)),
                        _amountRow('Paid', fmtMoney(inv.paidAmount)),
                        _amountRow('Balance', fmtMoney(inv.balance), bold: true),
                      ],
                    ),
                  ),
                ),
                if (inv.payments.isNotEmpty)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Padding(
                            padding: EdgeInsets.fromLTRB(14, 6, 14, 2),
                            child: Text('Payments', style: TextStyle(fontWeight: FontWeight.w700)),
                          ),
                          for (final p in inv.payments)
                            ListTile(
                              dense: true,
                              title: Text(
                                '${p.isReversal ? '- ' : ''}${fmtMoney(p.amount)}   ${p.receiptNo}',
                                style: TextStyle(color: p.isReversal ? Colors.red.shade700 : null),
                              ),
                              subtitle: Text(
                                '${fmtDate(p.paymentDate)}  |  ${p.isReversal ? 'Reversal' : _methodLabel(p.method)}'
                                '${p.reference.isEmpty ? '' : '  |  ${p.reference}'}',
                              ),
                              trailing: widget.isAdmin && reversible.contains(p.id)
                                  ? IconButton(
                                      tooltip: 'Reverse this payment',
                                      icon: const Icon(Icons.undo),
                                      onPressed: () => _reverse(p),
                                    )
                                  : null,
                            ),
                        ],
                      ),
                    ),
                  ),
                if (canPay || canCancel)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        if (canPay)
                          FilledButton.icon(
                            onPressed: () => _recordPayment(inv),
                            icon: const Icon(Icons.payments_outlined),
                            label: const Text('Record payment'),
                          ),
                        if (canCancel)
                          OutlinedButton.icon(
                            onPressed: () => _cancel(inv),
                            icon: const Icon(Icons.cancel_outlined),
                            label: const Text('Cancel invoice'),
                          ),
                      ],
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }
}

// ====================================================================== admin

/// Admin fee management: invoices, bulk generation, totals and the fee setup (heads and per-class amounts).
class FeesAdminScreen extends StatelessWidget {
  const FeesAdminScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 4,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Fees'),
          bottom: const TabBar(
            isScrollable: true,
            tabs: [
              Tab(text: 'Invoices'),
              Tab(text: 'Generate'),
              Tab(text: 'Summary'),
              Tab(text: 'Fee setup'),
            ],
          ),
        ),
        body: const TabBarView(
          children: [_InvoicesTab(), _GenerateTab(), _SummaryTab(), _SetupTab()],
        ),
      ),
    );
  }
}

class _InvoicesTab extends StatefulWidget {
  const _InvoicesTab();

  @override
  State<_InvoicesTab> createState() => _InvoicesTabState();
}

class _InvoicesTabState extends State<_InvoicesTab> {
  late Future<Paged<Invoice>> _future;
  String? _status;
  String _period = '';

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<Paged<Invoice>> _load() => context
      .read<OpsApi>()
      .invoices(status: _status, periodLabel: _period.trim().isEmpty ? null : _period.trim());

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    return ContentWidth(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 8,
                  children: [
                    for (final s in const <String?>[null, 'unpaid', 'partial', 'overdue', 'paid', 'cancelled'])
                      ChoiceChip(
                        label: Text(s == null ? 'All' : titleCase(s)),
                        selected: _status == s,
                        onSelected: (_) {
                          _status = s;
                          _reload();
                        },
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        decoration: const InputDecoration(
                          labelText: 'Period (for example November 2026)',
                          border: OutlineInputBorder(),
                          isDense: true,
                        ),
                        onChanged: (v) => _period = v,
                        onSubmitted: (_) => _reload(),
                      ),
                    ),
                    IconButton(tooltip: 'Search', icon: const Icon(Icons.search), onPressed: _reload),
                  ],
                ),
              ],
            ),
          ),
          Expanded(
            child: FutureView<Paged<Invoice>>(
              future: _future,
              onRetry: _reload,
              builder: (ctx, page) {
                if (page.items.isEmpty) {
                  return const EmptyView('No invoices match', icon: Icons.receipt_long_outlined);
                }
                return ListView(
                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 24),
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Text('${page.total} invoice${page.total == 1 ? '' : 's'}',
                          style: TextStyle(color: Theme.of(context).hintColor)),
                    ),
                    for (final inv in page.items)
                      _InvoiceCard(
                        invoice: inv,
                        showStudent: true,
                        onTap: () async {
                          await Navigator.of(context).push(MaterialPageRoute<void>(
                            builder: (_) => InvoiceDetailScreen(invoiceId: inv.id, isAdmin: true),
                          ));
                          _reload();
                        },
                      ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _Targets {
  const _Targets(this.classes, this.sections);

  final List<ClassItem> classes;
  final List<SectionItem> sections;
}

class _GenerateTab extends StatefulWidget {
  const _GenerateTab();

  @override
  State<_GenerateTab> createState() => _GenerateTabState();
}

class _GenerateTabState extends State<_GenerateTab> {
  late Future<_Targets> _future;
  bool _wholeClass = true;
  String? _classId;
  String? _sectionId;
  String _period = '';
  DateTime? _due;
  bool _busy = false;
  GenerateResult? _result;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_Targets> _load() async {
    final api = context.read<OpsApi>();
    final classes = await api.classes();
    final sections = await api.sections();
    return _Targets(classes, sections);
  }

  void _reload() => setState(() => _future = _load());

  Future<void> _generate() async {
    final problem = (_wholeClass
            ? (_classId == null ? 'Choose a class' : null)
            : (_sectionId == null ? 'Choose a section' : null)) ??
        Validators.minLength(_period, 3, 'Period') ??
        Validators.maxLength(_period, 30, 'Period') ??
        Validators.notPastDate(_due, label: 'Due date');
    if (problem != null) {
      showMessage(context, problem, error: true);
      return;
    }
    final ok = await confirmDialog(
      context,
      'Generate invoices?',
      'Invoices for "${_period.trim()}" will be created for every active student in the chosen '
          '${_wholeClass ? 'class' : 'section'} and their parents will be notified.',
      yes: 'Generate',
    );
    if (!ok || !mounted) return;
    final api = context.read<OpsApi>();
    final body = <String, dynamic>{
      if (_wholeClass) 'class_id': _classId else 'section_id': _sectionId,
      'period_label': _period.trim(),
      'due_date': ymd(_due!),
    };
    setState(() {
      _busy = true;
      _result = null;
    });
    GenerateResult? result;
    final done = await runAction(context, () async {
      result = await api.generateInvoices(body);
    });
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (done) _result = result;
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureView<_Targets>(
      future: _future,
      onRetry: _reload,
      builder: (ctx, t) {
        return ContentWidth(
          maxWidth: 620,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              const Text(
                'Creates one invoice per student from the fee setup of their class. Only active monthly fee '
                'heads are included. A student who already has an invoice for the same period is skipped.',
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 8,
                children: [
                  ChoiceChip(
                    label: const Text('Whole class'),
                    selected: _wholeClass,
                    onSelected: (_) => setState(() => _wholeClass = true),
                  ),
                  ChoiceChip(
                    label: const Text('One section'),
                    selected: !_wholeClass,
                    onSelected: (_) => setState(() => _wholeClass = false),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              if (_wholeClass)
                pickString('Class', _classId, [for (final c in t.classes) MapEntry(c.id, c.name)],
                    (v) => setState(() => _classId = v))
              else
                pickString('Section', _sectionId, [for (final s in t.sections) MapEntry(s.id, s.display)],
                    (v) => setState(() => _sectionId = v)),
              const SizedBox(height: 12),
              formText('Period', _period, (v) => _period = v, hint: 'For example November 2026'),
              const SizedBox(height: 12),
              DateField(
                label: 'Due date',
                value: _due,
                firstDate: DateTime.now(),
                onChanged: (d) => setState(() => _due = d),
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _busy ? null : _generate,
                icon: const Icon(Icons.auto_awesome),
                label: Text(_busy ? 'Generating...' : 'Generate invoices'),
              ),
              if (_result != null) ...[
                const SizedBox(height: 16),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Done', style: TextStyle(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 6),
                        InfoRow('Created', '${_result!.created}'),
                        InfoRow('Already existed', '${_result!.skippedExisting}'),
                        InfoRow('No fee setup', '${_result!.skippedNoStructure}'),
                      ],
                    ),
                  ),
                ),
              ],
            ],
          ),
        );
      },
    );
  }
}

class _SummaryTab extends StatefulWidget {
  const _SummaryTab();

  @override
  State<_SummaryTab> createState() => _SummaryTabState();
}

class _SummaryTabState extends State<_SummaryTab> {
  late Future<List<ClassItem>> _classes;

  @override
  void initState() {
    super.initState();
    _classes = context.read<OpsApi>().classes();
  }

  @override
  Widget build(BuildContext context) {
    return FutureView<List<ClassItem>>(
      future: _classes,
      onRetry: () => setState(() => _classes = context.read<OpsApi>().classes()),
      builder: (ctx, classes) => _SummaryBody(classes: classes),
    );
  }
}

class _SummaryBody extends StatefulWidget {
  const _SummaryBody({required this.classes});

  final List<ClassItem> classes;

  @override
  State<_SummaryBody> createState() => _SummaryBodyState();
}

class _SummaryBodyState extends State<_SummaryBody> {
  late Future<FeeSummary> _future;
  String? _classId;
  String _period = '';

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<FeeSummary> _load() => context
      .read<OpsApi>()
      .feeSummary(classId: _classId, periodLabel: _period.trim().isEmpty ? null : _period.trim());

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    return ContentWidth(
      maxWidth: 720,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          PickerField<String?>(
            label: 'Class',
            value: _classId,
            items: [
              const DropdownMenuItem<String?>(value: null, child: Text('All classes')),
              for (final c in widget.classes) DropdownMenuItem<String?>(value: c.id, child: Text(c.name)),
            ],
            onChanged: (v) {
              _classId = v;
              _reload();
            },
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: TextField(
                  decoration: const InputDecoration(
                    labelText: 'Period (optional)',
                    border: OutlineInputBorder(),
                    isDense: true,
                  ),
                  onChanged: (v) => _period = v,
                  onSubmitted: (_) => _reload(),
                ),
              ),
              IconButton(tooltip: 'Show', icon: const Icon(Icons.search), onPressed: _reload),
            ],
          ),
          const SizedBox(height: 16),
          FutureBuilder<FeeSummary>(
            future: _future,
            builder: (ctx, snap) {
              if (snap.connectionState != ConnectionState.done) {
                return const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator()));
              }
              if (snap.hasError) return ErrorView(error: snap.error!, onRetry: _reload);
              final s = snap.data!;
              return GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisSpacing: 8,
                mainAxisSpacing: 8,
                childAspectRatio: 2.2,
                children: [
                  StatCard(label: 'Billed', value: fmtMoney(s.billed)),
                  StatCard(label: 'Collected', value: fmtMoney(s.collected), color: Colors.green.shade700),
                  StatCard(label: 'Outstanding', value: fmtMoney(s.outstanding), color: Colors.orange.shade800),
                  StatCard(label: 'Overdue', value: fmtMoney(s.overdue), color: Colors.red.shade700),
                  StatCard(label: 'Invoices', value: '${s.invoiceCount}'),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _SetupTab extends StatefulWidget {
  const _SetupTab();

  @override
  State<_SetupTab> createState() => _SetupTabState();
}

class _SetupTabState extends State<_SetupTab> {
  late Future<List<FeeHead>> _heads;
  late Future<List<ClassItem>> _classes;
  Future<List<FeeStructure>>? _structures;
  String? _classId;

  @override
  void initState() {
    super.initState();
    final api = context.read<OpsApi>();
    _heads = api.feeHeads();
    _classes = api.classes();
  }

  void _reloadHeads() => setState(() => _heads = context.read<OpsApi>().feeHeads());

  void _reloadStructures() {
    setState(() {
      _structures = _classId == null ? null : context.read<OpsApi>().feeStructures(classId: _classId);
    });
  }

  Future<void> _headForm({FeeHead? existing}) async {
    final api = context.read<OpsApi>();
    var name = existing?.name ?? '';
    var frequency = existing?.frequency ?? 'monthly';
    final saved = await showFormDialog(
      context,
      title: existing == null ? 'New fee head' : 'Edit fee head',
      builder: (ctx, set) => Column(
        mainAxisSize: MainAxisSize.min,
        children: spaced([
          formText('Name', name, (v) => name = v, hint: 'For example Tuition Fee'),
          pickString('How often', frequency, _frequencies, (v) => set(() => frequency = v ?? frequency)),
        ]),
      ),
      validate: () => Validators.minLength(name, 2, 'Name') ?? Validators.maxLength(name, 100, 'Name'),
      onSubmit: () {
        final body = <String, dynamic>{'name': name.trim(), 'frequency': frequency};
        return existing == null ? api.createFeeHead(body) : api.updateFeeHead(existing.id, body);
      },
    );
    if (saved) _reloadHeads();
  }

  Future<void> _toggleHead(FeeHead head) async {
    final ok = await runAction(
      context,
      () => context.read<OpsApi>().updateFeeHead(head.id, <String, dynamic>{'is_active': !head.isActive}),
    );
    if (ok) _reloadHeads();
  }

  Future<void> _structureForm(List<FeeHead> heads, {FeeStructure? existing}) async {
    final api = context.read<OpsApi>();
    final active = heads.where((h) => h.isActive || h.id == existing?.feeHeadId).toList();
    if (active.isEmpty) {
      showMessage(context, 'Create a fee head first', error: true);
      return;
    }
    String? headId = existing?.feeHeadId;
    var amount = existing == null ? '' : fmtNum(existing.amount);
    final saved = await showFormDialog(
      context,
      title: existing == null ? 'Add fee to class' : 'Change amount',
      builder: (ctx, set) => Column(
        mainAxisSize: MainAxisSize.min,
        children: spaced([
          if (existing == null)
            pickString('Fee head', headId, [for (final h in active) MapEntry(h.id, '${h.name} (${titleCase(h.frequency)})')],
                (v) => set(() => headId = v)),
          formText('Amount (Rs)', amount, (v) => amount = v, number: true),
        ]),
      ),
      validate: () {
        if (existing == null && headId == null) return 'Choose a fee head';
        return Validators.positiveAmount(amount);
      },
      onSubmit: () {
        final value = Validators.parseNumber(amount);
        if (existing == null) {
          return api.createFeeStructure(<String, dynamic>{
            'class_id': _classId,
            'fee_head_id': headId,
            'amount': value,
          });
        }
        return api.updateFeeStructure(existing.id, <String, dynamic>{'amount': value});
      },
    );
    if (saved) _reloadStructures();
  }

  Future<void> _deleteStructure(FeeStructure s, String headName) async {
    final ok = await confirmDialog(context, 'Remove fee?', '$headName will no longer be billed for this class.', yes: 'Remove');
    if (!ok || !mounted) return;
    final done = await runAction(context, () => context.read<OpsApi>().deleteFeeStructure(s.id));
    if (done) _reloadStructures();
  }

  @override
  Widget build(BuildContext context) {
    return ContentWidth(
      maxWidth: 720,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              const Expanded(child: Text('Fee heads', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700))),
              FilledButton.icon(onPressed: () => _headForm(), icon: const Icon(Icons.add), label: const Text('Add')),
            ],
          ),
          const SizedBox(height: 8),
          FutureView<List<FeeHead>>(
            future: _heads,
            onRetry: _reloadHeads,
            builder: (ctx, heads) {
              if (heads.isEmpty) return const EmptyView('No fee heads yet');
              return Column(
                children: [
                  for (final h in heads)
                    Card(
                      child: ListTile(
                        title: Text(h.name),
                        subtitle: Text(titleCase(h.frequency) + (h.isActive ? '' : '  |  Inactive')),
                        trailing: PopupMenuButton<String>(
                          onSelected: (v) => v == 'edit' ? _headForm(existing: h) : _toggleHead(h),
                          itemBuilder: (_) => [
                            const PopupMenuItem(value: 'edit', child: Text('Edit')),
                            PopupMenuItem(value: 'toggle', child: Text(h.isActive ? 'Deactivate' : 'Activate')),
                          ],
                        ),
                      ),
                    ),
                ],
              );
            },
          ),
          const SizedBox(height: 24),
          const Text('Fees per class', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          FutureView<List<ClassItem>>(
            future: _classes,
            onRetry: () => setState(() => _classes = context.read<OpsApi>().classes()),
            builder: (ctx, classes) => pickString(
              'Class',
              _classId,
              [for (final c in classes) MapEntry(c.id, c.name)],
              (v) {
                _classId = v;
                _reloadStructures();
              },
            ),
          ),
          const SizedBox(height: 8),
          if (_structures != null)
            FutureView<List<FeeHead>>(
              future: _heads,
              onRetry: _reloadHeads,
              builder: (ctx, heads) => FutureView<List<FeeStructure>>(
                future: _structures!,
                onRetry: _reloadStructures,
                builder: (ctx2, structures) {
                  String nameOf(String id) {
                    for (final h in heads) {
                      if (h.id == id) return h.name;
                    }
                    return 'Fee';
                  }

                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Align(
                        alignment: Alignment.centerRight,
                        child: OutlinedButton.icon(
                          onPressed: () => _structureForm(heads),
                          icon: const Icon(Icons.add),
                          label: const Text('Add fee to this class'),
                        ),
                      ),
                      if (structures.isEmpty)
                        const Padding(padding: EdgeInsets.all(16), child: Text('No fees set for this class yet.')),
                      for (final s in structures)
                        Card(
                          child: ListTile(
                            title: Text(nameOf(s.feeHeadId)),
                            subtitle: Text(fmtMoney(s.amount)),
                            trailing: PopupMenuButton<String>(
                              onSelected: (v) => v == 'edit'
                                  ? _structureForm(heads, existing: s)
                                  : _deleteStructure(s, nameOf(s.feeHeadId)),
                              itemBuilder: (_) => const [
                                PopupMenuItem(value: 'edit', child: Text('Change amount')),
                                PopupMenuItem(value: 'delete', child: Text('Remove')),
                              ],
                            ),
                          ),
                        ),
                    ],
                  );
                },
              ),
            ),
        ],
      ),
    );
  }
}
