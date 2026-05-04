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

        layout.operator("rgba_mmd.detect", icon="VIEWZOOM", text="检测胸部骨骼")
        layout.operator("rgba_mmd.toggle_rigid_vis", icon="HIDE_OFF", text="显示/隐藏刚体")


class RGBAMMD_PT_simple(Panel):
    bl_label = "简单物理（推荐）"
    bl_idname = "RGBAMMD_PT_simple"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RGBA MMD"
    bl_parent_id = "RGBAMMD_PT_main"

    def draw(self, context):
        s = context.scene.rgba_mmd
        layout = self.layout

        layout.label(text="参考 Purifier Inase 18 方案", icon='INFO')
        layout.label(text="type=1 Dynamic, 无弹簧, Blender 有效")

        col = layout.column(align=True)
        col.operator("rgba_mmd.simple_physics", icon="PLAY", text="应用简单物理")
        col.operator("rgba_mmd.remove_simple", icon="X", text="移除简单物理")

        box = layout.box()
        box.prop(s, "simple_mass")
        box.prop(s, "simple_damping")
        box.prop(s, "simple_radius")
        box.prop(s, "simple_angle_limit")
        box.prop(s, "simple_collision_group")


class RGBAMMD_PT_spring_sim(Panel):
    bl_label = "弹簧模拟（关键帧）"
    bl_idname = "RGBAMMD_PT_spring_sim"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RGBA MMD"
    bl_parent_id = "RGBAMMD_PT_main"

    def draw(self, context):
        s = context.scene.rgba_mmd
        layout = self.layout

        layout.label(text="数学模拟，烘焙到骨骼关键帧", icon='INFO')

        col = layout.column(align=True)
        col.operator("rgba_mmd.spring_sim", icon="FORCE_HARMONIC", text="运行弹簧模拟")
        col.operator("rgba_mmd.clear_sim", icon="CANCEL", text="清除模拟关键帧")

        box = layout.box()
        box.prop(s, "sim_spring_k")
        box.prop(s, "sim_damping")
        box.prop(s, "sim_mass")
        box.prop(s, "sim_scale")
        box.prop(s, "sim_parent_bone")


class RGBAMMD_PT_rgba_rig(Panel):
    bl_label = "RGBA 5刚体（MMD导出用）"
    bl_idname = "RGBAMMD_PT_rgba_rig"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RGBA MMD"
    bl_parent_id = "RGBAMMD_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        s = context.scene.rgba_mmd
        layout = self.layout

        layout.label(text="5刚体+8关节/侧, 零限制技巧", icon='INFO')
        layout.label(text="Blender无效, 仅用于MMD导出")

        col = layout.column(align=True)
        col.operator("rgba_mmd.apply", icon="MOD_PHYSICS", text="应用 RGBA 刚体")
        col.operator("rgba_mmd.remove", icon="X", text="移除 RGBA 刚体")

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


class RGBAMMD_PT_wiggle(Panel):
    bl_label = "Wiggle 2 物理"
    bl_idname = "RGBAMMD_PT_wiggle"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RGBA MMD"
    bl_parent_id = "RGBAMMD_PT_main"

    def draw(self, context):
        s = context.scene.rgba_mmd
        layout = self.layout

        has_wiggle = hasattr(context.scene, 'wiggle_enable')
        if not has_wiggle:
            layout.label(text="Wiggle 2 未安装", icon='ERROR')
            layout.operator("wm.url_open", text="下载 Wiggle 2", icon='URL').url = "https://github.com/shteeve3d/blender-wiggle-2"
            return

        layout.label(text="骨骼级弹簧物理，实时预览", icon='INFO')

        col = layout.column(align=True)
        col.operator("rgba_mmd.wiggle_setup", icon="PLAY", text="一键配置胸部 Wiggle")
        col.operator("rgba_mmd.wiggle_remove", icon="X", text="移除 Wiggle")
        col.operator("rgba_mmd.wiggle_bake", icon="REC", text="烘焙到关键帧")

        box = layout.box()
        box.prop(s, "wiggle_stiffness")
        box.prop(s, "wiggle_damping")
        box.prop(s, "wiggle_mass")
        box.prop(s, "wiggle_gravity")


class RGBAMMD_PT_export(Panel):
    bl_label = "导出 PMX"
    bl_idname = "RGBAMMD_PT_export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RGBA MMD"
    bl_parent_id = "RGBAMMD_PT_main"

    def draw(self, context):
        s = context.scene.rgba_mmd
        layout = self.layout
        layout.prop(s, "export_path", text="")
        layout.operator("rgba_mmd.export_pmx", icon="FILE_TICK", text="导出带物理的 PMX")


_classes = (RGBAMMD_PT_main, RGBAMMD_PT_simple, RGBAMMD_PT_spring_sim,
            RGBAMMD_PT_wiggle, RGBAMMD_PT_rgba_rig, RGBAMMD_PT_export)


def register():
    for c in _classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
