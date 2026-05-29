'''
PURPOSE:
This script analyzes an ArcGIS Pro project (.aprx) to extract and summarize the data sources for all feature layers in the project.
It groups layers by their data source (such as SDE databases or file geodatabases), and writes a summary to a text file.

SETUP:
- Ensure you have ArcGIS Pro installed and are able to run Python scripts with the `arcpy` library.
- Update the `aprx_path` variable in the script to point to your ArcGIS Pro project file (.aprx).
- Update the `output_txt` variable to specify where you want the output text file to be saved.
- Run the script in an environment where you have access to the necessary network drives and permissions.

RESULTS:
- The script creates a text file listing each unique data source found in the project.
- For each source, it lists the full source paths and the names of all layers using that source.
- At the end of a run you will see the number of successful runs, failed runs, or flagged datasets. 
        # Successful runs = source count and destination count match
        # Failed copies = dataset didn’t copy at all 
        # Flagged copies = source and destination count are mis-matched
'''

import re
import zipfile
import os
import time
import arcpy
import datetime

DIRECTORY = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\VTPK\2026 FSBASEMAP VTPK\Geodatabase"  # Replace with your desired directory
CURRENT_DATE = datetime.datetime.now().strftime("%m%d%Y")

    # Define the name of the new geodatabase
DATA_COPY_GDB = f"vTPK_Data_2026.gdb"
    # Define the path of the new folder
DATA_COPY_FOLDER = os.path.join(DIRECTORY, f"vTPK_Data_Copy_{CURRENT_DATE}")
    
# Define source geodatabase paths
edw_source = r"\\usda.net\fs\FS\Reference\GeoTool\agency\DatabaseConnection\edw_sde_default_as_myself.sde"
ddcdw_source = r"\\usda.net\fs\FS\Reference\GeoTool\agency\DatabaseConnection\Postgres\EGDB\WO\wo_ddcdw as viewer.sde"
fsbasemap_source = r"\\usda.net\fs\FS\Reference\GeoTool\agency\DatabaseConnection\Postgres\EGDB\WO\wo_fsbasemap as viewer.sde"



#List of feature classes to copy from EDW
print('EDW  - feature layers')
edw_feature_classes = [
    "S_USA.BdyAdm_LSRS_AdministrativeForest",
    # "S_USA.BdyAdm_LSRS_RangerDistrict",
    # "S_USA.BdyAdm_SurfaceMgmtAgency_BLM",
    # "S_USA.BdyDesg_County",
    # "S_USA.BdyDesg_CountySubdivisions_CENSUS",
    # "S_USA.BdyDesg_LSRS_OtherNationalDesignatedArea",
    # "S_USA.BdyDesg_LSRS_WildScenicRiver",
    # "S_USA.BdyDesg_LSRS_Wilderness",
    # "S_USA.BdyDesg_UrbanArea_Census",
    # "S_USA.BdyOwn_LSRS_BasicOwnership",
    # "S_USA.BdyOwn_PADUS_Designation_USGS",
    # "S_USA.BdyOwn_PADUS_Fee_USGS",
    # "S_USA.BdyOwn_PADUS_Proclamation_USGS",
    # "S_USA.BdyPol_Place_Census",
    # "S_USA.Building",
    # "S_USA.GNIS_USGS",
    # "S_USA.Hydro_NWI_AK_Wetlands_FWS",
    # "S_USA.Hydro_NWI_CONUS_Wetlands_FWS",
    # "S_USA.Rec_RecreationSite",
    # "S_USA.Util_CommSite_SpeclUse",
]

print('DDCDW -  feature classes')
# List of feature classes to copy from DDCDW
ddcdw_feature_classes = [
    "wo_ddcdw.wo_ddcdw.County_Line_wLabels_GTAC",
    # "wo_ddcdw.wo_ddcdw.FSBoundaryLine_AK",
    # "wo_ddcdw.wo_ddcdw.FSCommonNames_singlepart",
    # "wo_ddcdw.wo_ddcdw.Glacier_RGI",
    # "wo_ddcdw.wo_ddcdw.PLSS_FirstDivision_BLM",
    # "wo_ddcdw.wo_ddcdw.PLSS_Township_BLM",
    # "wo_ddcdw.wo_ddcdw.Railroads_FRA",
    # "wo_ddcdw.wo_ddcdw.State_Line_wLabels_GTAC",
    # "wo_ddcdw.wo_ddcdw.contours_50ft_go",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_airfield_faa",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_airports_faa",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_byway_hifld",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_ferry_marine_hwy_gtac",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_foreign_land_gtac",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_gnis_populated_place_usgs",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_great_lakes_gtac",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_hifld_regional_series_gtac",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_hifld_plus_gtac",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_landform_area_gtac",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_landform_area_usgs",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_mvum_plus_gtac",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_national_trails_usgs",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_nhd_area_usgs",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_nhd_flowline_gtac",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_nhd_line_usgs",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_nhd_point_usgs",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_nhd_waterbody_usgs",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_places_20k_gtac",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_places_50_gtac",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_places_6k_gtac",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_recreation_site_blm",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_recreation_site_nps",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_region_line_generalized_gtac",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_state_generalized_census",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_state_international_boundary_gtac",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_structure_point_usgs",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_structure_poly_fema",
    # "wo_ddcdw.wo_ddcdw.ddcdw_ddcdw_summit_gap_200_gtac",
    # "wo_ddcdw.wo_ddcdw.hydro_area_regional_gtac_point",
    # "wo_ddcdw.wo_ddcdw.nfstrails_plus_gtac",
    # "wo_ddcdw.wo_ddcdw.places_1k",
    # "wo_ddcdw.wo_ddcdw.places_225_gtac",
    # "wo_ddcdw.wo_ddcdw.region_poly_generalized_service_gtac",
    # "wo_ddcdw.wo_ddcdw.wilderness_bands",
]

print('FSBASEMAP - feature classes')
# List of feature classes to copy from FSBasemap
fsbasemap_feature_classes = [
    # "wo_fsbasemap.wo_fsbasemap.gap_roads_gtac",
    # "wo_fsbasemap.wo_fsbasemap.hydro_area_regional_gtac",
    # "wo_fsbasemap.wo_fsbasemap.hydro_flowline_regional_gtac",
    # "wo_fsbasemap.wo_fsbasemap.landform_line_gtac",
    "wo_fsbasemap.wo_fsbasemap.nhs_trails_gtac",
]

def create_DATA_COPY_GDB():
    # Create the new folder
    if not os.path.exists(DATA_COPY_FOLDER):
        os.makedirs(DATA_COPY_FOLDER)
        print(f"Folder created: {DATA_COPY_FOLDER}")
    else:
        print(f"Folder already exists: {DATA_COPY_FOLDER}")

    # Full path to the new geodatabase
    gdb_path = f"{DATA_COPY_FOLDER}/{DATA_COPY_GDB}"
    
    # Create the file geodatabase
    arcpy.CreateFileGDB_management(DATA_COPY_FOLDER, DATA_COPY_GDB)
    
    print (f"Geodatabase created: {gdb_path}")
    return gdb_path


def gdb_cleaning(DATA_COPY_GDB):
    arcpy.env.workspace = DATA_COPY_GDB
    featureClassList = arcpy.ListFeatureClasses()
    print("Cleaning vTPK gdb...\n")
    for featureClass in featureClassList:
        st2 = time.time()
        arcpy.AddMessage("Working with feature Class: {}".format(featureClass))

        featureClassPath = os.path.join(str(DATA_COPY_GDB), featureClass)

        #arcpy.AddMessage("Repairing Geometry")
        arcpy.RepairGeometry_management(featureClassPath)
        arcpy.GetMessages()
        arcpy.AddMessage("Repairing Geometry Complete")

        try:
            #arcpy.AddMessage("Removing Spatial Reference")
            arcpy.RemoveSpatialIndex_management(featureClassPath)
            arcpy.GetMessages()
            arcpy.AddMessage("Removing Spatial Reference Complete")

        except:
            arcpy.AddMessage("Feature Class {} didn't have a spatial index.".format(featureClassPath))

        #arcpy.AddMessage("Recalculate Feature Class Extent")
        arcpy.RecalculateFeatureClassExtent_management(featureClassPath)
        arcpy.GetMessages()
        arcpy.AddMessage("Recalculate Feature Class Extent Complete")

        #arcpy.AddMessage("Calculate Default Grid Index")
        arcpy.CalculateDefaultGridIndex_management(featureClassPath)
        arcpy.GetMessages()
        arcpy.AddMessage("Calculate Default Grid Index Complete")

        #arcpy.AddMessage("Add Spatial Index")
        arcpy.AddSpatialIndex_management(featureClassPath)
        arcpy.GetMessages()
        arcpy.AddMessage("Add Spatial Index Complete")
        elapsed_time = time.time() - st2
        print('Execution time:', time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))
        arcpy.AddMessage(".........")
        del featureClassPath

        elapsed_time = time.time() - st2

def get_last_segments(path, segments=2):
    # This is to help with printing statements of the source and destination paths
    parts = path.split(os.sep)
    return os.sep.join(parts[-segments:])

def copy_feature_classes_with_workspace(source, DATA_COPY_GDB, feature_classes, log_file_path):
    """Copy specified feature classes from source to DATA_COPY_GDB geodatabase."""
    successful_copies = []
    failed_copies = []
    flagged_datasets = []

    for fc in feature_classes:
        print("}" * 50, "\n" * 1)
        fc_start_time = time.time()
        try:
            source_fc = os.path.join(source, fc)
            
            # File Geodatabases do not support periods in dataset names. 
            # We must strip out the schema/owner prefixes (e.g., 'S_USA.', 'wo_ddcdw.')
            fc_safe_name = fc.split('.')[-1]
            DATA_COPY_GDB_fc = os.path.join(DATA_COPY_GDB, fc_safe_name)

            # Get source count
            countfc = arcpy.GetCount_management(source_fc)

            # Copy the feature class
            arcpy.CopyFeatures_management(source_fc, DATA_COPY_GDB_fc)

            # Get output count
            countout = arcpy.GetCount_management(DATA_COPY_GDB_fc)

            fc_elapsed_time = time.time() - fc_start_time

            # Truncate paths to the last three segments
            truncated_source_fc = get_last_segments(source_fc)
            truncated_DATA_COPY_GDB_fc = get_last_segments(DATA_COPY_GDB_fc)

            print(f"\nCopied {truncated_source_fc} to {truncated_DATA_COPY_GDB_fc}")
            print("Source Count =", countfc[0])
            print("Destination Count =", countout[0])
            print(f"\n Time taken: {time.strftime('%H:%M:%S', time.gmtime(fc_elapsed_time))}")

            # Check if the source count and destination count are different
            if countfc[0] != countout[0]:
                flagged_datasets.append(fc)

            successful_copies.append(fc)
        except Exception as e:
            fc_elapsed_time = time.time() - fc_start_time
            print(f"Error copying {fc}: {str(e)}")
            print(f"Time taken: {time.strftime('%H:%M:%S', time.gmtime(fc_elapsed_time))}")
            failed_copies.append(fc)

            # Log the error to the log file
            with open(log_file_path, "a") as log_file:
                log_file.write(f"Error copying {fc}: {str(e)}\n")

    return successful_copies, failed_copies, flagged_datasets

def log_execution_time(directory, execution_time_seconds, cleaning_time_seconds, copy_time_seconds):
    log_file_path = os.path.join(directory, "execution_time_log.txt")
    
    # Calculate hours, minutes, and seconds from the total execution time in seconds
    hours, remainder = divmod(execution_time_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    # Calculate hours, minutes, and seconds from the copy time in seconds
    copy_hours, copy_remainder = divmod(copy_time_seconds, 3600)
    copy_minutes, copy_seconds = divmod(copy_remainder, 60)
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d")
                                                    
    # Calculate hours, minutes, and seconds from the cleaning time in seconds
    cleaning_hours, cleaning_remainder = divmod(cleaning_time_seconds, 3600)
    cleaning_minutes, cleaning_seconds = divmod(cleaning_remainder, 60)
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d")

    with open(log_file_path, "a") as log_file:
        log_file.write(f"\nExecution time on {current_time}:\n")
        log_file.write(f"Total execution time: {int(hours)} hours, {int(minutes)} minutes, {int(seconds)} seconds\n")
        log_file.write(f"Copy Features time: {int(copy_hours)} hours, {int(copy_minutes)} minutes, {int(copy_seconds)} seconds\n")
        log_file.write(f"Cleaning time: {int(cleaning_hours)} hours, {int(cleaning_minutes)} minutes, {int(cleaning_seconds)} seconds\n")

    print(f"\nExecution log updated with times {log_file_path}")

# Main function to create the geodatabase, copy feature classes, and handle user confirmation
def main():
    arcpy.env.overwriteOutput = True
    start_time = time.time()

    # Create the geodatabase with the current date
    DATA_COPY_GDB = create_DATA_COPY_GDB()
    
    # Initialize lists to store results
    results = []
    all_flagged_datasets = []
    failed_copies = []

    log_file_path = os.path.join(os.path.dirname(DATA_COPY_GDB), "execution_log.txt")

    Copy_start_time = time.time()
    # Copy feature classes and record the workspace
    print("\n\nCopying edw feature classes....")
    successful, failed, flagged = copy_feature_classes_with_workspace(edw_source, DATA_COPY_GDB, edw_feature_classes, log_file_path)
    results.append((successful, failed, flagged))
    all_flagged_datasets.extend(flagged)
    failed_copies.extend(failed)

    print("\n\nCopying ddcdw feature classes....")
    successful, failed, flagged = copy_feature_classes_with_workspace(ddcdw_source, DATA_COPY_GDB, ddcdw_feature_classes, log_file_path)
    results.append((successful, failed, flagged))
    all_flagged_datasets.extend(flagged)
    failed_copies.extend(failed)

    print("\n\nCopying fsbasemap feature classes....")
    successful, failed, flagged = copy_feature_classes_with_workspace(fsbasemap_source, DATA_COPY_GDB, fsbasemap_feature_classes, log_file_path)
    results.append((successful, failed, flagged))
    all_flagged_datasets.extend(flagged)
    failed_copies.extend(failed)

    Copy_time = time.time() - Copy_start_time
    print('Copy Features execution time:', time.strftime("%H:%M:%S", time.gmtime(Copy_time)))


    # Release any resources or locks and pause to ensure locks are released
    arcpy.ClearWorkspaceCache_management()
    print("\nPausing for 5 seconds to ensure all resources are released... \n")
    time.sleep(5)
    
    # Cleaning step
    cleaning_start_time = time.time()
    gdb_cleaning(DATA_COPY_GDB)
    cleaning_time = time.time() - cleaning_start_time
    print('Cleaning gdb execution time:', time.strftime("%H:%M:%S", time.gmtime(cleaning_time)))

    # Report the results
    total_successful = sum([len(r[0]) for r in results])
    total_failed = sum([len(r[1]) for r in results])
    total_flagged = sum([len(r[2]) for r in results])
    print(f"Copying complete. Successful: {total_successful}, Failed: {total_failed}, Flagged {total_flagged}")

    # Log the results to the log file
    with open(log_file_path, "a") as log_file:
        log_file.write(f"\nCopying complete. Successful: {total_successful}, Failed: {total_failed}, Flagged {total_flagged}\n")
        if total_flagged:
            log_file.write("\nFlagged datasets with count discrepancies:\n")
            for dataset in all_flagged_datasets:
                log_file.write(f"{dataset}\n")
        if total_failed:
            log_file.write("\nFailed to copy the following datasets:\n")
            for dataset in failed_copies:
                log_file.write(f"{dataset}\n")

    # Release any resources or locks and pause to ensure locks are released
    arcpy.ClearWorkspaceCache_management()
    print("\nPausing for 5 seconds to ensure all resources are released... \n")
    time.sleep(5)

    elapsed_time = time.time() - start_time
    print('\n Total execution time:', time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))
    log_execution_time(os.path.dirname(DATA_COPY_GDB), elapsed_time, Copy_time, cleaning_time)

main()