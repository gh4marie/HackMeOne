
## analytics.py
#Модуль для агрегации и анализа логов:


from django.db.models import Count, Avg, Sum, Q, F, FloatField
from django.db.models.functions import TruncHour, TruncDay, TruncWeek, TruncMonth
from django.utils import timezone
import pandas as pd
import numpy as np
from datetime import timedelta
from collections import defaultdict

# Предполагаем, что модель логов называется FactLog и находится в приложении log_analytics
from logparser.models import FactLog


class LogAnalytics:
    """Класс для получения агрегированных данных по логам."""

    @staticmethod
    def get_time_trunc_function(time_aggregation):
        """Возвращает функцию усечения времени на основе выбранной агрегации."""
        trunc_functions = {
            'hour': TruncHour,
            'day': TruncDay,
            'week': TruncWeek,
            'month': TruncMonth,
        }
        return trunc_functions.get(time_aggregation, TruncDay)

    @staticmethod
    def apply_filters(queryset, filters):
        """Применяет фильтры к queryset логов."""
        if filters.get('start_date'):
            queryset = queryset.filter(timestamp__gte=filters['start_date'])

        if filters.get('end_date'):
            # Добавляем 1 день к end_date для включения всего дня
            end_date = filters['end_date'] + timedelta(days=1)
            queryset = queryset.filter(timestamp__lt=end_date)

        if filters.get('ip_address'):
            queryset = queryset.filter(ip_address__icontains=filters['ip_address'])

        if filters.get('status_code'):
            code_prefix = filters['status_code'][0]
            queryset = queryset.filter(status_code__startswith=code_prefix)

        if filters.get('method'):
            queryset = queryset.filter(method=filters['method'])

        if filters.get('path'):
            queryset = queryset.filter(path__icontains=filters['path'])

        if filters.get('min_response_time') is not None:
            queryset = queryset.filter(response_time__gte=filters['min_response_time'])

        if filters.get('max_response_time') is not None:
            queryset = queryset.filter(response_time__lte=filters['max_response_time'])

        return queryset

    @classmethod
    def get_request_over_time(cls, filters=None, time_aggregation='day', metric='count'):
        """
        Возвращает данные о запросах за время с учетом фильтров.

        Args:
            filters: словарь с параметрами фильтрации
            time_aggregation: группировка по времени ('hour', 'day', 'week', 'month')
            metric: метрика для агрегации ('count', 'avg_time', 'error_rate', 'bandwidth')

        Returns:
            Словарь с временными метками и значениями метрики
        """
        if filters is None:
            filters = {}

        queryset = LogEntry.objects.all()
        queryset = cls.apply_filters(queryset, filters)

        # Получаем функцию усечения времени
        trunc_function = cls.get_time_trunc_function(time_aggregation)
        time_field = trunc_function('timestamp')

        # Подготовка данных в зависимости от метрики
        if metric == 'count':
            result = queryset.annotate(
                period=time_field
            ).values('period').annotate(
                value=Count('id')
            ).order_by('period')

        elif metric == 'avg_time':
            result = queryset.annotate(
                period=time_field
            ).values('period').annotate(
                value=Avg('response_time')
            ).order_by('period')

        elif metric == 'error_rate':
            # Рассчитываем % ошибок (коды 4xx и 5xx)
            total_per_period = queryset.annotate(
                period=time_field
            ).values('period').annotate(
                total=Count('id')
            )

            error_per_period = queryset.filter(
                Q(status_code__gte=400)
            ).annotate(
                period=time_field
            ).values('period').annotate(
                errors=Count('id')
            )

            # Создаем словари для объединения
            total_dict = {item['period']: item['total'] for item in total_per_period}
            error_dict = {item['period']: item['errors'] for item in error_per_period}

            # Объединяем данные
            result = []
            for period, total in total_dict.items():
                errors = error_dict.get(period, 0)
                error_rate = (errors / total * 100) if total > 0 else 0
                result.append({
                    'period': period,
                    'value': error_rate
                })
            result.sort(key=lambda x: x['period'])

        elif metric == 'bandwidth':
            # Предполагаем, что в модели есть поле response_size
            result = queryset.annotate(
                period=time_field
            ).values('period').annotate(
                value=Sum('response_size')
            ).order_by('period')

        # Преобразуем QuerySet в словарь
        data = {
            'labels': [item['period'].strftime('%Y-%m-%d %H:%M:%S') for item in result],
            'values': [float(item['value']) for item in result]
        }

        return data

    @classmethod
    def get_top_endpoints(cls, filters=None, limit=10):
        """Возвращает самые популярные эндпоинты."""
        if filters is None:
            filters = {}

        queryset = LogEntry.objects.all()
        queryset = cls.apply_filters(queryset, filters)

        result = queryset.values('path').annotate(
            count=Count('id'),
            avg_time=Avg('response_time')
        ).order_by('-count')[:limit]

        return list(result)

    @classmethod
    def get_status_code_distribution(cls, filters=None):
        """Возвращает распределение кодов состояния."""
        if filters is None:
            filters = {}

        queryset = LogEntry.objects.all()
        queryset = cls.apply_filters(queryset, filters)

        result = queryset.values('status_code').annotate(
            count=Count('id')
        ).order_by('-count')

        # Группируем коды по сотням (2xx, 3xx, 4xx, 5xx)
        groups = defaultdict(int)
        for item in result:
            status_code = item['status_code']
            group = f"{status_code // 100}xx"
            groups[group] += item['count']

        # Преобразуем в нужный формат
        data = {
            'labels': list(groups.keys()),
            'values': list(groups.values())
        }

        return data

    @classmethod
    def get_user_agent_stats(cls, filters=None, limit=5):
        """Возвращает статистику по User-Agent."""
        if filters is None:
            filters = {}

        queryset = LogEntry.objects.all()
        queryset = cls.apply_filters(queryset, filters)

        result = queryset.values('user_agent').annotate(
            count=Count('id')
        ).order_by('-count')[:limit]

        return list(result)

    @classmethod
    def get_ip_stats(cls, filters=None, limit=10):
        """Возвращает статистику по IP-адресам."""
        if filters is None:
            filters = {}

        queryset = LogEntry.objects.all()
        queryset = cls.apply_filters(queryset, filters)

        result = queryset.values('ip_address').annotate(
            count=Count('id'),
            avg_time=Avg('response_time')
        ).order_by('-count')[:limit]

        return list(result)

    @classmethod
    def get_summary_stats(cls, filters=None):
        """Возвращает сводную статистику."""
        if filters is None:
            filters = {}

        queryset = LogEntry.objects.all()
        queryset = cls.apply_filters(queryset, filters)

        total_requests = queryset.count()
        avg_response_time = queryset.aggregate(avg=Avg('response_time'))['avg'] or 0
        error_count = queryset.filter(status_code__gte=400).count()
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0

        return {
            'total_requests': total_requests,
            'avg_response_time': round(avg_response_time, 2),
            'error_count': error_count,
            'error_rate': round(error_rate, 2)
        }
