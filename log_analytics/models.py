from django.db import models
from django.db.models import Count

class DimIP(models.Model):
    ip_address = models.CharField(max_length=45, unique=True)
    def __str__(self):
        return self.ip_address

class DimDateTime(models.Model):
    log_date = models.DateField()
    log_time = models.TimeField()
    year = models.IntegerField()
    month = models.IntegerField()
    day = models.IntegerField()
    hour = models.IntegerField()
    minute = models.IntegerField()
    second = models.IntegerField()
    utc_offset = models.CharField(max_length=6)
    def __str__(self):
        return f"{self.log_date} {self.log_time} ({self.utc_offset})"

class DimRequest(models.Model):
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=255)
    http_version = models.CharField(max_length=10)
    def __str__(self):
        return f"{self.method} {self.path}"

class FactLog(models.Model):
    ip = models.ForeignKey(DimIP, on_delete=models.CASCADE)
    datetime_entry = models.ForeignKey(DimDateTime, on_delete=models.CASCADE)
    request = models.ForeignKey(DimRequest, on_delete=models.CASCADE)
    status_code = models.IntegerField()
    bytes_sent = models.IntegerField()
    referrer = models.CharField(max_length=255, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    remote_user = models.CharField(max_length=50, blank=True)
    def __str__(self):
        return f"Log #{self.id} (IP: {self.ip.ip_address})"

    @classmethod
    def get_status_distribution(cls):
        return cls.objects.values('status_code').annotate(count=Count('id'))

