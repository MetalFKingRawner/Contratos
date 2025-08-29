from django.contrib import admin
from django.urls import path, include
from workflow import views as wf_views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("admin/", admin.site.urls),
    path('accounts/', include('core.urls', namespace='core')),
    path("", wf_views.SeleccionDocumentoView.as_view(), name="inicio"),
    path("workflow/", include("workflow.urls")),
    path("reviews/", include("reviews.urls")),
    path('financiamiento/', include('financiamiento.urls', namespace='financiamiento')),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

