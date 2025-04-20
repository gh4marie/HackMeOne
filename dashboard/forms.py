
#Создадим формы для фильтрации данных:

from django import forms
from datetime import datetime, timedelta


class LogFilterForm(forms.Form):
    """Форма для фильтрации логов по различным параметрам."""

    # Настройка дат по умолчанию
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)

    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=week_ago,
        label='Дата начала'
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=today,
        label='Дата окончания'
    )

    ip_address = forms.CharField(
        required=False,
        label='IP адрес',
        widget=forms.TextInput(attrs={'placeholder': 'Например: 192.168.1.1'})
    )

    STATUS_CHOICES = [
        ('', 'Все статусы'),
        ('2xx', '2xx - Успешно'),
        ('3xx', '3xx - Перенаправление'),
        ('4xx', '4xx - Ошибка клиента'),
        ('5xx', '5xx - Ошибка сервера'),
    ]

    status_code = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        label='Код статуса'
    )

    method = forms.ChoiceField(
        choices=[
            ('', 'Все методы'),
            ('GET', 'GET'),
            ('POST', 'POST'),
            ('PUT', 'PUT'),
            ('DELETE', 'DELETE'),
            ('HEAD', 'HEAD'),
        ],
        required=False,
        label='HTTP метод'
    )

    path = forms.CharField(
        required=False,
        label='URL путь',
        widget=forms.TextInput(attrs={'placeholder': 'Например: /api/users/'})
    )

    min_response_time = forms.IntegerField(
        required=False,
        min_value=0,
        label='Мин. время ответа (мс)'
    )

    max_response_time = forms.IntegerField(
        required=False,
        min_value=0,
        label='Макс. время ответа (мс)'
    )

    limit = forms.IntegerField(
        initial=100,
        min_value=10,
        max_value=1000,
        label='Количество записей'
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("Дата начала не может быть позже даты окончания")

        return cleaned_data


class ChartConfigForm(forms.Form):
    """Форма для настройки отображения графиков."""

    CHART_TYPES = [
        ('line', 'Линейный график'),
        ('bar', 'Столбчатая диаграмма'),
        ('pie', 'Круговая диаграмма'),
        ('doughnut', 'Кольцевая диаграмма'),
    ]

    chart_type = forms.ChoiceField(
        choices=CHART_TYPES,
        initial='line',
        label='Тип графика'
    )

    AGGREGATION_CHOICES = [
        ('hour', 'По часам'),
        ('day', 'По дням'),
        ('week', 'По неделям'),
        ('month', 'По месяцам'),
    ]

    time_aggregation = forms.ChoiceField(
        choices=AGGREGATION_CHOICES,
        initial='day',
        label='Группировка по времени'
    )

    METRIC_CHOICES = [
        ('count', 'Количество запросов'),
        ('avg_time', 'Среднее время ответа'),
        ('error_rate', 'Частота ошибок (%)'),
        ('bandwidth', 'Использованная пропускная способность'),
    ]

    metric = forms.ChoiceField(
        choices=METRIC_CHOICES,
        initial='count',
        label='Метрика'
    )

    show_legend = forms.BooleanField(
        initial=True,
        required=False,
        label='Показать легенду'
    )

class LogUploadForm(forms.Form):
    log_file = forms.FileField(label='Выберите лог-файл')
