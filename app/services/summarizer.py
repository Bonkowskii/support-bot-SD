from typing import Dict, Any, List

def _line(label: str, value: Any) -> str:
    if value in (None, "", [], "N/A"):
        return ""
    if isinstance(value, list):
        v = ", ".join(str(x) for x in value)
    else:
        v = str(value)
    return f"- {label}: {v}\n"

def _format_device_row(i: int, d: Dict[str, Any]) -> str:
    name = d.get("name", "Device")
    os_v = d.get("os") or ", ".join(d.get("versions", []) or [])
    notes = d.get("notes")
    row = f"  {i}. {name}"
    if os_v:
        row += f" — {os_v}"
    if notes:
        row += f" ({notes})"
    return row + "\n"

def render_summary(data: Dict[str, Any], recommendation: Dict[str, Any]) -> str:
    out: List[str] = []
    out.append("Here’s a quick summary of your request:\n")
    out.append(_line("Platform", data.get("platform")))
    out.append(_line("Model", data.get("device_model")))
    out.append(_line("Quantity", data.get("quantity")))
    out.append(_line("Dates", data.get("rental_dates")))
    out.append(_line("Location", data.get("location")))
    if data.get("location") == "Other":
        out.append(_line("VPN OK", data.get("vpn_ok")))
    # Jeśli user nie wymaga OS, nie zaśmiecaj pustym polem
    need_os = (data.get("need_os_version") or "").lower() == "yes"
    if need_os:
        out.append(_line("OS", data.get("os_version")))
    out.append(_line("Accessories", data.get("accessories")))
    out.append(_line("Email", data.get("contact_email")))
    out.append("\n")

    status = (recommendation or {}).get("status")
    matches = (recommendation or {}).get("matches", [])
    alternatives = (recommendation or {}).get("alternatives", [])
    reason = (recommendation or {}).get("reason", "")

    if status == "match" and matches:
        out.append("Available now:\n")
        for i, d in enumerate(matches, 1):
            out.append(_format_device_row(i, d))
        out.append("If one of these fits your needs, we’ll reserve it for you.\n")
    else:
        if reason:
            out.append(f"{reason}\n")
        if alternatives:
            out.append("Currently available alternatives:\n")
            for i, d in enumerate(alternatives, 1):
                out.append(_format_device_row(i, d))
        out.append("We can forward your request to our team to source the exact device/version.\n")
        out.append("Would you like us to proceed with that?\n")

    return "".join(out)
