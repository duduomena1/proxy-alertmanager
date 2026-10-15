"""Capacidade enviada pelo produtor do alerta, sem consultar servidores externos."""
import math


CAPACITY_ANNOTATIONS = {'available_bytes', 'total_bytes', 'cpu_count', 'cpu_idle_percent'}


def nonnegative_number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def format_bytes(value):
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'):
        if value < 1024 or unit == 'PiB':
            return f'{value:.2f} {unit}'
        value /= 1024


def capacity_lines(alert_type, annotations):
    """Aceita números sem unidade; campos ausentes/inválidos nunca viram zero."""
    if alert_type in ('disk', 'memory'):
        available = nonnegative_number(annotations.get('available_bytes'))
        total = nonnegative_number(annotations.get('total_bytes'))
        if total == 0:
            total = None
        if available is not None and total is not None and available > total:
            return ['**Capacidade:** dados inconsistentes (disponível maior que total)']
        lines = []
        if available is not None:
            lines.append(f'**Disponível:** {format_bytes(available)}')
        else:
            lines.append('**Disponível:** indisponível (não informado no webhook)')
        if total is not None:
            lines.append(f'**Capacidade total:** {format_bytes(total)}')
            if available is not None:
                lines.append(f'**Disponível (%):** {100 * (available / total):.2f}%')
        return lines
    if alert_type == 'cpu':
        idle = nonnegative_number(annotations.get('cpu_idle_percent'))
        count = nonnegative_number(annotations.get('cpu_count'))
        lines = []
        if idle is not None and idle <= 100:
            lines.append(f'**Ociosidade da CPU:** {idle:.2f}%')
            if count is not None and count > 0 and count.is_integer():
                lines.append(f'**Capacidade ociosa equivalente:** {count * (idle / 100):.2f} de {count:.0f} CPUs lógicas')
        return lines
    return []
