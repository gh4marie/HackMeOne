import os
import re
import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from logparser.models import DimIP, DimDateTime, DimRequest, FactLog

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
    match = NEW_LOG_PATTERN.match(line)
    if not match:
        return None
    try:
        dt_obj = parse_datetime(match.group('datetime'))
    except ValueError:
        return None
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
        "user_agent": match.group('user_agent'),
        "response_time": float(match.group('response_time')) if match.group('response_time') else None,
    }

def batch_query(model, field_name, values, batch_size=500):
    results = {}
    values = list(values)
    for i in range(0, len(values), batch_size):
        chunk = values[i:i+batch_size]
        qs = model.objects.filter(**{f"{field_name}__in": chunk})
        for obj in qs:
            results[getattr(obj, field_name)] = obj.id
    return results

# ================================
# Функции для загрузки лог-файла
# ================================

@transaction.atomic
def process_chunk(lines, server):
    parsed = []
    for line in lines:
        data = parse_log_line(line)
        if data:
            parsed.append(data)
    if not parsed:
        return

    ips = {p["ip"] for p in parsed}
    dt_keys = {
        (p["date"], p["time"], p["utc_offset"], p["year"], p["month"], p["day"], p["hour"], p["minute"], p["second"])
        for p in parsed
    }
    req_keys = {(p["method"], p["path"], p["http_version"]) for p in parsed}
    existing_ips = batch_query(DimIP, "ip_address", ips, batch_size=500)
    existing_dt = {}
    for dt in DimDateTime.objects.all().values("id", "log_date", "log_time", "utc_offset",
                                                 "year", "month", "day", "hour", "minute", "second"):
        key = (dt["log_date"], dt["log_time"], dt["utc_offset"], dt["year"], dt["month"], dt["day"],
               dt["hour"], dt["minute"], dt["second"])
        existing_dt[key] = dt["id"]
    existing_req = {}
    for req in DimRequest.objects.all().values("id", "method", "path", "http_version"):
        key = (req["method"], req["path"], req["http_version"])
        existing_req[key] = req["id"]

    new_ips = [DimIP(ip_address=ip) for ip in ips if ip not in existing_ips]
    if new_ips:
        DimIP.objects.bulk_create(new_ips)
        new_ip_ids = batch_query(DimIP, "ip_address", {ip for ip in ips if ip not in existing_ips}, batch_size=500)
        existing_ips.update(new_ip_ids)

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
            key = (dt["log_date"], dt["log_time"], dt["utc_offset"], dt["year"], dt["month"], dt["day"],
                   dt["hour"], dt["minute"], dt["second"])
            existing_dt[key] = dt["id"]

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

    fact_objects = []
    for p in parsed:
        ip_id = existing_ips[p["ip"]]
        dt_key = (p["date"], p["time"], p["utc_offset"], p["year"], p["month"], p["day"], p["hour"], p["minute"], p["second"])
        dt_id = existing_dt[dt_key]
        req_key = (p["method"], p["path"], p["http_version"])
        req_id = existing_req[req_key]
        fact_objects.append(FactLog(
            ip_id=ip_id,
            datetime_entry_id=dt_id,
            request_id=req_id,
            status_code=p["status_code"],
            bytes_sent=p["bytes_sent"],
            referrer=p["referrer"],
            user_agent=p["user_agent"],
            remote_user=p["remote_user"],
            response_time=p["response_time"],
            server=server
        ))
    if fact_objects:
        FactLog.objects.bulk_create(fact_objects, batch_size=5000)


def process_log_file(filepath, chunk_size=10000):
    """
    Обрабатывает лог-файл по указанному пути: определяет сервер по имени файла и
    читает строки порциями (чанками) с последующей обработкой.
    """
    if not os.path.isfile(filepath):
        raise Exception(f"Файл {filepath} не найден: {filepath}")
    basename = os.path.basename(filepath)
    # Если в имени файла встречается "logfiles" (регистр не важен) – это Server B, иначе Server A
    server = "Server B" if "logfiles" in basename.lower() else "Server A"
    total_parsed = 0
    with open(filepath, 'r', encoding='utf-8') as f:
        chunk_lines = []
        for line in f:
            chunk_lines.append(line)
            if len(chunk_lines) >= chunk_size:
                process_chunk(chunk_lines, server)
                total_parsed += len(chunk_lines)
                print(f"Обработано {total_parsed} строк.")
                chunk_lines = []
        if chunk_lines:
            process_chunk(chunk_lines, server)
            total_parsed += len(chunk_lines)
            print(f"Обработано {total_parsed} строк.")
