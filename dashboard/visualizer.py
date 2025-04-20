
#Модуль для генерации данных для графиков:

import json
import random

class ChartVisualizer:
    """Класс для генерации конфигурации графиков для Chart.js."""

    @staticmethod
    def get_random_color(opacity=0.7):
        """Генерирует случайный цвет в формате rgba."""
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)
        return f'rgba({r}, {g}, {b}, {opacity})'

    @staticmethod
    def get_line_chart_config(data, title='', y_axis_label=''):
        """
        Генерирует конфигурацию для линейного графика Chart.js.

        Args:
            data: словарь с ключами 'labels' и 'values'
            title: заголовок графика
            y_axis_label: подпись для оси Y

        Returns:
            Словарь с конфигурацией графика для Chart.js
        """
        color = ChartVisualizer.get_random_color()
        border_color = color.replace(str(0.7), str(1.0))

        config = {
            'type': 'line',
            'data': {
                'labels': data['labels'],
                'datasets': [{
                    'label': title,
                    'data': data['values'],
                    'backgroundColor': color,
                    'borderColor': border_color,
                    'borderWidth': 2,
                    'fill': False,
                    'tension': 0.1
                }]
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'scales': {
                    'y': {
                        'beginAtZero': True,
                        'title': {
                            'display': True,
                            'text': y_axis_label
                        }
                    },
                    'x': {
                        'title': {
                            'display': True,
                            'text': 'Время'
                        }
                    }
                },
                'plugins': {
                    'title': {
                        'display': True,
                        'text': title,
                        'font': {
                            'size': 16
                        }
                    },
                    'tooltip': {
                        'mode': 'index',
                        'intersect': False
                    }
                }
            }
        }

        return config

    @staticmethod
    def get_bar_chart_config(data, title='', y_axis_label=''):
        """Генерирует конфигурацию для столбчатой диаграммы."""
        colors = [ChartVisualizer.get_random_color() for _ in range(len(data['labels']))]

        config = {
            'type': 'bar',
            'data': {
                'labels': data['labels'],
                'datasets': [{
                    'label': title,
                    'data': data['values'],
                    'backgroundColor': colors,
                    'borderWidth': 1
                }]
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'scales': {
                    'y': {
                        'beginAtZero': True,
                        'title': {
                            'display': True,
                            'text': y_axis_label
                        }
                    }
                },
                'plugins': {
                    'title': {
                        'display': True,
                        'text': title,
                        'font': {
                            'size': 16
                        }
                    }
                }
            }
        }

        return config

    @staticmethod
    def get_pie_chart_config(data, title=''):
        """Генерирует конфигурацию для круговой диаграммы."""
        colors = [ChartVisualizer.get_random_color() for _ in range(len(data['labels']))]

        config = {
            'type': 'pie',
            'data': {
                'labels': data['labels'],
                'datasets': [{
                    'data': data['values'],
                    'backgroundColor': colors,
                    'hoverOffset': 4
                }]
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'plugins': {
                    'title': {
                        'display': True,
                        'text': title,
                        'font': {
                            'size': 16
                        }
                    },
                    'legend': {
                        'position': 'right'
                    }
                }
            }
        }

        return config

    @staticmethod
    def get_doughnut_chart_config(data, title=''):
        """Генерирует конфигурацию для кольцевой диаграммы."""
        config = ChartVisualizer.get_pie_chart_config(data, title)
        config['type'] = 'doughnut'

        return config

    @staticmethod
    def get_chart_config(data, chart_type='line', title='', y_axis_label=''):
        """Возвращает конфигурацию в зависимости от выбранного типа графика."""
        if chart_type == 'line':
            return ChartVisualizer.get_line_chart_config(data, title, y_axis_label)
        elif chart_type == 'bar':
            return ChartVisualizer.get_bar_chart_config(data, title, y_axis_label)
        elif chart_type == 'pie':
            return ChartVisualizer.get_pie_chart_config(data, title)
        elif chart_type == 'doughnut':
            return ChartVisualizer.get_doughnut_chart_config(data, title)
        else:
            return ChartVisualizer.get_line_chart_config(data, title, y_axis_label)

    @staticmethod
    def to_json(config):
        """Преобразует конфигурацию в JSON-строку."""
        return json.dumps(config)
