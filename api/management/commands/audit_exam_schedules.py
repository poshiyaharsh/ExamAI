from django.core.management.base import BaseCommand
from django.utils import timezone
from api.models import Exam


class Command(BaseCommand):
    help = 'Audit exam schedules (starts_at, ends_at, timezone) across all exams in read-only / dry-run mode.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--status',
            type=str,
            default='all',
            help='Filter exams by status (e.g. draft, published, all)',
        )
        parser.add_argument(
            '--exam-id',
            type=int,
            default=None,
            help='Audit a specific exam ID',
        )

    def handle(self, *args, **options):
        status_filter = options.get('status', 'all')
        exam_id = options.get('exam_id')

        self.stdout.write(self.style.NOTICE('=== Exam Schedule Audit (Dry-Run / Read-Only) ==='))
        self.stdout.write(f'Current Server Time (UTC): {timezone.now().isoformat()}')

        qs = Exam.objects.select_related('institution', 'created_by').all().order_by('id')
        if exam_id:
            qs = qs.filter(id=exam_id)
        elif status_filter != 'all':
            qs = qs.filter(status=status_filter)

        total_count = qs.count()
        missing_count = 0
        scheduled_count = 0
        invalid_window_count = 0

        self.stdout.write(f'Inspecting {total_count} exam(s)...\n')

        format_str = '{:<6} | {:<25} | {:<10} | {:<10} | {:<22} | {:<22} | {:<8}'
        self.stdout.write(format_str.format('ID', 'Title', 'Status', 'Duration', 'Starts At (UTC)', 'Ends At (UTC)', 'Sched?'))
        self.stdout.write('-' * 115)

        for exam in qs:
            has_starts = bool(exam.starts_at)
            has_ends = bool(exam.ends_at)
            has_full_schedule = has_starts and has_ends

            if not has_full_schedule:
                missing_count += 1
                sched_status = 'MISSING'
            else:
                scheduled_count += 1
                if exam.ends_at <= exam.starts_at:
                    invalid_window_count += 1
                    sched_status = 'INVALID'
                else:
                    sched_status = 'OK'

            title_trunc = (exam.title[:22] + '...') if len(exam.title) > 25 else exam.title
            s_str = exam.starts_at.strftime('%Y-%m-%d %H:%M') if exam.starts_at else 'None'
            e_str = exam.ends_at.strftime('%Y-%m-%d %H:%M') if exam.ends_at else 'None'

            line = format_str.format(
                exam.id,
                title_trunc,
                exam.status,
                f'{exam.duration_minutes}m',
                s_str,
                e_str,
                sched_status,
            )

            if sched_status == 'MISSING':
                self.stdout.write(self.style.WARNING(line))
            elif sched_status == 'INVALID':
                self.stdout.write(self.style.ERROR(line))
            else:
                self.stdout.write(self.style.SUCCESS(line))

        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.NOTICE('SUMMARY:'))
        self.stdout.write(f'  Total Exams Checked:     {total_count}')
        self.stdout.write(f'  Fully Scheduled:         {scheduled_count}')
        self.stdout.write(f'  Missing Schedule:        {missing_count}')
        self.stdout.write(f'  Invalid Schedule Window: {invalid_window_count}')
        self.stdout.write('=' * 50)
        self.stdout.write(self.style.SUCCESS('Audit complete. No database records were altered.'))
