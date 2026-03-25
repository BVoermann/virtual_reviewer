"""
views.py

Three-step flow:
  1. / (disclaimer)   – lecturers confirm they understand AI limitations
  2. /upload/         – upload a student document + describe the assignment
  3. /ergebnis/       – display the AI's grading result

State between steps is kept in the server-side session (no database needed).
"""

from django.shortcuts import render, redirect
from django.contrib import messages

from .document_parser import extract_text
from .ai_client import grade_document, AVAILABLE_MODELS


# ---------------------------------------------------------------------------
# Step 1 — Disclaimer
# ---------------------------------------------------------------------------

def disclaimer(request):
    """
    GET  – show the disclaimer page.
    POST – mark the disclaimer as accepted in the session and go to the upload page.
    """
    if request.method == "POST":
        request.session["disclaimer_accepted"] = True
        return redirect("reviewer:upload")

    return render(request, "reviewer/disclaimer.html")


# ---------------------------------------------------------------------------
# Step 2 — Upload
# ---------------------------------------------------------------------------

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
# Step 3 — Result
# ---------------------------------------------------------------------------

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
