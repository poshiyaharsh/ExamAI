from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from faculty.models import FacultyProfile
from admins.models import AdminInstitution
from ai_paper_generator.models import PaperDraft

User = get_user_model()


class PaperDraftTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='admin_inst_test', password='pass123')
        self.institution = AdminInstitution.objects.create(
            institution_name="Test Institute",
            admin=self.admin_user
        )
        self.user1 = User.objects.create_user(
            username="faculty1",
            email="faculty1@test.com",
            password="Password@123"
        )
        self.faculty1 = FacultyProfile.objects.create(
            user=self.user1,
            institution=self.institution
        )

        self.user2 = User.objects.create_user(
            username="faculty2",
            email="faculty2@test.com",
            password="Password@123"
        )
        self.faculty2 = FacultyProfile.objects.create(
            user=self.user2,
            institution=self.institution
        )

        self.client1 = APIClient()
        self.client1.force_authenticate(user=self.user1)

        self.client2 = APIClient()
        self.client2.force_authenticate(user=self.user2)

    def test_save_and_get_draft(self):
        payload = {
            "draft": {
                "title": "OS Exam",
                "subject": "Operating Systems",
                "total_marks": 50,
                "sections": [{"type": "MCQ", "count": 10, "marks_per_question": 1}]
            },
            "version": 4
        }
        res_post = self.client1.post("/api/ai-generator/draft/", payload, format="json")
        self.assertEqual(res_post.status_code, 200)
        self.assertEqual(res_post.data["status"], "saved")

        res_get = self.client1.get("/api/ai-generator/draft/")
        self.assertEqual(res_get.status_code, 200)
        self.assertIsNotNone(res_get.data["draft"])
        self.assertEqual(res_get.data["draft"]["subject"], "Operating Systems")
        self.assertEqual(res_get.data["version"], 4)

    def test_draft_user_isolation(self):
        # Faculty 1 saves draft
        self.client1.post("/api/ai-generator/draft/", {
            "draft": {"title": "Faculty1 Paper", "subject": "CS101"}
        }, format="json")

        # Faculty 2 gets draft -> should be None
        res2 = self.client2.get("/api/ai-generator/draft/")
        self.assertEqual(res2.status_code, 200)
        self.assertIsNone(res2.data["draft"])

    def test_clear_draft(self):
        self.client1.post("/api/ai-generator/draft/", {
            "draft": {"title": "To be cleared", "subject": "CS"}
        }, format="json")

        res_del = self.client1.delete("/api/ai-generator/draft/")
        self.assertEqual(res_del.status_code, 200)

        res_get = self.client1.get("/api/ai-generator/draft/")
        self.assertIsNone(res_get.data["draft"])
