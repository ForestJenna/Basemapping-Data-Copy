The goal is to consolidate differnt copy and cleaning steps into a single workflow and python script.  I envision is a script that will compare data from map TOCs in two aprxs and copy all of from the source sdes to a local gdb, then I can have one data store on a local drive that any application / workflow can access. I want to run a single script to get new data and clean it if necessary.

Formating should be modeled off of Copy-and-Track-Data.py script. Using global variables when possible/reasonable. 

There should be pauses between each steps one and two so the user can review the master list and chose to continue with the data copying.

Each aprx will have to have it's own map name. Never process/ check all maps associated with the aprx, only the ones the user specifies. 

STEP ONE: LIST LAYERS IN MAP TOCS
First step in process should be modeled off of the idea of list-layer-names-in-map-TOC.py script. I want to keep the functions mostly intact from this script as the output is exactly what I need. 
        
    There are going to be at least two aprxs that need to be looked at. A lot of the data in these map TOCs are going to be the same, but a few layers will be different. The goal is to create a text file that has a master list of the data needed to be copied and cleaned without duplication of layers. This master list will be fed into the next step.
        There should be three text file outputs from step one.
            1. text file listing layers in vtpk.aprx
            2. text file listing layers in pdf.aprx
            3. master-layers-for-copy text file lising layers that need to be copies from both without duplication. 

STEP TWO: COPY DATA FROM SDE TO GDB
Step two is modeled off of the copy-and-track-data.py script except that I want to be able to feed in the master-layers-for-copy text file and have these layers copied to a local gdb. Look at the function called copy_feature_classes_with_workspace in the copy-data-from-sdes-to-local-gdb.py for how this can be set up. 
    Functionality desired:
        1. copy datasets from a source file geodatabase to a target file geodatabase that are included in the master-layers-for-copy text file. Include with robust logging, status tracking, and error handling.
        2. The script will continue to process all items even if some fail, and will produce a summary of results at the end.
        3. You can run this script repeatedly as it will skip copying items that are already current in the target location based on a 
        signature comparison. The status of each item is tracked in a JSON file, and detailed logs are written to a timestamped log file.


STEP THREE: CLEANING THE DATA
Step three performs a series of cleaning operations on all feature classes within a specified file geodatabase (GDB). 
The operations include repairing geometry, removing and adding spatial indexes, recalculating extents, and calculating default grid 
indexes. This is basically the stand-alone-gdb-cleaning.py script that need to be worked into the overall flow. Set this up to be optional like the Copy-and-Track-Data.py does with gdb_cleaning function. 
- Do NOT add or change any of the geoprocessing tools used in this process
