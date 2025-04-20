"""
URL configuration for hackme project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
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

from django.contrib import admin
from django.urls import path, include
from logparser.admin import admin_site
#from log_analytics.admin import admin_site
from django.http import HttpResponse

def home_view(request):
    return HttpResponse("Это главная страница. Перейдите на /admin/ для входа в админку.")

urlpatterns = [
    path('', home_view, name='home'),          # пустой путь
    path('admin/', admin_site.urls),           # или admin.site.urls, если используете стандартную админку
]


from django.urls import path
from logparser import admin as logparser_admin
from log_analytics import admin as analytics_admin

urlpatterns = [
    path('admin/logparser/', logparser_admin.admin.site.urls),
    path('admin/log_analytics/', analytics_admin.admin_site.urls),
    # другие маршруты...
]
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
#    path('logparser/', include('logparser.'),
    path('dashboard/', include('dashboard.urls')),
    #path('dashboard/', views.dashboard_view, name='dashboard'),
    #path('export/', include('export.urls')),
]
