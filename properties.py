import bpy
from bpy.props import FloatProperty, IntProperty, BoolProperty, StringProperty, PointerProperty


class RGBAMMDSettings(bpy.types.PropertyGroup):
    main_mass: FloatProperty(
        name="Main Mass",
        description="Mass of the main bust rigid",
        default=0.5, min=0.001, max=100.0,
    )
    aux_mass: FloatProperty(
        name="Aux Mass",
        description="Mass of each auxiliary rigid (translator/rotator)",
        default=0.05, min=0.001, max=100.0,
    )
    linear_damping: FloatProperty(
        name="Linear Damping",
        default=0.7, min=0.0, max=1.0,
    )
    angular_damping: FloatProperty(
        name="Angular Damping",
        default=0.7, min=0.0, max=1.0,
    )
    spring_stiff_strong: FloatProperty(
        name="Strong Spring k",
        description="Spring stiffness for binding joints. Tuned for bust bounce ~3-5Hz on 0.5kg body.",
        default=300.0, min=0.0, max=200000.0,
    )
    spring_stiff_loose: FloatProperty(
        name="Loose Spring k",
        description="Spring stiffness on rotation-allowing axes (lower = bouncier)",
        default=50.0, min=0.0, max=200000.0,
    )
    spring_damp: FloatProperty(
        name="Spring Damping",
        description="0=no damping (rings forever), 1=critically damped (no bounce). 0.3-0.5 is bouncy.",
        default=0.4, min=0.0, max=1.0,
    )
    body_radius: FloatProperty(
        name="Body Radius",
        description="Sphere radius for the main bust rigid (auxiliaries are 0.4x). Tune to fit the bust silhouette.",
        default=0.10, min=0.001, max=1.0, subtype='DISTANCE',
    )
    pos_along_bone: FloatProperty(
        name="Position Along Bone",
        description="Where to place the chest rigid along the bust bone: 0=head (symmetric, recommended), 0.5=midpoint, 1=tail. Models with asymmetric bone directions (common in xps_to_mmd conversions) will look crooked at >0.",
        default=0.0, min=-0.5, max=1.5,
    )
    pos_offset_z: FloatProperty(
        name="Z Offset",
        description="Manual world-Z offset on top of the auto-position; raise/lower if the rigid sits too high or too low",
        default=0.0, min=-1.0, max=1.0, subtype='DISTANCE',
    )
    pos_offset_y: FloatProperty(
        name="Y Offset (Forward)",
        description="Manual world-Y offset; push the rigid forward (negative Y) into the bust if it's stuck behind the chest mesh",
        default=0.0, min=-1.0, max=1.0, subtype='DISTANCE',
    )
    collision_group: IntProperty(
        name="Collision Group",
        description="MMD collision group (1-16) used by all RGBA bodies; mask is set so they collide with nothing",
        default=15, min=1, max=16,
    )
    parent_bone_name: StringProperty(
        name="Parent Bone",
        description="Bone the bust chain attaches to. Leave blank to auto-detect (上半身2 → 上半身 → bust bone's parent)",
        default="",
    )
    overwrite: BoolProperty(
        name="Overwrite Existing",
        description="If RGBA-named rigid bodies / joints for a side already exist, delete and recreate. Default off — skip with warning.",
        default=False,
    )
    last_status: StringProperty(default="")


def register():
    bpy.utils.register_class(RGBAMMDSettings)
    bpy.types.Scene.rgba_mmd = PointerProperty(type=RGBAMMDSettings)


def unregister():
    del bpy.types.Scene.rgba_mmd
    bpy.utils.unregister_class(RGBAMMDSettings)
