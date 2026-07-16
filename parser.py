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

# ============================================================
# NORMALIZIMI I LOG-EVE
# ============================================================

def parse_log_message(message: Any) -> dict[str, Any]:
    """
    E ndan log message në fusha më të qarta.

    Shembuj:

    Selecting AppData
    ->
    {
        "type": "selection",
        "action": "select",
        "target": "AppData"
    }

    ntfs: Selecting glob $MFT
    ->
    {
        "type": "glob_selection",
        "accessor": "ntfs",
        "action": "select_glob",
        "target": "$MFT"
    }
    """

    result: dict[str, Any] = {
        "type": "other",
        "action": None,
        "target": None,
        "accessor": None
    }

    if not isinstance(message, str):
        return result

    cleaned_message = message.strip()

    if not cleaned_message:
        return result

    starting_query_match = re.match(
        r"Starting query execution for (.+?)[.]?$",
        cleaned_message,
        flags=re.IGNORECASE
    )

    if starting_query_match:
        result["type"] = "query_start"
        result["action"] = "start_query"
        result["target"] = starting_query_match.group(1)
        return result

    accessor_glob_match = re.match(
        r"([^:]+):\s*Selecting glob\s+(.+)$",
        cleaned_message,
        flags=re.IGNORECASE
    )

    if accessor_glob_match:
        result["type"] = "glob_selection"
        result["action"] = "select_glob"
        result["accessor"] = accessor_glob_match.group(1).strip()
        result["target"] = accessor_glob_match.group(2).strip()
        return result

    selection_match = re.match(
        r"Selecting\s+(.+)$",
        cleaned_message,
        flags=re.IGNORECASE
    )

    if selection_match:
        result["type"] = "selection"
        result["action"] = "select"
        result["target"] = selection_match.group(1).strip()
        return result

    if "error" in cleaned_message.lower():
        result["type"] = "error"
        result["action"] = "report_error"
        return result

    if "warning" in cleaned_message.lower():
        result["type"] = "warning"
        result["action"] = "report_warning"
        return result

    return result


def normalize_logs(
    logs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Normalizon të gjitha log records.
    """

    normalized_logs: list[dict[str, Any]] = []

    for index, log in enumerate(logs, start=1):
        message = log.get("message")
        parsed_message = parse_log_message(message)

        normalized_logs.append({
            "record_id": f"log-{index}",
            "timestamp": normalize_timestamp(
                log.get("client_time")
            ),
            "level": log.get("level"),
            "message": message.strip()
            if isinstance(message, str)
            else message,
            "type": parsed_message.get("type"),
            "action": parsed_message.get("action"),
            "target": parsed_message.get("target"),
            "accessor": parsed_message.get("accessor"),
            "evidence_source": {
                "file": "log.json",
                "record_number": index
            }
        })

    return normalized_logs


# ============================================================
# NORMALIZIMI I UPLOAD-EVE
# ============================================================

def is_upload_complete(
    file_size: Any,
    uploaded_size: Any
) -> bool | None:
    """
    Kontrollon nëse file-i është upload-uar plotësisht.
    """

    if not isinstance(file_size, (int, float)):
        return None

    if not isinstance(uploaded_size, (int, float)):
        return None

    return file_size == uploaded_size


def normalize_uploads(
    uploads: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Normalizon upload records.
    """

    normalized_uploads: list[dict[str, Any]] = []

    for index, upload in enumerate(uploads, start=1):
        path = upload.get("vfs_path")
        file_size = upload.get("file_size")
        uploaded_size = upload.get("uploaded_size")

        normalized_uploads.append({
            "record_id": f"upload-{index}",
            "timestamp": normalize_timestamp(
                upload.get("Timestamp")
            ),
            "start_time": normalize_timestamp(
                upload.get("started")
            ),
            "path": path,
            "drive": extract_drive(path),
            "directory": extract_directory(path),
            "filename": extract_filename(path),
            "extension": extract_extension(path),
            "username": extract_username(path),
            "application": detect_application(path),
            "type": upload.get("Type"),
            "accessor": upload.get("_accessor"),
            "components": upload.get("_Components", []),
            "client_components": upload.get(
                "_client_components",
                []
            ),
            "file_size": file_size,
            "uploaded_size": uploaded_size,
            "upload_complete": is_upload_complete(
                file_size,
                uploaded_size
            ),
            "upload_percentage": calculate_percentage(
                uploaded_size,
                file_size
            ),
            "evidence_source": {
                "file": "uploads.json",
                "record_number": index,
                "original_path": path
            }
        })

    return normalized_uploads


# ============================================================
# NORMALIZIMI I REQUESTS.JSON
# ============================================================

def recursively_find_env_lists(
    value: Any
) -> list[list[dict[str, Any]]]:
    """
    Kërkon rekursivisht të gjitha listat që quhen 'env'.
    """

    found_env_lists: list[list[dict[str, Any]]] = []

    if isinstance(value, dict):
        for key, child_value in value.items():
            if key == "env" and isinstance(child_value, list):
                found_env_lists.append(child_value)

            found_env_lists.extend(
                recursively_find_env_lists(child_value)
            )

    elif isinstance(value, list):
        for item in value:
            found_env_lists.extend(
                recursively_find_env_lists(item)
            )

    return found_env_lists


def recursively_find_values_by_key(
    value: Any,
    target_key: str
) -> list[Any]:
    """
    Kërkon rekursivisht vlerat për një key të caktuar.
    """

    found_values: list[Any] = []

    if isinstance(value, dict):
        for key, child_value in value.items():
            if key == target_key:
                found_values.append(child_value)

            found_values.extend(
                recursively_find_values_by_key(
                    child_value,
                    target_key
                )
            )

    elif isinstance(value, list):
        for item in value:
            found_values.extend(
                recursively_find_values_by_key(
                    item,
                    target_key
                )
            )

    return found_values


def extract_request_modules(
    requests_data: Any
) -> tuple[list[str], list[str]]:
    """
    Nxjerr:
    - modulet e aktivizuara me value = Y;
    - modulet e përmendura pa value Y.

    Kjo bëhet pa u varur fort nga struktura e requests.json.
    """

    enabled_modules: set[str] = set()
    available_modules: set[str] = set()

    env_lists = recursively_find_env_lists(requests_data)

    for env_list in env_lists:
        for item in env_list:
            if not isinstance(item, dict):
                continue

            key = item.get("key")
            value = item.get("value")

            if not key:
                continue

            key_text = str(key)

            # Fushat teknike që nuk janë module evidence.
            ignored_keys = {
                "UseAutoAccessor",
                "Device",
                "VSSAnalysisAge",
                "KapeRules"
            }

            if key_text in ignored_keys:
                continue

            available_modules.add(key_text)

            if str(value).upper() == "Y":
                enabled_modules.add(key_text)

    return (
        sorted(enabled_modules),
        sorted(available_modules)
    )


def normalize_requests(requests_data: Any) -> dict[str, Any]:
    """
    Përmbledh requests.json në vend që ta ruajë të gjithë
    strukturën e madhe.
    """

    enabled_modules, available_modules = extract_request_modules(
        requests_data
    )

    session_ids = recursively_find_values_by_key(
        requests_data,
        "session_id"
    )

    request_ids = recursively_find_values_by_key(
        requests_data,
        "request_id"
    )

    artifact_values = recursively_find_values_by_key(
        requests_data,
        "artifact"
    )

    artifacts: list[str] = []

    for value in artifact_values:
        if isinstance(value, str):
            artifacts.append(value)

    return {
        "session_ids": sorted(
            set(str(item) for item in session_ids if item)
        ),
        "request_ids": sorted(
            set(str(item) for item in request_ids if item)
        ),
        "artifacts": sorted(set(artifacts)),
        "enabled_modules": enabled_modules,
        "available_modules_count": len(available_modules),
        "available_modules": available_modules
    }


# ============================================================
# KRIJIMI I DATASET-IT FINAL
# ============================================================

def build_summary(
    normalized_client: dict[str, Any],
    normalized_collection: dict[str, Any],
    normalized_logs: list[dict[str, Any]],
    normalized_uploads: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Krijon një përmbledhje të vogël të dataset-it.
    """

    complete_uploads = sum(
        1
        for upload in normalized_uploads
        if upload.get("upload_complete") is True
    )

    incomplete_uploads = sum(
        1
        for upload in normalized_uploads
        if upload.get("upload_complete") is False
    )

    zero_byte_files = sum(
        1
        for upload in normalized_uploads
        if upload.get("file_size") == 0
    )

    usernames = sorted({
        upload["username"]
        for upload in normalized_uploads
        if upload.get("username")
    })

    applications = sorted({
        upload["application"]
        for upload in normalized_uploads
        if upload.get("application")
    })

    log_levels: dict[str, int] = {}

    for log in normalized_logs:
        level = log.get("level") or "UNKNOWN"
        log_levels[level] = log_levels.get(level, 0) + 1

    return {
        "client_id": normalized_client.get("client_id"),
        "hostname": normalized_client.get("hostname"),
        "session_id": normalized_collection.get("session_id"),
        "log_records_loaded": len(normalized_logs),
        "upload_records_loaded": len(normalized_uploads),
        "complete_upload_records": complete_uploads,
        "incomplete_upload_records": incomplete_uploads,
        "zero_byte_file_records": zero_byte_files,
        "identified_usernames": usernames,
        "identified_applications": applications,
        "log_levels": log_levels
    }


def build_investigation_dataset() -> dict[str, Any]:
    """
    Hapat kryesorë:

    1. Lexon 5 file-t.
    2. I kthen në objekte Python.
    3. I normalizon.
    4. Krijon një objekt të vetëm.
    """

    print("1. Duke lexuar client_info.json...")
    client_info = load_json(CLIENT_INFO_FILE)

    print("2. Duke lexuar collection_context.json...")
    collection_context = load_json(
        COLLECTION_CONTEXT_FILE
    )

    print("3. Duke lexuar requests.json...")
    requests_data = load_json_or_jsonl(REQUESTS_FILE)

    print("4. Duke lexuar log.json si JSONL...")
    logs = load_jsonl(LOG_FILE)

    print("5. Duke lexuar uploads.json si JSONL...")
    uploads = load_jsonl(UPLOADS_FILE)

    print("6. Duke normalizuar client info...")
    normalized_client = normalize_client_info(client_info)

    print("7. Duke normalizuar collection context...")
    normalized_collection = normalize_collection_context(
        collection_context
    )

    print("8. Duke normalizuar requests...")
    normalized_requests = normalize_requests(requests_data)

    print("9. Duke normalizuar logs...")
    normalized_logs = normalize_logs(logs)

    print("10. Duke normalizuar uploads...")
    normalized_uploads = normalize_uploads(uploads)

    print("11. Duke krijuar përmbledhjen...")
    summary = build_summary(
        normalized_client,
        normalized_collection,
        normalized_logs,
        normalized_uploads
    )

    investigation = {
        "dataset_metadata": {
            "name": "AI-assisted investigation dataset",
            "created_at": datetime.now(
                timezone.utc
            ).isoformat().replace("+00:00", "Z"),
            "source_files": [
                "client_info.json",
                "collection_context.json",
                "requests.json",
                "log.json",
                "uploads.json"
            ],
            "description": (
                "Normalized forensic collection data prepared "
                "for evidence-based investigation agents."
            )
        },
        "summary": summary,
        "client": normalized_client,
        "collection": normalized_collection,
        "requests": normalized_requests,
        "logs": normalized_logs,
        "uploads": normalized_uploads
    }

    return investigation


def save_dataset(dataset: dict[str, Any]) -> None:
    """
    E ruan dataset-in final në output/normalized_dataset.json.
    """

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            dataset,
            file,
            indent=2,
            ensure_ascii=False
        )


def print_final_result(dataset: dict[str, Any]) -> None:
    """
    Shfaq rezultatet kryesore në terminal.
    """

    summary = dataset["summary"]
    client = dataset["client"]
    agent = client["incident_response_agent"]

    print("\n========================================")
    print("NORMALIZIMI U KRYE ME SUKSES")
    print("========================================")

    print(f"Client ID: {summary.get('client_id')}")
    print(f"Hostname: {summary.get('hostname')}")
    print(f"Session ID: {summary.get('session_id')}")

    print(
        "Incident response agent: "
        f"{agent.get('name')} {agent.get('version')}"
    )

    print(
        f"Logs të lexuara: "
        f"{summary.get('log_records_loaded')}"
    )

    print(
        f"Uploads të lexuara: "
        f"{summary.get('upload_records_loaded')}"
    )

    print(
        f"Uploads të plota: "
        f"{summary.get('complete_upload_records')}"
    )

    print(
        f"Uploads jo të plota: "
        f"{summary.get('incomplete_upload_records')}"
    )

    print(
        f"Users të identifikuar: "
        f"{summary.get('identified_usernames')}"
    )

    print(
        f"\nDataset-i u ruajt këtu:\n{OUTPUT_FILE}"
    )


def main() -> None:
    """
    Pika hyrëse e programit.
    """

    try:
        dataset = build_investigation_dataset()
        save_dataset(dataset)
        print_final_result(dataset)

    except FileNotFoundError as error:
        print("\nGabim: mungon një file.")
        print(error)

    except ValueError as error:
        print("\nGabim gjatë leximit të JSON-it.")
        print(error)

    except Exception as error:
        print("\nNdodhi një gabim i papritur.")
        print(f"{type(error).__name__}: {error}")


if __name__ == "__main__":
    main()