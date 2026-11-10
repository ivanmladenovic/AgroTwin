from __future__ import annotations

import hashlib
import json
import math
import re
from uuid import uuid4

from app.ai.base import ChatMessage, ChatResult, ImageAnalysisResult, ToolCall, ToolSpec
from app.ai.prompts import ANALYSIS_DISCLAIMER
from app.core.config import Settings
from app.core.exceptions import AppError


class LocalAIProvider:
    """Deterministic provider for development and tests.

    Embeddings are hashed token vectors so retrieval still works without an
    API key. Chat uses retrieved context plus tool results that the agronomist
    service already gathered — it does not invent orchard records.
    """

    name = "local"

    def __init__(self, settings: Settings) -> None:
        self.chat_model = "local-agronomist"
        self.embedding_model = "local-hash"
        self.vision_model = "local-vision"
        self.dim = settings.ai_embedding_dim

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSpec] | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
        model: str | None = None,
    ) -> ChatResult:
        del temperature, model
        latest = _latest_user_text(messages)
        if json_mode:
            system = " ".join(
                str(message.content)
                for message in messages
                if message.role == "system" and isinstance(message.content, str)
            )
            if "PARCEL_INTELLIGENCE" in system or "PARCEL_INTELLIGENCE_REQUEST" in latest:
                return ChatResult(content=_parcel_intelligence_json(latest), model=self.chat_model)
            return ChatResult(content=_analysis_json_from_prompt(latest), model=self.chat_model)
        if tools:
            call = _maybe_tool_call(latest, tools)
            if call is not None and not _tool_results_present(messages):
                return ChatResult(content="", tool_calls=[call], model=self.chat_model)
        return ChatResult(content=_compose_answer(messages, latest), model=self.chat_model)

    def analyze_image(
        self,
        image: bytes,
        mime_type: str,
        prompt: str,
        *,
        json_mode: bool = True,
    ) -> ImageAnalysisResult:
        del image, mime_type, json_mode
        payload = json.loads(_analysis_json_from_prompt(prompt))
        return ImageAnalysisResult(
            likely_issue=payload["likely_issue"],
            confidence=float(payload["confidence"]),
            observed_symptoms=list(payload["observed_symptoms"]),
            possible_alternatives=list(payload["possible_alternatives"]),
            recommended_inspection=payload["recommended_inspection"],
            recommended_next_step=payload["recommended_next_step"],
            observed_facts=payload["observed_facts"],
            uncertainty_notes=payload["uncertainty_notes"],
            disclaimer=payload["disclaimer"],
            model=self.vision_model,
            raw=payload,
        )

    def generate_embedding(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dim
            vec[idx] += 1.0
            idx2 = int.from_bytes(digest[4:8], "big") % self.dim
            vec[idx2] += 0.4
        return _normalize(vec)

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [self.generate_embedding(text) for text in texts]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9čćšžđ]+", text.lower())


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vec)) or 1.0
    return [value / norm for value in vec]


def _latest_user_text(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role != "user":
            continue
        if isinstance(message.content, str):
            return message.content
        if not message.content:
            continue
        parts = [str(item.get("text", "")) for item in message.content if isinstance(item, dict)]
        return "\n".join(part for part in parts if part)
    return ""


def _tool_results_present(messages: list[ChatMessage]) -> bool:
    return any(message.role == "tool" for message in messages)


def _maybe_tool_call(question: str, tools: list[ToolSpec]) -> ToolCall | None:
    names = {item.name for item in tools}
    lower = question.lower()
    row_match = re.search(r"(?:row|red)\s+(\d+)", lower)
    tree_match = re.search(r"(r\d+-t\d+)", lower, re.I)

    def make(name: str, arguments: dict) -> ToolCall | None:
        if name not in names:
            return None
        return ToolCall(id=f"local-{uuid4().hex[:8]}", name=name, arguments=arguments)

    if any(word in lower for word in ("cost", "spend", "euro", "€", "trošak", "trosk", "troškov", "cena")):
        return make("get_cost_summary", {})
    if tree_match and any(
        word in lower for word in ("history", "tree", "this tree", "journal", "stablo", "dnevnik", "istorij")
    ):
        return make("get_tree_history", {"tree_public_id": tree_match.group(1).upper()})
    if any(
        word in lower
        for word in (
            "unresolved",
            "open case",
            "disease",
            "issue",
            "problem",
            "weevil",
            "blight",
            "nerešen",
            "neresen",
            "bolest",
            "štetoč",
            "stetoc",
            "žižak",
            "zizak",
            "rakovin",
            "zdravl",
        )
    ):
        return make("get_recent_disease_cases", {"limit": 8})
    if any(
        word in lower
        for word in (
            "spray",
            "activit",
            "irrigat",
            "fertil",
            "performed",
            "journal",
            "prskanj",
            "prskan",
            "aktivnost",
            "navodnjav",
            "đubren",
            "djubren",
            "rezidb",
        )
    ):
        arguments: dict[str, object] = {"limit": 10}
        if row_match:
            arguments["row_number"] = int(row_match.group(1))
        if any(word in lower for word in ("spray", "prskanj", "prskan")):
            arguments["activity_hint"] = "spray"
        return make("get_recent_activities", arguments)
    if any(
        word in lower
        for word in ("parcel", "orchard", "north slope", "how many trees", "parcela", "voćnjak", "vocnjak", "severna")
    ):
        return make("get_parcel_summary", {})
    return None


def _compose_answer(messages: list[ChatMessage], question: str) -> str:
    tool_notes = [message.content for message in messages if message.role == "tool"]
    knowledge = _knowledge_from_system(messages)
    lines = [
        "Ovo je beleška o upravljanju voćnjakom, a ne potvrđena agronomska dijagnoza.",
        "",
    ]
    if tool_notes:
        lines.append("Iz evidencije AgroTwin:")
        for note in tool_notes:
            lines.append(_summarize_tool_payload(note))
        lines.append("")
    if knowledge:
        lines.append("Iz baze znanja:")
        for item in knowledge[:4]:
            page = f", strana {item['page']}" if item.get("page") else ""
            lines.append(f"- {item['title']}{page}: {item['excerpt']}")
        lines.append("")
    elif any(word in question.lower() for word in ("rain", "check", "kiš", "kis", "prover")):
        lines.append("Baza znanja nije vratila dovoljno dokaza za ovo pitanje.")
        lines.append("")
    lines.append(
        "Ako je potrebno sredstvo za zaštitu bilja, koristite samo registrovane etikete za ovaj voćnjak. Neću izmišljati nazive proizvoda, doze ni norme."
    )
    return "\n".join(lines).strip()


def _knowledge_from_system(messages: list[ChatMessage]) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for message in messages:
        if message.role != "system" or not isinstance(message.content, str):
            continue
        if "Knowledge excerpts:" not in message.content:
            continue
        block = message.content.split("Knowledge excerpts:", 1)[1]
        current: dict[str, str] = {}
        for line in block.splitlines():
            if line.startswith("SOURCE:"):
                if current:
                    sources.append(current)
                current = {"title": line.replace("SOURCE:", "").strip(), "excerpt": ""}
            elif line.startswith("PAGE:"):
                current["page"] = line.replace("PAGE:", "").strip()
            elif line.startswith("TEXT:"):
                current["excerpt"] = line.replace("TEXT:", "").strip()[:280]
        if current:
            sources.append(current)
    return sources


def _summarize_tool_payload(content: str) -> str:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return f"- {content[:400]}"
    if payload.get("error"):
        return f"- {payload['error']}"
    if "activities" in payload:
        rows = payload["activities"][:5]
        if not rows:
            return "- Nisu pronađene odgovarajuće aktivnosti."
        parts = []
        for item in rows:
            scope = item.get("tree_public_id") or (
                f"red {item['row_number']}" if item.get("row_number") else item.get("parcel_name")
            )
            parts.append(f"{item.get('performed_on')} {item.get('title')} ({scope})")
        return "- " + "; ".join(parts)
    if "cases" in payload:
        rows = payload["cases"][:6]
        if not rows:
            return "- Nema zabeleženih otvorenih opažanja."
        return "- " + "; ".join(
            f"{item.get('tree_public_id') or item.get('parcel_name')}: {item.get('title')} [{item.get('status')}/{item.get('severity')}]"
            for item in rows
        )
    if "total_costs" in payload:
        return f"- Evidentirani troškovi {payload['total_costs']} {payload.get('currency', 'EUR')} (godina {payload.get('current_year_costs')})."
    if "public_id" in payload:
        return (
            f"- Stablo {payload.get('public_id')} zdravlje {payload.get('health_status')}, "
            f"{payload.get('open_case_count', 0)} otvorenih opažanja."
        )
    if "name" in payload and "tree_count" in payload:
        return f"- Parcela {payload['name']}: {payload['tree_count']} stabala, {payload.get('issue_trees', 0)} trenutno označeno kao problem."
    return f"- {json.dumps(payload)[:400]}"


def _analysis_focus_text(prompt: str) -> str:
    """Use the case and tree context, not knowledge-base excerpts.

    Manuals mention many pests and diseases. Matching those keywords would
    mis-label an unrelated observation.
    """
    if "Context from AgroTwin:" in prompt:
        body = prompt.split("Context from AgroTwin:", 1)[1]
        return body.split("Relevant knowledge excerpts:", 1)[0]
    return prompt


def _parcel_intelligence_json(prompt: str) -> str:
    lower = prompt.lower()
    zone_keys, observation_date, kinds = _extract_zone_anomaly_hints(prompt)
    if zone_keys or (
        "ndvi" in lower and ("decline" in lower or "anomaly" in lower or "anomal" in lower or "opad")
    ):
        facts = [
            "Na satelitskom snimku deo parcele izgleda manje zeleno od ostatka.",
        ]
        if observation_date:
            facts.append(f"Snimak od {observation_date}.")
        tree_ids = _extract_tree_ids_from_prompt(prompt)
        if tree_ids:
            shown = ", ".join(tree_ids[:6])
            extra = len(tree_ids) - min(len(tree_ids), 6)
            facts.append(f"Stabla na koja treba obratiti pažnju: {shown}" + (f" (+{extra})" if extra > 0 else "."))
        elif zone_keys:
            facts.append(f"Uočeno na {min(len(zone_keys), 6)} mesta na parceli.")
        if kinds:
            if "persistent_low" in kinds:
                facts.append("Ista mesta su slabija na više snimaka zaredom.")
            elif "sudden_decline" in kinds:
                facts.append("Promena je nagla u odnosu na prethodni snimak.")
            else:
                facts.append("Ta mesta su slabija od proseka parcele.")
        title = (
            f"Slabije biljke kod {tree_ids[0]}" + (f" i još {len(tree_ids) - 1}" if len(tree_ids) > 1 else "")
            if tree_ids
            else "Slabije biljke na delu parcele"
        )
        payload = {
            "status": "WARNING",
            "title": title,
            "summary": (
                "Na snimku se vidi da su neka mesta manje zelena od ostatka zasada. "
                "Uzrok nije poznat — obiđite navedena stabla na terenu."
                if tree_ids
                else (
                    "Na snimku se vidi da su neka mesta manje zelena od ostatka zasada. "
                    "Uzrok nije poznat — obiđite ta mesta na terenu."
                )
            ),
            "observed_facts": facts,
            "possible_causes": [
                "moguće da fali vode",
                "moguće da fali hraniva u tlu",
                "moguće oštećenje ili štetočine (samo pretpostavka)",
            ],
            "recommended_actions": [
                "Obiđite navedena stabla i uporedite ih sa zelenijim delovima"
                if tree_ids
                else "Obiđite ta mesta i uporedite biljke sa zelenijim delovima",
                "Proverite zalivanje i da li ima suvih ili oštećenih biljaka",
                "Ako izgleda loše, pitajte agronoma pre bilo kakvog tretmana",
            ],
            "confidence": 0.55,
            "should_notify": True,
            "issue_key": "ndvi_zone_anomaly",
            "zone_keys": zone_keys[:8],
            "tree_public_ids": tree_ids[:20],
            "affected_indices": ["ndvi"],
            "observation_date": observation_date,
            "data_quality_notes": [
                "Ovo je upozorenje sa snimka, ne potvrđena dijagnoza.",
            ],
        }
    else:
        payload = {
            "status": "INFO",
            "title": "Parcela izgleda uobičajeno",
            "summary": "Na osnovu dostupnih podataka nema jasnog razloga za zabrinutost.",
            "observed_facts": ["Dostupni su podaci za praćenje parcele."],
            "possible_causes": [],
            "recommended_actions": ["Nastavite redovan monitoring"],
            "confidence": 0.4,
            "should_notify": False,
            "issue_key": "routine_ok",
            "zone_keys": [],
            "affected_indices": [],
            "observation_date": None,
            "data_quality_notes": [],
        }
    return json.dumps(payload)


def _extract_zone_anomaly_hints(prompt: str) -> tuple[list[str], str | None, list[str]]:
    """Best-effort parse of satellite_zone_anomalies from the intelligence context JSON."""
    zone_keys: list[str] = []
    kinds: list[str] = []
    observation_date: str | None = None
    try:
        marker = '"satellite_zone_anomalies"'
        idx = prompt.find(marker)
        if idx < 0:
            return [], None, []
        # Find acquisition_date near satellite_latest if present.
        date_match = re.search(r'"acquisition_date"\s*:\s*"([^"]+)"', prompt)
        if date_match:
            observation_date = date_match.group(1)
        for match in re.finditer(r'"zone_key"\s*:\s*"([^"]+)"', prompt[idx : idx + 8000]):
            key = match.group(1)
            if key not in zone_keys:
                zone_keys.append(key)
        for match in re.finditer(r'"kind"\s*:\s*"([^"]+)"', prompt[idx : idx + 8000]):
            kind = match.group(1)
            if kind not in kinds:
                kinds.append(kind)
    except Exception:  # noqa: BLE001
        return zone_keys, observation_date, kinds
    return zone_keys, observation_date, kinds


def _extract_tree_ids_from_prompt(prompt: str) -> list[str]:
    """Pull tree_public_ids from satellite_zone_anomalies context when present."""
    ids: list[str] = []
    try:
        marker = '"satellite_zone_anomalies"'
        idx = prompt.find(marker)
        if idx < 0:
            return []
        chunk = prompt[idx : idx + 12000]
        for match in re.finditer(r'"tree_public_ids"\s*:\s*\[(.*?)\]', chunk, re.S):
            for item in re.findall(r'"([^"]+)"', match.group(1)):
                value = item.strip().upper()
                if value and value not in ids:
                    ids.append(value)
        if not ids:
            for match in re.finditer(r'\b(R\d{2}-T\d{4})\b', chunk, re.I):
                value = match.group(1).upper()
                if value not in ids:
                    ids.append(value)
    except Exception:  # noqa: BLE001
        return ids
    return ids[:40]


def _analysis_json_from_prompt(prompt: str) -> str:
    lower = _analysis_focus_text(prompt).lower()
    if any(word in lower for word in ("canker", "blight", "twig", "rakovin", "rak na", "grančic", "grancic")):
        likely = "Moguća bolest koja pravi rakove na izdancima (samo opažanje)"
        symptoms = ["Lezije na grančicama ili proređivanje krošnje koje je opisao proizvođač"]
        alternatives = ["Zimsko oštećenje", "Disbalans hraniva", "Mehaničko oštećenje"]
        inspection = "Prođite istočnu i unutrašnju krošnju zbog širenja rakova i obeležite suve izdanke za stručni savet."
    elif any(word in lower for word in ("weevil", "nut hole", "exit hole", "žižak", "zizak", "rupa", "rupe u plod")):
        likely = "Moguće ishranjivanje štetočine na plodovima (samo opažanje)"
        symptoms = ["Rupe u razvijajućim plodovima navedene u terenskoj belešci"]
        alternatives = ["Opadanje plodova iz drugih razloga", "Oštećenje od ptica ili mehanizacije"]
        inspection = "Uporedite oštećene plodove na nekoliko susednih stabala i potražite larve ili odrasle žiške na zemlji."
    elif any(word in lower for word in ("pale", "yellow", "nutrient", "bled", "žut", "zut", "hraniv")):
        likely = "Moguće žućenje lista zbog hraniva ili vode (samo opažanje)"
        symptoms = ["Bledo ili međužilno žućenje opisano u belešci"]
        alternatives = ["Zamočvarenje posle kiše", "Zanošenje herbicida", "Uobičajena sezonska boja"]
        inspection = "Uporedite mlado i staro lišće i proverite vlažnost zemljišta na liniji kapanja."
    else:
        likely = "Neizvesno — slika i beleške nisu dovoljne za konkretan problem"
        symptoms = ["Samo fotografija i opis koje je dostavio proizvođač"]
        alternatives = ["Bolest", "Štetočina", "Abiotski stres", "Fizičko oštećenje"]
        inspection = "Zabeležite još jednu datiranu fotografiju i uporedite sa susednim stablima pre tretmana."
    payload = {
        "likely_issue": likely,
        "confidence": 0.42 if "neizvesno" not in likely.lower() and "uncertain" not in likely.lower() else 0.22,
        "observed_symptoms": symptoms,
        "possible_alternatives": alternatives,
        "recommended_inspection": inspection,
        "recommended_next_step": "Zadržite ovo kao opažanje. Pitajte savetnika pre bilo kog sredstva za zaštitu bilja.",
        "observed_facts": "Analiza koristi metapodatke otpremljene fotografije, beleške proizvođača i evidenciju voćnjaka. Ne može da potvrdi šta je na slici.",
        "uncertainty_notes": "Pouzdanost je niska bez laboratorijske potvrde ili pregleda na terenu.",
        "disclaimer": ANALYSIS_DISCLAIMER,
    }
    return json.dumps(payload)


def require_configured() -> None:
    raise AppError("Lokalni provajder je uvek dostupan", status_code=500)
