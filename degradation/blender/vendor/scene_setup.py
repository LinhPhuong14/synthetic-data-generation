# Adapted from tanguymagne/SyntheticDoc (generation/rendering/scene_setup.py), MIT License.
# See ../LICENSE. Unchanged from upstream.

import bpy
import config
from blender_utils import ensureInObjectMode


def initializeScene():
    """Empty the scene (if config.CLEAR_SCENE) and apply the configured unit system."""
    if config.VERBOSE:
        print("Initializing scene...")

    ensureInObjectMode()

    if config.CLEAR_SCENE:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        if config.VERBOSE:
            print("Scene cleared")

    bpy.context.scene.unit_settings.system = config.UNITS
    bpy.context.scene.unit_settings.scale_length = config.SCALE

    if config.VERBOSE:
        print(f"Units set to {config.UNITS} with scale {config.SCALE}")


def setupRenderSettings():
    """Configure the render engine, resolution and output format from config."""
    if config.VERBOSE:
        print("Configuring render settings...")

    scene = bpy.context.scene

    # Render engine. EEVEE was RENAMED between Blender versions: 4.2 ships
    # `BLENDER_EEVEE_NEXT` and 4.0/4.1 ship `BLENDER_EEVEE`, and asking for the
    # wrong one is a `TypeError` from `bpy_struct` deep inside the render, not a
    # readable message -- measured on Blender 4.0.2 (Ubuntu's package): `enum
    # "BLENDER_EEVEE_NEXT" not found in ('BLENDER_EEVEE', 'BLENDER_WORKBENCH',
    # 'CYCLES')`. Asked for by either name and resolved against what THIS build
    # actually has, so a config written for one Blender runs on the other.
    engine = config.RENDER_ENGINE
    available = {item.identifier for item in
                 bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    if engine not in available and engine.startswith("BLENDER_EEVEE"):
        engine = next((name for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE")
                       if name in available), engine)
    scene.render.engine = engine
    if config.VERBOSE:
        print(f"Render engine: {engine}"
              + ("" if engine == config.RENDER_ENGINE
                 else f" (asked for {config.RENDER_ENGINE}, this build has {sorted(available)})"))

    if engine == "CYCLES":
        scene.cycles.samples = config.RENDER_SAMPLES
        scene.cycles.use_denoising = config.USE_DENOISING

        # Restricted to CUDA: the dataset was rendered on NVIDIA GPUs. Cycles falls back to
        # CPU rendering if no CUDA device is present.
        cycles_preferences = bpy.context.preferences.addons["cycles"].preferences
        cycles_preferences.compute_device_type = "CUDA"
        cycles_preferences.get_devices()
        for device in cycles_preferences.devices:
            if device.type == "CUDA":
                device.use = True
                if config.VERBOSE:
                    print(f"  - Enabled: {device.name}")
            else:
                device.use = False

        scene.cycles.device = "GPU"
        scene.cycles.denoising_use_gpu = config.USE_DENOISING
        if config.VERBOSE:
            print(f"Cycles samples: {config.RENDER_SAMPLES}")
            print(f"Denoising {'enabled' if config.USE_DENOISING else 'disabled'}")

    elif engine.startswith("BLENDER_EEVEE"):
        # Same property name on both generations of EEVEE.
        scene.eevee.taa_render_samples = config.RENDER_SAMPLES
        if config.VERBOSE:
            print(f"EEVEE samples: {config.RENDER_SAMPLES}")

    else:
        raise ValueError(
            f"Unsupported config.RENDER_ENGINE '{config.RENDER_ENGINE}'. "
            f"Expected 'CYCLES' or EEVEE; this build has {sorted(available)}."
        )

    # Resolution
    scene.render.resolution_x = config.RESOLUTION_X
    scene.render.resolution_y = config.RESOLUTION_Y
    scene.render.resolution_percentage = config.RESOLUTION_PERCENTAGE

    if config.VERBOSE:
        print(f"Resolution: {config.RESOLUTION_X}x{config.RESOLUTION_Y}")

    # Output format
    scene.render.image_settings.file_format = config.FILE_FORMAT
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = config.COLOR_DEPTH

    if config.FILE_FORMAT == "PNG":
        scene.render.image_settings.compression = config.COMPRESSION

    if config.VERBOSE:
        print(f"Output format: {config.FILE_FORMAT}")

    # Opaque film keeps the table visible behind the paper.
    scene.render.film_transparent = False

    # Color management
    # Standard leaves the render untone-mapped, so pixel values stay comparable to the
    # document texture and the ground-truth maps. Filmic would remap them.
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"

    if config.VERBOSE:
        print("Render settings configured successfully\n")


def setupWorld(hdri_path=None, background_color=(0.01, 0.01, 0.01), strength=0.3):
    """Light the world from an HDRI if one is given, otherwise from a flat colour."""
    if config.VERBOSE:
        print("Setting up world environment...")

    world = bpy.context.scene.world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links

    nodes.clear()

    node_background = nodes.new(type="ShaderNodeBackground")
    node_output = nodes.new(type="ShaderNodeOutputWorld")

    if hdri_path:
        node_env = nodes.new(type="ShaderNodeTexEnvironment")
        node_env.image = bpy.data.images.load(hdri_path)
        links.new(node_env.outputs["Color"], node_background.inputs["Color"])
        node_background.inputs["Strength"].default_value = strength
        if config.VERBOSE:
            print(f"HDRI environment loaded: {hdri_path}")
    else:
        node_background.inputs["Color"].default_value = (*background_color, 1.0)
        node_background.inputs["Strength"].default_value = strength
        if config.VERBOSE:
            print(f"Background color: {background_color}, strength: {strength}")

    links.new(node_background.outputs["Background"], node_output.inputs["Surface"])

    if config.VERBOSE:
        print("World environment setup complete\n")


def prepareScene():
    """Run the full scene preparation; call once before rendering a sample."""
    initializeScene()
    setupRenderSettings()
    setupWorld()

    if config.VERBOSE:
        print("=" * 50)
        print("Scene preparation complete!")
        print("=" * 50 + "\n")
