import arcpy
import ctypes
import datetime
import json
import os
import sys
import time

# ============================================================
# Global Settings (EDIT THESE)
# ============================================================
SOURCE_GDB = r"E:\2026_vtpk\Geodatabase\vTPK_Data_2026.gdb"
TARGET_GDB = r"I:\2026_Basemap_Data_forVTPKandPDFs\Data\vTPK_Data_2026.gdb"
LOG_FILE = r"I:\2026_Basemap_Data_forVTPKandPDFs\Data\copy_log.txt"
STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "copy_status.json")

RETRY_ATTEMPTS = 3
RETRY_DELAY = 3          # seconds between retries

RUN_CLEANUP = False      # Enable/disable post-copy cleanup True or False


# ============================================================
# Logging Utility
# ============================================================
def get_run_log_file_path(base_path):
    log_dir, log_name = os.path.split(base_path)
    log_stem, log_ext = os.path.splitext(log_name)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return os.path.join(log_dir, f"{log_stem}_{timestamp}{log_ext}")


ACTIVE_LOG_FILE = get_run_log_file_path(LOG_FILE)


def ensure_parent_dir(file_path):
    parent_dir = os.path.dirname(file_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)


def write_log_line(message, mode="a", attempts=3, delay=1):
    ensure_parent_dir(ACTIVE_LOG_FILE)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} - {message}\n"

    for attempt in range(1, attempts + 1):
        try:
            with open(ACTIVE_LOG_FILE, mode, encoding="utf-8") as log_handle:
                log_handle.write(line)
            return True
        except PermissionError:
            if attempt < attempts:
                time.sleep(delay)

    return False


def log(message):
    print(message)
    if not write_log_line(message):
        print(f"WARNING: Could not write to log file: {ACTIVE_LOG_FILE}", file=sys.stderr)


# ============================================================
# Status Manifest Utility
# ============================================================
def load_status():
    if not os.path.exists(STATUS_FILE):
        return {"items": {}}

    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as status_handle:
            status = json.load(status_handle)
    except (OSError, json.JSONDecodeError):
        return {"items": {}}

    status.setdefault("items", {})
    return status


def save_status(status):
    ensure_parent_dir(STATUS_FILE)
    temp_file = f"{STATUS_FILE}.tmp"
    with open(temp_file, "w", encoding="utf-8") as status_handle:
        json.dump(status, status_handle, indent=2, sort_keys=True)
    os.replace(temp_file, STATUS_FILE)


# ============================================================
# Progress Bar Utility
# ============================================================
def progress_bar(current, total, bar_length=40):
    frac = current / total if total else 1
    filled = int(frac * bar_length)
    bar = "#" * filled + "-" * (bar_length - filled)
    percent = int(frac * 100)
    sys.stdout.write(f"\r[{bar}] {percent}% ({current}/{total})")
    sys.stdout.flush()


def format_elapsed(seconds):
    return time.strftime("%H:%M:%S", time.gmtime(max(0, seconds)))


# ============================================================
# Storage Checks
# ============================================================
def get_drive_root(path):
    drive, _ = os.path.splitdrive(os.path.abspath(path))
    return f"{drive}\\" if drive else path


def get_drive_type(path):
    if os.name != "nt":
        return "unknown"

    drive_type_codes = {
        0: "unknown",
        1: "no-root",
        2: "removable",
        3: "fixed",
        4: "remote",
        5: "cdrom",
        6: "ramdisk",
    }
    root = get_drive_root(path)
    drive_type = ctypes.windll.kernel32.GetDriveTypeW(root)
    return drive_type_codes.get(drive_type, "unknown")


def log_storage_location(label, path):
    drive_type = get_drive_type(path)
    log(f"{label}: {path} (drive type: {drive_type})")
    if drive_type not in {"fixed", "ramdisk"}:
        log(f"WARNING: {label} is not on a fast local disk. Copy speed may be limited by storage.")


# ============================================================
# Dataset Inspection Helpers
# ============================================================
def get_row_count(dataset_path):
    return int(arcpy.management.GetCount(dataset_path)[0])


def get_field_signature(dataset_path):
    field_signature = []
    for field in arcpy.ListFields(dataset_path):
        field_signature.append({
            "name": field.name,
            "type": field.type,
            "length": field.length,
            "precision": field.precision,
            "scale": field.scale,
        })
    return field_signature


def get_dataset_signature(dataset_path, row_count=None):
    if not arcpy.Exists(dataset_path):
        return None

    description = arcpy.Describe(dataset_path)
    spatial_reference = getattr(description, "spatialReference", None)

    return {
        "data_type": getattr(description, "dataType", None),
        "dataset_type": getattr(description, "datasetType", None),
        "shape_type": getattr(description, "shapeType", None),
        "spatial_reference": getattr(spatial_reference, "name", None),
        "row_count": row_count if row_count is not None else get_row_count(dataset_path),
        "fields": get_field_signature(dataset_path),
    }


def build_item_info(source_path, target_path):
    row_count = get_row_count(source_path)
    return {
        "name": os.path.basename(source_path),
        "src": source_path,
        "dest": target_path,
        "row_count": row_count,
        "source_signature": get_dataset_signature(source_path, row_count),
    }


def destination_is_current(item_info):
    if not arcpy.Exists(item_info["dest"]):
        return False, None

    try:
        target_row_count = get_row_count(item_info["dest"])
        target_signature = get_dataset_signature(item_info["dest"], target_row_count)
        return target_signature == item_info["source_signature"], target_signature
    except Exception as exc:
        log(f"WARNING: Existing target could not be inspected and will be recopied: {item_info['dest']} | {get_error_message(exc)}")
        arcpy.ClearWorkspaceCache_management()
        return False, None


def get_error_message(exc):
    arcpy_message = arcpy.GetMessages(2).strip()
    if arcpy_message:
        return arcpy_message
    return str(exc)


# ============================================================
# Copy Worker (Single-Process by Design)
# ============================================================
def copy_item(item_info):
    src = item_info["src"]
    dest = item_info["dest"]
    start_time = time.time()
    arcpy.env.overwriteOutput = True

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            if not arcpy.Exists(src):
                return {
                    "success": False,
                    "elapsed": time.time() - start_time,
                    "error": f"Source does not exist: {src}",
                    "target_signature": None,
                }

            if arcpy.Exists(dest):
                try:
                    arcpy.Delete_management(dest)
                except Exception as exc:
                    arcpy.ClearWorkspaceCache_management()
                    if arcpy.Exists(dest):
                        return {
                            "success": False,
                            "elapsed": time.time() - start_time,
                            "error": f"Existing target could not be removed: {dest} | {get_error_message(exc)}",
                            "target_signature": None,
                        }

            arcpy.Copy_management(src, dest)
            target_row_count = get_row_count(dest)
            return {
                "success": True,
                "elapsed": time.time() - start_time,
                "error": "",
                "target_signature": get_dataset_signature(dest, target_row_count),
            }
        except Exception as exc:
            error_message = get_error_message(exc)
            arcpy.ClearWorkspaceCache_management()
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY)
            else:
                return {
                    "success": False,
                    "elapsed": time.time() - start_time,
                    "error": error_message,
                    "target_signature": None,
                }


# ============================================================
# Cleanup Function (Runs After Copying)
#       - Your geoprocessing tools preserved exactly
# ============================================================
def gdb_cleaning(gdb_path):
    arcpy.env.workspace = gdb_path
    fc_list = arcpy.ListFeatureClasses() or []

    print("\n=== Cleaning GDB ===")
    log("Starting GDB cleaning...")

    for fc in fc_list:
        start_time = time.time()
        fc_path = os.path.join(gdb_path, fc)

        log(f"Cleaning {fc}")

        arcpy.RepairGeometry_management(fc_path)

        try:
            arcpy.RemoveSpatialIndex_management(fc_path)
        except Exception:
            log(f"{fc} had no spatial index to remove.")

        arcpy.RecalculateFeatureClassExtent_management(fc_path)
        arcpy.CalculateDefaultGridIndex_management(fc_path)
        arcpy.AddSpatialIndex_management(fc_path)

        elapsed = time.time() - start_time
        print(f"Cleaned {fc} in {format_elapsed(elapsed)}")

    log("GDB cleaning complete.")


# ============================================================
# Main Execution
# ============================================================
if __name__ == "__main__":
    if not write_log_line("=== Starting GDB Copy ===", mode="w"):
        print(f"WARNING: Could not initialize log file: {ACTIVE_LOG_FILE}", file=sys.stderr)

    status = load_status()

    log(f"Run log file: {ACTIVE_LOG_FILE}")
    log_storage_location("Source GDB", SOURCE_GDB)
    log_storage_location("Target GDB", TARGET_GDB)

    if not arcpy.Exists(TARGET_GDB):
        log(f"Creating target gdb: {TARGET_GDB}")
        arcpy.CreateFileGDB_management(os.path.dirname(TARGET_GDB), os.path.basename(TARGET_GDB))

    arcpy.env.workspace = SOURCE_GDB

    datasets = arcpy.ListDatasets("", "Feature") or []
    feature_classes = arcpy.ListFeatureClasses() or []
    tables = arcpy.ListTables() or []

    for dataset_name in datasets:
        arcpy.env.workspace = os.path.join(SOURCE_GDB, dataset_name)
        for feature_class in arcpy.ListFeatureClasses() or []:
            feature_classes.append(os.path.join(dataset_name, feature_class))

    arcpy.env.workspace = SOURCE_GDB

    log("Inspecting source datasets and calculating row counts...")
    items = []
    for feature_class in feature_classes:
        source_path = os.path.join(SOURCE_GDB, feature_class)
        target_path = os.path.join(TARGET_GDB, os.path.basename(feature_class))
        items.append(build_item_info(source_path, target_path))

    for table_name in tables:
        source_path = os.path.join(SOURCE_GDB, table_name)
        target_path = os.path.join(TARGET_GDB, os.path.basename(table_name))
        items.append(build_item_info(source_path, target_path))

    items.sort(key=lambda item: item["row_count"], reverse=True)

    total_items = len(items)
    log(f"Total items to process: {total_items}")
    log("Using 1 worker. Largest datasets are copied first based on source row count.")

    completed = 0
    copied = 0
    skipped = 0
    failed = 0
    run_start = time.time()

    print("Copying items...")

    for item in items:
        completed += 1
        progress_bar(completed, total_items)

        is_current, target_signature = destination_is_current(item)
        if is_current:
            skipped += 1
            status["items"][item["src"]] = {
                "name": item["name"],
                "status": "skipped_current",
                "row_count": item["row_count"],
                "source_signature": item["source_signature"],
                "target_signature": target_signature,
                "elapsed_seconds": 0,
                "updated_at": datetime.datetime.now().isoformat(),
            }
            save_status(status)
            log(f"SKIPPED CURRENT: {item['name']} | rows={item['row_count']:,}")
            continue

        log(f"\nSTARTING COPY: {item['name']} ({completed}/{total_items}) | rows={item['row_count']:,}")
        result = copy_item(item)
        elapsed = format_elapsed(result["elapsed"])

        status["items"][item["src"]] = {
            "name": item["name"],
            "status": "success" if result["success"] else "failed",
            "row_count": item["row_count"],
            "source_signature": item["source_signature"],
            "target_signature": result["target_signature"],
            "elapsed_seconds": result["elapsed"],
            "updated_at": datetime.datetime.now().isoformat(),
            "error": result["error"],
        }
        save_status(status)

        if result["success"]:
            copied += 1
            log(f"COPIED: {item['name']} | elapsed={elapsed}")
        else:
            failed += 1
            log(f"FAILED: {item['name']} | elapsed={elapsed} | {result['error']}")

    total_elapsed = format_elapsed(time.time() - run_start)
    print("\nCopy complete!")
    log(f"Summary: copied={copied}, skipped_current={skipped}, failed={failed}, total_elapsed={total_elapsed}")
    log("=== GDB Copy Completed ===")

    if RUN_CLEANUP:
        gdb_cleaning(TARGET_GDB)

    print("\nAll operations complete.")
    log("=== All operations complete ===")

    if failed:
        sys.exit(1)
