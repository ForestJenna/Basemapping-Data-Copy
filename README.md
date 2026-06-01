# Basemapping Data Copy Repo
These scripts can be used to manage geodatabase copy and cleaning. Each script is explained below. All script have logging and are intended to be run in an environment with ArcPy available.

If cleaning operations are applied these are the geoprocessing tools that will be run on each data layer. Repairing geometry, removing and adding spatial indexes, recalculating extents, and calculating default grid indexes.

The copy scripts are set up to copy the largest dataset to the smallest. So expect more time to between notifications at the start. Largest layers can take an hour to copy depending on the destination. 

# Copy-Clean-SDE-to-GDB.py
MAIN PROCESSING SCRIPT - DOES IT ALL
This script reads specified map TOCs from two APRXs, generates reports, and copies datasets to a local file geodatabase. It has optional data cleaning and can be run repeatedly. It will skip copying items that are already current in the target location based on signature comparisions. It consolidates workflows for layer-list reporting, data copying, and optional cleaning into a single process. 
    Currently set up to read the PDF.aprx and the vtpk.aprx managed by the Basemapping group for map production. 
    The instructions for conolistation script markdown was used to build this. It give idea background if more explination is needed. 

## Results
- Creates three text files and uses the master-list to copy the data from source SDE connections to the target gdb with the option to clean this data after copying.
- Text files generate:
  1. VTPK APRX layer list
  2. PDF APRX layer list
  3. Master layer list for copy, without duplicate source datasets

# Copy-and-Track-Data.py
USE TO MAKE A COPY OF A GDB 
This script copies datasets from a source file geodatabase to a target file geodatabase. You can run this script repeatedly as it will skip copying items that are already current in the target location based on a signature comparison.  Optionally, it can perform cleanup operations on the target geodatabase after copying is complete. 
## Result
  - Datasets from the source geodatabase will be copied to the target geodatabase, with progress and results logged.

# List-Layer-Names-In-Map-TOC.py 
This script analyzes an ArcGIS Pro project (.aprx) to extract and summarize the data sources for all feature layers in the project. 
It groups layers by their data source (such as SDE databases or file geodatabases), and writes a summary to a text file.

## Results
- The script creates a text file listing each unique data source found in the project.
- For each source, it lists the full source paths and the names of all layers using that source.

# Stand-alone-gdb-cleaning.py
This script performs a series of cleaning operations on all feature classes within a specified file geodatabase (GDB). 

## Result
- Cleaned gdb. 

# Copy-Data-From-SDEs-To-Local-GDB.py
ORIGIONAL FORMATTED DATA COPY AND CLEAN SCRIPT. CAN ARCHIVE IF DON'T USE. 
This script is based on an older version of the DDC data copy and clean process. It will analyzes a ArcGIS Pro project (.aprx) to extract and summarize the data sources for all feature layers in the project. From this text file you can build out the data copy list in the python script. Use the newer process copy-clean-sde-to-gdb.py script. 
## Result
- It groups layers by their data source (such as SDE databases or file geodatabases), and writes a summary to a text file. This file can then be used to populate the layers list in the main python script.

