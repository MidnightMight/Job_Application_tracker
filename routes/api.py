"""AI and upload API routes."""

import io
import json
import re as _re
import urllib.error
import urllib.request

from flask import Blueprint, jsonify, request

import db
from .auth import login_required, current_user_id

bp = Blueprint("api", __name__)

_MAX_JOB_DESC_LENGTH  = 4000
_MAX_ERROR_MSG_LENGTH = 120
_MAX_PROFILE_LENGTH   = 8000
_MAX_CHAT_MSG_LENGTH  = 1200

# ---------------------------------------------------------------------------
# AI provider helpers
# ---------------------------------------------------------------------------

def _call_ollama(prompt: str, url: str, model: str, timeout: int = 90) -> str:
    """Call the Ollama /api/generate endpoint and return the response text."""
    payload = json.dumps({
        "model":   model,
        "prompt":  prompt,
        "stream":  False,
        "options": {"temperature": 0.1},
    }).encode()
    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode())
    return (result.get("response") or "").strip()


def _call_openai_compat(prompt: str, api_key: str, base_url: str, model: str,
                        timeout: int = 90) -> str:
    """Call an OpenAI-compatible Chat Completions endpoint and return the response text."""
    payload = json.dumps({
        "model":    model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }).encode()
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode())
    return (result["choices"][0]["message"]["content"] or "").strip()


def _call_anthropic(prompt: str, api_key: str, model: str, timeout: int = 90) -> str:
    """Call the Anthropic Messages API and return the response text."""
    payload = json.dumps({
        "model":      model or "claude-3-haiku-20240307",
        "max_tokens": 1024,
        "messages":   [{"role": "user", "content": prompt}],
    }).encode()
    headers = {
        "Content-Type":      "application/json",
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode())
    return (result["content"][0]["text"] or "").strip()


def _call_ai(prompt: str, user_id, timeout: int = 90) -> str:
    """Route the AI call to the correct provider for *user_id*.

    Priority:
    1. If user set ``use_admin_ai=1`` (or has no personal settings), fall through
       to the global Ollama configuration.
    2. Otherwise use the user's own configured provider (openai / anthropic / custom).
    3. Fall back to global Ollama when nothing else is available.
    Raises RuntimeError with a user-friendly message when nothing is available.
    """
    cfg = db.get_user_ai_settings(user_id)
    use_admin = int(cfg.get("use_admin_ai", 1))
    provider = cfg.get("ai_provider", "ollama")

    # When the user chose to use their own provider (use_admin_ai = 0).
    if not use_admin:
        if provider == "ollama":
            api_url = cfg.get("api_url", "").strip()
            model = cfg.get("ai_model", "").strip() or db.get_setting("ollama_model", "llama3")
            if not api_url:
                raise RuntimeError("Personal Ollama URL is not configured. Go to Settings → AI Assistant.")
            return _call_ollama(prompt, api_url, model, timeout)

        if provider == "openai":
            api_key = cfg.get("api_key", "").strip()
            if not api_key:
                raise RuntimeError("OpenAI API key is not configured. Go to Settings → AI Assistant.")
            model = cfg.get("ai_model", "").strip() or "gpt-4o-mini"
            return _call_openai_compat(prompt, api_key, "https://api.openai.com/v1", model, timeout)

        if provider == "anthropic":
            api_key = cfg.get("api_key", "").strip()
            if not api_key:
                raise RuntimeError("Anthropic API key is not configured. Go to Settings → AI Assistant.")
            model = cfg.get("ai_model", "").strip() or "claude-3-haiku-20240307"
            return _call_anthropic(prompt, api_key, model, timeout)

        if provider == "custom":
            api_key = cfg.get("api_key", "").strip()
            api_url = cfg.get("api_url", "").strip()
            model   = cfg.get("ai_model", "").strip()
            if not api_url:
                raise RuntimeError("Custom API URL is not configured. Go to Settings → AI Assistant.")
            return _call_openai_compat(prompt, api_key, api_url, model, timeout)

    # Default / fallback: global Ollama
    if db.get_setting("ollama_enabled", "0") != "1":
        raise RuntimeError("Ollama AI Assistant is not enabled. Ask an admin to configure AI in Settings.")
    url   = db.get_setting("ollama_url",   "http://localhost:11434")
    model = db.get_setting("ollama_model", "llama3")
    return _call_ollama(prompt, url, model, timeout)


def _parse_json_response(raw: str) -> dict:
    """Strip markdown fences and extract the first JSON object from *raw*."""
    fence = _re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if fence:
        raw = fence.group(1).strip()
    obj = _re.search(r"\{[\s\S]+\}", raw)
    if obj:
        raw = obj.group(0)
    return json.loads(raw)


def _ai_available(user_id) -> bool:
    """Return True when at least one AI provider is usable for *user_id*."""
    if db.user_has_own_ai(user_id):
        return True
    return db.get_setting("ollama_enabled", "0") == "1"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route("/api/ollama-status")
@login_required
def ollama_status():
    """Check AI availability for the current user (Ollama or personal provider)."""
    user_id = current_user_id()
    cfg      = db.get_user_ai_settings(user_id)
    use_admin = int(cfg.get("use_admin_ai", 1))
    provider  = cfg.get("ai_provider", "ollama")

    # When the user chose their own provider (use_admin_ai = 0).
    if not use_admin:
        if provider == "ollama":
            api_url = cfg.get("api_url", "").strip()
            if not api_url:
                return jsonify({"ok": False, "provider": "ollama",
                                "error": "Personal Ollama URL not configured."})
            model = cfg.get("ai_model", "").strip() or db.get_setting("ollama_model", "llama3")
            try:
                req = urllib.request.Request(
                    f"{api_url.rstrip('/')}/api/tags",
                    headers={"Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = json.loads(resp.read().decode())
                models = [m.get("name", "") for m in data.get("models", [])]
                return jsonify({"ok": True, "provider": "ollama", "model": model, "models": models})
            except Exception:
                return jsonify({"ok": False, "provider": "ollama",
                                "error": "Could not connect to your personal Ollama server."})

        if provider == "openai":
            api_key = cfg.get("api_key", "").strip()
            if not api_key:
                return jsonify({"ok": False, "provider": "openai",
                                "error": "OpenAI API key not configured."})
            try:
                req = urllib.request.Request(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=5):
                    pass
                model = cfg.get("ai_model", "").strip() or "gpt-4o-mini"
                return jsonify({"ok": True, "provider": "openai", "model": model})
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403):
                    return jsonify({"ok": False, "provider": "openai",
                                    "error": "Invalid OpenAI API key."})
                return jsonify({"ok": False, "provider": "openai",
                                "error": f"OpenAI returned HTTP {exc.code}."})
            except Exception:
                return jsonify({"ok": False, "provider": "openai",
                                "error": "Could not reach OpenAI API."})

        if provider == "anthropic":
            api_key = cfg.get("api_key", "").strip()
            if not api_key:
                return jsonify({"ok": False, "provider": "anthropic",
                                "error": "Anthropic API key not configured."})
            try:
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key":         api_key,
                        "anthropic-version": "2023-06-01",
                        "Accept":            "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=5):
                    pass
                model = cfg.get("ai_model", "").strip() or "claude-3-haiku-20240307"
                return jsonify({"ok": True, "provider": "anthropic", "model": model})
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403):
                    return jsonify({"ok": False, "provider": "anthropic",
                                    "error": "Invalid Anthropic API key."})
                model = cfg.get("ai_model", "").strip() or "claude-3-haiku-20240307"
                return jsonify({"ok": True, "provider": "anthropic", "model": model})
            except Exception:
                return jsonify({"ok": False, "provider": "anthropic",
                                "error": "Could not reach Anthropic API."})

        if provider == "custom":
            api_url = cfg.get("api_url", "").strip()
            if not api_url:
                return jsonify({"ok": False, "provider": "custom",
                                "error": "Custom API URL not configured."})
            try:
                req = urllib.request.Request(
                    f"{api_url.rstrip('/')}/models",
                    headers={"Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=4):
                    pass
                model = cfg.get("ai_model", "").strip()
                return jsonify({"ok": True, "provider": "custom", "model": model})
            except Exception:
                return jsonify({"ok": False, "provider": "custom",
                                "error": "Could not reach custom API."})

    # Default / fallback: global Ollama
    if db.get_setting("ollama_enabled", "0") != "1":
        return jsonify({"ok": False, "provider": "ollama", "error": "Ollama is not enabled."})
    ollama_url = db.get_setting("ollama_url", "http://localhost:11434").rstrip("/")
    model      = db.get_setting("ollama_model", "llama3")
    try:
        req = urllib.request.Request(
            f"{ollama_url}/api/tags",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
        models = [m.get("name", "") for m in data.get("models", [])]
        return jsonify({"ok": True, "provider": "ollama", "model": model, "models": models})
    except urllib.error.URLError:
        return jsonify({"ok": False, "provider": "ollama", "error": "Server unreachable."})
    except Exception:
        return jsonify({"ok": False, "provider": "ollama",
                        "error": "Could not connect to Ollama server."})


@bp.route("/api/ai-fill", methods=["POST"])
@login_required
def ai_fill():
    """AJAX: send a pasted job description to AI and return extracted form fields."""
    user_id = current_user_id()
    if not _ai_available(user_id):
        return jsonify({"ok": False, "error": "AI Assistant is not configured. Go to Settings → AI Assistant."})

    body = request.get_json(silent=True) or {}
    job_description = (body.get("job_description") or "").strip()
    if not job_description:
        return jsonify({"ok": False, "error": "Please paste a job description first."})

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

    try:
        raw    = _call_ai(prompt, user_id, timeout=90)
        fields = _parse_json_response(raw)
        allowed = {"job_desc", "company", "team", "link", "comment"}
        fields = {k: str(v).strip() for k, v in fields.items() if k in allowed}
        return jsonify({"ok": True, "fields": fields})
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)[:200]})
    except urllib.error.URLError:
        return jsonify({"ok": False, "error": "Could not connect to the AI server. Is it running?"})
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
    user_id = current_user_id()

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

    # Save to per-user settings if logged in; fall back to global settings.
    if user_id is not None:
        db.save_user_ai_settings(user_id, {"profile_summary": extracted})
    else:
        db.set_setting("user_profile_summary", extracted)

    preview = extracted[:300].replace("\n", " ")
    return jsonify({"ok": True, "preview": preview, "char_count": len(extracted)})


@bp.route("/api/ai-fit", methods=["POST"])
@login_required
def ai_fit():
    """AJAX: compare user profile with a job description and return a fit analysis."""
    user_id = current_user_id()
    if not _ai_available(user_id):
        return jsonify({"ok": False, "error": "AI Assistant is not configured. Go to Settings → AI Assistant."})

    if db.get_setting("ai_fit_enabled", "0") != "1":
        return jsonify({"ok": False, "error": "Smart Job Fit Analysis is not enabled in Settings."})

    body = request.get_json(silent=True) or {}
    job_description = (body.get("job_description") or "").strip()
    if not job_description:
        return jsonify({"ok": False, "error": "No job description provided for fit analysis."})

    # Prefer per-user profile; fall back to global settings.
    if user_id is not None:
        cfg = db.get_user_ai_settings(user_id)
        skills     = cfg.get("profile_skills",     "").strip()
        experience = cfg.get("profile_experience", "").strip()
        summary    = cfg.get("profile_summary",    "").strip()
    else:
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

    # Include the user's historical success rate so the AI can contextualise advice.
    stats = db.get_stats(user_id=user_id)
    success_rate    = stats.get("success_rate", 0)
    total_submitted = stats.get("submitted", 0)
    offers_received = stats.get("offers", 0)
    success_context = (
        f"Candidate's job-search track record: "
        f"{total_submitted} applications submitted, "
        f"{offers_received} offers received "
        f"({success_rate}% success rate)."
        if total_submitted > 0
        else "Candidate's job-search track record: No submitted applications on record yet."
    )

    prompt = (
        "You are a career advisor. Given a candidate profile, their job-search track record, "
        "and a job description, evaluate how well the candidate fits the role.\n\n"
        "Return ONLY a single valid JSON object (no markdown fences, no extra text) with these keys:\n\n"
        '  "fit_score"        — integer 0–100 representing overall fit percentage\n'
        '  "verdict"          — one of: "Strong Fit", "Good Fit", "Moderate Fit", "Weak Fit", "Not a Fit"\n'
        '  "matching_skills"  — list of skills/qualities the candidate has that match the role (list of strings, max 6)\n'
        '  "skill_gaps"       — list of key requirements the candidate appears to lack (list of strings, max 5)\n'
        '  "recommendation"   — 2–3 sentence personalised recommendation for the candidate, taking into account '
        'their success rate and whether this role is a realistic match or a stretch goal (string)\n\n'
        "Candidate Profile:\n"
        "---\n"
        f"{profile_text}\n"
        "---\n\n"
        f"Track Record:\n{success_context}\n\n"
        "Job Description:\n"
        "---\n"
        f"{job_description[:_MAX_JOB_DESC_LENGTH]}\n"
        "---\n\n"
        "JSON object:"
    )

    try:
        raw      = _call_ai(prompt, user_id, timeout=120)
        analysis = _parse_json_response(raw)

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
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)[:200]})
    except urllib.error.URLError:
        return jsonify({"ok": False, "error": "Could not connect to the AI server. Is it running?"})
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


@bp.route("/api/assistant-chat", methods=["POST"])
@login_required
def assistant_chat():
    """AJAX: chat with O.t.t.o when AI is enabled for this user."""
    user_id = current_user_id()
    if not _ai_available(user_id):
        return jsonify({"ok": False, "error": "O.t.t.o is unavailable because AI is not enabled."})

    body = request.get_json(silent=True) or {}
    message = (body.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": "Please enter a message."})

    prompt = (
        "You are O.t.t.o, the Job Application Tracker system assistant.\n"
        "O.t.t.o stands for Organised Tracking & Target Opportunity.\n"
        "Be practical, concise, positive, and helpful.\n"
        "Use occasional light emoji, but keep it readable.\n"
        "If asked about unrelated dangerous topics, refuse briefly and steer back to career support.\n\n"
        f"User message:\n{message[:_MAX_CHAT_MSG_LENGTH]}\n\n"
        "Reply as O.t.t.o:"
    )
    try:
        reply = _call_ai(prompt, user_id, timeout=90)
        reply = (reply or "").strip()
        if not reply:
            return jsonify({"ok": False, "error": "O.t.t.o did not return a response. Please try again."})
        return jsonify({"ok": True, "reply": reply[:3000]})
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)[:200]})
    except urllib.error.URLError:
        return jsonify({"ok": False, "error": "Could not connect to the AI server."})
    except Exception:
        return jsonify({"ok": False, "error": "An unexpected error occurred while contacting O.t.t.o."})
