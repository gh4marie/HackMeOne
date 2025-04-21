from django.shortcuts import render
from django.http import HttpResponse
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
import tempfile
import random
from django.db.models import Q

from .forms import LogFilterForm, ChartConfigForm, LogUploadForm
from .analytics import LogAnalytics
from .visualizer import ChartVisualizer
from logparser.management.commands.load_logs import process_log_file
from logparser.models import FactLog  # Используем непосредственно FactLog для хранения логов
from django.shortcuts import render, redirect
from django.urls import reverse
from django.db.models import Count
from collections import defaultdict
from django.conf import settings
import os
from datetime import date, timedelta, datetime
import csv

def daterange(start_date: date, end_date: date):
    days = int((end_date - start_date).days)
    for n in range(days):
        yield start_date + timedelta(n)

def human_readable_size(num_bytes):
    """Переводит байты в удобочитаемый формат."""
    for unit in ('Б', 'КБ', 'МБ', 'ГБ', 'ТБ'):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} ПБ"


def get_sqlite_db_size():
    """Возвращает размер файла SQLite БД в байтах."""
    db_path = settings.DATABASES['default']['NAME']
    # если путь относительный, приведём его к абсолютному
    if not os.path.isabs(db_path):
        db_path = os.path.join(settings.BASE_DIR, db_path)
    try:
        return os.path.getsize(db_path)
    except OSError:
        return 0

def filter_logs(request):
    start_date_str = request.GET.get('start_date', None)
    end_date_str = request.GET.get('end_date', None)

    status_values = request.GET.getlist('status', [])
    # Handle wildcard for 1xx status codes
    if "1**" in status_values:
        status_values.remove("1**")
        status_values.extend(range(100, 200))  # Add all status codes from 100-199
    # Handle wildcard for 2xx status codes
    if "2**" in status_values:
        status_values.remove("2**")
        status_values.extend(range(200, 300))  # Add all status codes from 200-299
    # Handle wildcard for 3xx status codes
    if "3**" in status_values:
        status_values.remove("3**")
        status_values.extend(range(300, 400))  # Add all status codes from 300-399
    # Handle wildcard for 4xx status codes
    if "4**" in status_values:
        status_values.remove("4**")
        status_values.extend(range(400, 500))  # Add all status codes from 400-499
    # Handle wildcard for 5xx status codes
    if "5**" in status_values:
        status_values.remove("5**")
        status_values.extend(range(500, 600))  # Add all status codes from 500-599
    method_values = request.GET.getlist('http_method', [])

    browser_values = request.GET.getlist('browser', [])
    if browser_values == ['']: browser_values = []

    os_values = request.GET.getlist('os', [])
    if os_values == ['']: os_values = []


    # Фильтрация по дню через связь с моделью DimDateTime (поле log_date)
    if start_date_str and end_date_str:

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        # if int((end_date - start_date).days) > 365:
        #     return HttpResponse("Too many days")

        all_objects = FactLog.objects.filter(
                        *([Q(status_code__in=status_values)] if status_values else []),
                        *([Q(request__method__in=method_values)] if method_values else []),
                        *([Q(user_agent_detail__os_family__in=os_values)] if os_values else []),
                        *([Q(user_agent_detail__browser_family__in=browser_values)] if browser_values else []),
                        datetime_entry__log_date__range=(start_date, end_date)
                    )
        return all_objects
    else:
        return None

def index_panel(request):
    """
    Основной обработчик дашборда. Формирует статистику логов и передаёт данные в шаблон.
    """
    print("Creating day stats")

    start_date_str = request.GET.get('start_date', None)
    end_date_str = request.GET.get('end_date', None)
    filtered_objects = filter_logs(request)
    errors1 = []
    errors2 = []
    errors3 = []
    errors4 = []
    errors5 = []
    date_labels = []
    if filtered_objects != None:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        errors1 = [ FactLog.objects.filter(Q(datetime_entry__day=day.day) & Q(datetime_entry__month=day.month) & Q(datetime_entry__year=day.year) & Q(status_code__range=[100, 199])).count() for day in daterange(start_date, end_date) ]
        errors2 = [ FactLog.objects.filter(Q(datetime_entry__day=day.day) & Q(datetime_entry__month=day.month) & Q(datetime_entry__year=day.year) & Q(status_code__range=[200, 299])).count() for day in daterange(start_date, end_date) ]
        errors3 = [ FactLog.objects.filter(Q(datetime_entry__day=day.day) & Q(datetime_entry__month=day.month) & Q(datetime_entry__year=day.year) & Q(status_code__range=[300, 399])).count() for day in daterange(start_date, end_date) ]
        errors4 = [ FactLog.objects.filter(Q(datetime_entry__day=day.day) & Q(datetime_entry__month=day.month) & Q(datetime_entry__year=day.year) & Q(status_code__range=[400, 499])).count() for day in daterange(start_date, end_date) ]
        errors5 = [ FactLog.objects.filter(Q(datetime_entry__day=day.day) & Q(datetime_entry__month=day.month) & Q(datetime_entry__year=day.year) & Q(status_code__range=[500, 599])).count() for day in daterange(start_date, end_date) ]
        date_labels = [day.strftime("%Y-%m-%d") for day in daterange(start_date, end_date)]

        # Get all date counts in a single query
        date_counts = (
            filtered_objects
            .values('datetime_entry__log_date')
            .annotate(count=Count('id'))
        )

        # Create a dictionary mapping dates to counts
        date_count_dict = defaultdict(int)
        for item in date_counts:
            date_count_dict[item['datetime_entry__log_date']] = item['count']

        # Build the month_stats list using our in-memory dictionary
        month_stats = [
            date_count_dict[single_date]
            for single_date in daterange(start_date, end_date)
        ]
    else:
        month_stats = []

    print("Counting requests")
    total_requests = FactLog.objects.count()

    print("Counting errors")
    total_errors = total_requests - FactLog.objects.filter(status_code__range=[200, 299]).count()
    print("Counting unique users")
    total_unique_users = 0  # Здесь можно реализовать подсчёт уникальных пользователей

    # Получаем размер базы данных
    size_bytes = get_sqlite_db_size()
    db_size = human_readable_size(size_bytes)

    context = {
        "month_stats": "[" + ", ".join(map(str, month_stats)) + "]",
        'stats_size': len(month_stats),
        "total_requests": "{:,}".format(total_requests),
        "total_errors": "{:,}".format(total_errors),
        "total_unique_users": "{:,}".format(total_unique_users),
        "db_size": db_size,
    }


    context.update({
        'errors1': errors1,
        'errors2': errors2,
        'errors3': errors3,
        'errors4': errors4,
        'errors5': errors5,
        'date_labels' : date_labels,
    })

    return render(request, 'dashboard/index_1.html', context)

def request_export(request):
    print("Exporting data...")
    filtered_objects = filter_logs(request)
    if filtered_objects == None:
        return HttpResponse("Error: failed to apply filters")
    opts = filtered_objects.model._meta
    model = filtered_objects.model
    response = HttpResponse(content_type='text/csv')
    # force download.
    response['Content-Disposition'] = 'attachment;filename=export.csv'
    # the csv writer
    writer = csv.writer(response)

    print("Preparing CSV")
    field_names = [field.name for field in opts.fields]

    # Write a first row with header information
    writer.writerow(field_names)
    # Write data rows
    i = 0
    size = len(filtered_objects)
    if size > 100000:
        return HttpResponse("Error: too many records")
    for obj in filtered_objects:
        if i % 1000 == 0:
            print(f"Writing data {i}/{size}")
        writer.writerow([getattr(obj, field) for field in field_names])
        i += 1
    return response

def index_upload_log(request):
    """
    Обработчик для загрузки лог-файлов. При POST-запросе загруженный файл сохраняется во временное хранилище,
    после чего вызывается функция обработки логов process_log_file.
    """
    if request.method == 'POST':
        form = LogUploadForm(request.POST, request.FILES)
        if form.is_valid():
            log_file = form.cleaned_data['log_file']
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                for chunk in log_file.chunks():
                    tmp_file.write(chunk)
                tmp_file_path = tmp_file.name
            process_log_file(tmp_file_path)
            return redirect(reverse('panel'))  # редирект на главную страницу дашборда
             #   return render(request, 'upload_logs.html')
        else:
            return HttpResponse(b"Error")
    else:
        form = LogUploadForm()
        return render(request, 'dashboard/index_upload_form.html', {'form': form})

class DashboardView(TemplateView):
    """Главная страница дашборда с основными графиками и статистикой."""
    template_name = 'dashboard/index_1.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Получение данных из форм фильтрации и настройки графика
        filter_form = LogFilterForm(self.request.GET or None)
        chart_form = ChartConfigForm(self.request.GET or None)

        # Инициализация фильтров (исключаются пустые значения)
        filters = {}
        if filter_form.is_valid():
            for key, value in filter_form.cleaned_data.items():
                if value:
                    filters[key] = value

        chart_config = {}
        if chart_form.is_valid():
            chart_config = chart_form.cleaned_data

        # Получение данных для графика через модуль аналитики
        time_series_data = LogAnalytics.get_request_over_time(
            filters=filters,
            time_aggregation=chart_config.get('time_aggregation', 'day'),
            metric=chart_config.get('metric', 'count')
        )

        chart_type = chart_config.get('chart_type', 'line')

        # Определение заголовка и метки оси Y в зависимости от выбранной метрики
        metric_labels = {
            'count': ('Количество запросов', 'Запросы'),
            'avg_time': ('Среднее время ответа', 'Время (мс)'),
            'error_rate': ('Частота ошибок', 'Ошибки (%)'),
            'bandwidth': ('Использованная пропускная способность', 'Размер (байты)')
        }
        metric = chart_config.get('metric', 'count')
        title, y_axis_label = metric_labels.get(metric, ('', ''))

        chart_config_json = ChartVisualizer.to_json(
            ChartVisualizer.get_chart_config(
                time_series_data,
                chart_type=chart_type,
                title=title,
                y_axis_label=y_axis_label
            )
        )

        # Получение статистики распределения кодов состояния
        status_data = LogAnalytics.get_status_code_distribution(filters)
        status_chart_json = ChartVisualizer.to_json(
            ChartVisualizer.get_pie_chart_config(
                status_data,
                title='Распределение кодов состояния'
            )
        )

        # Получение топ эндпоинтов и статистики по IP
        top_endpoints = LogAnalytics.get_top_endpoints(filters, limit=10)
        ip_stats = LogAnalytics.get_ip_stats(filters, limit=10)
        summary_stats = LogAnalytics.get_summary_stats(filters)

        context.update({
            'filter_form': filter_form,
            'chart_form': chart_form,
            'chart_config': chart_config_json,
            'status_chart_config': status_chart_json,
            'top_endpoints': top_endpoints,
            'ip_stats': ip_stats,
            'summary_stats': summary_stats,
        })

        return context

class DailyStatsView(TemplateView):
    """Подробная статистика по дням."""
    template_name = 'dashboard/daily_stats.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_form = LogFilterForm(self.request.GET or None)

        filters = {}
        if filter_form.is_valid():
            for key, value in filter_form.cleaned_data.items():
                if value:
                    filters[key] = value

        # Данные для графика запросов по дням
        daily_data = LogAnalytics.get_request_over_time(
            filters=filters,
            time_aggregation='day',
            metric='count'
        )

        daily_chart_json = ChartVisualizer.to_json(
            ChartVisualizer.get_bar_chart_config(
                daily_data,
                title='Запросы по дням',
                y_axis_label='Количество запросов'
            )
        )

        # Данные по среднему времени ответа по дням
        response_time_data = LogAnalytics.get_request_over_time(
            filters=filters,
            time_aggregation='day',
            metric='avg_time'
        )

        response_time_chart_json = ChartVisualizer.to_json(
            ChartVisualizer.get_line_chart_config(
                response_time_data,
                title='Среднее время ответа по дням',
                y_axis_label='Время (мс)'
            )
        )

        context.update({
            'filter_form': filter_form,
            'daily_chart_config': daily_chart_json,
            'response_time_chart_config': response_time_chart_json,
        })

        return context

class ErrorAnalysisView(TemplateView):
    """Анализ ошибок."""
    template_name = 'dashboard/error_analysis.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_form = LogFilterForm(self.request.GET or None)

        filters = {}
        if filter_form.is_valid():
            for key, value in filter_form.cleaned_data.items():
                if value:
                    filters[key] = value

        # Фильтрация по 4xx и 5xx ошибкам
        error_filters = filters.copy()
        error_filters['status_code'] = '4xx'
        error_4xx_data = LogAnalytics.get_request_over_time(
            filters=error_filters,
            time_aggregation='day',
            metric='count'
        )
        error_4xx_chart_json = ChartVisualizer.to_json(
            ChartVisualizer.get_line_chart_config(
                error_4xx_data,
                title='Ошибки клиента (4xx) по дням',
                y_axis_label='Количество ошибок'
            )
        )

        error_filters['status_code'] = '5xx'
        error_5xx_data = LogAnalytics.get_request_over_time(
            filters=error_filters,
            time_aggregation='day',
            metric='count'
        )
        error_5xx_chart_json = ChartVisualizer.to_json(
            ChartVisualizer.get_line_chart_config(
                error_5xx_data,
                title='Ошибки сервера (5xx) по дням',
                y_axis_label='Количество ошибок'
            )
        )

        context.update({
            'filter_form': filter_form,
            'error_4xx_chart_config': error_4xx_chart_json,
            'error_5xx_chart_config': error_5xx_chart_json,
        })

        return context

def labels_f():
    return ['404', '502', '503', 'success']

def data_f():
    return [random.randint(1, 100) for _ in range(4)]

class ExampleError(TemplateView):
    """Анализ ошибок с генерацией случайных данных."""
    template_name = 'dashboard/ExampleError.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data = data_f()
        labels = labels_f()

        # Генерация случайных цветов для графика
        background_colors = [
            f'rgba({random.randint(0, 255)}, {random.randint(0, 255)}, {random.randint(0, 255)}, 0.2)'
            for _ in range(4)
        ]
        border_colors = [
            f'rgba({random.randint(0, 255)}, {random.randint(0, 255)}, {random.randint(0, 255)}, 1)'
            for _ in range(4)
        ]

        context['labels'] = labels
        context['data'] = data
        context['background_colors'] = background_colors
        context['border_colors'] = border_colors

        return context


#class ChartDataAPIView(View):
#    """API для получения данных графиков."""
#
#    def get(self, request, *args, **kwargs):
#        filter_form = LogFilterForm(request.GET or None)
#        chart_form = ChartConfigForm(request.GET or None)
#
#        filters = {}
#        if filter_form.is_valid():
#            for key, value in filter_form.cleaned_data.items():
#                if value:
#                    filters[key] = value
#
#        chart_config = {}
#        if chart_form.is_valid():
#            chart_config = chart_form.cleaned_data
#
#        time_aggregation = chart_config.get('time_aggregation', 'day')
#        metric = chart_config.get('metric', 'count')
#        chart_type = chart_config.get('chart_type', 'line')
