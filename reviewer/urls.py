from django.urls import path
from . import views

app_name = "reviewer"

urlpatterns = [
    path("",               views.disclaimer, name="disclaimer"),
    path("modus/",         views.mode,        name="mode"),
    path("upload/",        views.upload,      name="upload"),
    path("upload-zip/",    views.upload_zip,  name="upload_zip"),
    path("ergebnis/",      views.result,      name="result"),
    path("ergebnisse/",    views.zip_result,  name="zip_result"),
]
