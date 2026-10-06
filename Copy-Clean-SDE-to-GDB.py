'''
PURPOSE:
The purpose of this script is to consolidate the layer-list, data-copy, status-tracking,
and optional cleaning workflows into one repeatable process. It reads selected APRX
documents, writes layer-list reports, writes a master layer list without duplicate
datasets, pauses so the user can review that master list, then copies the listed SDE
datasets to a local file geodatabase.

SET UP:
1. Update the APRX configuration list below, especially APRX paths, output paths,
	target GDB, log path, and SDE connection paths.
2. This script checks all maps in the selected APRX documents.
3. Run in an ArcGIS Pro Python environment where ArcPy is available.
4. Set RUN_CLEANUP to True if the target GDB should be cleaned after copying.

RESULTS:
- Creates selected APRX layer list files and one master layer list for copy, without
	duplicate source datasets
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
# Configuration - Update these paths and settings as needed
# ============================================================
OUTPUT_FOLDER = r"I:\2026_Basemap_Data_forVTPKandPDFs\OCT_2026_DataCopy"
RUN_CLEANUP = False      # Enable/disable post-copy cleanup True or False

MASTER_LAYER_LIST_TXT = os.path.join(OUTPUT_FOLDER, "MASTER_layers_list_for_copy.txt")

TARGET_GDB = os.path.join(OUTPUT_FOLDER, "All_Maps_Data_2026.gdb")
LOG_FILE = os.path.join(OUTPUT_FOLDER, "copy_log.txt")
STATUS_FILE = os.path.join(OUTPUT_FOLDER, "copy_status.json")

RETRY_ATTEMPTS = 3
RETRY_DELAY = 3          # seconds between retries

APRX_ENTRIES = [
	{
		"selection_key": "vtpk",
		"label": "VTPK APRX",
		"report_name": "VTPK layer list",
		"aprx_path": r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\DataDevelopment\FeedbackApplication\FSBasemap_Feedback_TEMPLATE.aprx",
		"map_name": None,
		"layer_list_txt": os.path.join(OUTPUT_FOLDER, "vtpk_Layers_inTOC.txt"),
	},
	{
		"selection_key": "pdf",
		"label": "PDF APRX",
		"report_name": "PDF layer list",
		"aprx_path": r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\Workspace\JWilliams\2026_DataCopy\PDF_aprx_05282026.aprx",
		"map_name": None,
		"layer_list_txt": os.path.join(OUTPUT_FOLDER, "pdf_Layers_inTOC.txt"),
	},
	{
		"selection_key": "63360",
		"label": "63360 APRX",
		"report_name": "63360 layer list",
		"aprx_path": r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\APRX\Pro\63360_FSBaseMap\63360_FSBaseMap.aprx",
		"map_name": None,
		"layer_list_txt": os.path.join(OUTPUT_FOLDER, "63360_Layers_inTOC.txt"),
	},
	{
		"selection_key": "126720",
		"label": "126720 APRX",
		"report_name": "126720 layer list",
		"aprx_path": r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\APRX\Pro\126720_FSBaseMap\126720_FSBaseMap.aprx",
		"map_name": None,
		"layer_list_txt": os.path.join(OUTPUT_FOLDER, "126720_Layers_inTOC.txt"),
	},
	{
		"selection_key": "158400",
		"label": "158400 APRX",
		"report_name": "158400 layer list",
		"aprx_path": r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\APRX\Pro\158400_FSBaseMap\158400_FSBaseMap.aprx",
		"map_name": None,
		"layer_list_txt": os.path.join(OUTPUT_FOLDER, "158400_Layers_inTOC.txt"),
	},
	{
		"selection_key": "100K",
		"label": "100K APRX",
		"report_name": "100K layer list",
		"aprx_path": r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\APRX\Pro\100K_FSBaseMap\100K_FSBaseMap.aprx",
		"map_name": None,
		"layer_list_txt": os.path.join(OUTPUT_FOLDER, "100K_Layers_inTOC.txt"),
	},
	{
		"selection_key": "FSTopo",
		"label": "FSTopo APRX",
		"report_name": "FSTopo layer list",
		"aprx_path": r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\APRX\Pro\FSTopo\FSTopoContinental_2026_July_SDE.aprx",
		"map_name": None,
		"layer_list_txt": os.path.join(OUTPUT_FOLDER, "FSTopo_Layers_inTOC.txt"),
	},
]


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
	maps_to_check = aprx.listMaps()
	if not maps_to_check:
		raise ValueError(f"No maps were found in {aprx_label}.")
	if not map_name:
		return maps_to_check
	for map_to_check in maps_to_check:
		if map_to_check.name == map_name:
			return [map_to_check]
	raise ValueError(f"Map '{map_name}' was not found in {aprx_label}.")


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
	maps_to_check = get_exact_map(aprx, map_name, aprx_label)

	for map_to_check in maps_to_check:
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


def normalize_report_layer_name(raw_value):
	layer_name = raw_value.strip()
	if not layer_name:
		return ""

	# Remove list punctuation around the quoted dataset name and tolerate a
	# misplaced comma inside the closing quote.
	layer_name = layer_name.rstrip(",").strip()
	layer_name = layer_name.strip('"').strip("'").strip()
	layer_name = layer_name.rstrip(",").strip()
	layer_name = layer_name.strip('"').strip("'").strip()
	return layer_name


def parse_layer_report(report_path):
	source_dict, other_sources = make_empty_layer_report()
	current_source = None
	current_source_path = None
	in_layers = False

	with open(report_path, "r", encoding="utf-8") as report_handle:
		for raw_line in report_handle:
			line = raw_line.strip()
			if not line:
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
				layer_name = normalize_report_layer_name(line)
				if not layer_name:
					continue
				if current_source in source_dict:
					source_dict[current_source]["layers"].add(layer_name)
				else:
					other_sources[current_source_path]["layers"].add(layer_name)

	return source_dict, other_sources


def normalize_layer_report_file(report_path):
	source_dict, other_sources = parse_layer_report(report_path)
	write_layer_report(report_path, source_dict, other_sources)
	return source_dict, other_sources


def log_master_layers(source_dict, other_sources):
	master_layers = list(iter_master_layers(source_dict, other_sources))
	log(f"Parsed master layer count: {len(master_layers)}")
	for master_layer in master_layers:
		log(
			f"MASTER ITEM: {master_layer['source_name']} | "
			f"{master_layer['dataset_name']} "
		)
	return master_layers



def normalize_selection_token(value):
	return "".join(character for character in value.lower() if character.isalnum())


def build_aprx_selection_lookup():
	selection_lookup = {}
	for index, entry in enumerate(APRX_ENTRIES, start=1):
		selection_lookup[str(index)] = entry
		selection_lookup[normalize_selection_token(entry["selection_key"])] = entry
		selection_lookup[normalize_selection_token(entry["label"])] = entry
		selection_lookup[normalize_selection_token(entry["report_name"])] = entry
	return selection_lookup


def prompt_for_aprx_entries():
	selection_lookup = build_aprx_selection_lookup()

	while True:
		print("\nAvailable APRX entries:")
		for index, entry in enumerate(APRX_ENTRIES, start=1):
			print(f"  {index}. {entry['label']} (report: {entry['report_name']})")

		selection_text = input("Select APRX entries by number or label (comma-separated, Enter for all): ").strip()
		if not selection_text:
			return APRX_ENTRIES

		selected_indexes = []
		invalid_tokens = []
		for token in [part.strip() for part in selection_text.split(",") if part.strip()]:
			selected_entry = selection_lookup.get(token)
			if not selected_entry:
				selected_entry = selection_lookup.get(normalize_selection_token(token))
			if not selected_entry:
				invalid_tokens.append(token)
				continue
			selected_index = APRX_ENTRIES.index(selected_entry)
			if selected_index not in selected_indexes:
				selected_indexes.append(selected_index)

		if invalid_tokens:
			print(f"Invalid selection: {', '.join(invalid_tokens)}")
			print("Enter 1..n, a stable label, or press Enter to select all entries.")
			continue

		if not selected_indexes:
			print("No valid APRX entries were selected. Try again.")
			continue

		return [APRX_ENTRIES[index] for index in selected_indexes]


def build_layer_lists(selected_entries):
	log("\n Building layer lists from selected APRX documents...")
	report_items = []

	for entry in selected_entries:
		log(f"{entry['label']} selected for layer list collection")
		report = collect_layers_from_aprx(entry["aprx_path"], entry["map_name"], entry["label"])
		write_layer_report(entry["layer_list_txt"], report[0], report[1])
		log(f"{entry['report_name']} written to: {entry['layer_list_txt']}")
		report_items.append(report)

	master_source_dict, master_other_sources = merge_layer_reports(report_items)
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


def copy_master_layers_from_file():
	master_source_dict, master_other_sources = normalize_layer_report_file(MASTER_LAYER_LIST_TXT)
	log(f"Normalized master layer list: {MASTER_LAYER_LIST_TXT}")
	log_master_layers(master_source_dict, master_other_sources)
	status = load_status()

	if not arcpy.Exists(TARGET_GDB):
		log(f"\n Creating target gdb: {TARGET_GDB}")
		arcpy.CreateFileGDB_management(os.path.dirname(TARGET_GDB), os.path.basename(TARGET_GDB))

	items, failed_inspection = build_copy_items(master_source_dict, master_other_sources)

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
			log(f"FAILED: {item['name']} | elapsed={elapsed} | {result['error']}")

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
		log(f"Run log file: {ACTIVE_LOG_FILE}")
		log_storage_location("Target GDB", TARGET_GDB)

		selected_entries = prompt_for_aprx_entries()
		build_layer_lists(selected_entries)
		pause_for_master_list_review()

		run_failed = copy_master_layers_from_file()
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
