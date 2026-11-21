import '../../core/json.dart';

class FeeItem {
  FeeItem({required this.id, required this.description, required this.amount});
  final String id;
  final String description;
  final double amount;

  factory FeeItem.fromJson(Map<String, dynamic> j) =>
      FeeItem(id: asStr(j['id']), description: asStr(j['description']), amount: asDouble(j['amount']));
}

class FeePayment {
  FeePayment({
    required this.id,
    required this.receiptNo,
    required this.amount,
    required this.paymentDate,
    required this.method,
    this.reference,
    this.remarks,
    this.recordedByName,
    required this.isReversal,
    required this.isReversed,
  });
  final String id;
  final String receiptNo;
  final double amount;
  final DateTime? paymentDate;
  final String method;
  final String? reference;
  final String? remarks;
  final String? recordedByName;
  final bool isReversal;
  final bool isReversed;

  factory FeePayment.fromJson(Map<String, dynamic> j) => FeePayment(
        id: asStr(j['id']),
        receiptNo: asStr(j['receipt_no']),
        amount: asDouble(j['amount']),
        paymentDate: asDateN(j['payment_date']),
        method: asStr(j['method']),
        reference: asStrN(j['reference']),
        remarks: asStrN(j['remarks']),
        recordedByName: asStrN(j['recorded_by_name']),
        isReversal: asBool(j['is_reversal']),
        isReversed: asBool(j['is_reversed']),
      );
}

class FeeInvoice {
  FeeInvoice({
    required this.id,
    required this.invoiceNo,
    required this.studentId,
    required this.studentName,
    required this.rollNo,
    required this.sectionLabel,
    required this.periodLabel,
    required this.issueDate,
    required this.dueDate,
    required this.total,
    required this.discount,
    required this.net,
    required this.paid,
    required this.balance,
    required this.status,
    required this.items,
    required this.payments,
  });
  final String id;
  final String invoiceNo;
  final String studentId;
  final String studentName;
  final String rollNo;
  final String sectionLabel;
  final String periodLabel;
  final DateTime? issueDate;
  final DateTime? dueDate;
  final double total;
  final double discount;
  final double net;
  final double paid;
  final double balance;
  final String status;
  final List<FeeItem> items;
  final List<FeePayment> payments;

  factory FeeInvoice.fromJson(Map<String, dynamic> j) => FeeInvoice(
        id: asStr(j['id']),
        invoiceNo: asStr(j['invoice_no']),
        studentId: asStr(j['student_id']),
        studentName: asStr(j['student_name']),
        rollNo: asStr(j['roll_no']),
        sectionLabel: asStr(j['section_label']),
        periodLabel: asStr(j['period_label']),
        issueDate: asDateN(j['issue_date']),
        dueDate: asDateN(j['due_date']),
        total: asDouble(j['total_amount']),
        discount: asDouble(j['discount_amount']),
        net: asDouble(j['net_amount']),
        paid: asDouble(j['paid_amount']),
        balance: asDouble(j['balance']),
        status: asStr(j['status'], 'unpaid'),
        items: asMapList(j['items']).map(FeeItem.fromJson).toList(),
        payments: asMapList(j['payments']).map(FeePayment.fromJson).toList(),
      );
}

class FeeHead {
  FeeHead({required this.id, required this.name, required this.frequency, required this.isActive});
  final String id;
  final String name;
  final String frequency;
  final bool isActive;

  factory FeeHead.fromJson(Map<String, dynamic> j) => FeeHead(
        id: asStr(j['id']),
        name: asStr(j['name']),
        frequency: asStr(j['frequency']),
        isActive: asBool(j['is_active'], true),
      );
}

class FeeStructure {
  FeeStructure({
    required this.id,
    required this.classId,
    required this.className,
    required this.feeHeadId,
    required this.feeHeadName,
    required this.frequency,
    required this.amount,
  });
  final String id;
  final String classId;
  final String className;
  final String feeHeadId;
  final String feeHeadName;
  final String frequency;
  final double amount;

  factory FeeStructure.fromJson(Map<String, dynamic> j) => FeeStructure(
        id: asStr(j['id']),
        classId: asStr(j['class_id']),
        className: asStr(j['class_name']),
        feeHeadId: asStr(j['fee_head_id']),
        feeHeadName: asStr(j['fee_head_name']),
        frequency: asStr(j['frequency']),
        amount: asDouble(j['amount']),
      );
}

const List<String> kFeeFrequencies = ['monthly', 'quarterly', 'yearly', 'one_time'];
const List<String> kPaymentMethods = ['cash', 'bank_transfer', 'cheque', 'other'];
const List<String> kInvoiceStatuses = ['unpaid', 'partial', 'paid', 'overdue', 'cancelled'];

/// Rounds to two decimals so the API's `decimal_places=2` rule is never tripped by float noise.
double round2(double v) => double.parse(v.toStringAsFixed(2));
