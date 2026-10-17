import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from django.apps import apps

output_file = sys.argv[1] if len(sys.argv) > 1 else 'counts.txt'

lines = []
for model in sorted(apps.get_models(), key=lambda m: (m._meta.app_label, m._meta.model_name)):
    app_label = model._meta.app_label
    model_name = model._meta.model_name
    count = model.objects.count()
    lines.append(f"{app_label}.{model_name}: {count}")

with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

print(f"Recorded row counts for {len(lines)} models to {output_file}")
