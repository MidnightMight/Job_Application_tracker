"""AI and upload API routes."""

import io
import json
import re as _re
import urllib.error
import urllib.request

from flask import Blueprint, jsonify, request

import db
from .auth import login_required

bp = Blueprint("api", __name__)

_MAX_JOB_DESC_LENGTH  = 4000
_MAX_ERROR_MSG_LENGTH = 120
_MAX_PROFILE_LENGTH   = 8000


@bp.route("/api/ollama-status")
@login_required
def ollama_status():
    if db.get_setting("ollama_enabled", "0") != "1":
        return jsonify({"ok": False, "error": "Ollama is not enabled."})
    ollama_url = db.get_setting("ollama_url", "http://localhost:11434").rstrip("/")
    model = db.get_setting("ollama_model", "llama3")
    try:
        req = urllib.request.Request(
            f"{ollama_url}/api/tags",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
        models = [m.get("name", "") for m in data.get("models", [])]
        return jsonify({"ok": True, "model": model, "models": models})
    except urllib.error.URLError:
        return jsonify({"ok": False, "error": "Server unreachable."})
    except Exception:
        return jsonify({"ok": False, "error": "Could not connect to Ollama server."})


@bp.route("/api/ai-fill", methods=["POST"])
@login_required
def ai_fill():
    """AJAX: send a pasted job description to Ollama and return extracted form fields."""
    if db.get_setting("ollama_enabled", "0") != "1":
        return jsonify({"ok": False, "error": "Ollama AI Assistant is not enabled in Settings."})

    body = request.get_json(silent=True) or {}
    job_description = (body.get("job_description") or "").strip()
    if not job_description:
        return jsonify({"ok": False, "error": "Please paste a job description first."})

    ollama_url   = db.get_setting("ollama_url",   "http://localhost:11434").rstrip("/")
    ollama_model = db.get_setting("ollama_model", "llama3")

    prompt = (
        "You are a helpful assistant that extracts structured information from job postings.\n\n"
        "Given the job description below, return ONLY a single valid JSON object "
        "(no markdown fences, no extra text) with these keys:\n\n"
        '  "job_desc"  — the job title or role name (string)\n'
        '  "company"   — the company or organisation name (string)\n'
        '  "team"      — team, division, or department name, or "" if not stated (string)\n'
        '  "link"      — the application or posting URL if explicitly mentioned, or "" (string)\n'
        '  "comment"   — a concise 2–3 sentence summary of key requirements and responsibilities (string)\n\n'
        "Job Description:\n"
        "---\n"
        f"{job_description[:_MAX_JOB_DESC_LENGTH]}\n"
        "---\n\n"
        "JSON object:"
    )

    payload = json.dumps({
        "model":  ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }).encode()

    try:
        req = urllib.request.Request(
            f"{ollama_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read().decode())

        raw = (result.get("response") or "").strip()
        fence_match = _re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
        if fence_match:
            raw = fence_match.group(1).strip()
        obj_match = _re.search(r"\{[\s\S]+\}", raw)
        if obj_match:
            raw = obj_match.group(0)

        fields = json.loads(raw)
        allowed = {"job_desc", "company", "team", "link", "comment"}
        fields = {k: str(v).strip() for k, v in fields.items() if k in allowed}
        return jsonify({"ok": True, "fields": fields})

    except urllib.error.URLError:
        return jsonify({"ok": False, "error": "Could not connect to the Ollama server. Is it running?"})
    except json.JSONDecodeError:
        return jsonify({
            "ok": False,
            "error": (
                "The AI returned an unrecognised format. "
                "Try a different model or simplify the job description."
            ),
        })
    except Exception:
        return jsonify({"ok": False, "error": "An unexpected error occurred. Please try again."})


@bp.route("/api/upload-profile-pdf", methods=["POST"])
@login_required
def upload_profile_pdf():
    if db.get_setting("ollama_enabled", "0") != "1":
        return jsonify({"ok": False, "error": "Ollama AI Assistant is not enabled in Settings."})

    pdf_file = request.files.get("pdf")
    if not pdf_file or not pdf_file.filename:
        return jsonify({"ok": False, "error": "No file received."})

    if not pdf_file.filename.lower().endswith(".pdf"):
        return jsonify({"ok": False, "error": "Only PDF files are supported."})

    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_file.read()))
        pages_text = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages_text.append(text.strip())
        extracted = "\n\n".join(pages_text)
    except Exception:
        return jsonify({"ok": False, "error": "Could not read the PDF. Ensure it contains selectable text."})

    if not extracted.strip():
        return jsonify({"ok": False, "error": "No readable text found in the PDF. Try a text-based PDF."})

    extracted = extracted[:_MAX_PROFILE_LENGTH]
    db.set_setting("user_profile_summary", extracted)
    preview = extracted[:300].replace("\n", " ")
    return jsonify({"ok": True, "preview": preview, "char_count": len(extracted)})


@bp.route("/api/ai-fit", methods=["POST"])
@login_required
def ai_fit():
    """AJAX: compare user profile with a job description and return a fit analysis."""
    if db.get_setting("ollama_enabled", "0") != "1":
        return jsonify({"ok": False, "error": "Ollama AI Assistant is not enabled in Settings."})

    if db.get_setting("ai_fit_enabled", "0") != "1":
        return jsonify({"ok": False, "error": "Smart Job Fit Analysis is not enabled in Settings."})

    body = request.get_json(silent=True) or {}
    job_description = (body.get("job_description") or "").strip()
    if not job_description:
        return jsonify({"ok": False, "error": "No job description provided for fit analysis."})

    skills     = db.get_setting("user_profile_skills",     "").strip()
    experience = db.get_setting("user_profile_experience", "").strip()
    summary    = db.get_setting("user_profile_summary",    "").strip()

    if not (skills or experience or summary):
        return jsonify({
            "ok": False,
            "error": "Your profile is not set up yet. Go to Settings → AI Assistant and fill in your profile.",
        })

    profile_parts = []
    if summary:
        profile_parts.append(f"About me:\n{summary[:2000]}")
    if skills:
        profile_parts.append(f"My skills:\n{skills[:1000]}")
    if experience:
        profile_parts.append(f"My experience:\n{experience[:1500]}")
    profile_text = "\n\n".join(profile_parts)

    ollama_url   = db.get_setting("ollama_url",   "http://localhost:11434").rstrip("/")
    ollama_model = db.get_setting("ollama_model", "llama3")

    prompt = (
        "You are a career advisor. Given a candidate profile and a job description, "
        "evaluate how well the candidate fits the role.\n\n"
        "Return ONLY a single valid JSON object (no markdown fences, no extra text) with these keys:\n\n"
        '  "fit_score"        — integer 0–100 representing overall fit percentage\n'
        '  "verdict"          — one of: "Strong Fit", "Good Fit", "Moderate Fit", "Weak Fit", "Not a Fit"\n'
        '  "matching_skills"  — list of skills/qualities the candidate has that match the role (list of strings, max 6)\n'
        '  "skill_gaps"       — list of key requirements the candidate appears to lack (list of strings, max 5)\n'
        '  "recommendation"   — 2–3 sentence personalised recommendation for the candidate (string)\n\n'
        "Candidate Profile:\n"
        "---\n"
        f"{profile_text}\n"
        "---\n\n"
        "Job Description:\n"
        "---\n"
        f"{job_description[:_MAX_JOB_DESC_LENGTH]}\n"
        "---\n\n"
        "JSON object:"
    )

    payload = json.dumps({
        "model":   ollama_model,
        "prompt":  prompt,
        "stream":  False,
        "options": {"temperature": 0.2},
    }).encode()

    try:
        req = urllib.request.Request(
            f"{ollama_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())

        raw = (result.get("response") or "").strip()
        fence_match = _re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
        if fence_match:
            raw = fence_match.group(1).strip()
        obj_match = _re.search(r"\{[\s\S]+\}", raw)
        if obj_match:
            raw = obj_match.group(0)

        analysis = json.loads(raw)

        _VERDICT_VALUES = {"Strong Fit", "Good Fit", "Moderate Fit", "Weak Fit", "Not a Fit"}
        fit_score = analysis.get("fit_score", 0)
        try:
            fit_score = max(0, min(100, int(fit_score)))
        except (TypeError, ValueError):
            fit_score = 0

        verdict = str(analysis.get("verdict", "Moderate Fit"))
        if verdict not in _VERDICT_VALUES:
            verdict = "Moderate Fit"

        matching_skills = [str(s)[:100] for s in (analysis.get("matching_skills") or [])[:6]]
        skill_gaps      = [str(s)[:100] for s in (analysis.get("skill_gaps")      or [])[:5]]
        recommendation  = str(analysis.get("recommendation", ""))[:600]

        return jsonify({
            "ok": True,
            "fit_score":       fit_score,
            "verdict":         verdict,
            "matching_skills": matching_skills,
            "skill_gaps":      skill_gaps,
            "recommendation":  recommendation,
        })

    except urllib.error.URLError:
        return jsonify({"ok": False, "error": "Could not connect to the Ollama server. Is it running?"})
    except json.JSONDecodeError:
        return jsonify({
            "ok": False,
            "error": "The AI returned an unrecognised format. Try a different model.",
        })
    except Exception:
        return jsonify({"ok": False, "error": "An unexpected error occurred during fit analysis."})


@bp.route("/api/ai-fit-save", methods=["POST"])
@login_required
def ai_fit_save():
    """AJAX: persist AI fit analysis results to the application record."""
    body = request.get_json(silent=True) or {}
    app_id = body.get("app_id")
    if not app_id:
        return jsonify({"ok": False, "error": "app_id is required."})
    try:
        app_id = int(app_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "app_id must be an integer."})

    fit_score = body.get("fit_score", 0)
    try:
        fit_score = max(0, min(100, int(fit_score)))
    except (TypeError, ValueError):
        fit_score = 0

    _VERDICT_VALUES = {"Strong Fit", "Good Fit", "Moderate Fit", "Weak Fit", "Not a Fit"}
    verdict = str(body.get("verdict", "Moderate Fit"))
    if verdict not in _VERDICT_VALUES:
        verdict = "Moderate Fit"

    matching_skills = [str(s)[:100] for s in (body.get("matching_skills") or [])[:6]]
    skill_gaps      = [str(s)[:100] for s in (body.get("skill_gaps")      or [])[:5]]
    recommendation  = str(body.get("recommendation", ""))[:600]

    db.save_ai_fit(app_id, fit_score, verdict, matching_skills, skill_gaps, recommendation)
    return jsonify({"ok": True})
