import 'api_client.dart';
import 'json.dart';

class SectionRef {
  SectionRef({required this.id, required this.label, required this.classId, required this.className, required this.gradeLevel});
  final String id;
  final String label; // "Class 8-A"
  final String classId;
  final String className;
  final int gradeLevel;
  factory SectionRef.fromJson(Map<String, dynamic> j) => SectionRef(
      id: asStr(j['id']),
      label: asStr(j['label']),
      classId: asStr(j['class_id']),
      className: asStr(j['class_name']),
      gradeLevel: asInt(j['grade_level']));
}

class ClassRef {
  ClassRef({required this.id, required this.name, required this.gradeLevel});
  final String id;
  final String name;
  final int gradeLevel;
  factory ClassRef.fromJson(Map<String, dynamic> j) =>
      ClassRef(id: asStr(j['id']), name: asStr(j['name']), gradeLevel: asInt(j['grade_level']));
}

class SubjectRef {
  SubjectRef({required this.id, required this.name, required this.code});
  final String id;
  final String name;
  final String code;
  factory SubjectRef.fromJson(Map<String, dynamic> j) =>
      SubjectRef(id: asStr(j['id']), name: asStr(j['name']), code: asStr(j['code']));
}

class StudentRef {
  StudentRef({required this.id, required this.rollNo, required this.fullName, required this.sectionId, this.sectionLabel});
  final String id;
  final String rollNo;
  final String fullName;
  final String sectionId;
  final String? sectionLabel;
  String get display => '$fullName ($rollNo)';
  factory StudentRef.fromJson(Map<String, dynamic> j) => StudentRef(
      id: asStr(j['id']),
      rollNo: asStr(j['roll_no']),
      fullName: asStr(j['full_name']),
      sectionId: asStr(j['section_id']),
      sectionLabel: asStrN(j['section_label']));
}

class TeacherRef {
  TeacherRef({required this.id, required this.fullName, required this.employeeNo});
  final String id;
  final String fullName;
  final String employeeNo;
  factory TeacherRef.fromJson(Map<String, dynamic> j) =>
      TeacherRef(id: asStr(j['id']), fullName: asStr(j['full_name']), employeeNo: asStr(j['employee_no']));
}

/// A (section, subject) pair a teacher teaches.
class TeachingRef {
  TeachingRef({required this.sectionId, required this.sectionLabel, required this.subjectId, required this.subjectName});
  final String sectionId;
  final String sectionLabel;
  final String subjectId;
  final String subjectName;
  factory TeachingRef.fromJson(Map<String, dynamic> j) => TeachingRef(
      sectionId: asStr(j['section_id']),
      sectionLabel: asStr(j['section_label']),
      subjectId: asStr(j['subject_id']),
      subjectName: asStr(j['subject_name']));
}

/// A student as seen by the student themself or by a parent (their child).
class ChildRef {
  ChildRef({required this.studentId, required this.rollNo, required this.fullName, required this.sectionId, this.sectionLabel});
  final String studentId;
  final String rollNo;
  final String fullName;
  final String sectionId;
  final String? sectionLabel;
  factory ChildRef.fromJson(Map<String, dynamic> j) => ChildRef(
      studentId: asStr(j['student_id']),
      rollNo: asStr(j['roll_no']),
      fullName: asStr(j['full_name']),
      sectionId: asStr(j['section_id']),
      sectionLabel: asStrN(j['section_label']));
}

class MeProfile {
  MeProfile({required this.userId, required this.fullName, this.teacherId, this.student, this.children = const <ChildRef>[]});
  final String userId;
  final String fullName;
  final String? teacherId;
  final ChildRef? student;
  final List<ChildRef> children;
  factory MeProfile.fromJson(Map<String, dynamic> j) => MeProfile(
      userId: asStr(j['user_id']),
      fullName: asStr(j['full_name']),
      teacherId: asStrN(j['teacher_id']),
      student: j['student'] == null ? null : ChildRef.fromJson(asMap(j['student'])),
      children: asMapList(j['children']).map(ChildRef.fromJson).toList());
}

class AdminRef {
  AdminRef({required this.id, required this.fullName});
  final String id;
  final String fullName;
}

class AcademicYearRef {
  AcademicYearRef({required this.id, required this.name});
  final String id;
  final String name;
}

/// Role-scoped dropdown data (`GET /lookups/*`). Small results are cached for the session;
/// call [clear] after changes that affect them (rare) or on logout.
class Lookups {
  Lookups(this.api);
  final ApiClient api;

  final Map<String, Future<dynamic>> _cache = <String, Future<dynamic>>{};

  Future<T> _cached<T>(String key, Future<T> Function() load) {
    final hit = _cache[key];
    if (hit != null) return hit as Future<T>;
    final f = load();
    _cache[key] = f;
    f.then<void>((_) {}, onError: (Object e, StackTrace s) {
      _cache.remove(key); // do not cache failures
    });
    return f;
  }

  void clear() => _cache.clear();

  Future<MeProfile> me() => _cached('me', () async => MeProfile.fromJson(asMap(await api.get('/lookups/me'))));

  Future<AcademicYearRef> academicYear() => _cached('year', () async {
        final m = asMap(await api.get('/lookups/academic-year'));
        return AcademicYearRef(id: asStr(m['id']), name: asStr(m['name']));
      });

  Future<List<ClassRef>> classes() => _cached('classes', () async {
        return asMapList(await api.get('/lookups/classes')).map(ClassRef.fromJson).toList();
      });

  /// [all] = every section (admin / browsing timetables); default = the sections the caller works with.
  Future<List<SectionRef>> sections({bool all = false}) => _cached('sections:$all', () async {
        return asMapList(await api.get('/lookups/sections', query: {'scope': all ? 'all' : 'visible'}))
            .map(SectionRef.fromJson)
            .toList();
      });

  Future<List<SubjectRef>> subjects({String? sectionId}) => _cached('subjects:${sectionId ?? ''}', () async {
        return asMapList(await api.get('/lookups/subjects', query: {'section_id': sectionId}))
            .map(SubjectRef.fromJson)
            .toList();
      });

  Future<List<TeachingRef>> myAssignments() => _cached('my-assignments', () async {
        return asMapList(await api.get('/lookups/my-assignments')).map(TeachingRef.fromJson).toList();
      });

  Future<List<TeacherRef>> teachers({String? sectionId}) => _cached('teachers:${sectionId ?? ''}', () async {
        return asMapList(await api.get('/lookups/teachers', query: {'section_id': sectionId}))
            .map(TeacherRef.fromJson)
            .toList();
      });

  Future<List<StudentRef>> students(String sectionId) => _cached('students:$sectionId', () async {
        return asMapList(await api.get('/lookups/students', query: {'section_id': sectionId}))
            .map(StudentRef.fromJson)
            .toList();
      });

  /// Admin only: type-ahead student search (not cached).
  Future<List<StudentRef>> searchStudents(String q) async {
    return asMapList(await api.get('/lookups/students/search', query: {'q': q})).map(StudentRef.fromJson).toList();
  }

  Future<List<ChildRef>> myChildren() => _cached('children', () async {
        return asMapList(await api.get('/lookups/my-children')).map(ChildRef.fromJson).toList();
      });

  Future<List<AdminRef>> admins() => _cached('admins', () async {
        return asMapList(await api.get('/lookups/admins'))
            .map((m) => AdminRef(id: asStr(m['id']), fullName: asStr(m['full_name'])))
            .toList();
      });
}
