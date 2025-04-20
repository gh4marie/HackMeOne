import os
import re
import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from user_agents import parse as parse_user_agent

from logparser.models import DimIP, DimDateTime, DimRequest, DimUserAgent, FactLog

# Регулярное выражение для парсинга строки лога
NEW_LOG_PATTERN = re.compile(
    r'^(?P<client_ip>\S+)\s+'
    r'(?P<remote_log_name>\S+)\s+'
    r'(?P<user_id>\S+)\s+'
    r'\[(?P<datetime>[^\]]+)\]\s+'
    r'"(?P<method>GET|POST|PUT|DELETE)\s+(?P<api>\S+)\s+(?P<protocol>HTTP/\d\.\d)"\s+'
    r'(?P<status_code>\d+)\s+'
    r'(?P<bytes>\d+)\s+'
    r'"(?P<referrer>[^"]*)"\s+'
    r'"(?P<user_agent>[^"]*)"\s+'
    r'(?P<response_time>\d+)$'
)

def parse_datetime(dt_str):
    dt_format = "%Y-%m-%d %H:%M:%S %z"
    return datetime.datetime.strptime(dt_str, dt_format)

def parse_log_line(line):
    """
    Парсит строку лога и возвращает словарь с данными.
    Дополнительно анализирует user-agent для получения подробных данных.
    """
    match = NEW_LOG_PATTERN.match(line)
    if not match:
        return None
    try:
        dt_obj = parse_datetime(match.group('datetime'))
    except ValueError:
        return None

    ua_string = match.group('user_agent')
    user_agent = parse_user_agent(ua_string)

    return {
        "ip": match.group('client_ip'),
        "remote_user": match.group('user_id'),
        "date": dt_obj.date(),
        "time": dt_obj.time(),
        "year": dt_obj.year,
        "month": dt_obj.month,
        "day": dt_obj.day,
        "hour": dt_obj.hour,
        "minute": dt_obj.minute,
        "second": dt_obj.second,
        "utc_offset": dt_obj.strftime("%z"),
        "method": match.group('method'),
        "path": match.group('api'),
        "http_version": match.group('protocol'),
        "status_code": int(match.group('status_code')),
        "bytes_sent": int(match.group('bytes')),
        "referrer": match.group('referrer'),
        "user_agent": ua_string,  # оригинальная строка для справки
        # Дополнительные поля для разбора user-agent:
        "browser_family": user_agent.browser.family,
        "browser_version": user_agent.browser.version_string,
        "os_family": user_agent.os.family,
        "os_version": user_agent.os.version_string,
        "device_family": user_agent.device.family,
        "is_mobile": user_agent.is_mobile,
        "is_tablet": user_agent.is_tablet,
        "is_pc": user_agent.is_pc,
        "response_time": float(match.group('response_time')) if match.group('response_time') else None,
    }

def batch_query(model, field_name, values, batch_size=500):
    """
    Выполняет пакетный запрос в БД для модели model с фильтрацией по полю field_name из списка values.
    Возвращает словарь {значение: id объекта}
    """
    results = {}
    values = list(values)
    for i in range(0, len(values), batch_size):
        chunk = values[i:i+batch_size]
        qs = model.objects.filter(**{f"{field_name}__in": chunk})
        for obj in qs:
            results[getattr(obj, field_name)] = obj.id
    return results

class Command(BaseCommand):
    help = "Загрузка лог-файлов с полным набором полей из лога, с нормализацией данных user-agent."

    def add_arguments(self, parser):
        parser.add_argument('--logdir', type=str, default='logs', help='Путь к каталогу с .log файлами')
        parser.add_argument('--chunk_size', type=int, default=10000, help='Количество строк для обработки за один раз')

    def handle(self, *args, **options):
        logdir = options['logdir']
        chunk_size = options['chunk_size']
        if not os.path.isdir(logdir):
            raise CommandError(f"Каталог {logdir} не найден.")
        files = [os.path.join(logdir, f) for f in os.listdir(logdir) if f.endswith('.log')]
        if not files:
            self.stdout.write("Нет .log файлов в каталоге.")
            return
        total_parsed = 0
        for filepath in files:
            basename = os.path.basename(filepath)
            # Определяем сервер по имени файла: если в имени есть "logfiles", значит это Server B, иначе Server A.
            server = "Server B" if "logfiles" in basename.lower() else "Server A"
            self.stdout.write(f"Обрабатываю файл: {filepath} (Server: {server})")
            with open(filepath, 'r', encoding='utf-8') as f:
                chunk_lines = []
                for line in f:
                    chunk_lines.append(line)
                    if len(chunk_lines) >= chunk_size:
                        self.process_chunk(chunk_lines, server)
                        total_parsed += len(chunk_lines)
                        self.stdout.write(f"Обработано {total_parsed} строк.")
                        chunk_lines = []
                if chunk_lines:
                    self.process_chunk(chunk_lines, server)
                    total_parsed += len(chunk_lines)
                    self.stdout.write(f"Обработано {total_parsed} строк.")
        self.stdout.write(self.style.SUCCESS("Все лог-файлы успешно обработаны."))

    @transaction.atomic
    def process_chunk(self, lines, server):
        parsed = []
        for line in lines:
            data = parse_log_line(line)
            if data:
                parsed.append(data)
        if not parsed:
            return

        # 1. Обработка IP-адресов
        ips = {p["ip"] for p in parsed}
        existing_ips = batch_query(DimIP, "ip_address", ips, batch_size=500)
        new_ips = [DimIP(ip_address=ip) for ip in ips if ip not in existing_ips]
        if new_ips:
            DimIP.objects.bulk_create(new_ips)
            new_ip_ids = batch_query(DimIP, "ip_address", {ip for ip in ips if ip not in existing_ips}, batch_size=500)
            existing_ips.update(new_ip_ids)

        # 2. Обработка даты и времени
        dt_keys = {
            (p["date"], p["time"], p["utc_offset"], p["year"], p["month"], p["day"], p["hour"], p["minute"], p["second"])
            for p in parsed
        }
        existing_dt = {}
        for dt in DimDateTime.objects.all().values("id", "log_date", "log_time", "utc_offset",
                                                     "year", "month", "day", "hour", "minute", "second"):
            key = (dt["log_date"], dt["log_time"], dt["utc_offset"], dt["year"], dt["month"],
                   dt["day"], dt["hour"], dt["minute"], dt["second"])
            existing_dt[key] = dt["id"]
        new_dt = []
        for key in dt_keys:
            if key not in existing_dt:
                (log_date, log_time, utc_offset, year, month, day, hour, minute, second) = key
                new_dt.append(DimDateTime(
                    log_date=log_date,
                    log_time=log_time,
                    utc_offset=utc_offset,
                    year=year,
                    month=month,
                    day=day,
                    hour=hour,
                    minute=minute,
                    second=second,
                ))
        if new_dt:
            DimDateTime.objects.bulk_create(new_dt)
            for dt in DimDateTime.objects.all().values("id", "log_date", "log_time", "utc_offset",
                                                        "year", "month", "day", "hour", "minute", "second"):
                key = (dt["log_date"], dt["log_time"], dt["utc_offset"], dt["year"], dt["month"],
                       dt["day"], dt["hour"], dt["minute"], dt["second"])
                existing_dt[key] = dt["id"]

        # 3. Обработка HTTP-запросов
        req_keys = {(p["method"], p["path"], p["http_version"]) for p in parsed}
        existing_req = {}
        for req in DimRequest.objects.all().values("id", "method", "path", "http_version"):
            key = (req["method"], req["path"], req["http_version"])
            existing_req[key] = req["id"]
        new_req = []
        for key in req_keys:
            if key not in existing_req:
                (method, path, http_version) = key
                new_req.append(DimRequest(method=method, path=path, http_version=http_version))
        if new_req:
            DimRequest.objects.bulk_create(new_req)
            for req in DimRequest.objects.all().values("id", "method", "path", "http_version"):
                key = (req["method"], req["path"], req["http_version"])
                existing_req[key] = req["id"]

        # 4. Обработка данных user-agent через DimUserAgent
        ua_details = {}
        for p in parsed:
            ua_str = p["user_agent"]
            if ua_str not in ua_details:
                ua_details[ua_str] = {
                    "browser_family": p.get("browser_family", ""),
                    "browser_version": p.get("browser_version", ""),
                    "os_family": p.get("os_family", ""),
                    "os_version": p.get("os_version", ""),
                    "device_family": p.get("device_family", ""),
                    "is_mobile": p.get("is_mobile", False),
                    "is_tablet": p.get("is_tablet", False),
                    "is_pc": p.get("is_pc", False),
                }
        uas = set(ua_details.keys())
        existing_uas = {}
        for ua in DimUserAgent.objects.filter(original_user_agent__in=uas).values("id", "original_user_agent"):
            existing_uas[ua["original_user_agent"]] = ua["id"]
        new_uas = []
        for ua_str, details in ua_details.items():
            if ua_str not in existing_uas:
                new_uas.append(DimUserAgent(
                    original_user_agent=ua_str,
                    browser_family=details["browser_family"],
                    browser_version=details["browser_version"],
                    os_family=details["os_family"],
                    os_version=details["os_version"],
                    device_family=details["device_family"],
                    is_mobile=details["is_mobile"],
                    is_tablet=details["is_tablet"],
                    is_pc=details["is_pc"],
                ))
        if new_uas:
            DimUserAgent.objects.bulk_create(new_uas)
            for ua in DimUserAgent.objects.filter(original_user_agent__in=uas).values("id", "original_user_agent"):
                existing_uas[ua["original_user_agent"]] = ua["id"]

        # 5. Создание записей FactLog с учетом ссылки на DimUserAgent
        fact_objects = []
        for p in parsed:
            ip_id = existing_ips[p["ip"]]
            dt_key = (p["date"], p["time"], p["utc_offset"], p["year"], p["month"], p["day"], p["hour"], p["minute"], p["second"])
            dt_id = existing_dt[dt_key]
            req_key = (p["method"], p["path"], p["http_version"])
            req_id = existing_req[req_key]
            ua_id = existing_uas.get(p["user_agent"])
            fact_objects.append(FactLog(
                ip_id=ip_id,
                datetime_entry_id=dt_id,
                request_id=req_id,
                status_code=p["status_code"],
                bytes_sent=p["bytes_sent"],
                referrer=p["referrer"],
                user_agent=p["user_agent"],  # Оригинальная строка для справки
                user_agent_detail_id=ua_id,    # Ссылка на запись в DimUserAgent
                remote_user=p["remote_user"],
                response_time=p["response_time"],
                server=server
            ))
        if fact_objects:
            FactLog.objects.bulk_create(fact_objects, batch_size=5000)

# Функция-обёртка для обработки одного файла логов
def process_log_file(file_path):
    """
    Обрабатывает один файл логов, читая все строки и вызывая метод process_chunk.
    """
    command = Command()
    basename = os.path.basename(file_path)
    server = "Server B" if "logfiles" in basename.lower() else "Server A"
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    command.process_chunk(lines, server)

