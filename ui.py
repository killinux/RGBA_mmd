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

        if s.last_status:
            box = layout.box()
            for chunk in s.last_status.split(" | "):
                box.label(text=chunk)

        # === Blender Physics (RGBA Rigid Bodies) ===
        box = layout.box()
        box.label(text="Blender 物理（刚体方式）", icon='PHYSICS')
        col = box.column(align=True)
        col.operator("rgba_mmd.detect", icon="VIEWZOOM", text="检测胸部骨骼")
        col.operator("rgba_mmd.apply", icon="MOD_PHYSICS", text="应用 RGBA 刚体")
        col.operator("rgba_mmd.remove", icon="X", text="移除 RGBA 刚体")
        box.operator("rgba_mmd.toggle_rigid_vis", icon="HIDE_OFF", text="显示/隐藏刚体")

        # === Spring Simulation ===
        box = layout.box()
        box.label(text="弹簧模拟（推荐）", icon='FORCE_HARMONIC')
        col = box.column(align=True)
        col.operator("rgba_mmd.spring_sim", icon="PLAY", text="运行弹簧模拟")
        col.operator("rgba_mmd.clear_sim", icon="CANCEL", text="清除模拟关键帧")

        col = box.column(align=True)
        col.prop(s, "sim_spring_k")
        col.prop(s, "sim_damping")
        col.prop(s, "sim_mass")
        col.prop(s, "sim_scale")
        col.prop(s, "sim_parent_bone")

        # === Export ===
        box = layout.box()
        box.label(text="导出 PMX", icon='EXPORT')
        box.prop(s, "export_path", text="")
        box.operator("rgba_mmd.export_pmx", icon="FILE_TICK", text="导出带物理的 PMX")


class RGBAMMD_PT_rigid_settings(Panel):
    bl_label = "刚体参数"
    bl_idname = "RGBAMMD_PT_rigid_settings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RGBA MMD"
    bl_parent_id = "RGBAMMD_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        s = context.scene.rgba_mmd
        layout = self.layout

        box = layout.box()
        box.label(text="骨骼")
        box.prop(s, "parent_bone_name")
        box.prop(s, "overwrite")

        box = layout.box()
        box.label(text="刚体")
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
        box.label(text="关节")
        box.prop(s, "spring_stiff_strong")
        box.prop(s, "spring_stiff_loose")
        box.prop(s, "spring_damp")


_classes = (RGBAMMD_PT_main, RGBAMMD_PT_rigid_settings)


def register():
    for c in _classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
