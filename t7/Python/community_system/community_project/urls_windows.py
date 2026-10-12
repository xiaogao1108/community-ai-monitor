from django.urls import include, path

from .windows_media import image_alias, uploaded_image


urlpatterns = [
    path("static/imgs/<path:path>", uploaded_image, name="uploaded_image"),
    path("images/<path:path>", image_alias, name="image_alias"),
    path("", include("community_project.urls")),
]
