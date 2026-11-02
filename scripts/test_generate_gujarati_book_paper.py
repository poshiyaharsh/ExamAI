"""
Live End-to-End Test: Generate Full Gujarati Exam Paper from computer-book.PDF
"""
import os
import sys
import json

# Setup Django environment
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from ai_paper_generator.rag.loader import load_document
from ai_paper_generator.language import determine_paper_language
from ai_paper_generator.rag.embedder import RAGEmbedder
from ai_paper_generator.rag.vector_store import LocalVectorStore
from ai_paper_generator.rag.retriever import RAGRetriever
from ai_paper_generator.ollama_client import OllamaClient
from ai_paper_generator.prompts.mcq import build_batch_mcq_prompt, get_batch_mcq_schema
from ai_paper_generator.prompts.true_false import build_batch_true_false_prompt, get_batch_true_false_schema
from ai_paper_generator.prompts.short import build_batch_short_prompt, get_batch_short_schema
from ai_paper_generator.generators.json_repair import parse_and_repair_json
from ai_paper_generator.generators.validator import validate_rules
from ai_paper_generator.exporters.pdf import export_paper_to_pdf
from ai_paper_generator.exporters.docx import export_paper_to_docx


def main():
    pdf_path = r'C:\Users\Harsh Poshiya\Downloads\computer-book.PDF'
    print(f"Loading document: {pdf_path}...")
    pages = load_document(pdf_path)
    print(f"Extracted {len(pages)} pages.")

    # Select Chapter 1: Computer Fundamentals (Pages 10 to 18)
    ch1_pages = [p for p in pages if 10 <= p['page_number'] <= 18]
    print(f"Selected Chapter 1 pages: {len(ch1_pages)}")

    # Detect language
    lang_code, conf, meta = determine_paper_language(ch1_pages)
    print(f"\n[LANGUAGE DETECTION RESULT]")
    print(f"Detected: {lang_code} ({meta.get('language_name')}) | Conf: {conf:.2f} | Script: {meta.get('script')}")
    assert lang_code == 'gu', f"Expected 'gu', got '{lang_code}'"

    # Embed and index with bge-m3
    print("\n[RAG INDEXING with bge-m3]")
    embedder = RAGEmbedder(language=lang_code)
    store = LocalVectorStore(job_id=9999, embedder=embedder, language=lang_code)
    
    chunks_to_index = []
    for p in ch1_pages:
        chunks_to_index.append({
            'chunk_id': f"p_{p['page_number']}",
            'text': p['text'],
            'page': p['page_number'],
            'source': 'computer-book.PDF',
            'topic': 'કોમ્પ્યુટરની પાયાની સમજ'
        })
    store.add_chunks(chunks_to_index)
    print(f"Indexed {len(chunks_to_index)} chunks into vector store.")

    retriever = RAGRetriever(store, job_id=9999)
    client = OllamaClient()

    # 1. Generate Gujarati MCQs
    print("\n[GENERATING 2 MCQs in Gujarati]")
    mcq_context = retriever.retrieve_context_for_slot(
        topic="કોમ્પ્યુટર ઇનપુટ આઉટપુટ સાધનો સીપીયુ ડેટા",
        question_type="MCQ",
        difficulty="Medium"
    )
    mcq_slots = [
        {'slot_id': 1, 'difficulty': 'Easy', 'marks': 1, 'topic': 'કોમ્પ્યુટર ઇનપુટ સાધનો'},
        {'slot_id': 2, 'difficulty': 'Medium', 'marks': 1, 'topic': 'સીપીયુ અને મેમરી'}
    ]
    mcq_prompt = build_batch_mcq_prompt(
        subject="કમ્પ્યુટર માર્ગદર્શિકા",
        slots=mcq_slots,
        context=mcq_context,
        unit="પ્રકરણ ૧: કોમ્પ્યુટર પરિચય",
        language=lang_code,
    )
    mcq_schema = get_batch_mcq_schema(2)
    mcq_raw = client.generate(
        model="gemma3:4b",
        prompt=mcq_prompt,
        format=mcq_schema,
        temperature=0.3,
        num_ctx=4096,
        num_predict=2000
    )
    parsed_mcq = parse_and_repair_json(mcq_raw)
    mcqs = parsed_mcq.get('questions', []) if isinstance(parsed_mcq, dict) else parsed_mcq
    print(f"Generated {len(mcqs)} MCQs.")
    formatted_mcqs = []
    for idx, q in enumerate(mcqs, 1):
        opts = [q.get('correct')] + q.get('distractors', [])
        formatted_mcqs.append({
            'question': q.get('question'),
            'options': opts,
            'answer': q.get('correct'),
            'marks': 1,
            'difficulty': q.get('difficulty', 'Medium')
        })
        print(f"  Q{idx}: {q.get('question')}")
        print(f"      Options: {opts}")
        print(f"      Correct Answer: {q.get('correct')}")

    # 2. Generate Gujarati True/False
    print("\n[GENERATING 2 True/False in Gujarati]")
    tf_context = retriever.retrieve_context_for_slot(
        topic="કોમ્પ્યુટર હાર્ડવેર અને ડેટા પ્રોસેસિંગ",
        question_type="True/False",
        difficulty="Easy"
    )
    tf_slots = [
        {'slot_id': 3, 'difficulty': 'Easy', 'marks': 1, 'topic': 'ઇનપુટ ડિવાઇસ'},
        {'slot_id': 4, 'difficulty': 'Easy', 'marks': 1, 'topic': 'સીપીયુ કાર્ય'}
    ]
    tf_prompt = build_batch_true_false_prompt(
        subject="કમ્પ્યુટર માર્ગદર્શિકા",
        slots=tf_slots,
        context=tf_context,
        unit="પ્રકરણ ૧: કોમ્પ્યુટર પરિચય",
        language=lang_code,
    )
    tf_schema = get_batch_true_false_schema(2)
    tf_raw = client.generate(
        model="gemma3:4b",
        prompt=tf_prompt,
        format=tf_schema,
        temperature=0.3,
        num_ctx=4096,
        num_predict=1500
    )
    parsed_tf = parse_and_repair_json(tf_raw)
    tfs = parsed_tf.get('questions', []) if isinstance(parsed_tf, dict) else parsed_tf
    print(f"Generated {len(tfs)} True/False questions.")
    formatted_tfs = []
    for idx, q in enumerate(tfs, 1):
        formatted_tfs.append({
            'question': q.get('statement') or q.get('question'),
            'answer': "True" if q.get('answer') is True else "False",
            'marks': 1,
            'difficulty': q.get('difficulty', 'Easy')
        })
        print(f"  Q{idx}: {q.get('statement') or q.get('question')}")
        print(f"      Answer: {'True' if q.get('answer') is True else 'False'}")

    # 3. Generate Gujarati Short Answer
    print("\n[GENERATING 1 Short Answer in Gujarati]")
    short_context = retriever.retrieve_context_for_slot(
        topic="સેન્ટ્રલ પ્રોસેસિંગ યુનિટ (CPU) નું કાર્ય",
        question_type="Short Answer",
        difficulty="Medium"
    )
    short_slots = [
        {'slot_id': 5, 'difficulty': 'Medium', 'marks': 3, 'topic': 'સીપીયુ (CPU)'}
    ]
    short_prompt = build_batch_short_prompt(
        subject="કમ્પ્યુટર માર્ગદર્શિકા",
        slots=short_slots,
        context=short_context,
        unit="પ્રકરણ ૧: કોમ્પ્યુટર પરિચય",
        language=lang_code,
    )
    short_schema = get_batch_short_schema(1)
    short_raw = client.generate(
        model="gemma3:4b",
        prompt=short_prompt,
        format=short_schema,
        temperature=0.3,
        num_ctx=4096,
        num_predict=2000
    )
    parsed_short = parse_and_repair_json(short_raw)
    shorts = parsed_short.get('questions', []) if isinstance(parsed_short, dict) else parsed_short
    print(f"Generated {len(shorts)} Short Answer question.")
    formatted_shorts = []
    for idx, q in enumerate(shorts, 1):
        points = q.get('answer_points', [])
        model_ans = "\n".join(f"• {pt}" for pt in points)
        formatted_shorts.append({
            'question': q.get('question'),
            'model_answer': model_ans,
            'key_points': points,
            'marks': 3,
            'difficulty': q.get('difficulty', 'Medium')
        })
        print(f"  Q{idx}: {q.get('question')}")
        print(f"      Model Answer: {model_ans}")
        print(f"      Key Points: {points}")

    # Assemble complete paper
    all_questions = []
    q_num = 1
    for q in formatted_mcqs:
        q['question_number'] = q_num
        q['type'] = 'MCQ'
        all_questions.append(q)
        q_num += 1

    for q in formatted_tfs:
        q['question_number'] = q_num
        q['type'] = 'True/False'
        all_questions.append(q)
        q_num += 1

    for q in formatted_shorts:
        q['question_number'] = q_num
        q['type'] = 'Short Answer'
        all_questions.append(q)
        q_num += 1

    total_marks = sum(q['marks'] for q in all_questions)
    paper_data = {
        'title': 'કોમ્પ્યુટર વિજ્ઞાન - પ્રકરણ ૧ કસોટી',
        'subject': 'કમ્પ્યુટર માર્ગદર્શિકા',
        'duration': 30,
        'total_marks': total_marks,
        'language': 'gu',
        'questions': all_questions,
    }

    # Test PDF and DOCX Exports
    print("\n[TESTING EXPORTS]")
    pdf_bytes = export_paper_to_pdf(paper_data, include_answers=True)
    out_pdf_path = "output_gujarati_computer_exam.pdf"
    with open(out_pdf_path, 'wb') as f:
        f.write(pdf_bytes)
    print(f"  Successfully exported Gujarati PDF: {out_pdf_path} ({len(pdf_bytes)} bytes)")

    docx_bytes = export_paper_to_docx(paper_data, include_answers=True)
    out_docx_path = "output_gujarati_computer_exam.docx"
    with open(out_docx_path, 'wb') as f:
        f.write(docx_bytes)
    print(f"  Successfully exported Gujarati DOCX: {out_docx_path} ({len(docx_bytes)} bytes)")

    print("\n========================================================")
    print(f"SUCCESS: Generated {len(all_questions)} questions ({total_marks} marks) in Full Gujarati!")
    print("========================================================")


if __name__ == '__main__':
    main()
