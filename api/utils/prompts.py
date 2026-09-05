import json


def build_generation_prompt(
    title,
    duration_minutes,
    total_marks,
    topics,
    question_types,
    difficulty_pct,
    syllabus_text,
    counts,
    actual_total_marks,
):
    syllabus_excerpt = (syllabus_text or '')[:6000]
    return f"""Generate one exam paper as a single JSON object and nothing else.

Required JSON shape:
{{
  "title": "{title}",
  "duration_minutes": {duration_minutes},
  "total_marks": {actual_total_marks},
  "questions": [
    {{
      "type": "mcq|truefalse|fillblank|subjective",
      "difficulty": "easy|medium|hard",
      "topic": "topic name",
      "text": "question text",
      "options": ["option 1", "option 2", "option 3", "option 4"] or null,
      "correct_answer": "A",
      "model_answer": "model answer for subjective questions",
      "marks": 1
    }}
  ]
}}

Exam title: {title}
Duration in minutes: {duration_minutes}
Requested marks budget: {total_marks}
Computed actual total marks: {actual_total_marks}
Exact question counts: {json.dumps(counts)}
Allowed topics: {json.dumps(list(topics or []))}
Allowed question types: {json.dumps(list(question_types or []))}
Difficulty distribution: {json.dumps(difficulty_pct or {})}

Rules:
- Generate EXACTLY {counts.get('mcq', 0)} mcq questions, EXACTLY {counts.get('truefalse', 0)} truefalse questions, EXACTLY {counts.get('fillblank', 0)} fillblank questions, EXACTLY {counts.get('subjective', 0)} subjective questions. Do not generate more or fewer of any type.
- Do not decide question counts or marks yourself. Always set mcq, truefalse, and fillblank marks to 1, and subjective marks to 10.
- Use only the allowed question types and topics.
- MCQ and fillblank questions require exactly 4 option strings, labeled conceptually A/B/C/D, and correct_answer must be one of "A", "B", "C", or "D" for the correct option position.
- True/false questions must use options exactly ["True", "False"], where A means True and B means False, and correct_answer must be "A" or "B".
- Fill-in-the-blank questions must mark the blank in the text and provide one correct option plus three plausible distractors.
- Subjective questions must have no options and must provide a model_answer instead.
- Base every question only on the syllabus text and allowed topics.
- Return JSON only. Do not include commentary, explanations, markdown, or code fences.

Syllabus text:
{syllabus_excerpt}
"""


def build_type_generation_prompt(
    question_type,
    count,
    marks_per_question,
    topics,
    difficulty_pct,
    syllabus_text,
):
    syllabus_excerpt = (syllabus_text or '')[:6000]
    if question_type == 'truefalse':
        option_rules = 'Use options exactly ["True", "False"]. correct_answer must be "A" for True or "B" for False.'
    elif question_type in {'mcq', 'fillblank'}:
        option_rules = 'Use exactly 4 option strings. correct_answer must be one of "A", "B", "C", or "D" for the correct option position.'
    else:
        option_rules = 'Use no options and provide a useful model_answer.'

    return f"""Generate exactly {count} {question_type} questions as one JSON object and nothing else.

Required JSON shape:
{{
  "questions": [
    {{
      "type": "{question_type}",
      "difficulty": "easy|medium|hard",
      "topic": "topic name",
      "text": "question text",
      "options": ["option 1", "option 2", "option 3", "option 4"] or null,
      "correct_answer": "A|B|C|D",
      "model_answer": "model answer for subjective questions",
      "marks": {marks_per_question}
    }}
  ]
}}

Rules:
- Generate EXACTLY {count} questions of type {question_type}; do not generate more or fewer.
- Every question must be based only on these topics and syllabus text: {json.dumps(list(topics or []))}
- Difficulty distribution guidance: {json.dumps(difficulty_pct or {})}
- Every question must have marks exactly {marks_per_question}; never invent another value.
- {option_rules}
- For fillblank, mark the blank in the text and include one correct option plus three plausible distractors.
- Return JSON only with no markdown, commentary, or code fences.

Syllabus text:
{syllabus_excerpt}
"""


def build_evaluation_prompt(question_text, model_answer, student_answer, max_marks):
    return f"""Evaluate this student's answer against the model answer.
The student may use entirely different wording, structure, examples, or ordering than the model answer. Grade based on whether the student demonstrates correct understanding of the concept the question is actually asking about, not lexical similarity to the model answer.
If the student's answer covers the core concept correctly but omits minor details, award most of the marks, not zero. If the student answer contains extra correct elaboration beyond the model answer, do not penalize it. Only reduce marks for factual errors, missing core concepts, or irrelevant content. A blank or irrelevant answer receives 0.
Return only one JSON object in exactly this shape: {{"score": number, "feedback": "1-2 sentences"}}.
The score must be between 0 and {max_marks}.

Question:
{question_text}

Model answer:
{model_answer}

Student answer:
{student_answer}
"""
