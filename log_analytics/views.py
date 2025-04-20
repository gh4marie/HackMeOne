from django.shortcuts import render
from django.http import HttpResponse
from ..log_analytics.forms import LogUploadForm
from logparser.management.commands.load_logs import process_log_file  # импорт функции парсинга
import tempfile

def upload_log(request):
    if request.method == 'POST':
        form = LogUploadForm(request.POST, request.FILES)
        if form.is_valid():
            log_file = form.cleaned_data['log_file']
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                for chunk in log_file.chunks():
                    tmp_file.write(chunk)
                tmp_file_path = tmp_file.name
            process_log_file(tmp_file_path)
            return HttpResponse("Лог успешно загружен и обработан!")
    else:
        form = LogUploadForm()
        return render(request, 'upload.html', {'form': form})
