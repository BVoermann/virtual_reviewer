from django.urls import path
from . import views

app_name = "reviewer"

urlpatterns = [
    # Step 1: Disclaimer
    path("", views.disclaimer, name="disclaimer"),

    # Step 2: Upload document + assignment description
    path("upload/", views.upload, name="upload"),

    # Step 3: Show AI grading result
    path("ergebnis/", views.result, name="result"),
]
