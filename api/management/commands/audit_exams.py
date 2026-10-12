from django.core.management.base import BaseCommand
from api.models import Exam
from api.utils.departments import get_exam_visibility_status_for_faculty, get_faculty_department, normalize_department


class Command(BaseCommand):
    help = 'Audit all exams across institutions for missing or mismatched departments and isolation issues.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Automatically fix missing exam departments using creating faculty profile department',
        )

    def handle(self, *args, **options):
        should_fix = options.get('fix', False)
        self.stdout.write(self.style.NOTICE('Starting exam audit...'))

        exams = Exam.objects.select_related('institution', 'created_by').all()
        issue_count = 0
        fixed_count = 0

        for exam in exams:
            issues = []
            exam_dept = (exam.department or '').strip()
            faculty_dept = get_faculty_department(exam.created_by)

            if not exam_dept:
                issues.append('Department is MISSING/blank')

            if faculty_dept and exam_dept and faculty_dept.lower() != exam_dept.lower():
                issues.append(f'Department MISMATCH with creating faculty ({exam_dept} vs {faculty_dept})')

            if exam.questions.count() == 0:
                issues.append('Exam has 0 questions')

            if exam.starts_at and exam.ends_at and exam.starts_at > exam.ends_at:
                issues.append('Invalid schedule: start date after end date')

            if issues:
                issue_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Exam ID={exam.id} Title='{exam.title}' Inst='{exam.institution.institution_name}' Issues: {', '.join(issues)}"
                    )
                )

                if should_fix and not exam_dept and faculty_dept:
                    exam.department = faculty_dept
                    exam.save(update_fields=['department'])
                    fixed_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  -> Fixed: assigned department '{faculty_dept}'"))

        if issue_count == 0:
            self.stdout.write(self.style.SUCCESS('All exams are healthy! No department or isolation issues detected.'))
        else:
            self.stdout.write(self.style.NOTICE(f'Audit complete: {issue_count} exam(s) with issues, {fixed_count} fixed.'))
