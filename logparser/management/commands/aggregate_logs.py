from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db import transaction
from logparser.models import FactLog, IpDateAggregate, DateStatusAggregate

class Command(BaseCommand):
    help = 'Пересчитывает агрегаты: запросы по IP/дате и по статус‑коду/дате.'

    def handle(self, *args, **opts):
        self.stdout.write("Starting aggregation…")
        with transaction.atomic():
            # 1) Агрегат по IP + дате
            qs1 = (FactLog.objects
                        .values('ip_id', 'datetime_entry__log_date')
                        .annotate(cnt=Count('id')))
            IpDateAggregate.objects.all().delete()
            objs1 = [
                IpDateAggregate(
                    ip_id=rec['ip_id'],
                    log_date=rec['datetime_entry__log_date'],
                    count=rec['cnt']
                )
                for rec in qs1
            ]
            IpDateAggregate.objects.bulk_create(objs1, batch_size=5000)

            # 2) Агрегат по статус-коду + дате
            qs2 = (FactLog.objects
                        .values('datetime_entry__log_date', 'status_code')
                        .annotate(cnt=Count('id')))
            DateStatusAggregate.objects.all().delete()
            objs2 = [
                DateStatusAggregate(
                    log_date   = rec['datetime_entry__log_date'],
                    status_code= rec['status_code'],
                    count      = rec['cnt']
                )
                for rec in qs2
            ]
            DateStatusAggregate.objects.bulk_create(objs2, batch_size=5000)

        self.stdout.write(self.style.SUCCESS("Aggregation done."))
