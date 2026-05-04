import bpy
from bpy.types import Operator

from . import rig_builder


def _get_model_or_report(self, context):
    try:
        from mmd_tools.core.model import Model
    except ImportError:
        self.report({'ERROR'}, "mmd_tools is not installed/enabled. Install it first.")
        return None, None, None
    root = rig_builder.find_mmd_root(context)
    if root is None:
        self.report({'ERROR'}, "No MMD model found. Select an object inside an MMD model first.")
        return None, None, None
    arm = rig_builder.find_armature(root)
    if arm is None:
        self.report({'ERROR'}, f"MMD model '{root.name}' has no armature child.")
        return None, None, None
    return Model(root), root, arm


class RGBAMMD_OT_detect(Operator):
    bl_idname = "rgba_mmd.detect"
    bl_label = "Detect MMD Bust Bones"
    bl_description = "Scan the active MMD model for bust bones and a parent (上半身2)"
    bl_options = {'REGISTER'}

    def execute(self, context):
        s = context.scene.rgba_mmd
        model, root, arm = _get_model_or_report(self, context)
        if model is None:
            s.last_status = "No MMD model"
            return {'CANCELLED'}
        bones = rig_builder.detect_bust_bones(arm)
        parent = rig_builder.find_parent_bone(arm, s.parent_bone_name)
        if not bones:
            s.last_status = f"No bust bones found in '{arm.name}' (try renaming bones to include 胸/bust/breast)"
            self.report({'WARNING'}, s.last_status)
            return {'CANCELLED'}
        sides = ", ".join(f"{n}({sd or '?'})" for n, sd in bones)
        s.last_status = f"Model='{root.name}' arm='{arm.name}' parent={parent or 'NOT FOUND'} bust=[{sides}]"
        self.report({'INFO'}, s.last_status)
        return {'FINISHED'}


class RGBAMMD_OT_apply(Operator):
    bl_idname = "rgba_mmd.apply"
    bl_label = "Apply RGBA Rig"
    bl_description = "Build the 5-rigid-body / 8-joint RGBA bust rig for each detected side"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.rgba_mmd
        model, root, arm = _get_model_or_report(self, context)
        if model is None:
            return {'CANCELLED'}
        bones = rig_builder.detect_bust_bones(arm)
        parent = rig_builder.find_parent_bone(arm, s.parent_bone_name)
        if not bones:
            self.report({'ERROR'}, "No bust bones detected.")
            return {'CANCELLED'}
        if not parent:
            self.report({'ERROR'}, "No parent bone found (上半身2). Set Parent Bone manually.")
            return {'CANCELLED'}

        created = []
        skipped = []
        for bone_name, side in bones:
            suffix = f".{side}" if side else ""
            if rig_builder.side_already_built(model, suffix):
                if not s.overwrite:
                    skipped.append(bone_name)
                    continue
                rig_builder.remove_rgba_objects(model)  # full sweep on overwrite
            try:
                names = rig_builder.build_side(model, arm, bone_name, parent, suffix, s)
                created.extend(names)
            except Exception as e:
                self.report({'ERROR'}, f"Failed for bone '{bone_name}': {e}")
                raise

        # Wire up bone-rigid linkages via mmd_tools' own build_rig operator.
        # This creates the `mmd_tools_rigid_parent` empty under the armature,
        # parents STATIC bodies to bones via Blender constraints, and registers
        # everything with the scene's rigid_body_world.
        try:
            # ensure the rigid body world exists; build_rig assumes it
            if context.scene.rigidbody_world is None:
                bpy.ops.rigidbody.world_add()
            # build_rig must execute on the model root selection
            prev_active = context.view_layer.objects.active
            context.view_layer.objects.active = root
            try:
                bpy.ops.mmd_tools.build_rig()
            finally:
                context.view_layer.objects.active = prev_active
            # build_rig may leave the world disabled; re-enable it
            if context.scene.rigidbody_world is not None:
                w = context.scene.rigidbody_world
                w.enabled = True
                # bump solver quality so hard limits hold under fast animation
                if w.substeps_per_frame < 60:
                    w.substeps_per_frame = 60
                if w.solver_iterations < 60:
                    w.solver_iterations = 60
                pc = w.point_cache
                if pc is not None:
                    pc.frame_start = max(1, context.scene.frame_start)
                    pc.frame_end = max(pc.frame_start + 60, context.scene.frame_end)
            # Post-process the joints. Use GENERIC (no spring) as a hard
            # positional clamp on the locked axes — Bullet treats spring-less
            # GENERIC limits as a real constraint, while GENERIC_SPRING with
            # springs enabled is just a soft restoration that fast animation
            # easily yanks apart. Joints whose name carries a free axis token
            # (前1, 回転1, 前後1) keep their wider limit so rotation/Y-trans
            # remains free.
            for j in rig_builder.iter_rgba_joints():
                rbc = j.rigid_body_constraint
                if rbc is None:
                    continue
                rbc.type = 'GENERIC'
                # Disable any spring flags inherited from createJoint
                for ax in ("x", "y", "z"):
                    if hasattr(rbc, "use_spring_" + ax):
                        setattr(rbc, "use_spring_" + ax, False)
                    if hasattr(rbc, "use_spring_ang_" + ax):
                        setattr(rbc, "use_spring_ang_" + ax, False)
            # Free any stale physics cache from prior failed runs
            try:
                bpy.ops.ptcache.free_bake_all()
            except Exception:
                pass
        except Exception as e:
            self.report({'WARNING'}, f"build_rig wiring failed: {e}")

        msg_parts = [f"Created {len(created)} objects across {len(bones) - len(skipped)} side(s)"]
        if skipped:
            msg_parts.append(f"skipped existing: {', '.join(skipped)}")
        s.last_status = " | ".join(msg_parts)
        self.report({'INFO'}, s.last_status)
        return {'FINISHED'}


class RGBAMMD_OT_remove(Operator):
    bl_idname = "rgba_mmd.remove"
    bl_label = "Remove RGBA Rig"
    bl_description = "Delete every rigid body / joint created by this addon (matched by name pattern)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.rgba_mmd
        model, root, arm = _get_model_or_report(self, context)
        if model is None:
            return {'CANCELLED'}
        n = rig_builder.remove_rgba_objects(model)
        s.last_status = f"Removed {n} RGBA-rig objects"
        self.report({'INFO'}, s.last_status)
        return {'FINISHED'}


_classes = (RGBAMMD_OT_detect, RGBAMMD_OT_apply, RGBAMMD_OT_remove)


def register():
    for c in _classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
