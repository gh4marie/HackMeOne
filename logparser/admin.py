'''from django.contrib import admin
from .models import DimIP, DimDateTime, DimRequest, FactLog
# Register your models here.
# logparser/admin.py

admin.site.register(DimIP)
admin.site.register(DimDateTime)
admin.site.register(DimRequest)
admin.site.register(FactLog)'''

from django.contrib import admin
from django.urls import path
from django.template.response import TemplateResponse
from .models import DimIP, DimDateTime, DimRequest, FactLog
from django.db.models import Count

class MyAdminSite(admin.AdminSite):
    site_header = "Кастомная админ-панель"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analytics/', self.admin_view(self.analytics_view), name='analytics'),
        ]
        return custom_urls + urls

    def analytics_view(self, request):
        status_data = FactLog.objects.values('status_code').annotate(count=Count('id'))
        labels = [str(item['status_code']) for item in status_data]
        counts = [item['count'] for item in status_data]
        context = dict(
            self.each_context(request),
            labels=labels,
            counts=counts,
        )
        return TemplateResponse(request, "admin/analytics.html", context)

# Создаем экземпляр кастомного AdminSite
admin_site = MyAdminSite(name='myadmin')

# Регистрируем модели через кастомный admin_site
admin_site.register(DimIP)
admin_site.register(DimDateTime)
admin_site.register(DimRequest)
admin_site.register(FactLog)
