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
from django.urls import path
from saints.views import home_view, comparison_view, daily_view, calendar_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home_view, name="home"),
    path("comparison/", comparison_view, name="comparison"),
    path("comparison/<str:year>/", comparison_view, name="comparison_with_year"),
    path("day/<str:date>/", daily_view, name="daily_view"),
    path("calendar/", calendar_view, name="calendar_view"),
    path("calendar/<int:year>/<int:month>/", calendar_view, name="calendar_view_with_date"),
]
