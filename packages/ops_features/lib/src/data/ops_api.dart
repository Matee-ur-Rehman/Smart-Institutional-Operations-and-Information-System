import '../core/api_client.dart';
import '../core/json_utils.dart';
import '../models/models.dart';

/// Every backend call used by Member 2's screens, in one place (paths: docs/API_CONTRACT.md).
/// Screens never build URLs themselves.
class OpsApi {
  OpsApi(this.client);

  final ApiClient client;

  // ------------------------------------------------------------ lookups
  Future<List<ClassItem>> classes() async =>
      jMapList<ClassItem>(await client.get('/lookups/classes'), ClassItem.fromJson);

  Future<List<SectionItem>> sections() async =>
      jMapList<SectionItem>(await client.get('/lookups/sections'), SectionItem.fromJson);

  Future<List<SubjectItem>> subjects() async =>
      jMapList<SubjectItem>(await client.get('/lookups/subjects'), SubjectItem.fromJson);

  Future<List<TeacherItem>> teachers() async =>
      jMapList<TeacherItem>(await client.get('/lookups/teachers'), TeacherItem.fromJson);

  Future<List<StudentItem>> students({String? sectionId}) async => jMapList<StudentItem>(
      await client.get('/lookups/students', query: <String, dynamic>{'section_id': sectionId}), StudentItem.fromJson);

  Future<List<StudentItem>> myChildren() async =>
      jMapList<StudentItem>(await client.get('/lookups/my-children'), StudentItem.fromJson);

  Future<StudentItem> myStudent() async => StudentItem.fromJson(jMap(await client.get('/lookups/my-student')));

  Future<List<TeachingItem>> myTeaching() async =>
      jMapList<TeachingItem>(await client.get('/lookups/my-teaching'), TeachingItem.fromJson);

  // ------------------------------------------------------------ homework
  Future<Paged<Assignment>> assignments({String? studentId, String? sectionId, String? status, int pageSize = 100}) async =>
      Paged<Assignment>.fromJson(
        await client.get('/assignments', query: <String, dynamic>{
          'student_id': studentId,
          'section_id': sectionId,
          'status': status,
          'page_size': pageSize,
        }),
        Assignment.fromJson,
      );

  Future<void> createAssignment(Map<String, dynamic> body) => client.post('/assignments', data: body);

  Future<void> updateAssignment(String id, Map<String, dynamic> body) => client.patch('/assignments/$id', data: body);

  Future<void> deleteAssignment(String id) => client.delete('/assignments/$id');

  // ------------------------------------------------------------ exams
  Future<Paged<Exam>> exams({String? status, int pageSize = 100}) async => Paged<Exam>.fromJson(
        await client.get('/exams', query: <String, dynamic>{'status': status, 'page_size': pageSize}),
        Exam.fromJson,
      );

  Future<void> createExam(Map<String, dynamic> body) => client.post('/exams', data: body);

  Future<void> updateExam(String id, Map<String, dynamic> body) => client.patch('/exams/$id', data: body);

  Future<void> deleteExam(String id) => client.delete('/exams/$id');

  Future<void> publishResults(String id) => client.post('/exams/$id/publish-results');

  Future<List<ExamSchedule>> schedules(String examId, {String? sectionId}) async => jMapList<ExamSchedule>(
      await client.get('/exams/$examId/schedules', query: <String, dynamic>{'section_id': sectionId}),
      ExamSchedule.fromJson);

  Future<void> createSchedule(String examId, Map<String, dynamic> body) =>
      client.post('/exams/$examId/schedules', data: body);

  Future<void> deleteSchedule(String id) => client.delete('/exam-schedules/$id');

  Future<MarkSheet> markSheet(String scheduleId) async =>
      MarkSheet.fromJson(jMap(await client.get('/exam-schedules/$scheduleId/marks')));

  Future<void> saveMarks(String scheduleId, List<Map<String, dynamic>> entries) =>
      client.put('/exam-schedules/$scheduleId/marks', data: <String, dynamic>{'entries': entries});

  Future<List<GradeBand>> gradeScale() async =>
      jMapList<GradeBand>(await client.get('/grade-scales'), GradeBand.fromJson);

  Future<void> saveGradeScale(List<GradeBand> bands) =>
      client.put('/grade-scales', data: <String, dynamic>{'bands': bands.map((b) => b.toJson()).toList()});

  Future<List<ExamResultEntry>> studentResults(String studentId, {String? examId}) async {
    final body = jMap(await client.get('/results/students/$studentId', query: <String, dynamic>{'exam_id': examId}));
    return jMapList<ExamResultEntry>(body['results'], ExamResultEntry.fromJson);
  }

  Future<List<ExamResult>> sectionResults(String sectionId, String examId) async => jMapList<ExamResult>(
      await client.get('/results/sections/$sectionId', query: <String, dynamic>{'exam_id': examId}),
      ExamResult.fromJson);

  // ------------------------------------------------------------ fees
  Future<List<FeeHead>> feeHeads() async => jMapList<FeeHead>(await client.get('/fee-heads'), FeeHead.fromJson);

  Future<void> createFeeHead(Map<String, dynamic> body) => client.post('/fee-heads', data: body);

  Future<void> updateFeeHead(String id, Map<String, dynamic> body) => client.patch('/fee-heads/$id', data: body);

  Future<List<FeeStructure>> feeStructures({String? classId}) async => jMapList<FeeStructure>(
      await client.get('/fee-structures', query: <String, dynamic>{'class_id': classId}), FeeStructure.fromJson);

  Future<void> createFeeStructure(Map<String, dynamic> body) => client.post('/fee-structures', data: body);

  Future<void> updateFeeStructure(String id, Map<String, dynamic> body) => client.patch('/fee-structures/$id', data: body);

  Future<void> deleteFeeStructure(String id) => client.delete('/fee-structures/$id');

  Future<Paged<Invoice>> invoices({String? studentId, String? status, String? periodLabel, int pageSize = 100}) async =>
      Paged<Invoice>.fromJson(
        await client.get('/fee-invoices', query: <String, dynamic>{
          'student_id': studentId,
          'status': status,
          'period_label': periodLabel,
          'page_size': pageSize,
        }),
        Invoice.fromJson,
      );

  Future<Invoice> invoice(String id) async => Invoice.fromJson(jMap(await client.get('/fee-invoices/$id')));

  Future<GenerateResult> generateInvoices(Map<String, dynamic> body) async =>
      GenerateResult.fromJson(jMap(await client.post('/fee-invoices/generate', data: body)));

  Future<void> recordPayment(String invoiceId, Map<String, dynamic> body) =>
      client.post('/fee-invoices/$invoiceId/payments', data: body);

  Future<void> reversePayment(String paymentId, String reason) =>
      client.post('/fee-payments/$paymentId/reverse', data: <String, dynamic>{'reason': reason});

  Future<void> cancelInvoice(String id) => client.post('/fee-invoices/$id/cancel');

  Future<FeeSummary> feeSummary({String? classId, String? sectionId, String? periodLabel}) async =>
      FeeSummary.fromJson(jMap(await client.get('/fee-summary', query: <String, dynamic>{
        'class_id': classId,
        'section_id': sectionId,
        'period_label': periodLabel,
      })));

  // ------------------------------------------------------------ timetable
  Future<List<Period>> periods() async =>
      (jMapList<Period>(await client.get('/period-definitions'), Period.fromJson))..sort((a, b) => a.periodNo.compareTo(b.periodNo));

  Future<void> createPeriod(Map<String, dynamic> body) => client.post('/period-definitions', data: body);

  Future<void> deletePeriod(String id) => client.delete('/period-definitions/$id');

  Future<void> createSlot(Map<String, dynamic> body) => client.post('/timetable-slots', data: body);

  Future<void> deleteSlot(String id) => client.delete('/timetable-slots/$id');

  Future<Week> sectionWeek(String sectionId) async =>
      Week.fromJson(jMap(await client.get('/timetable/sections/$sectionId')));

  Future<Week> myWeek() async => Week.fromJson(jMap(await client.get('/timetable/me')));

  Future<Week> studentWeek(String studentId) async =>
      Week.fromJson(jMap(await client.get('/timetable/students/$studentId')));

  // ------------------------------------------------------------ calendar
  Future<Paged<EventItem>> events({String? month}) async => Paged<EventItem>.fromJson(
        await client.get('/events', query: <String, dynamic>{'month': month, 'page_size': 100}),
        EventItem.fromJson,
      );

  Future<void> createEvent(Map<String, dynamic> body) => client.post('/events', data: body);

  Future<void> deleteEvent(String id) => client.delete('/events/$id');

  // ------------------------------------------------------------ announcements
  Future<Paged<Announcement>> announcements({String? status}) async => Paged<Announcement>.fromJson(
        await client.get('/announcements', query: <String, dynamic>{'status': status, 'page_size': 100}),
        Announcement.fromJson,
      );

  Future<void> createAnnouncement(Map<String, dynamic> body) => client.post('/announcements', data: body);

  Future<void> publishAnnouncement(String id) => client.post('/announcements/$id/publish');

  Future<void> archiveAnnouncement(String id) => client.post('/announcements/$id/archive');

  Future<void> deleteAnnouncement(String id) => client.delete('/announcements/$id');

  // ------------------------------------------------------------ notifications
  Future<Paged<NotificationItem>> notifications({int pageSize = 50}) async => Paged<NotificationItem>.fromJson(
        await client.get('/notifications', query: <String, dynamic>{'page_size': pageSize}),
        NotificationItem.fromJson,
      );

  Future<int> unreadCount() async => jInt(jMap(await client.get('/notifications/unread-count'))['count']);

  Future<void> markRead(String id) => client.post('/notifications/$id/read');

  Future<void> markAllRead() => client.post('/notifications/read-all');

  // ------------------------------------------------------------ complaints
  Future<Paged<Complaint>> complaints({String? status}) async => Paged<Complaint>.fromJson(
        await client.get('/complaints', query: <String, dynamic>{'status': status, 'page_size': 100}),
        Complaint.fromJson,
      );

  Future<Complaint> complaint(String id) async => Complaint.fromJson(jMap(await client.get('/complaints/$id')));

  Future<void> createComplaint(Map<String, dynamic> body) => client.post('/complaints', data: body);

  Future<void> updateComplaint(String id, Map<String, dynamic> body) => client.patch('/complaints/$id', data: body);

  Future<void> addComment(String id, String message, {bool internal = false}) => client.post(
        '/complaints/$id/comments',
        data: <String, dynamic>{'message': message, 'is_internal': internal},
      );

  Future<Map<String, dynamic>> complaintSummary() async => jMap(await client.get('/complaints/summary'));
}
