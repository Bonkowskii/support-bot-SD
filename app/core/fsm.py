import os, time
from dataclasses import dataclass, field
from typing import Dict, Any
import regex as re

from .slots import Slots
from .parsers import parse_message, try_coerce_quantity_loose
from .validators import validate_slot
from app.services.recommender import suggest_devices
from app.services.summarizer import render_summary

# Konfiguracje
try:
    from . import config
    MAX_ERRORS = getattr(config, "MAX_ERRORS_PER_SLOT", 2)
except Exception:
    MAX_ERRORS = 2

MAX_TURNS = int(os.getenv("MAX_TURNS_PER_SESSION","40"))
SESSION_TTL_MIN = int(os.getenv("SESSION_TTL_MIN","60"))

YES_RE = re.compile(r"^\s*(yes|y|ok|sure|true)\s*$", re.I)
NO_RE  = re.compile(r"^\s*(no|n|false|nope)\s*$", re.I)
UNK_RE = re.compile(r"\b(idk|i\s*don'?t\s*know|not\s*sure|any|whatever)\b", re.I)
BARE_INT_RE = re.compile(r"^\s*(\d{1,2})\s*$")
RESET_RE = re.compile(r"^\s*(reset|restart|new|start over)\s*$", re.I)

NOW_EPOCH = lambda: int(time.time())

@dataclass
class SessionState:
    intent: str = "device_rental"
    data: Dict[str, Any] = field(default_factory=dict)
    current_slot: str = "platform"
    last_prompted: str = "platform"
    errors_in_row: int = 0
    done: bool = False
    confirmed: bool = False
    turns: int = 0
    updated_at: int = field(default_factory=NOW_EPOCH)

class BotEngine:
    def __init__(self):
        self.sessions: Dict[str, SessionState] = {}
        self.slots = Slots.load()
        self.supported_locations = [v for v in self.slots.defs["location"]["values"] if v != "Other"]

    def _expired(self, s: SessionState) -> bool:
        return (NOW_EPOCH() - s.updated_at) > (SESSION_TTL_MIN * 60)

    def _get(self, session_id: str) -> SessionState:
        s = self.sessions.get(session_id)
        if s is None or self._expired(s) or s.turns > MAX_TURNS:
            order = self.slots.order
            s = SessionState(current_slot=order[0], last_prompted=order[0])
            self.sessions[session_id] = s
        return s

    def _bump(self, s: SessionState):
        s.turns += 1
        s.updated_at = NOW_EPOCH()

    def handle_message(self, session_id: str, text: str) -> str:
        s = self._get(session_id)
        raw = (text or "").strip()

        # reset/ restart
        if RESET_RE.match(raw):
            order = self.slots.order
            self.sessions[session_id] = SessionState(current_slot=order[0], last_prompted=order[0])
            return "Session reset. Which platform do you need: Android or iOS?"

        # faza confirm
        if s.current_slot == "confirm":
            self._bump(s)
            answer = raw.lower()
            if answer in ("yes","y","ok","confirm"):
                s.confirmed = s.done = True
                return "Great, thanks! We will contact you shortly."
            if answer in ("no","n"):
                s.done = True
                return "No problem. You can restart anytime."
            return "Please answer Yes/No to confirm."

        # pasywna ekstrakcja
        extracted = parse_message(raw, self.slots)
        for k, v in extracted.items():
            if v is None: continue
            # nie nadpisuj poprawnych (poza accessories, które łączymy)
            if k in s.data and validate_slot(k, s.data[k], self.slots):
                if k == "accessories" and isinstance(v, list):
                    prev = s.data.get(k) or []
                    s.data[k] = sorted(list(set(prev + v)))
                continue
            s.data[k] = v

        # ilość – tryb luźny, gdy pytamy o quantity
        if s.current_slot == "quantity":
            if ("quantity" not in s.data) or (not validate_slot("quantity", s.data.get("quantity"), self.slots)):
                q = try_coerce_quantity_loose(raw)
                if q is not None:
                    s.data["quantity"] = q

        # pętla slotów
        for slot in self.slots.order:
            defs = self.slots.defs.get(slot, {})
            required = bool(defs.get("required", False))
            present = slot in s.data
            valid = validate_slot(slot, s.data.get(slot), self.slots) if present else False

            # vpn_ok — tylko gdy location == Other
            if slot == "vpn_ok":
                loc = str(s.data.get("location","")).strip()
                if loc and loc != "Other":
                    s.data["vpn_ok"] = "N/A"
                    continue
                required = True
                if s.last_prompted == "vpn_ok" and not present:
                    if YES_RE.match(raw): s.data["vpn_ok"]="Yes"; present=True; valid=True
                    elif NO_RE.match(raw): s.data["vpn_ok"]="No"; present=True; valid=True

            # need_os_version — zawsze pytamy (gate)
            if slot == "need_os_version":
                required = True
                if s.last_prompted == "need_os_version" and not present:
                    if YES_RE.match(raw): s.data["need_os_version"]="Yes"; present=True; valid=True
                    elif NO_RE.match(raw): s.data["need_os_version"]="No";  present=True; valid=True

            # os_version — tylko gdy gate Yes
            if slot == "os_version":
                gate = str(s.data.get("need_os_version","")).lower()
                if gate == "yes":
                    required = True
                    if s.last_prompted == "os_version":
                        # idk/any/no => rezygnujemy
                        if UNK_RE.search(raw) or NO_RE.match(raw):
                            s.data["need_os_version"] = "No"
                            s.data["os_version"] = ""
                            present = True; valid = True; required = False
                        else:
                            # sama liczba => dołącz platformę
                            m = BARE_INT_RE.match(raw)
                            if m:
                                plat = (s.data.get("platform") or "").strip()
                                if plat:
                                    s.data["os_version"] = f"{plat} {m.group(1)}"
                                    present = True
                                    valid = validate_slot("os_version", s.data["os_version"], self.slots)
                else:
                    s.data["os_version"] = ""
                    continue

            # czy pytać?
            need_ask = False
            if required and (not present or not valid):
                need_ask = True
            elif not required and present and not valid:
                need_ask = True

            if need_ask:
                s.current_slot = slot
                s.last_prompted = slot
                self._bump(s)

                # dynamiczne prompty i obsługa modelu
                if slot == "device_model" and "device_model" in extracted and not validate_slot("device_model", s.data.get("device_model"), self.slots):
                    s.errors_in_row += 1
                    platform = (s.data.get("platform") or "").lower()
                    if s.errors_in_row == 1:
                        if platform == "android":
                            return ("If you're not sure, here are popular Android models:\n"
                                    "- Samsung Galaxy S23\n- Google Pixel 7\n- OnePlus 11\n"
                                    "You can also say 'I don't know' and I'll proceed.")
                        elif platform == "ios":
                            return ("If you're not sure, here are popular iPhone models:\n"
                                    "- iPhone 13\n- iPhone 14\n- iPhone 15\n"
                                    "You can also say 'I don't know' and I'll proceed.")
                        else:
                            return ("Popular models include:\n"
                                    "- iPhone 14/15\n- Galaxy S23\n- Pixel 7\n"
                                    "You can say 'I don't know' and I'll proceed.")
                    else:
                        s.data["device_model"] = "TBD"
                        s.errors_in_row = 0
                        continue

                if slot == "vpn_ok":
                    return "Your location isn't in our supported regions. Would a VPN endpoint in Poland/Germany/Ghana be acceptable? (Yes/No)"
                if slot == "need_os_version":
                    return "Do you require a specific OS version? (Yes/No)"
                if slot == "os_version":
                    plat = (s.data.get("platform") or "").lower()
                    return "Which OS version do you need? (e.g., iOS 17)" if plat=="ios" else "Which OS version do you need? (e.g., Android 14)"
                return self.slots.prompt_for(slot)

        # zebrane wszystkie — summary + rekomendacje
        s.current_slot = "confirm"
        self._bump(s)
        rec = suggest_devices(s.data)
        pretty = render_summary(s.data, rec)
        return pretty + "\nPlease confirm (Yes/No)."
