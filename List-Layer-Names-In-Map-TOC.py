"""
PURPOSE:
This script analyzes an ArcGIS Pro project (.aprx) to extract and summarize the data sources for all feature layers in the project. 
It groups layers by their data source (such as SDE databases or file geodatabases), and writes a summary to a text file.

SETUP:
1. Ensure you have ArcGIS Pro installed and are able to run Python scripts with the `arcpy` library.
2. Update the `aprx_path` variable in the script to point to your ArcGIS Pro project file (.aprx).
3. Update the `output_txt` variable to specify where you want the output text file to be saved.
4. Run the script in an environment where you have access to the necessary network drives and permissions.

RESULTS:
- The script creates a text file listing each unique data source found in the project.
- For each source, it lists the full source paths and the names of all layers using that source.
- This helps users review and document where each layer's data is coming from, which is useful for data management and troubleshooting.
"""

import arcpy
import os
from collections import defaultdict

# Set the path to your ArcGIS Pro project (.aprx)
aprx_path = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\VTPK\2026 FSBASEMAP VTPK\APRX\FSBasemap_vtpk_Enhancements_2026MASTER_sdeLinked_COPY_JW.aprx"
output_txt = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\VTPK\2026 FSBASEMAP VTPK\DataChecks\vtpk_Layers_inTOC.txt"

MAP_NAME = "Enhancements 1_8"

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

# Open the project
aprx = arcpy.mp.ArcGISProject(aprx_path)

# Dictionary to group layers by source
source_dict = {
    "EDW": {"source_path": edw_source, "layers": set()},
    "DDCDW": {"source_path": ddcdw_source, "layers": set()},
    "FSBasemap": {"source_path": fsbasemap_source, "layers": set()},
}
other_sources = defaultdict(lambda: {"source_path": "", "layers": set()})


# Only get the map with the specified name
maps_to_check = [m for m in arcpy.mp.ArcGISProject(aprx_path).listMaps() if m.name == MAP_NAME]

# Iterate through only the map(s) matching MAP_NAME

# Collect layer names by known SDE source
for m in maps_to_check:
    for lyr in m.listLayers():
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
                    source_dict[display_name]["layers"].add(dataset_name)
            except Exception:
                continue

# Write report grouped by SDE source
with open(output_txt, "w") as f:
    for source_name in ["EDW", "DDCDW", "FSBasemap"]:
        layers = sorted(source_dict[source_name]["layers"])
        if not layers:
            continue
        f.write(f"Source: {source_name}\n")
        f.write(f"Source Path: \"{source_dict[source_name]['source_path']}\"\n\n")
        f.write("Layers:\n")
        for layer_name in layers:
            f.write(f'    "{layer_name}",\n')
        f.write("\n")

    for source_path in sorted(other_sources.keys()):
        layers = sorted(other_sources[source_path]["layers"])
        if not layers:
            continue
        f.write("Source: Other\n")
        f.write(f"Source Path: \"{source_path}\"\n\n")
        f.write("Layers:\n")
        for layer_name in layers:
            f.write(f'    "{layer_name}",\n')
        f.write("\n")

"""
This script analyzes an ArcGIS Pro project (.aprx) to extract and summarize the data sources for all feature layers in the project. 
It groups layers by their data source (such as SDE databases or file geodatabases), and writes a summary to a text file.
How to run:
1. Ensure you have ArcGIS Pro installed and are able to run Python scripts with the `arcpy` library.
2. Update the `aprx_path` variable in the script to point to your ArcGIS Pro project file (.aprx).
3. Update the `output_txt` variable to specify where you want the output text file to be saved.
4. Run the script in an environment where you have access to the necessary network drives and permissions.
Output:
- The script creates a text file listing each unique data source found in the project.
- For each source, it lists the full source paths and the names of all layers using that source.
- This helps users review and document where each layer's data is coming from, which is useful for data management and troubleshooting.
"""

import arcpy
import os
from collections import defaultdict

# Set the path to your ArcGIS Pro project (.aprx)
aprx_path = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\VTPK\2026 FSBASEMAP VTPK\APRX\FSBasemap_vtpk_Enhancements_2026MASTER_sdeLinked_COPY_JW.aprx"
output_txt = r"\\usda.net\fs\FS\NFS\WOEngineering\GMO-GTAC\Project\DDC\FSBaseMaps\VTPK\2026 FSBASEMAP VTPK\DataChecks\vtpk_Layers_inTOC.txt"

MAP_NAME = "Enhancements 1_8"

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

# Open the project
aprx = arcpy.mp.ArcGISProject(aprx_path)

# Dictionary to group layers by source
source_dict = {
    "EDW": {"source_path": edw_source, "layers": set()},
    "DDCDW": {"source_path": ddcdw_source, "layers": set()},
    "FSBasemap": {"source_path": fsbasemap_source, "layers": set()},
}
other_sources = defaultdict(lambda: {"source_path": "", "layers": set()})


# Only get the map with the specified name
maps_to_check = [m for m in arcpy.mp.ArcGISProject(aprx_path).listMaps() if m.name == MAP_NAME]

# Iterate through only the map(s) matching MAP_NAME

# Collect layer names by known SDE source
for m in maps_to_check:
    for lyr in m.listLayers():
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
                    source_dict[display_name]["layers"].add(dataset_name)
            except Exception:
                continue

# Write report grouped by SDE source
with open(output_txt, "w") as f:
    for source_name in ["EDW", "DDCDW", "FSBasemap"]:
        layers = sorted(source_dict[source_name]["layers"])
        if not layers:
            continue
        f.write(f"Source: {source_name}\n")
        f.write(f"Source Path: \"{source_dict[source_name]['source_path']}\"\n\n")
        f.write("Layers:\n")
        for layer_name in layers:
            f.write(f'    "{layer_name}",\n')
        f.write("\n")

    for source_path in sorted(other_sources.keys()):
        layers = sorted(other_sources[source_path]["layers"])
        if not layers:
            continue
        f.write("Source: Other\n")
        f.write(f"Source Path: \"{source_path}\"\n\n")
        f.write("Layers:\n")
        for layer_name in layers:
            f.write(f'    "{layer_name}",\n')
        f.write("\n")

print(f"Layer sources written to {output_txt}")