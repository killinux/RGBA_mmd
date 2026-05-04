import bpy
from bpy.types import Panel


class RGBAMMD_PT_main(Panel):
    bl_label = "RGBA MMD Bust Rig"
    bl_idname = "RGBAMMD_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RGBA MMD"

    def draw(self, context):
        s = context.scene.rgba_mmd
        layout = self.layout

        col = layout.column(align=True)
        col.operator("rgba_mmd.detect", icon="VIEWZOOM")
        col.operator("rgba_mmd.apply", icon="MOD_PHYSICS")
        col.operator("rgba_mmd.remove", icon="X")

        if s.last_status:
            box = layout.box()
            for chunk in s.last_status.split(" | "):
                box.label(text=chunk)

        box = layout.box()
        box.label(text="Bones")
        box.prop(s, "parent_bone_name")
        box.prop(s, "overwrite")

        box = layout.box()
        box.label(text="Bodies")
        box.prop(s, "body_radius")
        box.prop(s, "pos_along_bone")
        row = box.row(align=True)
        row.prop(s, "pos_offset_y")
        row.prop(s, "pos_offset_z")
        box.prop(s, "main_mass")
        box.prop(s, "aux_mass")
        box.prop(s, "linear_damping")
        box.prop(s, "angular_damping")
        box.prop(s, "collision_group")

        box = layout.box()
        box.label(text="Joints")
        box.prop(s, "spring_stiff_strong")
        box.prop(s, "spring_stiff_loose")
        box.prop(s, "spring_damp")


_classes = (RGBAMMD_PT_main,)


def register():
    for c in _classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
