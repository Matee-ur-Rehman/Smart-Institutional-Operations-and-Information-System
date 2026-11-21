import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/lookups.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import 'fee_invoice_dialogs.dart';
import 'fee_models.dart';

/// Admin fee management (web): overview, invoices, fee structures and fee heads.
class FeesAdminPage extends StatelessWidget {
  const FeesAdminPage({super.key});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 4,
      child: PageFrame(
        title: 'Fee Management',
        subtitle: 'Invoices, payments and fee structures',
        child: Column(children: const [
          Align(
            alignment: Alignment.centerLeft,
            child: TabBar(
              isScrollable: true,
              tabAlignment: TabAlignment.start,
              tabs: [Tab(text: 'Overview'), Tab(text: 'Invoices'), Tab(text: 'Fee structure'), Tab(text: 'Fee heads')],
            ),
          ),
          SizedBox(height: 12),
          Expanded(child: TabBarView(children: [_OverviewTab(), _InvoicesTab(), _StructuresTab(), _HeadsTab()])),
        ]),
      ),
    );
  }
}

// ------------------------------------------------------------------ overview
class _OverviewTab extends StatelessWidget {
  const _OverviewTab();

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return AsyncView<Map<String, dynamic>>(
      loader: () async => asMap(await api.get('/fee-summary')),
      builder: (context, s, reload) {
        final byClass = asMapList(s['by_class']);
        final byStatus = asMap(s['by_status']);
        final rate = asDouble(s['collection_rate']);
        final cards = <Widget>[
          KpiCard(label: 'Total billed', value: formatMoney(asDouble(s['billed'])), icon: Icons.receipt_long, color: Brand.info),
          KpiCard(label: 'Collected', value: formatMoney(asDouble(s['collected'])), icon: Icons.account_balance_wallet, color: Brand.success),
          KpiCard(label: 'Outstanding', value: formatMoney(asDouble(s['outstanding'])), icon: Icons.hourglass_bottom, color: Brand.warning),
          KpiCard(label: 'Overdue', value: formatMoney(asDouble(s['overdue'])), icon: Icons.warning_amber, color: Brand.danger),
        ];
        return RefreshIndicator(
          onRefresh: reload,
          child: ListView(children: [
            _grid(cards),
            const SizedBox(height: 12),
            AppCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Collection rate: ${formatPercent(rate)} of ${asInt(s['invoices'])} invoices',
                    style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                LinearProgressIndicator(value: (rate / 100).clamp(0.0, 1.0).toDouble(), minHeight: 8, borderRadius: BorderRadius.circular(8)),
                const SizedBox(height: 10),
                Wrap(spacing: 8, runSpacing: 6, children: [
                  for (final e in byStatus.entries) Chip(label: Text('${humanize(e.key)}: ${asInt(e.value)}')),
                ]),
              ]),
            ),
            const SectionTitle('By class'),
            if (byClass.isEmpty)
              const AppCard(child: Text('No invoices generated yet. Use the Invoices tab to generate them.', style: TextStyle(color: Brand.muted))),
            for (final c in byClass) _classRow(c),
            const SectionTitle('Defaulters — overdue invoices'),
            _OverdueList(api: api),
          ]),
        );
      },
    );
  }

  Widget _grid(List<Widget> cards) => LayoutBuilder(builder: (context, c) {
        final cols = c.maxWidth >= 900 ? 4 : (c.maxWidth >= 560 ? 2 : 1);
        final w = (c.maxWidth - 12 * (cols - 1)) / cols;
        return Wrap(spacing: 12, runSpacing: 12, children: [for (final k in cards) SizedBox(width: w, child: k)]);
      });

  Widget _classRow(Map<String, dynamic> c) {
    final billed = asDouble(c['billed']);
    final collected = asDouble(c['collected']);
    final pct = billed > 0 ? (collected / billed).clamp(0.0, 1.0).toDouble() : 0.0;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: AppCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(asStr(c['class_name']), style: const TextStyle(fontWeight: FontWeight.w700))),
            Text('${asInt(c['invoices'])} invoices', style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
          ]),
          const SizedBox(height: 6),
          LinearProgressIndicator(value: pct, minHeight: 6, borderRadius: BorderRadius.circular(6)),
          const SizedBox(height: 6),
          Wrap(spacing: 16, runSpacing: 4, children: [
            Text('Billed ${formatMoney(billed)}'),
            Text('Collected ${formatMoney(collected)}', style: const TextStyle(color: Brand.success)),
            Text('Outstanding ${formatMoney(asDouble(c['outstanding']))}', style: const TextStyle(color: Brand.warning)),
            Text('Overdue ${formatMoney(asDouble(c['overdue']))}', style: const TextStyle(color: Brand.danger)),
          ]),
        ]),
      ),
    );
  }
}

class _OverdueList extends StatefulWidget {
  const _OverdueList({required this.api});
  final ApiClient api;

  @override
  State<_OverdueList> createState() => _OverdueListState();
}

class _OverdueListState extends State<_OverdueList> {
  int _rev = 0;

  @override
  Widget build(BuildContext context) {
    return AsyncView<PageResult<FeeInvoice>>(
      loadKey: _rev,
      loader: () async => PageResult<FeeInvoice>.fromJson(
          await widget.api.get('/fee-invoices', query: {'status': 'overdue', 'page_size': 10}), FeeInvoice.fromJson),
      builder: (context, page, reload) {
        if (page.items.isEmpty) {
          return const AppCard(child: Text('No overdue invoices. 🎉', style: TextStyle(color: Brand.muted)));
        }
        return Column(children: [
          for (final inv in page.items)
            InvoiceTile(
              invoice: inv,
              onTap: () async {
                final changed = await showInvoiceDetail(context, invoiceId: inv.id, isAdmin: true);
                if (changed && mounted) setState(() => _rev++);
              },
            ),
          if (page.total > page.items.length)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('Showing ${page.items.length} of ${page.total} overdue invoices — filter by "Overdue" in the Invoices tab.',
                  style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
            ),
        ]);
      },
    );
  }
}

// ------------------------------------------------------------------ invoices
class _InvoicesTab extends StatefulWidget {
  const _InvoicesTab();

  @override
  State<_InvoicesTab> createState() => _InvoicesTabState();
}

class _InvoicesTabState extends State<_InvoicesTab> {
  int _page = 1;
  String? _status;
  String? _sectionId;
  String _period = '';
  int _rev = 0;
  final _periodCtl = TextEditingController();
  final _debounce = Debouncer();

  @override
  void dispose() {
    _periodCtl.dispose();
    _debounce.dispose();
    super.dispose();
  }

  Future<void> _generate() async {
    final ok = await showAppDialog<bool>(context, title: 'Generate invoices', builder: (ctx) => const _GenerateForm());
    if (ok == true && mounted) setState(() => _rev++);
  }

  Future<void> _single() async {
    final ok = await showAppDialog<bool>(context, title: 'New invoice', builder: (ctx) => const _SingleInvoiceForm());
    if (ok == true && mounted) setState(() => _rev++);
  }

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    final lookups = context.read<Lookups>();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Align(
        alignment: Alignment.centerLeft,
        child: Wrap(spacing: 8, runSpacing: 8, children: [
          FilledButton.icon(onPressed: _generate, icon: const Icon(Icons.auto_awesome), label: const Text('Generate invoices')),
          OutlinedButton.icon(onPressed: _single, icon: const Icon(Icons.add), label: const Text('Single invoice')),
        ]),
      ),
      const SizedBox(height: 12),
      FutureBuilder<List<SectionRef>>(
        future: lookups.sections(all: true),
        builder: (context, snap) {
          final sections = snap.data ?? const <SectionRef>[];
          return FilterBar(children: [
            AppDropdown<String>(
              label: 'Status',
              value: _status,
              allowClear: true,
              hint: 'All statuses',
              items: [for (final s in kInvoiceStatuses) DropdownMenuItem<String>(value: s, child: Text(humanize(s)))],
              onChanged: (v) => setState(() {
                _status = v;
                _page = 1;
              }),
            ),
            AppDropdown<String>(
              label: 'Section',
              value: _sectionId,
              allowClear: true,
              hint: 'All sections',
              items: [for (final s in sections) DropdownMenuItem<String>(value: s.id, child: Text(s.label))],
              onChanged: (v) => setState(() {
                _sectionId = v;
                _page = 1;
              }),
            ),
            TextField(
              controller: _periodCtl,
              decoration: const InputDecoration(labelText: 'Period (exact label)', prefixIcon: Icon(Icons.filter_alt_outlined)),
              onChanged: (v) => _debounce.run(() {
                if (mounted) {
                  setState(() {
                    _period = v.trim();
                    _page = 1;
                  });
                }
              }),
            ),
          ]);
        },
      ),
      Expanded(
        child: AsyncView<PageResult<FeeInvoice>>(
          loadKey: '$_page|$_status|$_sectionId|$_period|$_rev',
          loader: () async => PageResult<FeeInvoice>.fromJson(
              await api.get('/fee-invoices', query: {
                'page': _page,
                'page_size': 20,
                'status': _status,
                'section_id': _sectionId,
                'period_label': _period,
              }),
              FeeInvoice.fromJson),
          builder: (context, res, reload) {
            if (res.items.isEmpty) {
              return const EmptyState(icon: Icons.receipt_long, title: 'No invoices found', message: 'Change the filters or generate invoices for a section.');
            }
            return Column(children: [
              Expanded(
                child: RefreshIndicator(
                  onRefresh: reload,
                  child: ListView(children: [
                    for (final inv in res.items)
                      InvoiceTile(
                        invoice: inv,
                        onTap: () async {
                          final changed = await showInvoiceDetail(context, invoiceId: inv.id, isAdmin: true);
                          if (changed && mounted) setState(() => _rev++);
                        },
                      ),
                  ]),
                ),
              ),
              PaginationBar(page: res.page, pageSize: res.pageSize, total: res.total, onPage: (p) => setState(() => _page = p)),
            ]);
          },
        ),
      ),
    ]);
  }
}

class _GenerateForm extends StatefulWidget {
  const _GenerateForm();

  @override
  State<_GenerateForm> createState() => _GenerateFormState();
}

class _GenerateFormState extends State<_GenerateForm> with BusyMixin {
  final _key = GlobalKey<FormState>();
  final _period = TextEditingController(text: formatMonthYear(DateTime.now()));
  String _target = 'section';
  String? _sectionId;
  String? _classId;
  DateTime? _due = dateOnly(DateTime.now().add(const Duration(days: 15)));

  @override
  void dispose() {
    _period.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_key.currentState?.validate() ?? false)) return;
    final id = _target == 'section' ? _sectionId : _classId;
    if (id == null) {
      showSnack(context, 'Please select a ${_target == 'section' ? 'section' : 'class'}.', error: true);
      return;
    }
    if (_due == null) {
      showSnack(context, 'Please choose a due date.', error: true);
      return;
    }
    final api = context.read<ApiClient>();
    Map<String, dynamic> result = <String, dynamic>{};
    final ok = await runBusy(() async {
      result = asMap(await api.post('/fee-invoices/generate', body: {
        _target == 'section' ? 'section_id' : 'class_id': id,
        'period_label': _period.text.trim(),
        'due_date': isoDate(_due!),
      }));
    });
    if (!ok || !mounted) return;
    final msg = 'Created ${asInt(result['created'])} invoice(s); '
        '${asInt(result['skipped_existing'])} already existed; '
        '${asInt(result['skipped_no_structure'])} had no fee structure.';
    // The dialog is about to close: keep the messenger of the page that opened it and report through that.
    final messenger = ScaffoldMessenger.of(context);
    Navigator.pop(context, true);
    messenger.showSnackBar(SnackBar(content: Text(msg), duration: const Duration(seconds: 6)));
  }

  @override
  Widget build(BuildContext context) {
    final lookups = context.read<Lookups>();
    return Form(
      key: _key,
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('Invoices are built from the fee structure of each student\'s class. Existing invoices for the same period are skipped.',
            style: TextStyle(color: Brand.muted)),
        const SizedBox(height: 12),
        AppDropdown<String>(
          label: 'Generate for',
          value: _target,
          items: const [
            DropdownMenuItem<String>(value: 'section', child: Text('One section')),
            DropdownMenuItem<String>(value: 'class', child: Text('Whole class (all sections)')),
          ],
          onChanged: (v) => setState(() => _target = v ?? 'section'),
        ),
        const SizedBox(height: 12),
        if (_target == 'section')
          FutureBuilder<List<SectionRef>>(
            future: lookups.sections(all: true),
            builder: (context, snap) => AppDropdown<String>(
              label: 'Section',
              value: _sectionId,
              items: [for (final s in snap.data ?? const <SectionRef>[]) DropdownMenuItem<String>(value: s.id, child: Text(s.label))],
              onChanged: (v) => setState(() => _sectionId = v),
            ),
          )
        else
          FutureBuilder<List<ClassRef>>(
            future: lookups.classes(),
            builder: (context, snap) => AppDropdown<String>(
              label: 'Class',
              value: _classId,
              items: [for (final c in snap.data ?? const <ClassRef>[]) DropdownMenuItem<String>(value: c.id, child: Text(c.name))],
              onChanged: (v) => setState(() => _classId = v),
            ),
          ),
        const SizedBox(height: 12),
        TextFormField(
          controller: _period,
          maxLength: 30,
          decoration: const InputDecoration(labelText: 'Period label', hintText: 'e.g. November 2026'),
          validator: (v) => (v ?? '').trim().length < 3 ? 'Enter a period label (at least 3 characters)' : null,
        ),
        DateField(label: 'Due date', value: _due, onChanged: (d) => setState(() => _due = d)),
        const SizedBox(height: 16),
        FilledButton(onPressed: busy ? null : _submit, child: Text(busy ? 'Generating…' : 'Generate')),
      ]),
    );
  }
}

class _SingleInvoiceForm extends StatefulWidget {
  const _SingleInvoiceForm();

  @override
  State<_SingleInvoiceForm> createState() => _SingleInvoiceFormState();
}

class _SingleInvoiceFormState extends State<_SingleInvoiceForm> with BusyMixin {
  final _key = GlobalKey<FormState>();
  final _period = TextEditingController(text: formatMonthYear(DateTime.now()));
  final _discount = TextEditingController(text: '0');
  StudentRef? _student;
  DateTime? _due = dateOnly(DateTime.now().add(const Duration(days: 15)));

  @override
  void dispose() {
    _period.dispose();
    _discount.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_key.currentState?.validate() ?? false)) return;
    if (_student == null || _due == null) {
      showSnack(context, 'Select a student and a due date.', error: true);
      return;
    }
    final api = context.read<ApiClient>();
    final ok = await runBusy(() async {
      await api.post('/fee-invoices', body: {
        'student_id': _student!.id,
        'period_label': _period.text.trim(),
        'due_date': isoDate(_due!),
        'discount_amount': round2(double.tryParse(_discount.text.trim()) ?? 0),
      });
    }, success: 'Invoice created from the fee structure');
    if (ok && mounted) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _key,
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        StudentPickerField(onSelected: (s) => _student = s),
        const SizedBox(height: 12),
        TextFormField(
          controller: _period,
          maxLength: 30,
          decoration: const InputDecoration(labelText: 'Period label'),
          validator: (v) => (v ?? '').trim().length < 3 ? 'Enter a period label (at least 3 characters)' : null,
        ),
        DateField(label: 'Due date', value: _due, onChanged: (d) => setState(() => _due = d)),
        const SizedBox(height: 12),
        TextFormField(
          controller: _discount,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: const InputDecoration(labelText: 'Discount (PKR)'),
          validator: (v) {
            final n = double.tryParse((v ?? '').trim());
            return (n == null || n < 0) ? 'Enter 0 or a positive amount' : null;
          },
        ),
        const SizedBox(height: 16),
        FilledButton(onPressed: busy ? null : _submit, child: Text(busy ? 'Saving…' : 'Create invoice')),
      ]),
    );
  }
}

// ------------------------------------------------------------------ structures
class _StructuresTab extends StatefulWidget {
  const _StructuresTab();

  @override
  State<_StructuresTab> createState() => _StructuresTabState();
}

class _StructuresTabState extends State<_StructuresTab> {
  String? _classId;
  int _rev = 0;

  Future<void> _add() async {
    final ok = await showAppDialog<bool>(context, title: 'Add fee to class', builder: (ctx) => _StructureForm(classId: _classId));
    if (ok == true && mounted) setState(() => _rev++);
  }

  Future<void> _edit(FeeStructure s) async {
    final ok = await showAppDialog<bool>(context, title: 'Edit amount', builder: (ctx) => _StructureForm(existing: s));
    if (ok == true && mounted) setState(() => _rev++);
  }

  Future<void> _delete(FeeStructure s) async {
    final yes = await confirmDialog(context,
        title: 'Remove fee?',
        message: '${s.feeHeadName} will be removed from ${s.className}. Existing invoices are not affected.',
        confirmLabel: 'Remove',
        destructive: true);
    if (!yes || !mounted) return;
    try {
      await context.read<ApiClient>().delete('/fee-structures/${s.id}');
      if (!mounted) return;
      showSnack(context, 'Fee removed');
      setState(() => _rev++);
    } catch (e) {
      if (mounted) showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    final lookups = context.read<Lookups>();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Align(
        alignment: Alignment.centerLeft,
        child: FilledButton.icon(onPressed: _add, icon: const Icon(Icons.add), label: const Text('Add fee to a class')),
      ),
      const SizedBox(height: 12),
      FutureBuilder<List<ClassRef>>(
        future: lookups.classes(),
        builder: (context, snap) => FilterBar(children: [
          AppDropdown<String>(
            label: 'Class',
            value: _classId,
            allowClear: true,
            hint: 'All classes',
            items: [for (final c in snap.data ?? const <ClassRef>[]) DropdownMenuItem<String>(value: c.id, child: Text(c.name))],
            onChanged: (v) => setState(() => _classId = v),
          ),
        ]),
      ),
      Expanded(
        child: AsyncView<List<FeeStructure>>(
          loadKey: '$_classId|$_rev',
          loader: () async => parseList(await api.get('/fee-structures', query: {'class_id': _classId}), FeeStructure.fromJson),
          builder: (context, rows, reload) {
            if (rows.isEmpty) {
              return const EmptyState(icon: Icons.price_change_outlined, title: 'No fee structure yet', message: 'Add fee heads and amounts per class; invoices are generated from them.');
            }
            return RefreshIndicator(
              onRefresh: reload,
              child: ListView(children: [
                for (final s in rows)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: AppCard(
                      child: Row(children: [
                        Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text(s.feeHeadName, style: const TextStyle(fontWeight: FontWeight.w700)),
                            Text('${s.className} · ${humanize(s.frequency)}', style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
                          ]),
                        ),
                        Text(formatMoney(s.amount), style: const TextStyle(fontWeight: FontWeight.w700)),
                        IconButton(tooltip: 'Edit amount', icon: const Icon(Icons.edit_outlined), onPressed: () => _edit(s)),
                        IconButton(tooltip: 'Remove', icon: const Icon(Icons.delete_outline, color: Brand.danger), onPressed: () => _delete(s)),
                      ]),
                    ),
                  ),
              ]),
            );
          },
        ),
      ),
    ]);
  }
}

class _StructureForm extends StatefulWidget {
  const _StructureForm({this.existing, this.classId});
  final FeeStructure? existing;
  final String? classId;

  @override
  State<_StructureForm> createState() => _StructureFormState();
}

class _StructureFormState extends State<_StructureForm> with BusyMixin {
  final _key = GlobalKey<FormState>();
  late final TextEditingController _amount;
  String? _classId;
  String? _headId;
  late final Future<dynamic> _heads;

  @override
  void initState() {
    super.initState();
    _heads = widget.existing == null ? context.read<ApiClient>().get('/fee-heads', query: {'active_only': true}) : Future<dynamic>.value(<dynamic>[]);
    _classId = widget.classId;
    _amount = TextEditingController(text: widget.existing == null ? '' : widget.existing!.amount.toStringAsFixed(2));
  }

  @override
  void dispose() {
    _amount.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_key.currentState?.validate() ?? false)) return;
    final api = context.read<ApiClient>();
    final amount = round2(double.parse(_amount.text.trim()));
    final ex = widget.existing;
    if (ex == null && (_classId == null || _headId == null)) {
      showSnack(context, 'Select a class and a fee head.', error: true);
      return;
    }
    final ok = await runBusy(() async {
      if (ex == null) {
        await api.post('/fee-structures', body: {'class_id': _classId, 'fee_head_id': _headId, 'amount': amount});
      } else {
        await api.patch('/fee-structures/${ex.id}', body: {'amount': amount});
      }
    }, success: 'Saved');
    if (ok && mounted) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    final lookups = context.read<Lookups>();
    final ex = widget.existing;
    return Form(
      key: _key,
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (ex != null)
          Padding(padding: const EdgeInsets.only(bottom: 12), child: Text('${ex.feeHeadName} · ${ex.className}', style: const TextStyle(fontWeight: FontWeight.w600)))
        else ...[
          FutureBuilder<List<ClassRef>>(
            future: lookups.classes(),
            builder: (context, snap) => AppDropdown<String>(
              label: 'Class',
              value: _classId,
              items: [for (final c in snap.data ?? const <ClassRef>[]) DropdownMenuItem<String>(value: c.id, child: Text(c.name))],
              onChanged: (v) => setState(() => _classId = v),
            ),
          ),
          const SizedBox(height: 12),
          FutureBuilder<dynamic>(
            future: _heads,
            builder: (context, snap) {
              final heads = parseList(snap.data, FeeHead.fromJson);
              return AppDropdown<String>(
                label: 'Fee head',
                value: _headId,
                items: [for (final h in heads) DropdownMenuItem<String>(value: h.id, child: Text('${h.name} (${humanize(h.frequency)})'))],
                onChanged: (v) => setState(() => _headId = v),
              );
            },
          ),
          const SizedBox(height: 12),
        ],
        TextFormField(
          controller: _amount,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: const InputDecoration(labelText: 'Amount (PKR)'),
          validator: (v) {
            final n = double.tryParse((v ?? '').trim());
            if (n == null || n <= 0) return 'Enter an amount greater than zero';
            if (n > 10000000) return 'Amount is too large';
            return null;
          },
        ),
        const SizedBox(height: 16),
        FilledButton(onPressed: busy ? null : _submit, child: Text(busy ? 'Saving…' : 'Save')),
      ]),
    );
  }
}

// ------------------------------------------------------------------ heads
class _HeadsTab extends StatefulWidget {
  const _HeadsTab();

  @override
  State<_HeadsTab> createState() => _HeadsTabState();
}

class _HeadsTabState extends State<_HeadsTab> {
  int _rev = 0;

  Future<void> _add() async {
    final ok = await showAppDialog<bool>(context, title: 'New fee head', builder: (ctx) => const _HeadForm());
    if (ok == true && mounted) setState(() => _rev++);
  }

  Future<void> _toggle(FeeHead h) async {
    try {
      await context.read<ApiClient>().patch('/fee-heads/${h.id}', body: {'is_active': !h.isActive});
      if (mounted) setState(() => _rev++);
    } catch (e) {
      if (mounted) showError(context, e);
    }
  }

  Future<void> _delete(FeeHead h) async {
    final yes = await confirmDialog(context,
        title: 'Delete fee head?', message: '"${h.name}" will be deleted. Heads already used by fee structures or invoices cannot be deleted; deactivate them instead.',
        confirmLabel: 'Delete', destructive: true);
    if (!yes || !mounted) return;
    try {
      await context.read<ApiClient>().delete('/fee-heads/${h.id}');
      if (!mounted) return;
      showSnack(context, 'Fee head deleted');
      setState(() => _rev++);
    } catch (e) {
      if (mounted) showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Align(alignment: Alignment.centerLeft, child: FilledButton.icon(onPressed: _add, icon: const Icon(Icons.add), label: const Text('New fee head'))),
      const SizedBox(height: 12),
      Expanded(
        child: AsyncView<List<FeeHead>>(
          loadKey: _rev,
          loader: () async => parseList(await api.get('/fee-heads'), FeeHead.fromJson),
          builder: (context, heads, reload) {
            if (heads.isEmpty) {
              return const EmptyState(icon: Icons.category_outlined, title: 'No fee heads', message: 'Create heads such as Tuition, Admission or Exam fee.');
            }
            return RefreshIndicator(
              onRefresh: reload,
              child: ListView(children: [
                for (final h in heads)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: AppCard(
                      child: Row(children: [
                        Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text(h.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                            Text(humanize(h.frequency), style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
                          ]),
                        ),
                        StatusChip(h.isActive ? 'active' : 'inactive', color: h.isActive ? Brand.success : Brand.muted),
                        const SizedBox(width: 8),
                        Switch(value: h.isActive, onChanged: (_) => _toggle(h)),
                        IconButton(tooltip: 'Delete', icon: const Icon(Icons.delete_outline, color: Brand.danger), onPressed: () => _delete(h)),
                      ]),
                    ),
                  ),
              ]),
            );
          },
        ),
      ),
    ]);
  }
}

class _HeadForm extends StatefulWidget {
  const _HeadForm();

  @override
  State<_HeadForm> createState() => _HeadFormState();
}

class _HeadFormState extends State<_HeadForm> with BusyMixin {
  final _key = GlobalKey<FormState>();
  final _name = TextEditingController();
  String _freq = 'monthly';

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_key.currentState?.validate() ?? false)) return;
    final api = context.read<ApiClient>();
    final ok = await runBusy(() async {
      await api.post('/fee-heads', body: {'name': _name.text.trim(), 'frequency': _freq});
    }, success: 'Fee head created');
    if (ok && mounted) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _key,
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        TextFormField(
          controller: _name,
          maxLength: 100,
          decoration: const InputDecoration(labelText: 'Name', hintText: 'e.g. Tuition fee'),
          validator: (v) => (v ?? '').trim().length < 2 ? 'Enter a name (at least 2 characters)' : null,
        ),
        AppDropdown<String>(
          label: 'Frequency',
          value: _freq,
          items: [for (final f in kFeeFrequencies) DropdownMenuItem<String>(value: f, child: Text(humanize(f)))],
          onChanged: (v) => setState(() => _freq = v ?? _freq),
        ),
        const SizedBox(height: 16),
        FilledButton(onPressed: busy ? null : _submit, child: Text(busy ? 'Saving…' : 'Create')),
      ]),
    );
  }
}
