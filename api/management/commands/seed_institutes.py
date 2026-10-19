import csv
import os
import random
import sys
from typing import Dict, List, Tuple

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from admins.models import AdminDepartment, AdminInstitution, AdminProfile
from faculty.models import FacultyProfile
from students.models import StudentProfile


FICTIONAL_INSTITUTES = [
    {
        "name": "Pragyan Institute of Technology & Science",
        "short_code": "pits",
        "prefix": "PITS",
        "type": "Autonomous Technical Institute",
        "city": "Jaipur",
        "state": "Rajasthan",
        "est_year": 1988,
        "website": "https://pits.example.edu",
        "address": "NH-8, Bilochi Knowledge Park, Jaipur, Rajasthan 302001",
        "phone": "+91 141 298 5001",
    },
    {
        "name": "Deccan Institute of Advanced Engineering",
        "short_code": "diae",
        "prefix": "DIAE",
        "type": "Deemed Technical University",
        "city": "Pune",
        "state": "Maharashtra",
        "est_year": 1994,
        "website": "https://diae.example.edu",
        "address": "Sector 29, Hinjawadi Phase 2, Pune, Maharashtra 411057",
        "phone": "+91 20 6675 4100",
    },
    {
        "name": "Kaveri National Institute of Engineering",
        "short_code": "knie",
        "prefix": "KNIE",
        "type": "Regional Engineering College",
        "city": "Mysuru",
        "state": "Karnataka",
        "est_year": 1978,
        "website": "https://knie.example.edu",
        "address": "KRS Road, Metagalli Industrial Area, Mysuru, Karnataka 570016",
        "phone": "+91 821 240 3210",
    },
    {
        "name": "Gangetic University of Applied Sciences",
        "short_code": "guas",
        "prefix": "GUAS",
        "type": "State Technological University",
        "city": "Varanasi",
        "state": "Uttar Pradesh",
        "est_year": 2002,
        "website": "https://guas.example.edu",
        "address": "Knowledge City, Babatpur Highway, Varanasi, Uttar Pradesh 221006",
        "phone": "+91 542 262 7700",
    },
    {
        "name": "Brahmaputra Technological College",
        "short_code": "btc",
        "prefix": "BTC",
        "type": "Premier Engineering Institute",
        "city": "Guwahati",
        "state": "Assam",
        "est_year": 1985,
        "website": "https://btc.example.edu",
        "address": "Jalukbari Hills, Near Saraighat, Guwahati, Assam 781014",
        "phone": "+91 361 258 4001",
    },
    {
        "name": "Coromandel Institute of Science & Technology",
        "short_code": "cist",
        "prefix": "CIST",
        "type": "Coastal Polytechnic University",
        "city": "Kochi",
        "state": "Kerala",
        "est_year": 2006,
        "website": "https://cist.example.edu",
        "address": "Seaport-Airport Road, Kakkanad, Kochi, Kerala 682030",
        "phone": "+91 484 297 8820",
    },
]

OFFICIAL_DEPARTMENTS = [
    "Computer Science",
    "Information Technology",
    "Electronics and Communication",
    "Mechanical Engineering",
    "Civil Engineering",
    "Electrical Engineering",
    "Artificial Intelligence and Data Science",
    "Management",
]

FIRST_NAMES = [
    "Aarav", "Aditi", "Akhil", "Ananya", "Aniket", "Ankita", "Arjun", "Bhavya",
    "Chirag", "Deepak", "Divya", "Gaurav", "Harini", "Ishaan", "Kavya", "Madhav",
    "Manish", "Meera", "Neha", "Nikhil", "Pooja", "Pranav", "Priya", "Rahul",
    "Rhea", "Rohan", "Sanjay", "Shreya", "Siddharth", "Sneha", "Tanvi", "Varun",
    "Vikram", "Yash", "Zoya", "Alok", "Devika", "Karthik", "Lavanya", "Naveen",
    "Pallavi", "Rajesh", "Sandhya", "Tarun", "Vidya", "Abhishek", "Geeta", "Mohit"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Joshi", "Mehta", "Rathore", "Chauhan", "Rajput",
    "Iyer", "Nair", "Murthy", "Rao", "Reddy", "Venkatesh", "Krishnan", "Gowda",
    "Das", "Banerjee", "Mukherjee", "Saikia", "Borah", "Barman", "Roy", "Bose",
    "Mishra", "Tiwari", "Dubey", "Shukla", "Tripathi", "Pandey", "Saxena", "Bhat"
]

FACULTY_DESIGNATIONS = [
    "Assistant Professor",
    "Associate Professor",
    "Professor",
    "Head of Department",
]

DEFAULT_PASSWORD = "DevSeed@2026!"


class Command(BaseCommand):
    help = "Seed fictional Indian institutes with realistic multi-tenant faculty and students."

    def add_arguments(self, parser):
        parser.add_argument(
            "--institutes",
            type=int,
            default=6,
            help="Number of institutes to seed (1 to 6, default 6)",
        )
        parser.add_argument(
            "--faculty-per-dept",
            type=int,
            default=3,
            help="Number of faculty per department (default 3)",
        )
        parser.add_argument(
            "--students-per-dept",
            type=int,
            default=10,
            help="Number of students per department (default 10)",
        )
        parser.add_argument(
            "--dev-password",
            type=str,
            default=DEFAULT_PASSWORD,
            help=f"Shared development password for seeded users (default: {DEFAULT_PASSWORD})",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducible name generation (default 42)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the seeding process without modifying the database",
        )
        parser.add_argument(
            "--reset-seed",
            action="store_true",
            help="Safely remove ONLY seeded records (is_seed=True), leaving all real data intact",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm actions automatically without interactive prompt",
        )
        parser.add_argument(
            "--i-know-this-is-not-prod",
            action="store_true",
            help="Bypass production guard when DEBUG=False",
        )

    def handle(self, *args, **options):
        # 1. Production safety guard
        if not getattr(settings, "DEBUG", False) and not options.get("i_know_this_is_not_prod"):
            raise CommandError(
                "SAFETY GUARD: seed_institutes cannot run in a production environment (DEBUG=False) "
                "without passing the explicit --i-know-this-is-not-prod flag."
            )

        # 2. Reset Seed Data handler
        if options.get("reset_seed"):
            self._handle_reset_seed(options)
            return

        # 3. Seeding Execution
        self._handle_seed(options)

    def _handle_reset_seed(self, options):
        inst_count = AdminInstitution.objects.filter(is_seed=True).count()
        fac_count = FacultyProfile.objects.filter(is_seed=True).count()
        stu_count = StudentProfile.objects.filter(is_seed=True).count()
        adm_count = AdminProfile.objects.filter(is_seed=True).count()

        total_profiles = fac_count + stu_count + adm_count
        self.stdout.write(self.style.WARNING(
            f"\n=== RESET SEED DATA REQUESTED ===\n"
            f"Target records marked with is_seed=True:\n"
            f"  - Institutions: {inst_count}\n"
            f"  - Admin Profiles: {adm_count}\n"
            f"  - Faculty Profiles: {fac_count}\n"
            f"  - Student Profiles: {stu_count}\n"
            f"Total seeded user accounts: {total_profiles}\n"
        ))

        if total_profiles == 0 and inst_count == 0:
            self.stdout.write(self.style.SUCCESS("No seeded records found to remove."))
            return

        if not options.get("yes"):
            confirm = input("Are you sure you want to delete these seeded records? (yes/no): ").strip().lower()
            if confirm != "yes":
                self.stdout.write(self.style.NOTICE("Reset operation cancelled by user."))
                return

        with transaction.atomic():
            # Collect seeded user IDs
            admin_user_ids = list(AdminProfile.objects.filter(is_seed=True).values_list('user_id', flat=True))
            fac_user_ids = list(FacultyProfile.objects.filter(is_seed=True).values_list('user_id', flat=True))
            stu_user_ids = list(StudentProfile.objects.filter(is_seed=True).values_list('user_id', flat=True))
            all_seed_user_ids = set(admin_user_ids + fac_user_ids + stu_user_ids)

            # Delete institutions (cascades to departments, exams created by seed)
            deleted_insts = AdminInstitution.objects.filter(is_seed=True).delete()
            # Delete seed users
            deleted_users = User.objects.filter(id__in=all_seed_user_ids).delete()

        self.stdout.write(self.style.SUCCESS(
            f"Successfully removed seed data:\n"
            f"  - Institutions deleted: {deleted_insts[0]}\n"
            f"  - Users deleted: {deleted_users[0]}\n"
            f"All real non-seed accounts, exams, and data remain completely untouched.\n"
        ))

    def _handle_seed(self, options):
        target_institutes_count = max(1, min(options.get("institutes", 6), len(FICTIONAL_INSTITUTES)))
        faculty_per_dept = max(1, options.get("faculty_per_dept", 3))
        students_per_dept = max(1, options.get("students_per_dept", 10))
        dev_password = options.get("dev_password", DEFAULT_PASSWORD)
        is_dry_run = options.get("dry_run", False)
        rng_seed = options.get("seed", 42)

        rng = random.Random(rng_seed)

        self.stdout.write(self.style.NOTICE(
            f"\n=== SEED INSTITUTES CONFIGURATION ===\n"
            f"Institutes: {target_institutes_count}\n"
            f"Departments per Institute: {len(OFFICIAL_DEPARTMENTS)}\n"
            f"Faculty per Department: {faculty_per_dept}\n"
            f"Students per Department: {students_per_dept}\n"
            f"Dry Run: {is_dry_run}\n"
            f"Random Seed: {rng_seed}\n"
        ))

        selected_institutes = FICTIONAL_INSTITUTES[:target_institutes_count]

        # Credentials tracking
        credentials_records: List[Dict[str, str]] = []

        total_created = {
            "institutions": 0,
            "departments": 0,
            "admins": 0,
            "faculty": 0,
            "students": 0,
        }
        total_skipped = 0

        # Unique username generator helper
        used_usernames = set(User.objects.values_list("username", flat=True))

        for inst_data in selected_institutes:
            self.stdout.write(self.style.HTTP_INFO(f"\nProcessing Institute: {inst_data['name']} ({inst_data['prefix']})..."))

            if is_dry_run:
                self.stdout.write(f"  [DRY-RUN] Would create/verify institution: {inst_data['name']}")
                self.stdout.write(f"  [DRY-RUN] Would create {len(OFFICIAL_DEPARTMENTS)} departments")
                self.stdout.write(f"  [DRY-RUN] Would create 1 Admin, {len(OFFICIAL_DEPARTMENTS) * faculty_per_dept} Faculty, {len(OFFICIAL_DEPARTMENTS) * students_per_dept} Students")
                total_created["institutions"] += 1
                total_created["admins"] += 1
                total_created["departments"] += len(OFFICIAL_DEPARTMENTS)
                total_created["faculty"] += len(OFFICIAL_DEPARTMENTS) * faculty_per_dept
                total_created["students"] += len(OFFICIAL_DEPARTMENTS) * students_per_dept
                continue

            with transaction.atomic():
                # 1. Admin User & Institution
                admin_username = f"admin.{inst_data['short_code']}@example.edu"
                admin_email = admin_username

                admin_user, created_adm = User.objects.get_or_create(
                    username=admin_username,
                    defaults={
                        "email": admin_email,
                        "first_name": "Admin",
                        "last_name": inst_data["prefix"],
                        "is_staff": False,
                        "is_active": True,
                    },
                )
                if created_adm:
                    admin_user.set_password(dev_password)
                    admin_user.save()
                    total_created["admins"] += 1
                else:
                    total_skipped += 1

                used_usernames.add(admin_username)
                credentials_records.append({
                    "institute": inst_data["name"],
                    "role": "admin",
                    "department": "Administration",
                    "name": f"Admin {inst_data['prefix']}",
                    "username": admin_username,
                    "email": admin_email,
                    "password": dev_password,
                    "id_number": "N/A",
                })

                # Admin Profile
                AdminProfile.objects.get_or_create(
                    user=admin_user,
                    defaults={"is_seed": True},
                )

                # Institution Record
                institution = AdminInstitution.objects.filter(
                    institution_name=inst_data["name"]
                ).first()

                if not institution:
                    # Generate code: INST-2026-xxx
                    inst_code = AdminInstitution.generate_unique_institution_code()
                    institution = AdminInstitution.objects.create(
                        admin=admin_user,
                        institution_name=inst_data["name"],
                        institution_code=inst_code,
                        short_code=inst_data["short_code"],
                        institution_type=inst_data["type"],
                        city=inst_data["city"],
                        state=inst_data["state"],
                        established_year=inst_data["est_year"],
                        website=inst_data["website"],
                        address=inst_data["address"],
                        phone=inst_data["phone"],
                        status=AdminInstitution.STATUS_ACTIVE,
                        is_seed=True,
                    )
                    total_created["institutions"] += 1
                else:
                    total_skipped += 1

                # 2. Departments
                for dept_name in OFFICIAL_DEPARTMENTS:
                    dept, created_dept = AdminDepartment.objects.get_or_create(
                        institution=institution,
                        department_name=dept_name,
                    )
                    if created_dept:
                        total_created["departments"] += 1

                    dept_code = "".join([w[0].upper() for w in dept_name.replace("and", "").split() if w])[:4]

                    # 3. Faculty for this Department
                    for f_idx in range(1, faculty_per_dept + 1):
                        first = rng.choice(FIRST_NAMES)
                        last = rng.choice(LAST_NAMES)
                        base_username = f"{first.lower()}.{last.lower()}.fac.{f_idx}@{inst_data['short_code']}.example.edu"
                        fac_email = base_username

                        fac_user, created_fac = User.objects.get_or_create(
                            username=base_username,
                            defaults={
                                "email": fac_email,
                                "first_name": first,
                                "last_name": last,
                                "is_active": True,
                            },
                        )
                        if created_fac:
                            fac_user.set_password(dev_password)
                            fac_user.save()

                        emp_id = f"F{inst_data['prefix'][:3]}{dept_code}{f_idx:02d}"[:12]
                        designation = rng.choice(FACULTY_DESIGNATIONS)

                        fac_profile, prof_created = FacultyProfile.objects.get_or_create(
                            user=fac_user,
                            defaults={
                                "institution": institution,
                                "department": dept_name,
                                "employee_id": emp_id,
                                "designation": designation,
                                "is_seed": True,
                            },
                        )
                        if created_fac or prof_created:
                            total_created["faculty"] += 1
                        else:
                            total_skipped += 1

                        credentials_records.append({
                            "institute": inst_data["name"],
                            "role": "faculty",
                            "department": dept_name,
                            "name": f"{first} {last}",
                            "username": base_username,
                            "email": fac_email,
                            "password": dev_password,
                            "id_number": emp_id,
                        })

                    # 4. Students for this Department
                    for s_idx in range(1, students_per_dept + 1):
                        first = rng.choice(FIRST_NAMES)
                        last = rng.choice(LAST_NAMES)
                        base_username = f"{first.lower()}.{last.lower()}.stu.{s_idx}@{inst_data['short_code']}.example.edu"
                        stu_email = base_username

                        stu_user, created_stu = User.objects.get_or_create(
                            username=base_username,
                            defaults={
                                "email": stu_email,
                                "first_name": first,
                                "last_name": last,
                                "is_active": True,
                            },
                        )
                        if created_stu:
                            stu_user.set_password(dev_password)
                            stu_user.save()

                        # Student ID format (max 13 chars): e.g. PITS-CS-0001
                        roll_no = f"{inst_data['prefix'][:4]}-{dept_code[:2]}-{s_idx:04d}"

                        stu_profile, stu_prof_created = StudentProfile.objects.get_or_create(
                            user=stu_user,
                            defaults={
                                "institution": institution,
                                "department": dept_name,
                                "student_id": roll_no,
                                "is_seed": True,
                            },
                        )
                        if created_stu or stu_prof_created:
                            total_created["students"] += 1
                        else:
                            total_skipped += 1

                        credentials_records.append({
                            "institute": inst_data["name"],
                            "role": "student",
                            "department": dept_name,
                            "name": f"{first} {last}",
                            "username": base_username,
                            "email": stu_email,
                            "password": dev_password,
                            "id_number": roll_no,
                        })

        # 5. Write credentials to gitignored file seed_credentials.csv
        if not is_dry_run and credentials_records:
            cred_file = os.path.join(settings.BASE_DIR, "seed_credentials.csv")
            try:
                with open(cred_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=["institute", "role", "department", "name", "username", "email", "password", "id_number"]
                    )
                    writer.writeheader()
                    writer.writerows(credentials_records)
                self.stdout.write(self.style.SUCCESS(f"\nSaved {len(credentials_records)} user credentials to {cred_file} (gitignored)."))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"Failed to write credentials file: {exc}"))

        # Summary output
        self.stdout.write(self.style.SUCCESS(
            f"\n=== SEEDING SUMMARY ===\n"
            f"Institutes created/verified: {total_created['institutions']}\n"
            f"Departments created/verified: {total_created['departments']}\n"
            f"Admin accounts created: {total_created['admins']}\n"
            f"Faculty accounts created: {total_created['faculty']}\n"
            f"Student accounts created: {total_created['students']}\n"
            f"Total Seed Users: {total_created['admins'] + total_created['faculty'] + total_created['students']}\n"
            f"Existing/Skipped items: {total_skipped}\n"
        ))
