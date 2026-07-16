import json
import re
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any


# ============================================================
# FOLDERAT DHE FILE-T
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

CLIENT_INFO_FILE = DATA_DIR / "client_info.json"
COLLECTION_CONTEXT_FILE = DATA_DIR / "collection_context.json"
REQUESTS_FILE = DATA_DIR / "requests.json"
LOG_FILE = DATA_DIR / "log.json"
UPLOADS_FILE = DATA_DIR / "uploads.json"

OUTPUT_FILE = OUTPUT_DIR / "normalized_dataset.json"


# ============================================================
# LEXIMI I FILE-VE
# ============================================================

def load_json(file_path: Path) -> Any:
    """
    Lexon një file JSON normal.

    Shembull:
    {
        "client_id": "...",
        "hostname": "..."
    }
    """

    if not file_path.exists():
        raise FileNotFoundError(
            f"File nuk u gjet: {file_path}"
        )

    try:
        with file_path.open("r", encoding="utf-8-sig") as file:
            return json.load(file)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"JSON jo valid në file-in {file_path.name}: {error}"
        ) from error


def load_jsonl(file_path: Path) -> list[dict[str, Any]]:
    """
    Lexon JSON Lines / JSONL.

    Në JSONL, çdo rresht është një objekt JSON i veçantë:

    {"client_time": 123, "message": "..."}
    {"client_time": 456, "message": "..."}
    """

    if not file_path.exists():
        raise FileNotFoundError(
            f"File nuk u gjet: {file_path}"
        )

    records: list[dict[str, Any]] = []

    with file_path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            cleaned_line = line.strip()

            if not cleaned_line:
                continue

            try:
                record = json.loads(cleaned_line)

                if isinstance(record, dict):
                    records.append(record)
                else:
                    print(
                        f"Paralajmërim: rreshti {line_number} në "
                        f"{file_path.name} nuk është JSON object."
                    )

            except json.JSONDecodeError as error:
                print(
                    f"Paralajmërim: rreshti {line_number} në "
                    f"{file_path.name} nuk u lexua: {error}"
                )

    return records


def load_json_or_jsonl(file_path: Path) -> Any:
    """
    Provon fillimisht ta lexojë file-in si JSON normal.
    Nëse dështon, e lexon si JSONL.

    Kjo e bën parser-in më robust për requests.json,
    sepse struktura e tij mund të ndryshojë.
    """

    try:
        return load_json(file_path)
    except ValueError:
        return load_jsonl(file_path)


# ============================================================
# NORMALIZIMI I TIMESTAMP-EVE
# ============================================================

def normalize_timestamp(value: Any) -> str | None:
    """
    Konverton timestamp-et në format ISO UTC.

    Mbështet:
    - Unix seconds
    - milliseconds
    - microseconds
    - nanoseconds
    - string timestamps si:
      2025-10-09 18:02:20.001254233 +0000 UTC
    """

    if value is None or value == "":
        return None

    if isinstance(value, str):
        stripped_value = value.strip()

        if not stripped_value:
            return None

        # Nëse string-u përmban vetëm numër.
        try:
            numeric_value = float(stripped_value)
            return normalize_numeric_timestamp(numeric_value)
        except ValueError:
            pass

        # Normalizon formatin e Velociraptor-it:
        # 2025-10-09 18:02:20.001254233 +0000 UTC
        cleaned_value = stripped_value.replace(" UTC", "")
        cleaned_value = cleaned_value.replace(" +0000", "+00:00")

        # Python mbështet mikrosekonda me maksimum 6 shifra.
        cleaned_value = re.sub(
            r"(\.\d{6})\d+",
            r"\1",
            cleaned_value
        )

        try:
            parsed_date = datetime.fromisoformat(cleaned_value)

            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)

            return (
                parsed_date
                .astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )

        except ValueError:
            # Nëse nuk mund të konvertohet, ruaje siç është.
            return stripped_value

    if isinstance(value, (int, float)):
        return normalize_numeric_timestamp(float(value))

    return str(value)


def normalize_numeric_timestamp(value: float) -> str | None:
    """
    Detekton njësinë e Unix timestamp-it sipas madhësisë.
    """

    try:
        absolute_value = abs(value)

        # Nanoseconds
        if absolute_value >= 1_000_000_000_000_000_000:
            value = value / 1_000_000_000

        # Microseconds
        elif absolute_value >= 1_000_000_000_000_000:
            value = value / 1_000_000

        # Milliseconds
        elif absolute_value >= 1_000_000_000_000:
            value = value / 1_000

        parsed_date = datetime.fromtimestamp(
            value,
            tz=timezone.utc
        )

        return parsed_date.isoformat().replace("+00:00", "Z")

    except (ValueError, OverflowError, OSError):
        return None


# ============================================================
# NORMALIZIMI I PATH-AVE
# ============================================================

def get_windows_path_parts(path_value: Any) -> PureWindowsPath | None:
    """
    Kthen një Windows path object.
    """

    if not isinstance(path_value, str):
        return None

    cleaned_path = path_value.strip()

    if not cleaned_path:
        return None

    return PureWindowsPath(cleaned_path)


def extract_username(path_value: Any) -> str | None:
    """
    Nxjerr username nga path-i:

    C:\\Users\\dallen\\AppData\\...
    rezulton:
    dallen
    """

    path = get_windows_path_parts(path_value)

    if path is None:
        return None

    parts = list(path.parts)

    for index, part in enumerate(parts):
        if part.lower() == "users" and index + 1 < len(parts):
            return parts[index + 1]

    return None


def extract_filename(path_value: Any) -> str | None:
    """
    Nxjerr emrin e file-it.
    """

    path = get_windows_path_parts(path_value)

    if path is None:
        return None

    return path.name or None


def extract_extension(path_value: Any) -> str:
    """
    Nxjerr extension-in e file-it.
    Nëse nuk ka extension, kthen string bosh.
    """

    path = get_windows_path_parts(path_value)

    if path is None:
        return ""

    return path.suffix.lower()


def extract_directory(path_value: Any) -> str | None:
    """
    Nxjerr directory-n ku ndodhet file-i.
    """

    path = get_windows_path_parts(path_value)

    if path is None:
        return None

    parent = str(path.parent)

    if parent == ".":
        return None

    return parent


def extract_drive(path_value: Any) -> str | None:
    """
    Nxjerr drive-in, për shembull C:.
    """

    path = get_windows_path_parts(path_value)

    if path is None:
        return None

    return path.drive or None


def detect_application(path_value: Any) -> str | None:
    """
    Detekton aplikacionin nga path-i.

    Kjo është vetëm klasifikim sipas path-it,
    jo dëshmi që aplikacioni është përdorur.
    """

    if not isinstance(path_value, str):
        return None

    lower_path = path_value.lower()

    application_patterns = {
        "Microsoft Edge": [
            "\\microsoft\\edge\\",
            "\\edge\\user data\\"
        ],
        "Google Chrome": [
            "\\google\\chrome\\"
        ],
        "Mozilla Firefox": [
            "\\mozilla\\firefox\\"
        ],
        "OneDrive": [
            "\\onedrive\\"
        ],
        "AnyDesk": [
            "\\anydesk\\"
        ],
        "Microsoft Teams": [
            "\\microsoft\\teams\\",
            "\\msteams\\"
        ],
        "PowerShell": [
            "\\powershell\\"
        ],
        "Visual Studio Code": [
            "\\microsoft\\vscode\\",
            "\\visual studio code\\"
        ],
        "Windows WebCache": [
            "\\microsoft\\windows\\webcache\\"
        ],
        "Internet Explorer": [
            "\\internet explorer\\"
        ]
    }

    for application, patterns in application_patterns.items():
        for pattern in patterns:
            if pattern in lower_path:
                return application

    return None


# ============================================================
# NORMALIZIMI I CLIENT INFO
# ============================================================

def normalize_client_info(
    client_info: dict[str, Any]
) -> dict[str, Any]:
    """
    Pastron dhe normalizon client_info.json.
    """

    ip_address = client_info.get("ip_address")
    ip = None
    port = None

    if isinstance(ip_address, str):
        # Shembull: 10.101.2.9:51421
        if ":" in ip_address:
            ip, port_text = ip_address.rsplit(":", 1)

            try:
                port = int(port_text)
            except ValueError:
                port = None
        else:
            ip = ip_address

    return {
        "client_id": client_info.get("client_id"),
        "hostname": client_info.get("hostname"),
        "fqdn": client_info.get("fqdn"),
        "system": client_info.get("system"),
        "operating_system": client_info.get("release"),
        "architecture": client_info.get("architecture"),
        "ip_address": ip,
        "port": port,
        "incident_response_agent": {
            "name": client_info.get("client_name"),
            "version": client_info.get("client_version")
        },
        "first_seen_at": normalize_timestamp(
            client_info.get("first_seen_at")
        ),
        "build_time": normalize_timestamp(
            client_info.get("build_time")
        ),
        "labels": client_info.get("labels", []),
        "mac_addresses": client_info.get("mac_addresses", []),
        "last_interrogate_flow_id": client_info.get(
            "last_interrogate_flow_id"
        ),
        "last_interrogate_artifact_name": client_info.get(
            "last_interrogate_artifact_name"
        ),
        "last_hunt_timestamp": normalize_timestamp(
            client_info.get("last_hunt_timestamp")
        ),
        "last_event_table_version": client_info.get(
            "last_event_table_version"
        ),
        "labels_timestamp": normalize_timestamp(
            client_info.get("labels_timestamp")
        )
    }


# ============================================================
# NORMALIZIMI I COLLECTION CONTEXT
# ============================================================

def calculate_percentage(
    numerator: Any,
    denominator: Any
) -> float | None:
    """
    Llogarit përqindjen në mënyrë të sigurt.
    """

    if not isinstance(numerator, (int, float)):
        return None

    if not isinstance(denominator, (int, float)):
        return None

    if denominator == 0:
        return None

    return round((numerator / denominator) * 100, 2)


def get_enabled_collection_parameters(
    collection_context: dict[str, Any]
) -> list[str]:
    """
    Nxjerr parametrat me value = Y nga collection_context.
    """

    enabled_parameters: list[str] = []

    request = collection_context.get("request", {})
    specs = request.get("specs", [])

    if not isinstance(specs, list):
        return enabled_parameters

    for spec in specs:
        if not isinstance(spec, dict):
            continue

        parameters = spec.get("parameters", {})
        environment = parameters.get("env", [])

        if not isinstance(environment, list):
            continue

        for item in environment:
            if not isinstance(item, dict):
                continue

            key = item.get("key")
            value = item.get("value")

            if key and str(value).upper() == "Y":
                enabled_parameters.append(str(key))

    return sorted(set(enabled_parameters))


def normalize_collection_context(
    collection_context: dict[str, Any]
) -> dict[str, Any]:
    """
    Normalizon collection_context.json.
    """

    request = collection_context.get("request", {})

    uploaded_bytes = collection_context.get(
        "total_uploaded_bytes"
    )

    expected_bytes = collection_context.get(
        "total_expected_uploaded_bytes"
    )

    return {
        "client_id": collection_context.get("client_id"),
        "session_id": collection_context.get("session_id"),
        "creator": request.get("creator"),
        "artifacts": request.get("artifacts", []),
        "enabled_parameters": get_enabled_collection_parameters(
            collection_context
        ),
        "timeout_seconds": request.get("timeout"),
        "max_upload_bytes": request.get("max_upload_bytes"),
        "created_at": normalize_timestamp(
            collection_context.get("create_time")
        ),
        "start_time": normalize_timestamp(
            collection_context.get("start_time")
        ),
        "last_active_at": normalize_timestamp(
            collection_context.get("active_time")
        ),
        "execution_duration_raw": collection_context.get(
            "execution_duration"
        ),
        "state": collection_context.get("state"),
        "statistics": {
            "total_uploaded_files": collection_context.get(
                "total_uploaded_files"
            ),
            "total_expected_uploaded_bytes": expected_bytes,
            "total_uploaded_bytes": uploaded_bytes,
            "upload_completion_percentage": calculate_percentage(
                uploaded_bytes,
                expected_bytes
            ),
            "total_collected_rows": collection_context.get(
                "total_collected_rows"
            ),
            "total_logs": collection_context.get("total_logs"),
            "total_requests": collection_context.get(
                "total_requests"
            )
        },
        "artifacts_with_results": collection_context.get(
            "artifacts_with_results",
            []
        ),
        "query_stats": collection_context.get(
            "query_stats",
            []
        )
    }
