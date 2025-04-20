from django.db import models
#from django.db import models
#from .models import DimIP




class DimIP(models.Model):
    ip_address = models.CharField(max_length=45, unique=True)  # 45 символов на случай IPv6

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

# Новая модель для детального хранения данных user-agent
class DimUserAgent(models.Model):
    # Оригинальная строка user-agent, по которой можно выполнять поиск уникальных записей
    original_user_agent = models.CharField(max_length=255, unique=True)
    browser_family = models.CharField(max_length=50, blank=True)
    browser_version = models.CharField(max_length=50, blank=True)
    os_family = models.CharField(max_length=50, blank=True)
    os_version = models.CharField(max_length=50, blank=True)
    device_family = models.CharField(max_length=50, blank=True)
    is_mobile = models.BooleanField(default=False)
    is_tablet = models.BooleanField(default=False)
    is_pc = models.BooleanField(default=False)

    def __str__(self):
        return self.original_user_agent

class FactLog(models.Model):
    ip = models.ForeignKey(DimIP, on_delete=models.CASCADE)
    datetime_entry = models.ForeignKey(DimDateTime, on_delete=models.CASCADE)
    request = models.ForeignKey(DimRequest, on_delete=models.CASCADE)
    # Ссылка на детальную информацию по user-agent
    user_agent_detail = models.ForeignKey(DimUserAgent, on_delete=models.CASCADE, null=True, blank=True)
    status_code = models.IntegerField()
    bytes_sent = models.IntegerField()
    referrer = models.CharField(max_length=255, blank=True)
    # Можно оставить оригинальную строку для справки:
    user_agent = models.CharField(max_length=255, blank=True)
    remote_user = models.CharField(max_length=50, blank=True)
    response_time = models.FloatField(blank=True, null=True)
    server = models.CharField(max_length=100, blank=True, default="")

    def __str__(self):
        return f"Log #{self.id} (IP: {self.ip.ip_address})"

class IpDateAggregate(models.Model):
    """
    Сколько запросов сделал каждый IP за каждый день.
    """
    ip         = models.ForeignKey(DimIP, on_delete=models.CASCADE)
    log_date   = models.DateField()
    count      = models.IntegerField()

    class Meta:
        unique_together = ('ip', 'log_date')
        indexes = [
            models.Index(fields=['log_date']),
            models.Index(fields=['ip']),
        ]

class DateStatusAggregate(models.Model):
    """
    Сколько запросов каждого status_code в каждый день.
    """
    log_date    = models.DateField()
    status_code = models.IntegerField()
    count       = models.IntegerField()

    class Meta:
        unique_together = ('log_date', 'status_code')
        indexes = [
            models.Index(fields=['log_date']),
            models.Index(fields=['status_code']),
        ]