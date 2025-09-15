from django.urls import path

from . import views

urlpatterns = [
    # Main pages
    path("", views.home, name="home"),
    path("gallery/", views.gallery, name="gallery"),
    # Brief management
    path("brief/create/", views.create_brief, name="create_brief"),
    path("brief/upload/", views.upload_brief, name="upload_brief"),
    path("brief/<int:brief_id>/", views.brief_detail, name="brief_detail"),
    # Asset generation and management
    path("brief/<int:brief_id>/generate/", views.generate_assets, name="generate_assets"),
    path("brief/<int:brief_id>/download/", views.download_assets, name="download_assets"),
    path("asset/<int:asset_id>/", views.asset_detail, name="asset_detail"),
    # API endpoints
    path("api/brief/<int:brief_id>/status/", views.api_brief_status, name="api_brief_status"),
]
