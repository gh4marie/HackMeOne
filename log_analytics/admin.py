from django.contrib import admin
from django.urls import path
from django.template.response import TemplateResponse
from django.db.models import Count
#from logparser.models import FactLog, DimIP, DimDateTime, DimRequest
from log_analytics.models import FactLog, DimIP, DimDateTime, DimRequest

class MyAdminSite(admin.AdminSite):
    site_header = "Панель администрирования с аналитикой"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analytics/', self.admin_view(self.analytics_view), name='analytics'),
        ]
        return custom_urls + urls

    def analytics_view(self, request):
        # Получаем данные для визуализации: распределение запросов по статус-кодам
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

# Регистрируем модели через наш кастомный админ-сайт
admin_site.register(FactLog)
admin_site.register(DimIP)
admin_site.register(DimDateTime)
admin_site.register(DimRequest)
