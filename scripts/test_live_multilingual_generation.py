"""
Live Multilingual End-to-End Verification Script.
Runs on actual local Ollama with installed models (gemma3:4b and bge-m3).
Tests:
1. RAG retrieval on Gujarati curriculum with bge-m3
2. Generation of 1 Gujarati MCQ with gemma3:4b
3. Generation of 1 Hindi Short Answer with gemma3:4b
4. PDF & DOCX rendering with real model outputs
"""
import sys
import os
import io
import time
import json

sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from ai_paper_generator.ollama_client import OllamaClient
from ai_paper_generator.rag.embedder import RAGEmbedder
from ai_paper_generator.rag.vector_store import LocalVectorStore
from ai_paper_generator.rag.retriever import RAGRetriever
from ai_paper_generator.generators.question_generator import QuestionGenerator
from ai_paper_generator.exporters.pdf import export_paper_to_pdf
from ai_paper_generator.exporters.docx import export_paper_to_docx
from ai_paper_generator.language import detect_language, verify_question_language

print("=== Starting Live Multilingual End-to-End Probe ===")

client = OllamaClient()

# 1. RAG Indexing & Retrieval with bge-m3
gujarati_material = [
    {
        'chunk_id': 'c1',
        'text': 'પ્રકાશસંશ્લેષણ એ એવી પ્રક્રિયા છે જેમાં લીલી વનસ્પતિ સૂર્યપ્રકાશ, પાણી અને કાર્બન ડાયોક્સાઇડનો ઉપયોગ કરીને ખોરાક (ગ્લુકોઝ) બનાવે છે અને ઓક્સિજન વાયુ મુક્ત કરે છે. હરિતદ્રવ્ય (ક્લોરોફિલ) સૂર્યની પ્રકાશઊર્જાનું શોષણ કરે છે.',
        'topic': 'પ્રકાશસંશ્લેષણ',
        'page': 1,
        'source': 'biology_gujarati.txt',
    },
    {
        'chunk_id': 'c2',
        'text': 'પૃથ્વી પર જળચક્ર એ પાણીનું વાતાવરણ, જમીન અને મહાસાગરો વચ્ચે સતત થતું પરિભ્રમણ છે. બાષ્પીભવન, ઘનીભવન અને વરસાદ એ જળચક્રના મુખ્ય ઘટકો છે.',
        'topic': 'જળચક્ર',
        'page': 2,
        'source': 'geography_gujarati.txt',
    }
]

vs = LocalVectorStore(job_id=9999, language='gu')
vs.add_chunks(gujarati_material)
retriever = RAGRetriever(vs, job_id=9999)

ctx = retriever.retrieve_context_for_slot(topic='પ્રકાશસંશ્લેષણ', question_type='MCQ', difficulty='Medium')
print(f"[1/4] RAG Retrieval with bge-m3: Got {len(ctx)} chars of context.")
assert 'ગ્લુકોઝ' in ctx, "Expected Gujarati terms in retrieved context"
print("      RAG Retrieval: SUCCESS")

# 2. MCQ Generation in Gujarati with gemma3:4b
qgen = QuestionGenerator(client, retriever, job_id=9999, language='gu')
slot_mcq = {
    'slot_index': 1,
    'type': 'MCQ',
    'topic': 'પ્રકાશસંશ્લેષણ',
    'difficulty': 'Medium',
    'marks': 1,
}

t0 = time.time()
mcq_res = qgen.generate_single_slot(slot_mcq, subject='વિજ્ઞાન', model_name='gemma3:4b')
t_gen = time.time() - t0
print(f"[2/4] Gujarati MCQ generated in {t_gen:.2f}s:")
print(f"      Question: {mcq_res.get('question')}")
print(f"      Options: {mcq_res.get('options')}")
print(f"      Answer: {mcq_res.get('answer')}")

assert mcq_res.get('question'), "Missing question text"
assert len(mcq_res.get('options', [])) == 4, f"Expected 4 options, got {len(mcq_res.get('options', []))}"
lang_ok, reason = verify_question_language(mcq_res, 'gu')
print(f"      Language verification: {lang_ok} ({reason or 'Pure Gujarati'})")
assert lang_ok, f"Language check failed: {reason}"

# 3. Short Answer in Hindi with gemma3:4b
qgen_hi = QuestionGenerator(client, retriever, job_id=9998, language='hi')
slot_short = {
    'slot_index': 2,
    'type': 'Short Answer',
    'topic': 'પ્રકાશસંશ્લેષણ',
    'difficulty': 'Medium',
    'marks': 2,
}
t0 = time.time()
short_res = qgen_hi.generate_single_slot(slot_short, subject='जीव विज्ञान', model_name='gemma3:4b')
t_short = time.time() - t0
print(f"[3/4] Hindi Short Answer generated in {t_short:.2f}s:")
print(f"      Question: {short_res.get('question')}")
print(f"      Answer: {short_res.get('answer')}")
print(f"      Rubric key_points: {short_res.get('key_points')}")
assert short_res.get('question'), "Missing Hindi short answer"

# 4. PDF and DOCX Exports
paper_payload = {
    'title': 'વિજ્ઞાન કસોટી ૨૦૨૬',
    'subject': 'વિજ્ઞાન',
    'duration': 60,
    'total_marks': 3,
    'language': 'gu',
    'questions': [mcq_res, short_res],
}
pdf_bytes = export_paper_to_pdf(paper_payload, include_answers=True)
docx_bytes = export_paper_to_docx(paper_payload, include_answers=True)
print(f"[4/4] Exports verified: PDF ({len(pdf_bytes)} bytes), DOCX ({len(docx_bytes)} bytes)")
assert pdf_bytes.startswith(b'%PDF-'), "Invalid PDF header"
assert docx_bytes.startswith(b'PK'), "Invalid DOCX header"

# Clean up test vector store
vs.clear()

print("=== ALL LIVE MULTILINGUAL VERIFICATION TESTS PASSED SUCCESSFULLY! ===")
