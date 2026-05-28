import arcpy
import datetime
import os
import sys
import time

# ============================================================
# Global Settings (EDIT THESE)
# ============================================================
CLEAN_GDB_PATH = r"E:\2026_vtpk\Geodatabase\vTPK_Fresh5Data_2026.gdb"
LOG_FILE = r"E:\2026_vtpk\Geodatabase\Fresh5DataCleaning_Log.txt"

RUN_REPAIR_GEOMETRY = True
RUN_REMOVE_SPATIAL_INDEX = True
RUN_RECALCULATE_EXTENT = True
RUN_CALCULATE_DEFAULT_GRID_INDEX = True
RUN_ADD_SPATIAL_INDEX = True


# ============================================================
# Logging Utility
# ============================================================
def reset_log():
	with open(LOG_FILE, "w", encoding="utf-8") as log_handle:
		log_handle.write("=== Starting GDB Cleaning ===\n")


def log(message):
	timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	line = f"{timestamp} - {message}"

	print(line)

	with open(LOG_FILE, "a", encoding="utf-8") as log_handle:
		log_handle.write(f"{line}\n")


def format_elapsed(seconds):
	return time.strftime("%H:%M:%S", time.gmtime(max(0, seconds)))


def get_arcpy_error(exc):
	arcpy_message = arcpy.GetMessages(2).strip()
	if arcpy_message:
		return arcpy_message
	return str(exc)


# ============================================================
# Dataset Discovery
# ============================================================
def list_feature_classes_for_cleaning(gdb_path):
	feature_class_paths = []
	arcpy.env.workspace = gdb_path

	for feature_class in arcpy.ListFeatureClasses() or []:
		feature_class_paths.append(os.path.join(gdb_path, feature_class))

	for dataset_name in arcpy.ListDatasets("", "Feature") or []:
		dataset_path = os.path.join(gdb_path, dataset_name)
		arcpy.env.workspace = dataset_path
		dataset_feature_classes = arcpy.ListFeatureClasses() or []

		if dataset_feature_classes:
			for feature_class in dataset_feature_classes:
				feature_class_paths.append(os.path.join(dataset_path, feature_class))
		else:
			log(f"Dataset has no feature classes: {dataset_name}")

	arcpy.env.workspace = gdb_path
	return feature_class_paths


# ============================================================
# Cleaning Helpers
# ============================================================
def run_cleaning_tools(feature_class_path):
	feature_class_name = os.path.basename(feature_class_path)

	if RUN_REPAIR_GEOMETRY:
		log(f"RepairGeometry: {feature_class_name}")
		arcpy.RepairGeometry_management(feature_class_path)

	if RUN_REMOVE_SPATIAL_INDEX:
		try:
			log(f"RemoveSpatialIndex: {feature_class_name}")
			arcpy.RemoveSpatialIndex_management(feature_class_path)
		except Exception:
			log(f"{feature_class_name} had no spatial index to remove.")

	if RUN_RECALCULATE_EXTENT:
		log(f"RecalculateExtent: {feature_class_name}")
		arcpy.RecalculateFeatureClassExtent_management(feature_class_path)

	if RUN_CALCULATE_DEFAULT_GRID_INDEX:
		log(f"CalculateDefaultGridIndex: {feature_class_name}")
		arcpy.CalculateDefaultGridIndex_management(feature_class_path)

	if RUN_ADD_SPATIAL_INDEX:
		log(f"AddSpatialIndex: {feature_class_name}")
		arcpy.AddSpatialIndex_management(feature_class_path)


# ============================================================
# Main Cleaning Function
# ============================================================
def gdb_cleaning(gdb_path):
	arcpy.env.overwriteOutput = False
	arcpy.env.workspace = gdb_path
	feature_class_paths = list_feature_classes_for_cleaning(gdb_path)

	log("=== Cleaning GDB ===")
	log(f"Target GDB: {gdb_path}")
	log(f"Feature classes queued: {len(feature_class_paths)}")

	cleaned_count = 0
	failed_count = 0
	failed_items = []

	for index, feature_class_path in enumerate(feature_class_paths, start=1):
		start_time = time.time()
		feature_class_name = os.path.basename(feature_class_path)

		log(f"Starting {feature_class_name} ({index}/{len(feature_class_paths)})")

		try:
			run_cleaning_tools(feature_class_path)
			cleaned_count += 1
			elapsed = time.time() - start_time
			log(f"Finished {feature_class_name} in {format_elapsed(elapsed)}\n")
		except Exception as exc:
			failed_count += 1
			elapsed = time.time() - start_time
			error_message = get_arcpy_error(exc)
			failed_items.append((feature_class_name, error_message))
			log(f"FAILED {feature_class_name} in {format_elapsed(elapsed)} | {error_message}\n")
		finally:
			arcpy.ClearWorkspaceCache_management()

	return cleaned_count, failed_count, failed_items


# ============================================================
# Script Entry Point
# ============================================================
if __name__ == "__main__":
	reset_log()
	run_start = time.time()

	log(f"CLEAN_GDB_PATH: {CLEAN_GDB_PATH}")
	log(f"LOG_FILE: {LOG_FILE}")

	if not arcpy.Exists(CLEAN_GDB_PATH):
		log(f"ERROR: Geodatabase does not exist: {CLEAN_GDB_PATH}")
		sys.exit(1)

	try:
		cleaned_count, failed_count, failed_items = gdb_cleaning(CLEAN_GDB_PATH)
	except Exception as exc:
		log(f"FATAL ERROR: {get_arcpy_error(exc)}")
		sys.exit(1)

	total_elapsed = format_elapsed(time.time() - run_start)
	log(f"Summary: cleaned={cleaned_count}, failed={failed_count}, elapsed={total_elapsed}")

	if failed_items:
		log("Failed feature classes:")
		for feature_class_name, error_message in failed_items:
			log(f"  {feature_class_name} | {error_message}")

	log("=== GDB Cleaning Complete ===")

	if failed_count:
		sys.exit(1)
