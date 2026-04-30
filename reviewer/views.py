"""
views.py

Four-step flow:
  1. / (disclaimer)      – lecturers confirm they understand AI limitations
  1b. /modus/            – choose between single-document and ZIP upload
  2a. /upload/           – upload a student document + describe the assignment
  2b. /upload-zip/       – upload a ZIP with multiple question/answer pairs
  3a. /ergebnis/         – display the AI's grading result (single document)
  3b. /ergebnisse/       – display AI grading results for all ZIP entries

State between steps is kept in the server-side session (no database needed).
"""

import io
import zipfile as _zipfile
from pathlib import PurePosixPath

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .document_parser import extract_text
from .ai_client import grade_document, AVAILABLE_MODELS


# ---------------------------------------------------------------------------
# Step 1 — Disclaimer
# ---------------------------------------------------------------------------

@login_required
def disclaimer(request):
    """
    GET  – show the disclaimer page.
    POST – mark the disclaimer as accepted in the session and go to mode selection.
    """
    if request.method == "POST":
        request.session["disclaimer_accepted"] = True
        return redirect("reviewer:mode")

    return render(request, "reviewer/disclaimer.html")


# ---------------------------------------------------------------------------
# Step 1b — Mode selection
# ---------------------------------------------------------------------------

@login_required
def mode(request):
    if not request.session.get("disclaimer_accepted"):
        return redirect("reviewer:disclaimer")
    return render(request, "reviewer/mode_select.html")


# ---------------------------------------------------------------------------
# Step 2 — Upload
# ---------------------------------------------------------------------------

@login_required
def upload(request):
    """
    GET  – show the upload form.
    POST – extract text from the document, call the AI, store the result in
           the session, and redirect to the result page.
    """
    # Enforce that the user has read the disclaimer first
    if not request.session.get("disclaimer_accepted"):
        return redirect("reviewer:disclaimer")

    if request.method == "POST":
        assignment_description = request.POST.get("assignment_description", "").strip()
        uploaded_file = request.FILES.get("document")
        selected_model = request.POST.get("model", "").strip()

        # --- Basic validation ------------------------------------------------
        valid_model_ids = [m[0] for m in AVAILABLE_MODELS]
        errors = []

        if not assignment_description:
            errors.append("Bitte eine Aufgabenbeschreibung eingeben.")

        if not uploaded_file:
            errors.append("Bitte ein Dokument hochladen.")

        if selected_model not in valid_model_ids:
            errors.append("Bitte ein gültiges KI-Modell auswählen.")

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, "reviewer/upload.html", {"models": AVAILABLE_MODELS})

        # --- Extract text from the uploaded file -----------------------------
        try:
            document_text = extract_text(uploaded_file, uploaded_file.name)
        except ValueError as exc:
            # Unsupported file format
            messages.error(request, str(exc))
            return render(request, "reviewer/upload.html", {"models": AVAILABLE_MODELS})
        except Exception as exc:
            messages.error(request, f"Fehler beim Lesen der Datei: {exc}")
            return render(request, "reviewer/upload.html", {"models": AVAILABLE_MODELS})

        if not document_text.strip():
            messages.error(
                request,
                "Das hochgeladene Dokument enthält keinen lesbaren Text. "
                "Bitte prüfen Sie, ob die Datei korrekt ist.",
            )
            return render(request, "reviewer/upload.html", {"models": AVAILABLE_MODELS})

        # --- Call the AI via OpenRouter --------------------------------------
        try:
            result = grade_document(document_text, assignment_description, selected_model)
        except RuntimeError as exc:
            messages.error(request, f"Fehler bei der KI-Bewertung: {exc}")
            return render(request, "reviewer/upload.html", {"models": AVAILABLE_MODELS})

        # Store the result in the session so the result page can display it
        request.session["grading_result"] = result
        request.session["filename"] = uploaded_file.name

        return redirect("reviewer:result")

    # GET — simply show the upload form
    return render(request, "reviewer/upload.html", {"models": AVAILABLE_MODELS})


# ---------------------------------------------------------------------------
# Step 3a — Result (single document)
# ---------------------------------------------------------------------------

@login_required
def result(request):
    """
    Display the grading result that was stored in the session.
    If there is no result (e.g. direct URL access), redirect to the upload page.
    """
    grading_result = request.session.get("grading_result")

    if not grading_result:
        messages.warning(request, "Bitte zuerst ein Dokument hochladen.")
        return redirect("reviewer:upload")

    context = {
        "result":   grading_result,
        "filename": request.session.get("filename", "Unbekannte Datei"),
    }
    return render(request, "reviewer/result.html", context)


# ---------------------------------------------------------------------------
# Step 2b — ZIP upload
# ---------------------------------------------------------------------------

@login_required
def upload_zip(request):
    if not request.session.get("disclaimer_accepted"):
        return redirect("reviewer:disclaimer")

    if request.method == "POST":
        uploaded_zip = request.FILES.get("zipfile")
        selected_model = request.POST.get("model", "").strip()

        valid_model_ids = [m[0] for m in AVAILABLE_MODELS]
        errors = []

        if not uploaded_zip:
            errors.append("Bitte eine ZIP-Datei hochladen.")
        if selected_model not in valid_model_ids:
            errors.append("Bitte ein gültiges KI-Modell auswählen.")

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, "reviewer/upload_zip.html", {"models": AVAILABLE_MODELS})

        try:
            results = _process_zip(uploaded_zip, selected_model)
        except _zipfile.BadZipFile:
            messages.error(request, "Die hochgeladene Datei ist kein gültiges ZIP-Archiv.")
            return render(request, "reviewer/upload_zip.html", {"models": AVAILABLE_MODELS})
        except Exception as exc:
            messages.error(request, f"Fehler beim Verarbeiten der ZIP-Datei: {exc}")
            return render(request, "reviewer/upload_zip.html", {"models": AVAILABLE_MODELS})

        if not results:
            messages.error(
                request,
                "Keine vollständigen Frage-Antwort-Paare in der ZIP-Datei gefunden. "
                "Es werden Paare aus _questiontext.pdf und _response.pdf erwartet.",
            )
            return render(request, "reviewer/upload_zip.html", {"models": AVAILABLE_MODELS})

        request.session["zip_results"] = results
        request.session["zip_filename"] = uploaded_zip.name
        return redirect("reviewer:zip_result")

    return render(request, "reviewer/upload_zip.html", {"models": AVAILABLE_MODELS})


def _process_zip(zip_file_obj, selected_model):
    results = []

    with _zipfile.ZipFile(zip_file_obj, "r") as z:
        file_map = {}

        for name in z.namelist():
            p = PurePosixPath(name)
            if len(p.parts) != 2:
                continue
            student, filename = p.parts
            stem = PurePosixPath(filename).stem

            if stem.endswith("_response"):
                base = stem[: -len("_response")]
                file_map.setdefault((student, base), {})["response"] = name
            elif stem.endswith("_questiontext"):
                base = stem[: -len("_questiontext")]
                file_map.setdefault((student, base), {})["questiontext"] = name

        for (student, question_base), files in sorted(file_map.items()):
            if "response" not in files or "questiontext" not in files:
                continue

            name_parts = student.split("_")
            if len(name_parts) >= 3:
                student_display = f"{' '.join(name_parts[:2])} ({name_parts[2]})"
            else:
                student_display = student.replace("_", " ")

            question_display = question_base.replace("_", " ")

            try:
                response_data = io.BytesIO(z.read(files["response"]))
                questiontext_data = io.BytesIO(z.read(files["questiontext"]))

                response_text = extract_text(response_data, files["response"].split("/")[-1])
                assignment_text = extract_text(questiontext_data, files["questiontext"].split("/")[-1])

                grading_result = grade_document(response_text, assignment_text, selected_model)

                results.append({
                    "student": student_display,
                    "question": question_display,
                    "result": grading_result,
                    "error": None,
                })
            except Exception as exc:
                results.append({
                    "student": student_display,
                    "question": question_display,
                    "result": None,
                    "error": str(exc),
                })

    return results


# ---------------------------------------------------------------------------
# Step 3b — ZIP results
# ---------------------------------------------------------------------------

@login_required
def zip_result(request):
    zip_results = request.session.get("zip_results")

    if not zip_results:
        messages.warning(request, "Bitte zuerst eine ZIP-Datei hochladen.")
        return redirect("reviewer:upload_zip")

    context = {
        "results":  zip_results,
        "filename": request.session.get("zip_filename", "Unbekannte Datei"),
    }
    return render(request, "reviewer/zip_result.html", context)
