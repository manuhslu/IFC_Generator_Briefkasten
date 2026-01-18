import trimesh
import numpy as np
import io
import zipfile
import ezdxf
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from shapely.geometry import Polygon


def _generate_common_geometry(text: str):
    """
    Calculates shared geometry data (dimensions, positioned text polygons)
    to ensure consistency between different file formats (STL, DXF).
    """
    # 1. Define dimensions
    base_width = 50.0
    base_height = 10.0
    base_depth = 3.0
    text_extrusion_height = 1.0

    # 2. Generate 2D text path using matplotlib
    font_props = FontProperties(family='sans-serif', style='normal', weight='bold')
    font_size = base_height * 0.7
    text_path = TextPath((0, 0), text, size=font_size, prop=font_props)
    polygons_2d = text_path.to_polygons(closed_only=True)

    # 3. Validate and structure polygons with Shapely to handle holes
    # 3.1. Create Shapely polygons from the Matplotlib paths.
    raw_polygons = []
    for p in polygons_2d:
        try:
            poly = Polygon(p)
            if not poly.is_empty and poly.is_valid:
                raw_polygons.append(poly)
        except Exception:
            continue

    if not raw_polygons:
        return None

    # 3.2. Sort these polygons by area in descending order (largest first).
    sorted_polygons = sorted(raw_polygons, key=lambda p: p.area, reverse=True)

    # 3.3. Iterate through the sorted polygons to identify shells and their holes.
    shells = []
    holes = []
    for poly in sorted_polygons:
        is_hole = False
        # Check if the polygon is contained within any of the already identified shells.
        for shell in shells:
            if shell.contains(poly):
                holes.append((shell, poly))
                is_hole = True
                break  # A polygon can only be a hole for one shell.
        if not is_hole:
            shells.append(poly)  # If not a hole, it's a new shell.

    # 3.4. Reconstruct polygons with their respective holes.
    valid_polygons = []
    for shell in shells:
        shell_holes = [h.exterior for s, h in holes if s is shell]
        valid_polygons.append(Polygon(shell.exterior, shell_holes))

    # 4. Calculate positioning based on a temporary mesh
    temp_meshes = [trimesh.creation.extrude_polygon(p, height=1.0) for p in valid_polygons]
    combined_mesh = trimesh.util.concatenate(temp_meshes)
    
    text_bounds = combined_mesh.bounds
    text_height = text_bounds[1, 1] - text_bounds[0, 1]

    # Calculate translation for final positioning
    translate_x = 5.0 - text_bounds[0, 0]
    translate_y = (base_height - text_height) / 2 - text_bounds[0, 1]

    # 5. Apply translation to the 2D Shapely polygons
    positioned_polygons = []
    for poly in valid_polygons:
        coords = np.array(poly.exterior.coords)
        coords[:, 0] += translate_x
        coords[:, 1] += translate_y
        
        interiors = []
        for interior in poly.interiors:
            interior_coords = np.array(interior.coords)
            interior_coords[:, 0] += translate_x
            interior_coords[:, 1] += translate_y
            interiors.append(interior_coords)
            
        positioned_polygons.append(Polygon(coords, interiors))

    return {
        "base_width": base_width,
        "base_height": base_height,
        "base_depth": base_depth,
        "text_extrusion_height": text_extrusion_height,
        "positioned_polygons": positioned_polygons,
    }

def _create_nameplate_stl_bytes(geom_data: dict) -> bytes:
    """Generates the STL file as bytes from the common geometry data."""
    base = trimesh.creation.box(extents=[geom_data['base_width'], geom_data['base_height'], geom_data['base_depth']])
    base.apply_translation([geom_data['base_width'] / 2, geom_data['base_height'] / 2, geom_data['base_depth'] / 2])

    text_meshes = [trimesh.creation.extrude_polygon(p, height=geom_data['text_extrusion_height']) for p in geom_data['positioned_polygons']]
    text_mesh = trimesh.util.concatenate(text_meshes)
    text_mesh.apply_translation([0, 0, geom_data['base_depth']])

    final_mesh = trimesh.util.concatenate([base, text_mesh])

    with io.BytesIO() as f:
        final_mesh.export(f, file_type='stl')
        f.seek(0)
        return f.read()

def _create_nameplate_dxf_str(geom_data: dict) -> str:
    """Generates the DXF file as a string from the common geometry data."""
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    doc.layers.new(name="OUTLINE", dxfattribs={'color': 4})  # Cyan
    doc.layers.new(name="TEXT", dxfattribs={'color': 7})  # White/Black

    # Draw base rectangle
    msp.add_lwpolyline(
        [(0, 0), (geom_data['base_width'], 0), (geom_data['base_width'], geom_data['base_height']), (0, geom_data['base_height'])],
        close=True,
        dxfattribs={'layer': 'OUTLINE'}
    )

    # Draw text polygons
    for poly in geom_data['positioned_polygons']:
        msp.add_lwpolyline(list(poly.exterior.coords), close=True, dxfattribs={'layer': 'TEXT'})
        for interior in poly.interiors:
            msp.add_lwpolyline(list(interior.coords), close=True, dxfattribs={'layer': 'TEXT'})

    with io.StringIO() as s:
        doc.write(s)
        s.seek(0)
        return s.read()

def generate_production_packages(text: str):
    """
    Orchestrates the generation of STL and DXF files and bundles them into a ZIP archive.

    Args:
        text (str): The text to be placed on the nameplate.

    Returns:
        bytes: The content of the ZIP file, or None if generation fails.
    """
    try:
        if not text or not text.strip():
            return None

        # 1. Generate common geometry data
        geom_data = _generate_common_geometry(text)
        if not geom_data:
            print(f"Warning: Could not generate valid geometry for text '{text}'.")
            return None

        # 2. Create STL and DXF in memory
        stl_bytes = _create_nameplate_stl_bytes(geom_data)
        dxf_str = _create_nameplate_dxf_str(geom_data)

        # 3. Create ZIP archive in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('namensschild.stl', stl_bytes)
            zip_file.writestr('namensschild.dxf', dxf_str)
        
        zip_buffer.seek(0)
        return zip_buffer.read()

    except Exception as e:
        print(f"An error occurred in generate_production_packages: {e}")
        raise