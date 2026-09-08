import os
import json
import uuid
import urllib.request
import urllib.error

import fitz
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY was not found. "
        "Please create a .env file inside the backend folder."
    )

# ============================================================
# GEMINI CONFIGURATION
# ============================================================

# Use the current Gemini model directly through the REST API.
# This avoids old google-genai SDK model mappings that can silently
# redirect a request to an unavailable model.
GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
]
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def generate_gemini_json(prompt):
    """Call Gemini directly and return the generated JSON text.

    We try the current 3.6 Flash model first and fall back to 3.5 Flash
    only if the account/API key does not have access to the first model.
    """
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": 6000,
        },
    }

    last_error = None

    for model in GEMINI_MODELS:
        url = f"{GEMINI_API_BASE}/{model}:generateContent"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY,
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                raw = response.read().decode("utf-8")

            data = json.loads(raw)
            candidates = data.get("candidates") or []

            if not candidates:
                raise RuntimeError(
                    f"Gemini returned no candidates for {model}: {raw[:2000]}"
                )

            parts = (candidates[0].get("content") or {}).get("parts") or []
            text_parts = [
                str(part.get("text", ""))
                for part in parts
                if isinstance(part, dict) and part.get("text")
            ]
            text = "".join(text_parts).strip()

            if not text:
                raise RuntimeError(
                    f"Gemini returned an empty response for {model}."
                )

            print(f"Gemini model used: {model}")
            return text

        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(
                f"Gemini {model} HTTP {exc.code}: {error_body[:3000]}"
            )
            print(str(last_error))

            # Try the next current model for model/access errors.
            if exc.code in (400, 401, 403, 404, 429):
                continue
            raise last_error

        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = RuntimeError(
                f"Could not connect to Gemini: {exc}"
            )
            break
        except json.JSONDecodeError as exc:
            last_error = RuntimeError(
                f"Gemini returned invalid HTTP JSON: {exc}"
            )
            break

    raise last_error or RuntimeError("Gemini analysis failed.")

# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)
CORS(app)

# ============================================================
# CONFIGURATION
# ============================================================

UPLOAD_FOLDER = "uploads"
DATA_FOLDER = "data"
RESUME_DB = os.path.join(DATA_FOLDER, "resumes.json")
ANALYSIS_DB = os.path.join(DATA_FOLDER, "analyses.json")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Maximum upload size = 10 MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_score(value):
    """Convert a score to an integer between 0 and 100."""
    try:
        value = int(float(value))
    except (TypeError, ValueError):
        value = 0

    return max(0, min(100, value))


def clean_list(value):
    """Make sure a value is a list of strings."""
    if not isinstance(value, list):
        return []

    cleaned = []

    for item in value:
        if item is None:
            continue

        item = str(item).strip()

        if item and item not in cleaned:
            cleaned.append(item)

    return cleaned


def clean_skill_matches(value):
    """Clean skill_matches returned by Gemini."""
    if not isinstance(value, list):
        return []

    cleaned = []

    for item in value:
        if not isinstance(item, dict):
            continue

        skill = str(item.get("skill", "")).strip()

        if not skill:
            continue

        score = clean_score(item.get("score", 0))

        evidence = str(item.get("evidence", "")).strip()

        if not evidence:
            evidence = "No evidence provided."

        cleaned.append(
            {
                "skill": skill,
                "score": score,
                "evidence": evidence,
            }
        )

    return cleaned


def clean_keyword_analysis(value):
    """Clean keyword analysis returned by Gemini."""
    if not isinstance(value, dict):
        value = {}

    return {
        "matched_keywords": clean_list(value.get("matched_keywords", [])),
        "missing_keywords": clean_list(value.get("missing_keywords", [])),
        "important_keywords": clean_list(value.get("important_keywords", [])),
    }


def clean_score_breakdown(value):
    """Clean the ATS score breakdown returned by Gemini."""
    if not isinstance(value, dict):
        value = {}

    return {
        "skills": clean_score(value.get("skills", 0)),
        "experience": clean_score(value.get("experience", 0)),
        "education": clean_score(value.get("education", 0)),
        "keywords": clean_score(value.get("keywords", 0)),
        "resume_quality": clean_score(value.get("resume_quality", 0)),
    }


def normalize_result(result):
    """
    Make sure Gemini's response always has
    the structure expected by the frontend.
    """
    if not isinstance(result, dict):
        result = {}

    # --------------------------------------------------------
    # Scores
    # --------------------------------------------------------

    result["ats_score"] = clean_score(result.get("ats_score", 0))
    result["skill_score"] = clean_score(result.get("skill_score", 0))
    result["experience_score"] = clean_score(
        result.get("experience_score", 0)
    )
    result["education_score"] = clean_score(
        result.get("education_score", 0)
    )

    result["score_breakdown"] = clean_score_breakdown(
        result.get("score_breakdown", {})
    )

    result["keyword_analysis"] = clean_keyword_analysis(
        result.get("keyword_analysis", {})
    )

    # --------------------------------------------------------
    # Lists
    # --------------------------------------------------------

    result["matched_skills"] = clean_list(
        result.get("matched_skills", [])
    )

    result["missing_skills"] = clean_list(
        result.get("missing_skills", [])
    )

    result["required_skills"] = clean_list(
        result.get("required_skills", [])
    )

    result["recommendations"] = clean_list(
        result.get("recommendations", [])
    )

    # --------------------------------------------------------
    # Skill matches
    # --------------------------------------------------------

    result["skill_matches"] = clean_skill_matches(
        result.get("skill_matches", [])
    )

    # --------------------------------------------------------
    # Calculate skill score ourselves
    # --------------------------------------------------------

    if result["skill_matches"]:
        total = sum(
            item["score"]
            for item in result["skill_matches"]
        )

        calculated_score = round(
            total / len(result["skill_matches"])
        )

        result["skill_score"] = clean_score(
            calculated_score
        )

    result["score_breakdown"]["skills"] = result["skill_score"]

    return result


# ============================================================
# PERSISTENT STORAGE HELPERS
# ============================================================

def load_json_file(path, default):
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, type(default)) else default
    except Exception as exc:
        print("STORAGE READ ERROR:", path, exc)
        return default


def save_json_file(path, value):
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, path)


def load_resumes():
    return load_json_file(RESUME_DB, [])


def save_resumes(items):
    save_json_file(RESUME_DB, items)


def load_analyses():
    return load_json_file(ANALYSIS_DB, [])


def save_analyses(items):
    save_json_file(ANALYSIS_DB, items)


def public_resume(record):
    return {
        "id": record.get("id"),
        "filename": record.get("filename"),
        "stored_filename": record.get("stored_filename"),
        "size": record.get("size", 0),
        "uploaded_at": record.get("uploaded_at"),
        "view_url": "/uploads/" + record.get("stored_filename", "") if record.get("stored_filename") else None,
    }


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify(
        {
            "status": "success",
            "message": "ResumeAI backend is working!",
            "endpoints": [
                "/",
                "/health",
                "/upload-resume",
                "/resumes",
                "/analyses",
                "/analyze",
            ],
        }
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "healthy",
            "gemini_configured": bool(GEMINI_API_KEY),
        }
    )


# ============================================================
# PDF UPLOAD + TEXT EXTRACTION
# ============================================================

@app.route("/upload-resume", methods=["POST"])
def upload_resume():

    # --------------------------------------------------------
    # Check file
    # --------------------------------------------------------

    if "resume" not in request.files:
        return jsonify(
            {"error": "No resume file uploaded."}
        ), 400

    file = request.files["resume"]

    if not file or file.filename == "":
        return jsonify(
            {"error": "No file selected."}
        ), 400

    # --------------------------------------------------------
    # Check extension
    # --------------------------------------------------------

    if not file.filename.lower().endswith(".pdf"):
        return jsonify(
            {"error": "Only PDF files are supported."}
        ), 400

    # --------------------------------------------------------
    # Secure filename
    # --------------------------------------------------------

    filename = secure_filename(file.filename)

    if not filename:
        return jsonify(
            {"error": "Invalid filename."}
        ), 400

    # Use a unique server-side filename so two uploads with the same
    # original filename never overwrite each other.
    stored_filename = f"{uuid.uuid4().hex}_{filename}"
    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        stored_filename
    )

    # --------------------------------------------------------
    # Save file
    # --------------------------------------------------------

    try:
        file.save(filepath)

    except Exception as e:
        print("FILE SAVE ERROR:", str(e))

        return jsonify(
            {"error": "Could not save the uploaded PDF."}
        ), 500

    # --------------------------------------------------------
    # Extract PDF text
    # --------------------------------------------------------

    try:
        pdf = fitz.open(filepath)

        pages = []

        for page in pdf:
            page_text = page.get_text()

            if page_text:
                pages.append(page_text)

        pdf.close()

        resume_text = "\n".join(pages).strip()

        # ----------------------------------------------------
        # Check text
        # ----------------------------------------------------

        if not resume_text:
            return jsonify(
                {
                    "error": (
                        "The PDF contains no readable text. "
                        "Please upload a text-based resume PDF."
                    )
                }
            ), 400

        # ----------------------------------------------------
        # Limit text
        # ----------------------------------------------------

        resume_text = resume_text[:50000]

        print("Resume extracted successfully.")
        print("Text length:", len(resume_text))

        resume_id = uuid.uuid4().hex
        record = {
            "id": resume_id,
            "filename": filename,
            "stored_filename": stored_filename,
            "size": os.path.getsize(filepath),
            "uploaded_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "resume_text": resume_text,
        }

        resumes = load_resumes()
        resumes.append(record)
        save_resumes(resumes)

        return jsonify(
            {
                "message": "Resume uploaded successfully.",
                "resume_id": resume_id,
                "filename": filename,
                "text": resume_text,
                "text_length": len(resume_text),
                "resume": public_resume(record),
            }
        ), 200

    except Exception as e:
        print("PDF EXTRACTION ERROR:", str(e))

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError:
            pass

        return jsonify(
            {
                "error": f"Could not read PDF: {str(e)}"
            }
        ), 500


# ============================================================
# RESUME LIBRARY
# ============================================================

@app.route("/resumes", methods=["GET"])
def get_resumes():
    # Import any PDFs already present in uploads/ but missing from the JSON index.
    # This makes the new persistent library recover older uploads when possible.
    resumes = load_resumes()
    known_files = {x.get("stored_filename") for x in resumes}
    changed = False

    for stored_filename in os.listdir(app.config["UPLOAD_FOLDER"]):
        if not stored_filename.lower().endswith(".pdf") or stored_filename in known_files:
            continue
        path = os.path.join(app.config["UPLOAD_FOLDER"], stored_filename)
        if not os.path.isfile(path):
            continue
        original = stored_filename.split("_", 1)[-1]
        try:
            with fitz.open(path) as pdf:
                text = "\n".join((page.get_text() or "") for page in pdf).strip()[:50000]
        except Exception:
            text = ""
        record = {
            "id": uuid.uuid4().hex,
            "filename": original,
            "stored_filename": stored_filename,
            "size": os.path.getsize(path),
            "uploaded_at": __import__("datetime").datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="seconds"),
            "resume_text": text,
        }
        resumes.append(record)
        changed = True

    if changed:
        save_resumes(resumes)

    resumes.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
    return jsonify([public_resume(item) for item in resumes]), 200


@app.route("/resumes/<resume_id>", methods=["GET"])
def get_resume(resume_id):
    for item in load_resumes():
        if item.get("id") == resume_id:
            return jsonify(item), 200
    return jsonify({"error": "Resume not found."}), 404


@app.route("/resumes/<resume_id>", methods=["DELETE"])
def delete_resume(resume_id):
    resumes = load_resumes()
    target = next((x for x in resumes if x.get("id") == resume_id), None)

    if not target:
        return jsonify({"error": "Resume not found."}), 404

    resumes = [x for x in resumes if x.get("id") != resume_id]
    save_resumes(resumes)

    stored = target.get("stored_filename")
    if stored:
        path = os.path.join(app.config["UPLOAD_FOLDER"], stored)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as exc:
            print("FILE DELETE WARNING:", exc)

    analyses = [x for x in load_analyses() if x.get("resume_id") != resume_id]
    save_analyses(analyses)

    return jsonify({"message": "Resume deleted successfully."}), 200


@app.route("/uploads/<path:filename>", methods=["GET"])
def serve_uploaded_resume(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=False)


@app.route("/analyses", methods=["GET"])
def get_analyses():
    analyses = load_analyses()
    analyses.sort(key=lambda x: x.get("analyzed_at", ""), reverse=True)
    return jsonify(analyses), 200


# ============================================================
# ATS ANALYSIS
# ============================================================

@app.route("/analyze", methods=["POST"])
def analyze_resume():

    # --------------------------------------------------------
    # Get JSON
    # --------------------------------------------------------

    data = request.get_json(silent=True)

    if not data:
        return jsonify(
            {"error": "No JSON data received."}
        ), 400

    # --------------------------------------------------------
    # Get resume
    # --------------------------------------------------------

    resume_text = str(
        data.get("resume_text", "")
    ).strip()

    # --------------------------------------------------------
    # Get job description
    # --------------------------------------------------------

    job_description = str(
        data.get("job_description", "")
    ).strip()

    resume_id = str(data.get("resume_id", "")).strip()

    # --------------------------------------------------------
    # Validate resume
    # --------------------------------------------------------

    if not resume_text:
        return jsonify(
            {"error": "Resume text is missing."}
        ), 400

    # --------------------------------------------------------
    # Validate job description
    # --------------------------------------------------------

    if not job_description:
        return jsonify(
            {"error": "Job description is missing."}
        ), 400

    # --------------------------------------------------------
    # Limit input
    # --------------------------------------------------------

    resume_text = resume_text[:50000]
    job_description = job_description[:30000]

    # ========================================================
    # PROMPT
    # ========================================================

    prompt = f"""
You are an expert Applicant Tracking System (ATS)
resume analyzer.

Compare the candidate's resume against the job description.

Be objective and evidence-based.

Do NOT assume a skill is fully matched just because
its name appears once.

==================== RESUME ====================

{resume_text}

================ JOB DESCRIPTION =================

{job_description}

===================================================

Return ONLY valid JSON.

Use exactly this structure:

{{
    "ats_score": 0,
    "skill_score": 0,
    "experience_score": 0,
    "education_score": 0,
    "score_breakdown": {{
        "skills": 0,
        "experience": 0,
        "education": 0,
        "keywords": 0,
        "resume_quality": 0
    }},
    "keyword_analysis": {{
        "matched_keywords": [],
        "missing_keywords": [],
        "important_keywords": []
    }},
    "required_skills": [],
    "matched_skills": [],
    "missing_skills": [],
    "skill_matches": [
        {{
            "skill": "",
            "score": 0,
            "evidence": ""
        }}
    ],
    "recommendations": []
}}

Scoring instructions:

1. ats_score

Give an overall compatibility score from 0 to 100.

Consider:
- Required skills
- Technical skills
- Experience
- Projects
- Education
- Relevant keywords
- Job relevance
- Resume quality

Do not give a high score simply because many keywords appear.

2. skill_score

Measure how strongly the resume supports the required skills.

This must be based on the individual skill_matches.

3. experience_score

Compare the candidate's actual experience with the job requirements.

Consider:
- Internships
- Employment
- Projects
- Practical experience
- Relevant responsibilities

Do not automatically give 100.

4. education_score

Compare the candidate's education against the job requirements.

If the job explicitly requires a degree or field and the resume
does not satisfy it, reduce the score.

If the job does not mention education requirements, use 50.

5. required_skills

List only important technical or professional skills actually
required by the job description.

Do not invent skills.

6. matched_skills

List required skills for which the resume contains meaningful
evidence.

7. missing_skills

List important required skills for which there is insufficient
or no evidence.

8. skill_matches

Create ONE object for EVERY skill in required_skills.

Each object must contain:

skill:
Exact skill name.

score:
Integer from 0 to 100.

evidence:
Short explanation based ONLY on the resume.

Scoring:

0-10:
No evidence.

11-30:
Very weak or indirect evidence.

31-50:
Skill is mentioned or weakly demonstrated.

51-70:
Skill demonstrated through coursework or projects.

71-85:
Strong evidence through projects, internships,
or relevant experience.

86-100:
Very strong repeated evidence through substantial
relevant experience.

Do NOT give 100 merely because the skill appears.

9. keyword_analysis

Analyze important keywords from the job description and compare them
with the resume.

Return:
- matched_keywords: important job-description keywords supported by the resume
- missing_keywords: important job-description keywords not sufficiently supported
- important_keywords: the most important keywords from the job description

Do not invent keywords. Keep the lists concise and relevant.

10. score_breakdown

Return five component scores from 0 to 100:
- skills: technical/professional skill match
- experience: relevant experience match
- education: education match
- keywords: important keyword coverage
- resume_quality: clarity, structure, relevance, and ATS readability

The component scores should be evidence-based and should reasonably
support the overall ats_score.

11. recommendations

Give 3 to 5 specific recommendations.

Recommendations must be based on actual differences between
the resume and job description.

Do not give generic advice.
"""

    # ========================================================
    # GEMINI ANALYSIS
    # ========================================================

    try:
        print("")
        print("========================================")
        print("STARTING GEMINI ATS ANALYSIS")
        print("========================================")

        print("Trying Gemini models: gemini-3.6-flash -> gemini-3.5-flash")

        # Direct REST call. Do not use the old SDK model mapping here.
        response_text = generate_gemini_json(prompt)

        print("Gemini response received.")

        # ----------------------------------------------------
        # Check empty response
        # ----------------------------------------------------

        if not response_text:
            return jsonify(
                {
                    "error": (
                        "Gemini returned an empty response."
                    )
                }
            ), 500

        # ----------------------------------------------------
        # Convert JSON
        # ----------------------------------------------------

        try:
            result = json.loads(response_text)

        except json.JSONDecodeError:
            print("Gemini returned invalid JSON:")
            print(response_text[:3000])

            return jsonify(
                {
                    "error": (
                        "Gemini returned invalid JSON."
                    ),
                    "raw_response": response_text[:5000],
                }
            ), 500

        # ----------------------------------------------------
        # Normalize
        # ----------------------------------------------------

        result = normalize_result(result)

        # ----------------------------------------------------
        # Print scores
        # ----------------------------------------------------

        print("ATS SCORE:", result["ats_score"])
        print("SKILL SCORE:", result["skill_score"])
        print(
            "EXPERIENCE SCORE:",
            result["experience_score"]
        )
        print(
            "EDUCATION SCORE:",
            result["education_score"]
        )
        print(
            "MATCHED SKILLS:",
            result["matched_skills"]
        )
        print(
            "MISSING SKILLS:",
            result["missing_skills"]
        )

        print("========================================")
        print("ANALYSIS COMPLETE")
        print("========================================")
        print("")

        return jsonify(result), 200

    # ========================================================
    # GEMINI ERROR
    # ========================================================

    except Exception as e:
        print("")
        print("========================================")
        print("GEMINI ANALYSIS ERROR")
        print("========================================")
        print(str(e))
        print("========================================")
        print("")

        return jsonify(
            {
                "error": (
                    f"Gemini analysis failed: {str(e)}"
                )
            }
        ), 500


# ============================================================
# FILE SIZE ERROR
# ============================================================

@app.errorhandler(413)
def file_too_large(error):
    return jsonify(
        {
            "error": (
                "File is too large. "
                "Maximum size is 10 MB."
            )
        }
    ), 413


# ============================================================
# GENERAL ERROR HANDLER
# ============================================================

@app.errorhandler(Exception)
def handle_exception(error):
    print("SERVER ERROR:", str(error))

    return jsonify(
        {
            "error": "Internal server error.",
            "details": str(error),
        }
    ), 500


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    print("")
    print("========================================")
    print("       ResumeAI Backend Server")
    print("========================================")
    print("Server: http://127.0.0.1:5000")
    print("Health: http://127.0.0.1:5000/health")
    print("Upload: http://127.0.0.1:5000/upload-resume")
    print("Analyze: http://127.0.0.1:5000/analyze")
    print("========================================")
    print("")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
