import json
import os
import traceback
from datetime import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import django

django.setup()

from rest_framework.test import APIClient


client = APIClient()
out = {
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "results": [],
}

payload = {
    "first_name": "Test",
    "last_name": "User",
    "email": "debug_auth_user@example.com",
    "password": "Harsh@2102",
}

roles = ["students", "faculty", "admins"]

for role in roles:
    signup_path = f"/api/{role}/signup/"
    login_path = f"/api/{role}/login/"

    for kind, path, body in [
        ("signup", signup_path, payload),
        (
            "login",
            login_path,
            {"email": payload["email"], "password": payload["password"]},
        ),
    ]:
        item = {"role": role, "type": kind, "path": path}
        try:
            response = client.post(path, data=body, format="json")
            item["status_code"] = response.status_code
            try:
                item["json"] = response.json()
            except Exception:
                item["content"] = response.content.decode("utf-8", errors="replace")
        except Exception:
            item["exception"] = traceback.format_exc()
        out["results"].append(item)

with open("auth_diagnostics.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
