'''
PURPOSE:
The purpose of this script is to consolidate the layer-list, data-copy, status-tracking,
and optional cleaning workflows into one repeatable process. It reads specified map TOCs
from APRXs, writes layer-list reports, writes a master layer list without duplicate
datasets, pauses so the user can review that master list, then copies the listed SDE
datasets to a local file geodatabase.

SET UP:
1. Update the global settings below, especially APRX paths, map names, output paths,
   target GDB, log path, and SDE connection paths.
2. Each APRX has its own map name. This script only checks those specified maps.
3. Run in an ArcGIS Pro Python environment where ArcPy is available.
4. Set RUN_CLEANUP to True if the target GDB should be cleaned after copying.

RESULTS:
- Creates text files:
	1. Layer list for each APRX map, showing source datasets and layers.
	2. Master layer list for copy, without duplicate source datasets
- Pauses after creating the master list so the user can review it before copying.
- Creates the target GDB if it does not exist.
- Copies master-list datasets from source SDE connections to the target GDB.
- Tracks copy status in JSON and writes detailed timestamped logs.
'''

import arcpy
import ctypes
import datetime
import json
import os
import sys
import time
from collections import defaultdict


# ============================================================
# Global Settings (EDIT THESE)
# ============================================================
VTPK_APRX = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\DataDevelopment\FeedbackApplication\FSBasemap_Feedback_TEMPLATE.aprx"
#PDF_APRX = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\Workspace\JWilliams\2026_DataCopy\PDF_aprx_05282026.aprx"
MAP_126720 = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\APRX\Pro\126720_FSBaseMap\126720_FSBaseMap.aprx"
MAP_63360_PR = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\APRX\Pro\63360_FSBaseMap_PuertoRico\63360_FSBaseMap_PuertoRico.aprx"
MAP_63360 = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\APRX\Pro\63360_FSBaseMap\63360_FSBaseMap.aprx"
MAP_100K = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\APRX\Pro\100K_FSBaseMap\100K_FSBaseMap.aprx"
FSTOPO = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\APRX\Pro\FSTopo\FSTopoContinental_2026_July_SDE.aprx"
FSTOPO_PR = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\Workspace\wdgarrett\2026 The Map Maker\aprx\FSTopoPR_2026.aprx"
ADMIN_SERIES = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\APRX\Pro\Admin_Series\AdminSeries.aprx"
ALASKA_FOREST_SERIES = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\APRX\Pro\ForestSeries_Alaska\AlaskaForestSeriesMaps.aprx"

OUTPUT_FOLDER = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\Workspace\JWilliams\2026_DataCopy\GDB"

VTPK_MAP_NAME = "VTPK_June_2026"
#PDF_MAP_NAME = "Map"
MAP_126720_NAME = "Layers"
MAP_63360_PR_NAME = "Main Map"
MAP_63360_NAME = "Layers"
MAP_100K_NAME = "Layers"
FSTOPO_NAME = "BaseMap"
FSTOPO_PR_NAME = "BaseMap"
ADMIN_SERIES_NAME = "Main Map"
ALASKA_FOREST_SERIES_NAME = "Main Map"


VTPK_LAYER_LIST_TXT = os.path.join(OUTPUT_FOLDER, "vtpk_Layers_inTOC.txt")
PDF_LAYER_LIST_TXT = os.path.join(OUTPUT_FOLDER, "pdf_Layers_inTOC.txt")
MAP_126720_LAYER_LIST_TXT = os.path.join(OUTPUT_FOLDER, "126720_Layers_inTOC.txt")
MAP_63360_PR_LAYER_LIST_TXT = os.path.join(OUTPUT_FOLDER, "63360_PR_Layers_inTOC.txt")
MAP_63360_LAYER_LIST_TXT = os.path.join(OUTPUT_FOLDER, "63360_Layers_inTOC.txt")
MAP_100K_LAYER_LIST_TXT = os.path.join(OUTPUT_FOLDER, "100K_Layers_inTOC.txt")
FSTOPO_LAYER_LIST_TXT = os.path.join(OUTPUT_FOLDER, "FSTopo_Layers_inTOC.txt")
FSTOPO_PR_LAYER_LIST_TXT = os.path.join(OUTPUT_FOLDER, "FSTopoPR_Layers_inTOC.txt")
ADMIN_SERIES_LAYER_LIST_TXT = os.path.join(OUTPUT_FOLDER, "AdminSeries_Layers_inTOC.txt")
ALASKA_FOREST_SERIES_LAYER_LIST_TXT = os.path.join(OUTPUT_FOLDER, "AlaskaForestSeries_Layers_inTOC.txt")
MASTER_LAYER_LIST_TXT = os.path.join(OUTPUT_FOLDER, "MASTER_layers_list_for_copy.txt")
FAILED_COPY_LAYER_LIST_TXT = os.path.join(OUTPUT_FOLDER, "FAILED_layers_list_for_copy.txt")

TARGET_GDB = os.path.join(OUTPUT_FOLDER, "vTPK_and_PDF_Data_2026.gdb")
LOG_FILE = os.path.join(OUTPUT_FOLDER, "copy_log.txt")
STATUS_FILE = os.path.join(OUTPUT_FOLDER, "copy_status.json")

RETRY_ATTEMPTS = 3
RETRY_DELAY = 3          # seconds between retries


RUN_CLEANUP = False      # Enable/disable post-copy cleanup True or False

# Known source geodatabase paths
edw_source = r"\\usda.net\fs\FS\Reference\GeoTool\agency\AG4SDatabaseConnection\edw_dev_default_as_myself.sde"
ddcdw_source = r"\\usda.net\fs\FS\Reference\GeoTool\agency\DatabaseConnection\Postgres\EGDB\WO\wo_ddcdw as viewer.sde"
fsbasemap_source = r"\\usda.net\fs\FS\Reference\GeoTool\agency\DatabaseConnection\Postgres\EGDB\WO\wo_fsbasemap as viewer.sde"

KNOWN_SOURCE_PATHS = {
	"SDE_EDW": edw_source,
	"wo_ddcdw": ddcdw_source,
	"wo_fsbasemap": fsbasemap_source,
}

SOURCE_DISPLAY_NAMES = {
	"SDE_EDW": "EDW",
	"wo_ddcdw": "DDCDW",
	"wo_fsbasemap": "FSBasemap",
}

SOURCE_ORDER = ["EDW", "DDCDW", "FSBasemap"]


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
# APRX Layer List Helpers
# ============================================================
def get_known_sde_source(datasource):
    lower_source = datasource.lower()

    if "instance=wo_ddcdw" in lower_source or "dataset=wo_ddcdw." in lower_source or "wo_ddcdw as viewer.sde" in lower_source:
        return "wo_ddcdw", ddcdw_source

    if "instance=wo_fsbasemap" in lower_source or "dataset=wo_fsbasemap." in lower_source or "wo_fsbasemap as viewer.sde" in lower_source:
        return "wo_fsbasemap", fsbasemap_source

    if "instance=sde_edw" in lower_source or "server=sde_edw" in lower_source or "dataset=s_usa." in lower_source or "edw_dev_default_as_myself.sde" in lower_source:
        return "SDE_EDW", edw_source

    return None, None

def prompt_copy_sources():
    print("\nSelect data source(s) to copy:")
    print("  1) EDW only")
    print("  2) DDCDW only")
    print("  3) FSBasemap only")
    print("  4) All (EDW + DDCDW + FSBasemap)")

    while True:
        choice = input("Enter 1, 2, 3, or 4: ").strip().lower()

        if choice in {"1", "edw"}:
            return {"EDW"}
        if choice in {"2", "ddcdw"}:
            return {"DDCDW"}
        if choice in {"3", "fsbasemap", "fs"}:
            return {"FSBasemap"}
        if choice in {"4", "all", "a"}:
            return set(SOURCE_ORDER)

        print("Invalid selection. Please enter 1, 2, 3, or 4.")

def prompt_run_mode():
    print("\nSelect run mode:")
    print("  1) Copy data")
    print("  2) Cleanup only")

    while True:
        choice = input("Enter 1 or 2: ").strip().lower()
        if choice in {"1", "copy", "c"}:
            return "copy"
        if choice in {"2", "cleanup", "clean", "cleanup only"}:
            return "cleanup_only"
        print("Invalid selection. Please enter 1 or 2.")

def filter_selected_sources(source_dict, other_sources, selected_sources):
    filtered_source_dict, filtered_other_sources = make_empty_layer_report()

    for source_name in SOURCE_ORDER:
        if source_name not in selected_sources:
            continue
        filtered_source_dict[source_name]["source_path"] = source_dict[source_name]["source_path"]
        filtered_source_dict[source_name]["layers"] = set(source_dict[source_name]["layers"])

    # Intentionally exclude 'Other' for this run mode.
    return filtered_source_dict, filtered_other_sources

def is_guid_name(value):
	parts = value.split("-")
	if len(parts) != 5:
		return False
	lengths = [8, 4, 4, 4, 12]
	return all(len(part) == length for part, length in zip(parts, lengths))


def split_connection_string(datasource):
	properties = {}
	for part in datasource.split(","):
		if "=" not in part:
			continue
		key, value = part.split("=", 1)
		properties[key.strip()] = value.strip()
	return properties


def get_file_gdb_source_display(gdb_path):
	gdb_name = os.path.basename(gdb_path)
	parent_name = os.path.basename(os.path.dirname(gdb_path))
	if is_guid_name(os.path.splitext(gdb_name)[0]) and parent_name:
		return os.path.join(parent_name, gdb_name)
	return gdb_name


def parse_datasource(datasource):
	lower_source = datasource.lower()
	known_source_display, known_source_path = get_known_sde_source(datasource)

	if ".gdb" in lower_source:
		parts = datasource.split("\\")
		for index, part in enumerate(parts):
			if part.lower().endswith(".gdb"):
				gdb_path = "\\".join(parts[: index + 1])
				layer_name = "\\".join(parts[index + 1:]) or os.path.splitext(part)[0]
				source_display = get_file_gdb_source_display(gdb_path)
				return source_display, gdb_path, layer_name

	if ".sde" in lower_source:
		parts = datasource.split("\\")
		for index, part in enumerate(parts):
			if part.lower().endswith(".sde"):
				source_display = known_source_display or os.path.splitext(os.path.basename(part))[0]
				layer_name = "\\".join(parts[index + 1:]) or source_display
				source_path = known_source_path or "\\".join(parts[: index + 1])
				return source_display, source_path, layer_name

	if "Dataset=" in datasource:
		connection_props = split_connection_string(datasource)
		source_display = known_source_display or connection_props.get("Instance") or connection_props.get("Server") or "Other"
		dataset_name = connection_props.get("Dataset", datasource)
		layer_name = dataset_name.split(".")[-1]
		full_source_path = known_source_path or KNOWN_SOURCE_PATHS.get(source_display, datasource)
		return source_display, full_source_path, layer_name

	return "Other", datasource, datasource


def get_full_dataset_name(datasource):
	if "Dataset=" in datasource:
		parts = datasource.split("Dataset=")
		if len(parts) > 1:
			return parts[1].split(";")[0].strip()

	lower_source = datasource.lower()
	if ".sde" in lower_source:
		sde_index = lower_source.rfind(".sde")
		if sde_index != -1:
			dataset_name = datasource[sde_index + 4:]
			return dataset_name.lstrip("\\/")

	return datasource


def get_exact_map(aprx, map_name, aprx_label):
	matching_maps = [m for m in aprx.listMaps() if m.name == map_name]
	if not matching_maps:
		raise ValueError(f"Map named '{map_name}' was not found in {aprx_label}. This script will not process all maps.")
	if len(matching_maps) > 1:
		raise ValueError(f"More than one map named '{map_name}' was found in {aprx_label}. Use a unique map name.")
	return matching_maps[0]


def make_empty_layer_report():
	source_dict = {
		"EDW": {"source_path": edw_source, "layers": set()},
		"DDCDW": {"source_path": ddcdw_source, "layers": set()},
		"FSBasemap": {"source_path": fsbasemap_source, "layers": set()},
	}
	other_sources = defaultdict(lambda: {"source_path": "", "layers": set()})
	return source_dict, other_sources


def collect_layers_from_aprx(aprx_path, map_name, aprx_label):
	source_dict, other_sources = make_empty_layer_report()
	aprx = arcpy.mp.ArcGISProject(aprx_path)
	map_to_check = get_exact_map(aprx, map_name, aprx_label)

	for lyr in map_to_check.listLayers():
		if lyr.isFeatureLayer and hasattr(lyr, "dataSource"):
			try:
				known_source_display, known_source_path = get_known_sde_source(lyr.dataSource)
				if not known_source_display:
					source_display, full_source_path, layer_name = parse_datasource(lyr.dataSource)
					dataset_name = get_full_dataset_name(lyr.dataSource)
					other_sources[full_source_path]["source_path"] = full_source_path
					other_sources[full_source_path]["layers"].add(dataset_name or layer_name)
					continue
				display_name = SOURCE_DISPLAY_NAMES.get(known_source_display)
				if not display_name:
					continue
				dataset_name = get_full_dataset_name(lyr.dataSource)
				if dataset_name:
					source_dict[display_name]["source_path"] = known_source_path
					source_dict[display_name]["layers"].add(dataset_name)
			except Exception as exc:
				log(f"WARNING: Could not read layer datasource in {aprx_label}: {get_error_message(exc)}")

	return source_dict, other_sources


def write_layer_report(output_txt, source_dict, other_sources):
	ensure_parent_dir(output_txt)

	with open(output_txt, "w", encoding="utf-8") as output_handle:
		for source_name in SOURCE_ORDER:
			layers = sorted(source_dict[source_name]["layers"])
			if not layers:
				continue
			output_handle.write(f"Source: {source_name}\n")
			output_handle.write(f"Source Path: \"{source_dict[source_name]['source_path']}\"\n\n")
			output_handle.write("Layers:\n")
			for layer_name in layers:
				output_handle.write(f'    "{layer_name}",\n')
			output_handle.write("\n")

		for source_path in sorted(other_sources.keys()):
			layers = sorted(other_sources[source_path]["layers"])
			if not layers:
				continue
			output_handle.write("Source: Other\n")
			output_handle.write(f"Source Path: \"{source_path}\"\n\n")
			output_handle.write("Layers:\n")
			for layer_name in layers:
				output_handle.write(f'    "{layer_name}",\n')
			output_handle.write("\n")


def merge_layer_reports(report_items):
	master = {}

	for source_dict, other_sources in report_items:
		for source_name in SOURCE_ORDER:
			source_path = source_dict[source_name]["source_path"]
			key = (source_name, source_path)
			master.setdefault(key, set()).update(source_dict[source_name]["layers"])

		for source_path, source_info in other_sources.items():
			key = ("Other", source_path)
			master.setdefault(key, set()).update(source_info["layers"])

	merged_source_dict, merged_other_sources = make_empty_layer_report()
	for (source_name, source_path), layers in master.items():
		if source_name in merged_source_dict:
			merged_source_dict[source_name]["source_path"] = source_path
			merged_source_dict[source_name]["layers"].update(layers)
		else:
			merged_other_sources[source_path]["source_path"] = source_path
			merged_other_sources[source_path]["layers"].update(layers)

	return merged_source_dict, merged_other_sources


def parse_layer_report(report_path):
	source_dict, other_sources = make_empty_layer_report()
	current_source = None
	current_source_path = None
	in_layers = False

	with open(report_path, "r", encoding="utf-8") as report_handle:
		for raw_line in report_handle:
			line = raw_line.strip()
			if not line:
				in_layers = False
				continue

			if line.startswith("Source: "):
				current_source = line.split(":", 1)[1].strip()
				current_source_path = None
				in_layers = False
				continue

			if line.startswith("Source Path: "):
				current_source_path = line.split(":", 1)[1].strip().strip('"')
				if current_source in source_dict:
					source_dict[current_source]["source_path"] = current_source_path
				elif current_source == "Other":
					other_sources[current_source_path]["source_path"] = current_source_path
				continue

			if line == "Layers:":
				in_layers = True
				continue

			if in_layers and current_source and current_source_path:
				layer_name = line.rstrip(",").strip().strip('"')
				if not layer_name:
					continue
				if current_source in source_dict:
					source_dict[current_source]["layers"].add(layer_name)
				else:
					other_sources[current_source_path]["layers"].add(layer_name)

	return source_dict, other_sources


def build_layer_lists():
	log("\n Building layer lists from specified APRX map TOCs...")
	log(f"VTPK APRX map: {VTPK_MAP_NAME}")
	vtpk_report = collect_layers_from_aprx(VTPK_APRX, VTPK_MAP_NAME, "VTPK_APRX")
	write_layer_report(VTPK_LAYER_LIST_TXT, vtpk_report[0], vtpk_report[1])
	log(f"VTPK layer list written to: {VTPK_LAYER_LIST_TXT}")

	# log(f"\n PDF APRX map: {PDF_MAP_NAME}")
	# pdf_report = collect_layers_from_aprx(PDF_APRX, PDF_MAP_NAME, "PDF_APRX")
	# write_layer_report(PDF_LAYER_LIST_TXT, pdf_report[0], pdf_report[1])
	# log(f"PDF layer list written to: {PDF_LAYER_LIST_TXT}")

	log(f"\n MAP 126720 APRX map: {MAP_126720_NAME}")
	map_126720_report = collect_layers_from_aprx(MAP_126720, MAP_126720_NAME, "MAP_126720")
	write_layer_report(MAP_126720_LAYER_LIST_TXT, map_126720_report[0], map_126720_report[1])
	log(f"MAP 126720 layer list written to: {MAP_126720_LAYER_LIST_TXT}")

	log(f"\n MAP_63360_PR APRX map: {MAP_63360_PR_NAME}")
	map_63360_pr_report = collect_layers_from_aprx(MAP_63360_PR, MAP_63360_PR_NAME, "MAP_63360_PR")
	write_layer_report(MAP_63360_PR_LAYER_LIST_TXT, map_63360_pr_report[0], map_63360_pr_report[1])
	log(f"MAP 63360 PR layer list written to: {MAP_63360_PR_LAYER_LIST_TXT}")

	log(f"\n MAP_63360 APRX map: {MAP_63360_NAME}")
	map_63360_report = collect_layers_from_aprx(MAP_63360, MAP_63360_NAME, "MAP_63360")
	write_layer_report(MAP_63360_LAYER_LIST_TXT, map_63360_report[0], map_63360_report[1])
	log(f"MAP 63360 layer list written to: {MAP_63360_LAYER_LIST_TXT}")

	log(f"\n MAP_100K APRX map: {MAP_100K_NAME}")
	map_100k_report = collect_layers_from_aprx(MAP_100K, MAP_100K_NAME, "MAP_100K")
	write_layer_report(MAP_100K_LAYER_LIST_TXT, map_100k_report[0], map_100k_report[1])
	log(f"MAP 100K layer list written to: {MAP_100K_LAYER_LIST_TXT}")

	log(f"\n FSTOPO APRX map: {FSTOPO_NAME}")
	fstopo_report = collect_layers_from_aprx(FSTOPO, FSTOPO_NAME, "FSTOPO")
	write_layer_report(FSTOPO_LAYER_LIST_TXT, fstopo_report[0], fstopo_report[1])
	log(f"FSTOPO layer list written to: {FSTOPO_LAYER_LIST_TXT}")

	log(f"\n ADMIN_SERIES APRX map: {ADMIN_SERIES_NAME}")
	admin_series_report = collect_layers_from_aprx(ADMIN_SERIES, ADMIN_SERIES_NAME, "ADMIN_SERIES")
	write_layer_report(ADMIN_SERIES_LAYER_LIST_TXT, admin_series_report[0], admin_series_report[1])
	log(f"ADMIN_SERIES layer list written to: {ADMIN_SERIES_LAYER_LIST_TXT}")

	log(f"\n ALASKA_FOREST_SERIES APRX map: {ALASKA_FOREST_SERIES_NAME}")
	alaska_forest_series_report = collect_layers_from_aprx(ALASKA_FOREST_SERIES, ALASKA_FOREST_SERIES_NAME, "ALASKA_FOREST_SERIES")
	write_layer_report(ALASKA_FOREST_SERIES_LAYER_LIST_TXT, alaska_forest_series_report[0], alaska_forest_series_report[1])
	log(f"ALASKA_FOREST_SERIES layer list written to: {ALASKA_FOREST_SERIES_LAYER_LIST_TXT}")

	master_source_dict, master_other_sources = merge_layer_reports([vtpk_report, map_126720_report, map_63360_pr_report, map_63360_report, map_100k_report, fstopo_report, admin_series_report, alaska_forest_series_report])
	write_layer_report(MASTER_LAYER_LIST_TXT, master_source_dict, master_other_sources)
	log(f"\n Master layer list written to: {MASTER_LAYER_LIST_TXT}")


def pause_for_master_list_review():
	print("\nStep one is complete.")
	print(f"Review the master layer list before copying: {MASTER_LAYER_LIST_TXT}")
	answer = input("Type Y to continue with data copying, or anything else to stop: ").strip().lower()
	if answer not in {"y", "yes"}:
		log("User stopped workflow after reviewing the master layer list.")
		sys.exit(0)


def iter_master_layers(source_dict, other_sources):
	for source_name in SOURCE_ORDER:
		source_path = source_dict[source_name]["source_path"]
		for dataset_name in sorted(source_dict[source_name]["layers"]):
			yield {
				"source_name": source_name,
				"source_path": source_path,
				"dataset_name": dataset_name,
			}

	for source_path in sorted(other_sources.keys()):
		for dataset_name in sorted(other_sources[source_path]["layers"]):
			yield {
				"source_name": "Other",
				"source_path": source_path,
				"dataset_name": dataset_name,
			}


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


def get_target_name(dataset_name):
	target_name = dataset_name.replace("/", "\\").split("\\")[-1]
	return target_name.split(".")[-1]


def get_source_dataset_path(source_path, dataset_name):
	if dataset_name.lower().startswith(source_path.lower()):
		return dataset_name
	return os.path.join(source_path, dataset_name)


def build_item_info(master_layer):
	source_path = get_source_dataset_path(master_layer["source_path"], master_layer["dataset_name"])
	target_name = get_target_name(master_layer["dataset_name"])
	target_path = os.path.join(TARGET_GDB, target_name)
	row_count = get_row_count(source_path)

	return {
		"name": target_name,
		"source_name": master_layer["source_name"],
		"dataset_name": master_layer["dataset_name"],
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

			arcpy.CopyFeatures_management(src, dest)
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


def build_copy_items(master_source_dict, master_other_sources):
	log("\n Inspecting source datasets and calculating row counts...")
	items = []
	failed_inspection = []

	for master_layer in iter_master_layers(master_source_dict, master_other_sources):
		try:
			item_info = build_item_info(master_layer)
			items.append(item_info)
		except Exception as exc:
			error_message = get_error_message(exc)
			failed_inspection.append((master_layer, error_message))
			log(f"FAILED INSPECTION: {master_layer['source_name']} | {master_layer['dataset_name']} | {error_message}")
			arcpy.ClearWorkspaceCache_management()

	items.sort(key=lambda item: item["row_count"], reverse=True)
	return items, failed_inspection


def copy_master_layers_from_file(selected_sources=None):
    master_source_dict, master_other_sources = parse_layer_report(MASTER_LAYER_LIST_TXT)

    if selected_sources:
        master_source_dict, master_other_sources = filter_selected_sources(
            master_source_dict,
            master_other_sources,
            selected_sources
        )
        log(f"Selected sources for copy: {', '.join([s for s in SOURCE_ORDER if s in selected_sources])}")

    status = load_status()

    if not arcpy.Exists(TARGET_GDB):
        log(f"\n Creating target gdb: {TARGET_GDB}")
        arcpy.CreateFileGDB_management(os.path.dirname(TARGET_GDB), os.path.basename(TARGET_GDB))

    items, failed_inspection = build_copy_items(master_source_dict, master_other_sources)

    failed_source_dict, failed_other_sources = make_empty_layer_report()
    for master_layer, _ in failed_inspection:
        source_name = master_layer["source_name"]
        source_path = master_layer["source_path"]
        dataset_name = master_layer["dataset_name"]
        if source_name in failed_source_dict:
            failed_source_dict[source_name]["source_path"] = source_path
            failed_source_dict[source_name]["layers"].add(dataset_name)
        else:
            failed_other_sources[source_path]["source_path"] = source_path
            failed_other_sources[source_path]["layers"].add(dataset_name)

    total_items = len(items)
    log(f"Total items to process: {total_items}")
    log("Using 1 worker. Largest datasets are copied first based on source row count.")

    completed = 0
    copied = 0
    skipped = 0
    failed = len(failed_inspection)
    run_start = time.time()

    print("\n Copying items...")

    for item in items:
        completed += 1
        progress_bar(completed, total_items)

        is_current, target_signature = destination_is_current(item)
        if is_current:
            skipped += 1
            status["items"][item["src"]] = {
                "name": item["name"],
                "source_name": item["source_name"],
                "dataset_name": item["dataset_name"],
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
            "source_name": item["source_name"],
            "dataset_name": item["dataset_name"],
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
            if item["source_name"] in failed_source_dict:
                failed_source_dict[item["source_name"]]["source_path"] = item["source_path"]
                failed_source_dict[item["source_name"]]["layers"].add(item["dataset_name"])
            else:
                failed_other_sources[item["source_path"]]["source_path"] = item["source_path"]
                failed_other_sources[item["source_path"]]["layers"].add(item["dataset_name"])
            log(f"FAILED: {item['name']} | elapsed={elapsed} | {result['error']}")

    write_layer_report(FAILED_COPY_LAYER_LIST_TXT, failed_source_dict, failed_other_sources)
    log(f"Failed copy layer list written to: {FAILED_COPY_LAYER_LIST_TXT}")

    total_elapsed = format_elapsed(time.time() - run_start)
    print("\nCopy complete!")
    log(f"Summary: copied={copied}, skipped_current={skipped}, failed={failed}, total_elapsed={total_elapsed}")

    return failed


# ============================================================
# Cleanup Function (Runs After Copying)
#       - Geoprocessing tools preserved from cleaning process
# ============================================================
def list_feature_classes_for_cleaning(gdb_path):
	feature_class_paths = []
	arcpy.env.workspace = gdb_path

	for feature_class in arcpy.ListFeatureClasses() or []:
		feature_class_paths.append(os.path.join(gdb_path, feature_class))

	for dataset_name in arcpy.ListDatasets("", "Feature") or []:
		dataset_path = os.path.join(gdb_path, dataset_name)
		arcpy.env.workspace = dataset_path
		for feature_class in arcpy.ListFeatureClasses() or []:
			feature_class_paths.append(os.path.join(dataset_path, feature_class))

	arcpy.env.workspace = gdb_path
	return feature_class_paths


def gdb_cleaning(gdb_path):
	arcpy.env.overwriteOutput = False
	arcpy.env.workspace = gdb_path
	feature_class_paths = list_feature_classes_for_cleaning(gdb_path)

	print("\n=== Cleaning GDB ===")
	log("Starting GDB cleaning...")
	log(f"Target GDB: {gdb_path}")
	log(f"Feature classes queued: {len(feature_class_paths)}")

	cleaned_count = 0
	failed_count = 0

	for index, feature_class_path in enumerate(feature_class_paths, start=1):
		start_time = time.time()
		feature_class_name = os.path.basename(feature_class_path)

		log(f"Cleaning {feature_class_name} ({index}/{len(feature_class_paths)})")

		try:
			arcpy.RepairGeometry_management(feature_class_path)

			try:
				arcpy.RemoveSpatialIndex_management(feature_class_path)
			except Exception:
				log(f"{feature_class_name} had no spatial index to remove.")

			arcpy.RecalculateFeatureClassExtent_management(feature_class_path)
			arcpy.CalculateDefaultGridIndex_management(feature_class_path)
			arcpy.AddSpatialIndex_management(feature_class_path)

			cleaned_count += 1
			elapsed = time.time() - start_time
			print(f"Cleaned {feature_class_name} in {format_elapsed(elapsed)}")
		except Exception as exc:
			failed_count += 1
			elapsed = time.time() - start_time
			log(f"FAILED CLEANING: {feature_class_name} | elapsed={format_elapsed(elapsed)} | {get_error_message(exc)}")
		finally:
			arcpy.ClearWorkspaceCache_management()

	log(f"GDB cleaning complete. cleaned={cleaned_count}, failed={failed_count}")
	return failed_count


# ============================================================
# Main Execution
# ============================================================
if __name__ == "__main__":
    if not write_log_line("=== Starting Consolidated APRX Layer List, GDB Copy, and Clean Workflow ===", mode="w"):
        print(f"WARNING: Could not initialize log file: {ACTIVE_LOG_FILE}", file=sys.stderr)

    run_failed = 0

    try:
        run_mode = prompt_run_mode()

        if run_mode == "cleanup_only":
            run_failed = gdb_cleaning(TARGET_GDB)
            print("\nAll operations complete.")
            log("=== Cleanup-only operation complete ===")
        else:
            selected_sources = prompt_copy_sources()
            run_failed = copy_master_layers_from_file(selected_sources=selected_sources)
            log("=== GDB Copy Completed ===")

            if RUN_CLEANUP:
                run_failed += gdb_cleaning(TARGET_GDB)

            print("\nAll operations complete.")
            log("=== All operations complete ===")
    except Exception as exc:
        log(f"FATAL ERROR: {get_error_message(exc)}")
        sys.exit(1)

    if run_failed:
        sys.exit(1)
