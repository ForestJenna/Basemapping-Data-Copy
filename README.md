# Basemapping Data Copy Repo
These scripts can be used to manage geodatabase copy and cleaning. Each script is explained below. All script have logging and are intended to be run in an environment with ArcPy available.


# Copy-and-Track-Data.py
This script copies datasets from a source file geodatabase to a target file geodatabase. You can run this script repeatedly as it will skip copying items that are already current in the target location based on a signature comparison.  Optionally, it can perform cleanup operations on the target geodatabase after copying is complete. 


# Copy-Data-From-SDEs-To-Local-GDB.py
This script is based on an older version of the DDC data copy and clean process. It will analyzes a ArcGIS Pro project (.aprx) to extract and summarize the data sources for all feature layers in the project. 
##Result: It groups layers by their data source (such as SDE databases or file geodatabases), and writes a summary to a text file. This file can then be used to populate the layers list in the main python script.

