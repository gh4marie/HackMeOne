from django import forms

class LogUploadForm(forms.Form):
    log_file = forms.FileField(label='Выберите лог-файл')