import '../core/json_utils.dart';

/// Plain data classes that mirror the JSON returned by the backend (docs/API_CONTRACT.md).
/// Every `fromJson` is defensive: a missing field never throws.

class Paged<T> {
  const Paged({required this.items, required this.total, required this.page, required this.pageSize});

  final List<T> items;
  final int total;
  final int page;
  final int pageSize;

  bool get hasMore => page * pageSize < total;

  factory Paged.fromJson(dynamic json, T Function(Map<String, dynamic>) build) {
    final m = jMap(json);
    return Paged<T>(
      items: jMapList<T>(m['items'], build),
      total: jInt(m['total']),
      page: jInt(m['page'], 1),
      pageSize: jInt(m['page_size'], 20),
    );
  }
}

// ---------------------------------------------------------------- lookups

class ClassItem {
  const ClassItem({required this.id, required this.name, required this.gradeLevel});

  final String id;
  final String name;
  final int gradeLevel;

  factory ClassItem.fromJson(Map<String, dynamic> j) =>
      ClassItem(id: jStr(j['id']), name: jStr(j['name']), gradeLevel: jInt(j['grade_level']));
}

class SectionItem {
  const SectionItem({
    required this.id,
    required this.name,
    required this.classId,
    required this.className,
    required this.display,
  });

  final String id;
  final String name;
  final String classId;
  final String className;
  final String display;

  factory SectionItem.fromJson(Map<String, dynamic> j) => SectionItem(
        id: jStr(j['id']),
        name: jStr(j['name']),
        classId: jStr(j['class_id']),
        className: jStr(j['class_name']),
        display: jStr(j['display']),
      );
}

class SubjectItem {
  const SubjectItem({required this.id, required this.name, required this.code});

  final String id;
  final String name;
  final String code;

  factory SubjectItem.fromJson(Map<String, dynamic> j) =>
      SubjectItem(id: jStr(j['id']), name: jStr(j['name']), code: jStr(j['code']));
}

class TeacherItem {
  const TeacherItem({required this.id, required this.userId, required this.fullName, required this.employeeNo});

  final String id;
  final String userId;
  final String fullName;
  final String employeeNo;

  factory TeacherItem.fromJson(Map<String, dynamic> j) => TeacherItem(
        id: jStr(j['id']),
        userId: jStr(j['user_id']),
        fullName: jStr(j['full_name']),
        employeeNo: jStr(j['employee_no']),
      );
}

class StudentItem {
  const StudentItem({
    required this.id,
    required this.rollNo,
    required this.fullName,
    required this.sectionId,
    required this.sectionName,
  });

  final String id;
  final String rollNo;
  final String fullName;
  final String sectionId;
  final String sectionName;

  factory StudentItem.fromJson(Map<String, dynamic> j) => StudentItem(
        id: jStr(j['id']),
        rollNo: jStr(j['roll_no']),
        fullName: jStr(j['full_name']),
        sectionId: jStr(j['section_id']),
        sectionName: jStr(j['section_name']),
      );
}

class TeachingItem {
  const TeachingItem({
    required this.sectionId,
    required this.sectionName,
    required this.subjectId,
    required this.subjectName,
  });

  final String sectionId;
  final String sectionName;
  final String subjectId;
  final String subjectName;

  String get key => '$sectionId|$subjectId';

  factory TeachingItem.fromJson(Map<String, dynamic> j) => TeachingItem(
        sectionId: jStr(j['section_id']),
        sectionName: jStr(j['section_name']),
        subjectId: jStr(j['subject_id']),
        subjectName: jStr(j['subject_name']),
      );
}

// ---------------------------------------------------------------- homework

class Assignment {
  const Assignment({
    required this.id,
    required this.teacherName,
    required this.sectionId,
    required this.sectionName,
    required this.subjectId,
    required this.subjectName,
    required this.title,
    required this.description,
    required this.assignedDate,
    required this.dueDate,
    required this.maxMarks,
    required this.hasAttachment,
    required this.status,
  });

  final String id;
  final String teacherName;
  final String sectionId;
  final String sectionName;
  final String subjectId;
  final String subjectName;
  final String title;
  final String description;
  final DateTime assignedDate;
  final DateTime dueDate;
  final double? maxMarks;
  final bool hasAttachment;
  final String status;

  bool get isOverdue {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    return status == 'published' && dueDate.isBefore(today);
  }

  factory Assignment.fromJson(Map<String, dynamic> j) => Assignment(
        id: jStr(j['id']),
        teacherName: jStr(j['teacher_name']),
        sectionId: jStr(j['section_id']),
        sectionName: jStr(j['section_name']),
        subjectId: jStr(j['subject_id']),
        subjectName: jStr(j['subject_name']),
        title: jStr(j['title']),
        description: jStr(j['description']),
        assignedDate: jDate(j['assigned_date']),
        dueDate: jDate(j['due_date']),
        maxMarks: jNumN(j['max_marks']),
        hasAttachment: jBool(j['has_attachment']),
        status: jStr(j['status']),
      );
}

// ---------------------------------------------------------------- exams

class Exam {
  const Exam({
    required this.id,
    required this.name,
    required this.examType,
    required this.startDate,
    required this.endDate,
    required this.status,
  });

  final String id;
  final String name;
  final String examType;
  final DateTime startDate;
  final DateTime endDate;
  final String status;

  bool get resultsPublished => status == 'results_published';

  factory Exam.fromJson(Map<String, dynamic> j) => Exam(
        id: jStr(j['id']),
        name: jStr(j['name']),
        examType: jStr(j['exam_type']),
        startDate: jDate(j['start_date']),
        endDate: jDate(j['end_date']),
        status: jStr(j['status']),
      );
}

class ExamSchedule {
  const ExamSchedule({
    required this.id,
    required this.examId,
    required this.sectionId,
    required this.sectionName,
    required this.subjectId,
    required this.subjectName,
    required this.examDate,
    required this.startTime,
    required this.endTime,
    required this.room,
    required this.totalMarks,
    required this.passingMarks,
  });

  final String id;
  final String examId;
  final String sectionId;
  final String sectionName;
  final String subjectId;
  final String subjectName;
  final DateTime examDate;
  final String startTime;
  final String endTime;
  final String room;
  final double totalMarks;
  final double passingMarks;

  String get teachingKey => '$sectionId|$subjectId';

  factory ExamSchedule.fromJson(Map<String, dynamic> j) => ExamSchedule(
        id: jStr(j['id']),
        examId: jStr(j['exam_id']),
        sectionId: jStr(j['section_id']),
        sectionName: jStr(j['section_name']),
        subjectId: jStr(j['subject_id']),
        subjectName: jStr(j['subject_name']),
        examDate: jDate(j['exam_date']),
        startTime: jStr(j['start_time']),
        endTime: jStr(j['end_time']),
        room: jStr(j['room']),
        totalMarks: jNum(j['total_marks']),
        passingMarks: jNum(j['passing_marks']),
      );
}

class MarkRow {
  const MarkRow({
    required this.studentId,
    required this.rollNo,
    required this.studentName,
    required this.marksObtained,
    required this.isAbsent,
  });

  final String studentId;
  final String rollNo;
  final String studentName;
  final double? marksObtained;
  final bool isAbsent;

  factory MarkRow.fromJson(Map<String, dynamic> j) => MarkRow(
        studentId: jStr(j['student_id']),
        rollNo: jStr(j['roll_no']),
        studentName: jStr(j['student_name']),
        marksObtained: jNumN(j['marks_obtained']),
        isAbsent: jBool(j['is_absent']),
      );
}

class MarkSheet {
  const MarkSheet({required this.schedule, required this.examStatus, required this.rows});

  final ExamSchedule schedule;
  final String examStatus;
  final List<MarkRow> rows;

  bool get locked => examStatus == 'results_published';

  factory MarkSheet.fromJson(Map<String, dynamic> j) => MarkSheet(
        schedule: ExamSchedule.fromJson(jMap(j['schedule'])),
        examStatus: jStr(j['exam_status']),
        rows: jMapList<MarkRow>(j['rows'], MarkRow.fromJson),
      );
}

class GradeBand {
  const GradeBand({
    required this.grade,
    required this.minPercentage,
    required this.maxPercentage,
    required this.gpaPoints,
    required this.remark,
    required this.isPass,
  });

  final String grade;
  final double minPercentage;
  final double maxPercentage;
  final double? gpaPoints;
  final String remark;
  final bool isPass;

  factory GradeBand.fromJson(Map<String, dynamic> j) => GradeBand(
        grade: jStr(j['grade']),
        minPercentage: jNum(j['min_percentage']),
        maxPercentage: jNum(j['max_percentage']),
        gpaPoints: jNumN(j['gpa_points']),
        remark: jStr(j['remark']),
        isPass: jBool(j['is_pass'], true),
      );

  Map<String, dynamic> toJson() => <String, dynamic>{
        'grade': grade,
        'min_percentage': minPercentage,
        'max_percentage': maxPercentage,
        if (gpaPoints != null) 'gpa_points': gpaPoints,
        'remark': remark,
        'is_pass': isPass,
      };
}

class SubjectResult {
  const SubjectResult({
    required this.subjectName,
    required this.totalMarks,
    required this.passingMarks,
    required this.status,
    required this.marksObtained,
    required this.percentage,
    required this.grade,
    required this.passed,
  });

  final String subjectName;
  final double totalMarks;
  final double passingMarks;
  final String status; // entered | absent | pending
  final double? marksObtained;
  final double? percentage;
  final String? grade;
  final bool? passed;

  factory SubjectResult.fromJson(Map<String, dynamic> j) => SubjectResult(
        subjectName: jStr(j['subject_name']),
        totalMarks: jNum(j['total_marks']),
        passingMarks: jNum(j['passing_marks']),
        status: jStr(j['status']),
        marksObtained: jNumN(j['marks_obtained']),
        percentage: jNumN(j['percentage']),
        grade: jStrN(j['grade']),
        passed: j['passed'] is bool ? j['passed'] as bool : null,
      );
}

class ExamResult {
  const ExamResult({
    required this.studentId,
    required this.rollNo,
    required this.studentName,
    required this.subjects,
    required this.totalObtained,
    required this.totalMarks,
    required this.percentage,
    required this.grade,
    required this.remark,
    required this.complete,
    required this.passed,
    required this.position,
  });

  final String studentId;
  final String rollNo;
  final String studentName;
  final List<SubjectResult> subjects;
  final double totalObtained;
  final double totalMarks;
  final double? percentage;
  final String? grade;
  final String? remark;
  final bool complete;
  final bool? passed;
  final int? position;

  factory ExamResult.fromJson(Map<String, dynamic> j) => ExamResult(
        studentId: jStr(j['student_id']),
        rollNo: jStr(j['roll_no']),
        studentName: jStr(j['student_name']),
        subjects: jMapList<SubjectResult>(j['subjects'], SubjectResult.fromJson),
        totalObtained: jNum(j['total_obtained']),
        totalMarks: jNum(j['total_marks']),
        percentage: jNumN(j['percentage']),
        grade: jStrN(j['grade']),
        remark: jStrN(j['remark']),
        complete: jBool(j['complete']),
        passed: j['passed'] is bool ? j['passed'] as bool : null,
        position: j['position'] == null ? null : jInt(j['position']),
      );
}

class ExamResultEntry {
  const ExamResultEntry({required this.examName, required this.examType, required this.result});

  final String examName;
  final String examType;
  final ExamResult result;

  factory ExamResultEntry.fromJson(Map<String, dynamic> j) {
    final exam = jMap(j['exam']);
    return ExamResultEntry(
      examName: jStr(exam['name']),
      examType: jStr(exam['exam_type']),
      result: ExamResult.fromJson(jMap(j['result'])),
    );
  }
}

// ---------------------------------------------------------------- fees

class FeeHead {
  const FeeHead({required this.id, required this.name, required this.frequency, required this.isActive});

  final String id;
  final String name;
  final String frequency;
  final bool isActive;

  factory FeeHead.fromJson(Map<String, dynamic> j) => FeeHead(
        id: jStr(j['id']),
        name: jStr(j['name']),
        frequency: jStr(j['frequency']),
        isActive: jBool(j['is_active'], true),
      );
}

class FeeStructure {
  const FeeStructure({required this.id, required this.classId, required this.feeHeadId, required this.amount});

  final String id;
  final String classId;
  final String feeHeadId;
  final double amount;

  factory FeeStructure.fromJson(Map<String, dynamic> j) => FeeStructure(
        id: jStr(j['id']),
        classId: jStr(j['class_id']),
        feeHeadId: jStr(j['fee_head_id']),
        amount: jNum(j['amount']),
      );
}

class InvoiceItem {
  const InvoiceItem({required this.description, required this.amount});

  final String description;
  final double amount;

  factory InvoiceItem.fromJson(Map<String, dynamic> j) =>
      InvoiceItem(description: jStr(j['description']), amount: jNum(j['amount']));
}

class Payment {
  const Payment({
    required this.id,
    required this.receiptNo,
    required this.amount,
    required this.paymentDate,
    required this.method,
    required this.reference,
    required this.isReversal,
    required this.reversesPaymentId,
  });

  final String id;
  final String receiptNo;
  final double amount;
  final DateTime paymentDate;
  final String method;
  final String reference;
  final bool isReversal;
  final String? reversesPaymentId;

  factory Payment.fromJson(Map<String, dynamic> j) => Payment(
        id: jStr(j['id']),
        receiptNo: jStr(j['receipt_no']),
        amount: jNum(j['amount']),
        paymentDate: jDate(j['payment_date']),
        method: jStr(j['method']),
        reference: jStr(j['reference']),
        isReversal: jBool(j['is_reversal']),
        reversesPaymentId: jStrN(j['reverses_payment_id']),
      );
}

class Invoice {
  const Invoice({
    required this.id,
    required this.invoiceNo,
    required this.studentId,
    required this.studentName,
    required this.rollNo,
    required this.sectionName,
    required this.periodLabel,
    required this.issueDate,
    required this.dueDate,
    required this.totalAmount,
    required this.discountAmount,
    required this.netAmount,
    required this.paidAmount,
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
  final String sectionName;
  final String periodLabel;
  final DateTime issueDate;
  final DateTime dueDate;
  final double totalAmount;
  final double discountAmount;
  final double netAmount;
  final double paidAmount;
  final double balance;
  final String status;
  final List<InvoiceItem> items;
  final List<Payment> payments;

  /// Payments that have not been reversed yet (a reversal row points at the payment it cancels).
  List<Payment> get reversiblePayments {
    final reversed = payments.where((p) => p.isReversal).map((p) => p.reversesPaymentId).toSet();
    return payments.where((p) => !p.isReversal && !reversed.contains(p.id)).toList();
  }

  factory Invoice.fromJson(Map<String, dynamic> j) => Invoice(
        id: jStr(j['id']),
        invoiceNo: jStr(j['invoice_no']),
        studentId: jStr(j['student_id']),
        studentName: jStr(j['student_name']),
        rollNo: jStr(j['roll_no']),
        sectionName: jStr(j['section_name']),
        periodLabel: jStr(j['period_label']),
        issueDate: jDate(j['issue_date']),
        dueDate: jDate(j['due_date']),
        totalAmount: jNum(j['total_amount']),
        discountAmount: jNum(j['discount_amount']),
        netAmount: jNum(j['net_amount']),
        paidAmount: jNum(j['paid_amount']),
        balance: jNum(j['balance']),
        status: jStr(j['status']),
        items: jMapList<InvoiceItem>(j['items'], InvoiceItem.fromJson),
        payments: jMapList<Payment>(j['payments'], Payment.fromJson),
      );
}

class FeeSummary {
  const FeeSummary({
    required this.billed,
    required this.collected,
    required this.outstanding,
    required this.overdue,
    required this.invoiceCount,
  });

  final double billed;
  final double collected;
  final double outstanding;
  final double overdue;
  final int invoiceCount;

  factory FeeSummary.fromJson(Map<String, dynamic> j) => FeeSummary(
        billed: jNum(j['billed']),
        collected: jNum(j['collected']),
        outstanding: jNum(j['outstanding']),
        overdue: jNum(j['overdue']),
        invoiceCount: jInt(j['invoice_count']),
      );
}

class GenerateResult {
  const GenerateResult({required this.created, required this.skippedExisting, required this.skippedNoStructure});

  final int created;
  final int skippedExisting;
  final int skippedNoStructure;

  factory GenerateResult.fromJson(Map<String, dynamic> j) => GenerateResult(
        created: jInt(j['created']),
        skippedExisting: jInt(j['skipped_existing']),
        skippedNoStructure: jInt(j['skipped_no_fee_structure']),
      );
}

// ---------------------------------------------------------------- timetable

class Period {
  const Period({
    required this.id,
    required this.periodNo,
    required this.label,
    required this.startTime,
    required this.endTime,
    required this.isBreak,
  });

  final String id;
  final int periodNo;
  final String label;
  final String startTime;
  final String endTime;
  final bool isBreak;

  factory Period.fromJson(Map<String, dynamic> j) => Period(
        id: jStr(j['id']),
        periodNo: jInt(j['period_no']),
        label: jStr(j['label']),
        startTime: jStr(j['start_time']),
        endTime: jStr(j['end_time']),
        isBreak: jBool(j['is_break']),
      );
}

class Slot {
  const Slot({
    required this.id,
    required this.sectionName,
    required this.subjectName,
    required this.teacherName,
    required this.dayOfWeek,
    required this.periodId,
    required this.room,
  });

  final String id;
  final String sectionName;
  final String subjectName;
  final String teacherName;
  final int dayOfWeek;
  final String periodId;
  final String room;

  factory Slot.fromJson(Map<String, dynamic> j) => Slot(
        id: jStr(j['id']),
        sectionName: jStr(j['section_name']),
        subjectName: jStr(j['subject_name']),
        teacherName: jStr(j['teacher_name']),
        dayOfWeek: jInt(j['day_of_week']),
        periodId: jStr(j['period_id']),
        room: jStr(j['room']),
      );
}

class Week {
  const Week({required this.periods, required this.slots});

  final List<Period> periods;
  final List<Slot> slots;

  Slot? at(int day, String periodId) {
    for (final s in slots) {
      if (s.dayOfWeek == day && s.periodId == periodId) return s;
    }
    return null;
  }

  factory Week.fromJson(Map<String, dynamic> j) {
    final periods = jMapList<Period>(j['periods'], Period.fromJson)..sort((a, b) => a.periodNo.compareTo(b.periodNo));
    return Week(periods: periods, slots: jMapList<Slot>(j['slots'], Slot.fromJson));
  }
}

// ---------------------------------------------------------------- events, announcements, notifications

class EventItem {
  const EventItem({
    required this.id,
    required this.title,
    required this.description,
    required this.eventType,
    required this.startDate,
    required this.endDate,
    required this.startTime,
    required this.endTime,
    required this.location,
    required this.audience,
  });

  final String id;
  final String title;
  final String description;
  final String eventType;
  final DateTime startDate;
  final DateTime endDate;
  final String? startTime;
  final String? endTime;
  final String location;
  final String audience;

  factory EventItem.fromJson(Map<String, dynamic> j) => EventItem(
        id: jStr(j['id']),
        title: jStr(j['title']),
        description: jStr(j['description']),
        eventType: jStr(j['event_type']),
        startDate: jDate(j['start_date']),
        endDate: jDate(j['end_date']),
        startTime: jStrN(j['start_time']),
        endTime: jStrN(j['end_time']),
        location: jStr(j['location']),
        audience: jStr(j['audience']),
      );
}

class Announcement {
  const Announcement({
    required this.id,
    required this.title,
    required this.body,
    required this.audience,
    required this.priority,
    required this.publishAt,
    required this.expiresAt,
    required this.status,
    required this.createdAt,
  });

  final String id;
  final String title;
  final String body;
  final String audience;
  final String priority;
  final DateTime? publishAt;
  final DateTime? expiresAt;
  final String status;
  final DateTime createdAt;

  factory Announcement.fromJson(Map<String, dynamic> j) => Announcement(
        id: jStr(j['id']),
        title: jStr(j['title']),
        body: jStr(j['body']),
        audience: jStr(j['audience']),
        priority: jStr(j['priority']),
        publishAt: jDateN(j['publish_at']),
        expiresAt: jDateN(j['expires_at']),
        status: jStr(j['status']),
        createdAt: jDate(j['created_at']),
      );
}

class NotificationItem {
  const NotificationItem({
    required this.id,
    required this.title,
    required this.body,
    required this.type,
    required this.isRead,
    required this.createdAt,
  });

  final String id;
  final String title;
  final String body;
  final String type;
  final bool isRead;
  final DateTime createdAt;

  factory NotificationItem.fromJson(Map<String, dynamic> j) => NotificationItem(
        id: jStr(j['id']),
        title: jStr(j['title']),
        body: jStr(j['body']),
        type: jStr(j['type']),
        isRead: jBool(j['is_read']),
        createdAt: jDate(j['created_at']),
      );
}

// ---------------------------------------------------------------- complaints

class ComplaintComment {
  const ComplaintComment({
    required this.authorName,
    required this.authorRole,
    required this.message,
    required this.isInternal,
    required this.createdAt,
  });

  final String authorName;
  final String authorRole;
  final String message;
  final bool isInternal;
  final DateTime createdAt;

  factory ComplaintComment.fromJson(Map<String, dynamic> j) => ComplaintComment(
        authorName: jStr(j['author_name']),
        authorRole: jStr(j['author_role']),
        message: jStr(j['message']),
        isInternal: jBool(j['is_internal']),
        createdAt: jDate(j['created_at']),
      );
}

class Complaint {
  const Complaint({
    required this.id,
    required this.ticketNo,
    required this.submitterName,
    required this.studentName,
    required this.category,
    required this.kind,
    required this.subject,
    required this.description,
    required this.status,
    required this.priority,
    required this.assignedTo,
    required this.createdAt,
    required this.comments,
  });

  final String id;
  final String ticketNo;
  final String submitterName;
  final String studentName;
  final String category;
  final String kind;
  final String subject;
  final String description;
  final String status;
  final String priority;
  final String? assignedTo;
  final DateTime createdAt;
  final List<ComplaintComment> comments;

  factory Complaint.fromJson(Map<String, dynamic> j) => Complaint(
        id: jStr(j['id']),
        ticketNo: jStr(j['ticket_no']),
        submitterName: jStr(j['submitter_name']),
        studentName: jStr(j['student_name']),
        category: jStr(j['category']),
        kind: jStr(j['kind']),
        subject: jStr(j['subject']),
        description: jStr(j['description']),
        status: jStr(j['status']),
        priority: jStr(j['priority']),
        assignedTo: jStrN(j['assigned_to']),
        createdAt: jDate(j['created_at']),
        comments: jMapList<ComplaintComment>(j['comments'], ComplaintComment.fromJson),
      );
}
