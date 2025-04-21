# dashboard/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('panel/', views.index_panel, name='panel'),
    path('export/', views.request_export, name='request_export'),
    path('upload-log/', views.index_upload_log, name='upload-log'),
    path('ExampleError/', views.ExampleError.as_view(), name='example-error'),]
