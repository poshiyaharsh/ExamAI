"""
Management command to safely remove testing/temporary institutes in strict dependency order.
Supports --dry-run and --apply with atomic per-institute transactions and mandatory confirmation.
"""
import os
import sys
from typing import List
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from admins.models import AdminInstitution, AdminDepartment
from faculty.models import FacultyProfile, Paper, PaperQuestion, SyllabusUpload
from students.models import StudentProfile
from api.models import (
    Exam, Question, Option, StudentAttempt, StudentAnswer, AttemptEvent,
    Notification, QuestionImportLog, QuestionAuditLog, EvaluationChangeAuditLog
)
from ai_paper_generator.models import GenerationJob, GenerationLog
from superadmin.audit import log_super_admin_action

User = get_user_model()
CONFIRMATION_PHRASE = "CONFIRM_DELETE_INSTITUTES"


class Command(BaseCommand):
    help = "Safely and atomically remove testing institutes and their isolated records."

    def add_arguments(self, parser):
        parser.add_argument(
            '--ids',
            nargs='+',
            type=int,
            required=True,
            help="List of institute IDs to remove (e.g. --ids 19 20 21)"
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help="Simulate the deletion and print record counts without making database changes."
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help="Execute the actual deletion."
        )
        parser.add_argument(
            '--confirm',
            type=str,
            default='',
            help=f"Required confirmation phrase to execute deletion: '{CONFIRMATION_PHRASE}'"
        )

    def handle(self, *args, **options):
        inst_ids: List[int] = options['ids']
        dry_run: bool = options['dry_run']
        apply_mode: bool = options['apply']
        confirm_str: str = options['confirm']

        if not dry_run and not apply_mode:
            raise CommandError("You must specify either --dry-run or --apply.")

        if apply_mode and dry_run:
            raise CommandError("Cannot specify both --dry-run and --apply.")

        if apply_mode and confirm_str != CONFIRMATION_PHRASE:
            raise CommandError(
                f"Safety check failed: You must pass --confirm=\"{CONFIRMATION_PHRASE}\" to apply deletions."
            )

        self.stdout.write(self.style.NOTICE(f"\nEvaluating {len(inst_ids)} institutes for removal: {inst_ids}"))

        # Pre-check for protected institutes and accounts
        institutes_to_process = []
        for inst_id in inst_ids:
            try:
                inst = AdminInstitution.objects.get(id=inst_id)
            except AdminInstitution.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  [SKIPPED] Institute #{inst_id} does not exist."))
                continue

            # Safety guard: Check for protected keywords or Harsh accounts
            fac_users = User.objects.filter(faculty_profile__institution=inst)
            stud_users = User.objects.filter(student_profile__institution=inst)
            admin_user = [inst.admin] if inst.admin else []
            all_inst_users = set(list(fac_users) + list(stud_users) + admin_user)

            for u in all_inst_users:
                if 'poshiya' in u.email.lower():
                    raise CommandError(
                        f"ABORTED: Institute #{inst.id} ({inst.institution_name}) contains protected real account {u.email}! Refusing to delete."
                    )
                if hasattr(u, 'super_admin_profile'):
                    raise CommandError(
                        f"ABORTED: Institute #{inst.id} ({inst.institution_name}) references Super Admin {u.email}! Refusing to delete."
                    )

            institutes_to_process.append(inst)

        if not institutes_to_process:
            self.stdout.write(self.style.SUCCESS("No matching institutes found to process."))
            return

        total_deleted_summary = {}

        for inst in institutes_to_process:
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\n--- Institute #{inst.id}: '{inst.institution_name}' ({inst.institution_code or inst.short_code}) ---"
            ))

            # Query all dependent sets
            depts = AdminDepartment.objects.filter(institution=inst)
            exams = Exam.objects.filter(institution=inst)
            questions = Question.objects.filter(exam__in=exams)
            options_qs = Option.objects.filter(question__in=questions)
            
            attempts = StudentAttempt.objects.filter(exam__in=exams)
            answers = StudentAnswer.objects.filter(attempt__in=attempts)
            events = AttemptEvent.objects.filter(attempt__in=attempts)
            eval_logs = EvaluationChangeAuditLog.objects.filter(attempt__in=attempts)

            papers = Paper.objects.filter(institution=inst)
            paper_qs = PaperQuestion.objects.filter(paper__in=papers)
            syllabus_uploads = SyllabusUpload.objects.filter(institution=inst)

            jobs = GenerationJob.objects.filter(institution=inst)
            job_logs = GenerationLog.objects.filter(job__in=jobs)

            notifs = Notification.objects.filter(institution=inst)
            q_import_logs = QuestionImportLog.objects.filter(institution=inst)
            q_audit_logs = QuestionAuditLog.objects.filter(question__in=questions)

            fac_profiles = FacultyProfile.objects.filter(institution=inst)
            stud_profiles = StudentProfile.objects.filter(institution=inst)

            # Users candidate for deletion (only if not attached to any other institution!)
            candidate_user_ids = set()
            for fp in fac_profiles:
                candidate_user_ids.add(fp.user_id)
            for sp in stud_profiles:
                candidate_user_ids.add(sp.user_id)
            if inst.admin:
                candidate_user_ids.add(inst.admin_id)

            safe_users_to_delete = []
            for uid in candidate_user_ids:
                # Check if this user belongs to any OTHER institution
                other_fac = FacultyProfile.objects.filter(user_id=uid).exclude(institution=inst).exists()
                other_stud = StudentProfile.objects.filter(user_id=uid).exclude(institution=inst).exists()
                other_admin = AdminInstitution.objects.filter(admin_id=uid).exclude(id=inst.id).exists()
                if not other_fac and not other_stud and not other_admin:
                    safe_users_to_delete.append(uid)

            counts = {
                'departments': depts.count(),
                'exams': exams.count(),
                'questions': questions.count(),
                'options': options_qs.count(),
                'attempts': attempts.count(),
                'answers': answers.count(),
                'attempt_events': events.count(),
                'evaluation_audit_logs': eval_logs.count(),
                'papers': papers.count(),
                'paper_questions': paper_qs.count(),
                'syllabus_uploads': syllabus_uploads.count(),
                'ai_generation_jobs': jobs.count(),
                'ai_generation_logs': job_logs.count(),
                'notifications': notifs.count(),
                'question_import_logs': q_import_logs.count(),
                'question_audit_logs': q_audit_logs.count(),
                'faculty_profiles': fac_profiles.count(),
                'student_profiles': stud_profiles.count(),
                'users': len(safe_users_to_delete),
                'institutions': 1,
            }

            self.stdout.write(f"  Departments:           {counts['departments']}")
            self.stdout.write(f"  Faculty Profiles:      {counts['faculty_profiles']}")
            self.stdout.write(f"  Student Profiles:      {counts['student_profiles']}")
            self.stdout.write(f"  Auth Users (Isolated): {counts['users']}")
            self.stdout.write(f"  Exams:                 {counts['exams']}")
            self.stdout.write(f"  Questions:             {counts['questions']}")
            self.stdout.write(f"  Options:               {counts['options']}")
            self.stdout.write(f"  Attempts:              {counts['attempts']}")
            self.stdout.write(f"  Answers:               {counts['answers']}")
            self.stdout.write(f"  Notifications:         {counts['notifications']}")

            if dry_run:
                self.stdout.write(self.style.SUCCESS(f"  [DRY RUN] Would cleanly delete institute #{inst.id}."))
                for k, v in counts.items():
                    total_deleted_summary[k] = total_deleted_summary.get(k, 0) + v
                continue

            # Apply actual deletion atomically per institute
            with transaction.atomic():
                inst_name = inst.institution_name
                inst_id_val = inst.id

                # 1. Option items & Questions
                options_qs.delete()
                q_audit_logs.delete()
                questions.delete()

                # 2. Attempts, Answers, Events
                answers.delete()
                events.delete()
                eval_logs.delete()
                attempts.delete()

                # 3. Exams
                q_import_logs.delete()
                exams.delete()

                # 4. Papers & PaperQuestions
                paper_qs.delete()
                papers.delete()

                # 5. Syllabus uploads (and physical files)
                for su in syllabus_uploads:
                    if su.file and hasattr(su.file, 'path') and os.path.exists(su.file.path):
                        try:
                            os.remove(su.file.path)
                        except Exception:
                            pass
                syllabus_uploads.delete()

                # 6. AI Generation Jobs & Logs
                job_logs.delete()
                jobs.delete()

                # 7. Notifications
                notifs.delete()

                # 8. Profiles
                fac_profiles.delete()
                stud_profiles.delete()

                # 9. Departments
                depts.delete()

                # 10. The Institution itself
                inst.delete()

                # 11. Isolated Auth Users
                User.objects.filter(id__in=safe_users_to_delete).delete()

                # 12. Write SuperAdmin Audit Log
                log_super_admin_action(
                    request=None,
                    action='REMOVE_TESTING_INSTITUTE',
                    target_entity='AdminInstitution',
                    target_id=str(inst_id_val),
                    description=f"Permanently removed testing institute #{inst_id_val} ('{inst_name}') and associated test data.",
                    before_state={'institution_id': inst_id_val, 'name': inst_name, 'counts': counts},
                    after_state={'status': 'DELETED'}
                )

                self.stdout.write(self.style.SUCCESS(f"  [APPLIED] Successfully deleted institute #{inst_id_val}."))
                for k, v in counts.items():
                    total_deleted_summary[k] = total_deleted_summary.get(k, 0) + v

        mode_label = "DRY RUN SUMMARY" if dry_run else "DELETION APPLIED SUMMARY"
        self.stdout.write(self.style.SUCCESS(f"\n{'='*60}\n{mode_label}\n{'='*60}"))
        for k, v in total_deleted_summary.items():
            self.stdout.write(f"  {k:<25}: {v}")
