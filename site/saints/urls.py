"""saints URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from saints.api import BiographyViewSet, CalendarListView, DayView, LiturgicalYearView
from saints.views import calendar_view, comparison_view, daily_view, home_view, mcp_chat_view

from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView
from rest_framework.response import Response
from django.urls import reverse

router = DefaultRouter()
router.include_root_view = False
router.register("biographies", BiographyViewSet, basename="biography")


class APIRootView(APIView):
    """List available API endpoints."""

    def get(self, request):
        base = request.build_absolute_uri()
        base = base.rstrip('/') + '/'
        return Response(
            {
                "biographies": base + "biographies/",
                "biography-detail": base + "biographies/{uuid}/",
                "liturgical-year": base + "liturgical-year/{year}/{calendar}/",
                "day": base + "day/{date}/",
                "calendars": base + "calendars/",
                "schema": request.build_absolute_uri(reverse("openapi-schema")),
                "docs": request.build_absolute_uri(reverse("swagger-ui")),
            }
        )

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home_view, name="home"),
    path("comparison/", comparison_view, name="comparison"),
    path("comparison/<str:year>/", comparison_view, name="comparison_with_year"),
    path("day/<str:date>/", daily_view, name="daily_view"),
    path("calendar/", calendar_view, name="calendar_view"),
    path("calendar/<int:year>/<int:month>/", calendar_view, name="calendar_view_with_date"),
    path("mcp-chat/", mcp_chat_view, name="mcp_chat"),

    # API Endpoints
    path("api/", APIRootView.as_view(), name="api-root"),
    path("api/", include(router.urls)),
    path("api/liturgical-year/<int:year>/<str:calendar>/", LiturgicalYearView.as_view(), name="liturgical-year"),
    path("api/day/<str:date>/", DayView.as_view(), name="day-api"),
    path("api/calendars/", CalendarListView.as_view(), name="calendar-list"),

    # OpenAPI schema and docs
    path("openapi.yaml", SpectacularAPIView.as_view(), name="openapi-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="openapi-schema"), name="swagger-ui"),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
