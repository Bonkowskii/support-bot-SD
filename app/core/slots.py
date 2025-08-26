import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional

import yaml

APP_ENV = os.getenv("APP_ENV", "dev")
SLOTS_PATH = Path(__file__).parent.parent / "data" / "slots.yaml"

_SLOTS_CACHE: Optional["Slots"] = None


@dataclass
class Slots:
    order: List[str]
    defs: Dict[str, Any]
    _mtime: float = 0.0  # do hot-reload w dev

    @classmethod
    def load(cls, force_reload: bool = False) -> "Slots":
        """
        Ładuje slots.yaml z prostym cache.
        W trybie dev auto-reload przy zmianie mtime.
        """
        global _SLOTS_CACHE
        p = SLOTS_PATH
        if not p.exists():
            # minimalny fallback – puste definicje
            if _SLOTS_CACHE is None:
                _SLOTS_CACHE = cls(order=[], defs={}, _mtime=0.0)
            return _SLOTS_CACHE

        mtime = p.stat().st_mtime
        need_reload = (
            force_reload
            or _SLOTS_CACHE is None
            or (APP_ENV == "dev" and (_SLOTS_CACHE._mtime != mtime))
        )

        if need_reload:
            with open(p, "r", encoding="utf-8") as f:
                y = yaml.safe_load(f) or {}
            order = y.get("order", [])
            defs = y.get("definitions", {})
            _SLOTS_CACHE = cls(order=order, defs=defs, _mtime=mtime)

        return _SLOTS_CACHE

    # === Brakujące metody używane przez FSM ===
    def prompt_for(self, slot: str) -> str:
        """
        Zwraca prompt z YAML dla danego slota,
        a gdy go brak – generuje domyślny.
        """
        d = self.defs.get(slot, {})
        prompt = d.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            return prompt
        # domyślne, czytelne prompty
        label = slot.replace("_", " ").strip().capitalize()
        return f"Please provide {label}."

    def error_for(self, slot: str) -> str:
        """
        Zwraca komunikat błędu z YAML, a gdy go brak – łączy
        prosty błąd z ponownym promptem.
        """
        d = self.defs.get(slot, {})
        err = d.get("error")
        if isinstance(err, str) and err.strip():
            return err
        # fallback: generuj błąd + prompt
        label = slot.replace("_", " ").strip().capitalize()
        return f"Invalid {label}. {self.prompt_for(slot)}"
