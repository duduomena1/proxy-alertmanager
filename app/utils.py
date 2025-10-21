import re
from datetime import datetime


def _is_meaningful(value):
    if value is None:
        return False
    v = str(value).strip()
    if v == "":
        return False
    lowered = v.lower()
    return lowered not in {"n/a", "none", "null", "unknown", "desconhecido", "-", "localhost", "0.0.0.0"}


def pick_first_nonempty(*candidates):
    for c in candidates:
        if _is_meaningful(c):
            return str(c).strip()
    return None


def _strip_port(host_or_ip: str) -> str:
    if not host_or_ip:
        return host_or_ip
    if ":" in host_or_ip:
        return host_or_ip.split(":")[0]
    return host_or_ip


def format_timestamp(timestamp_str):
    if not timestamp_str or timestamp_str == 'N/A':
        return 'N/A'
    try:
        clean_timestamp = timestamp_str.replace('Z', '').replace('T', ' ')
        return clean_timestamp
    except Exception:
        return timestamp_str


def format_metric_value(value, unit):
    try:
        if value is None:
            return "indisponível"
        return f"{float(value):.1f}{unit}"
    except Exception:
        return "indisponível"


def extract_metric_value_enhanced(values, value_string, alert_type="default", debug_mode=False):
    if debug_mode:
        print(f"[DEBUG] extract_metric_value_enhanced - Alert Type: {alert_type}")
        print(f"[DEBUG] Values received: {values}")
        print(f"[DEBUG] ValueString received: {value_string}")

    extracted_value = None
    extraction_source = None

    if values and isinstance(values, dict):
        for key in ['A', 'C', 'B', 'D']:
            if key in values and values[key] is not None:
                try:
                    extracted_value = float(values[key])
                    extraction_source = f"values[{key}]"
                    if debug_mode:
                        print(f"[DEBUG] Extracted {extracted_value} from {extraction_source}")
                    break
                except (ValueError, TypeError) as e:
                    if debug_mode:
                        print(f"[DEBUG] Failed to convert values[{key}]={values[key]}: {e}")
                    continue

        if extracted_value is None:
            for key, value in values.items():
                if value is not None:
                    try:
                        extracted_value = float(value)
                        extraction_source = f"values[{key}]"
                        if debug_mode:
                            print(f"[DEBUG] Extracted {extracted_value} from fallback {extraction_source}")
                        break
                    except (ValueError, TypeError) as e:
                        if debug_mode:
                            print(f"[DEBUG] Failed to convert values[{key}]={value}: {e}")
                        continue

    if extracted_value is None and value_string:
        try:
            value_match = re.search(r'value=([0-9]*\.?[0-9]+)', str(value_string))
            if value_match:
                extracted_value = float(value_match.group(1))
                extraction_source = "valueString(value=pattern)"
                if debug_mode:
                    print(f"[DEBUG] Extracted {extracted_value} from {extraction_source}")
            else:
                number_match = re.search(r'([0-9]*\.?[0-9]+)', str(value_string))
                if number_match:
                    extracted_value = float(number_match.group(1))
                    extraction_source = "valueString(number_pattern)"
                    if debug_mode:
                        print(f"[DEBUG] Extracted {extracted_value} from {extraction_source}")
        except (ValueError, AttributeError) as e:
            if debug_mode:
                print(f"[DEBUG] Failed to extract from valueString: {e}")

    if extracted_value is None:
        extracted_value = 0.0
        extraction_source = "default_fallback"
        if debug_mode:
            print(f"[DEBUG] No value found, using default: {extracted_value}")

    if alert_type in ['cpu', 'memory', 'disk']:
        if extracted_value > 1 and extracted_value <= 100:
            pass
        elif extracted_value > 0 and extracted_value <= 1:
            extracted_value = extracted_value * 100
            if debug_mode:
                print(f"[DEBUG] Converted fraction to percentage: {extracted_value}%")
        elif extracted_value > 100:
            if debug_mode:
                print(f"[DEBUG] Value > 100%, might need normalization: {extracted_value}")

    if debug_mode:
        print(f"[DEBUG] Final extracted value: {extracted_value} from {extraction_source}")

    return extracted_value
