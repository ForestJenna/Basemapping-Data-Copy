import arcpy
import os
import datetime
import multiprocessing
import time
import sys

# ============================================================
# Global Settings (EDIT THESE)
# ============================================================
SOURCE_GDB = r"E:\2026_vtpk\Geodatabase\vTPK_Data_2026.gdb"
TARGET_GDB = r"C:\Path\To\Target.gdb"
LOG_FILE = r"C:\Path\To\copy_log.txt"

DEFAULT_WORKERS = 8      # Auto‑adjusts based on CPU cores
RETRY_ATTEMPTS = 3
RETRY_DELAY = 3          # seconds between retries

RUN_CLEANUP = True       # Enable/disable post-copy cleanup True or False


# ============================================================
# Logging Utility
# ============================================================
def log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"{timestamp} - {message}\n")
    print(message)



# ============================================================
# Progress Bar Utility
# ============================================================
def progress_bar(current, total, bar_length=40):
    frac = current / total
    filled = int(frac * bar_length)
    bar = "#" * filled + "-" * (bar_length - filled)
    percent = int(frac * 100)
    sys.stdout.write(f"\r[{bar}] {percent}% ({current}/{total})")
    sys.stdout.flush()



# ============================================================
# Worker: Copies a Single Feature Class or Table
# ============================================================
def copy_item(item):
    import arcpy  # Must re-import within each worker process

    src, dest = item

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            arcpy.Copy_management(src, dest)
            return (src, True, "")
        except Exception as e:
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY)
            else:
                return (src, False, str(e))



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

        # Repair geometry
        arcpy.RepairGeometry_management(fc_path)

        # Remove spatial index (may not exist)
        try:
            arcpy.RemoveSpatialIndex_management(fc_path)
        except:
            log(f"{fc} had no spatial index to remove.")

        # Recalculate extent
        arcpy.RecalculateFeatureClassExtent_management(fc_path)

        # Calculate default grid index
        arcpy.CalculateDefaultGridIndex_management(fc_path)

        # Add spatial index
        arcpy.AddSpatialIndex_management(fc_path)

        # Timing output
        elapsed = time.time() - start_time
        print(f"Cleaned {fc} in {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")

    log("GDB cleaning complete.")



# ============================================================
# Main Execution
# ============================================================
if __name__ == "__main__":

    # Reset log
    with open(LOG_FILE, "w") as f:
        f.write("=== Starting GDB Copy ===\n")

    # Ensure target GDB exists
    if not arcpy.Exists(TARGET_GDB):
        log(f"Creating target gdb: {TARGET_GDB}")
        arcpy.CreateFileGDB_management(os.path.dirname(TARGET_GDB),
                                       os.path.basename(TARGET_GDB))

    arcpy.env.workspace = SOURCE_GDB

    # Collect items
    datasets = arcpy.ListDatasets("", "Feature") or []
    feature_classes = arcpy.ListFeatureClasses() or []
    tables = arcpy.ListTables() or []

    # Feature classes inside datasets
    for ds in datasets:
        arcpy.env.workspace = os.path.join(SOURCE_GDB, ds)
        for fc in arcpy.ListFeatureClasses() or []:
            feature_classes.append(os.path.join(ds, fc))

    arcpy.env.workspace = SOURCE_GDB

    # Build copy list
    items = []
    for fc in feature_classes:
        items.append((fc, os.path.join(TARGET_GDB, os.path.basename(fc))))
    for tbl in tables:
        items.append((tbl, os.path.join(TARGET_GDB, os.path.basename(tbl))))

    total_items = len(items)
    log(f"Total items to copy: {total_items}")

    # Determine worker count
    cpu_count = multiprocessing.cpu_count()
    workers = min(DEFAULT_WORKERS, cpu_count)
    log(f"Using {workers} workers (system has {cpu_count} cores).")

    # ============================================================
    # Multiprocessing Pool
    # ============================================================
    completed = 0
    print("Copying items...")

    with multiprocessing.Pool(processes=workers) as pool:
        for src, success, err in pool.imap_unordered(copy_item, items):
            completed += 1
            progress_bar(completed, total_items)

            if success:
                log(f"SUCCESS: {src}")
            else:
                log(f"FAILED: {src} - {err}")

    print("\nCopy complete!")
    log("=== GDB Copy Completed ===")

    # ============================================================
    # Optional Cleanup Stage
    # ============================================================
    if RUN_CLEANUP:
        gdb_cleaning(TARGET_GDB)

    print("\nAll operations complete.")
    log("=== All operations complete ===")
