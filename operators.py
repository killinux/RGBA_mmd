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


class RGBAMMD_OT_spring_sim(Operator):
    bl_idname = "rgba_mmd.spring_sim"
    bl_label = "Spring Simulate"
    bl_description = "数学弹簧模拟：将弹跳效果烘焙到胸部骨骼关键帧（推荐方式）"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import math
        s = context.scene.rgba_mmd
        model, root, arm = _get_model_or_report(self, context)
        if arm is None:
            # fallback: find any armature
            arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
            if arm is None:
                self.report({'ERROR'}, "No armature found.")
                return {'CANCELLED'}

        scn = context.scene
        if arm.animation_data is None or arm.animation_data.action is None:
            self.report({'ERROR'}, "No animation on armature. Load a VMD first.")
            return {'CANCELLED'}

        # find parent bone
        parent_name = s.sim_parent_bone.strip()
        if not parent_name:
            for cand in ("上半身2", "上半身", "Upper body 2", "Upper Body 2"):
                if cand in arm.pose.bones:
                    parent_name = cand
                    break
        if not parent_name or parent_name not in arm.pose.bones:
            self.report({'ERROR'}, f"Parent bone '{parent_name}' not found.")
            return {'CANCELLED'}

        # find bust bones
        bust_bones = rig_builder.detect_bust_bones(arm)
        if not bust_bones:
            self.report({'ERROR'}, "No bust bones detected.")
            return {'CANCELLED'}

        parent_bone = arm.pose.bones[parent_name]
        fr = arm.animation_data.action.frame_range
        frame_start = int(fr[0])
        frame_end = int(fr[1])

        # record parent rotation per frame
        frames = list(range(frame_start, frame_end + 1))
        px, py, pz = [], [], []
        for f in frames:
            scn.frame_set(f)
            bpy.context.view_layer.update()
            mat = arm.matrix_world @ parent_bone.matrix
            rot = mat.to_euler()
            px.append(rot.x)
            py.append(rot.y)
            pz.append(rot.z)

        # spring simulation
        K = s.sim_spring_k
        D = s.sim_damping
        M = s.sim_mass
        SC = s.sim_scale
        DT = 1.0 / (scn.render.fps or 30)

        def spring_sim(targets):
            pos = targets[0]
            vel = 0.0
            deltas = []
            for t in targets:
                force = K * (t - pos) - D * vel
                vel += (force / M) * DT
                pos += vel * DT
                deltas.append((pos - t) * SC)
            return deltas

        dx = spring_sim(px)
        dz = spring_sim(pz)

        # apply to bust bones
        count = 0
        for bone_name, side in bust_bones:
            bone = arm.pose.bones[bone_name]
            bone.rotation_mode = 'XYZ'
            for i, f in enumerate(frames):
                bone.rotation_euler.x = dx[i]
                bone.rotation_euler.y = 0
                bone.rotation_euler.z = dz[i]
                bone.keyframe_insert(data_path="rotation_euler", frame=f)
            count += 1

        max_dx = max(abs(v) for v in dx)
        max_dz = max(abs(v) for v in dz)
        s.last_status = f"Spring sim: {count} bones, {len(frames)} frames, max Δx={math.degrees(max_dx):.1f}° Δz={math.degrees(max_dz):.1f}°"
        self.report({'INFO'}, s.last_status)
        return {'FINISHED'}


class RGBAMMD_OT_clear_sim(Operator):
    bl_idname = "rgba_mmd.clear_sim"
    bl_label = "Clear Simulation"
    bl_description = "清除胸部骨骼上的弹簧模拟关键帧"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.rgba_mmd
        arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
        if arm is None or arm.animation_data is None:
            self.report({'ERROR'}, "No armature or animation.")
            return {'CANCELLED'}

        action = arm.animation_data.action
        bust_bones = rig_builder.detect_bust_bones(arm)
        removed = 0
        for bone_name, side in bust_bones:
            for axis in range(3):
                dp = f'pose.bones["{bone_name}"].rotation_euler'
                fc = action.fcurves.find(dp, index=axis)
                if fc:
                    action.fcurves.remove(fc)
                    removed += 1
            bone = arm.pose.bones[bone_name]
            bone.rotation_mode = 'XYZ'
            bone.rotation_euler = (0, 0, 0)

        s.last_status = f"Cleared {removed} fcurves from {len(bust_bones)} bust bones"
        self.report({'INFO'}, s.last_status)
        return {'FINISHED'}


class RGBAMMD_OT_export_pmx(Operator):
    bl_idname = "rgba_mmd.export_pmx"
    bl_label = "Export PMX"
    bl_description = "导出带RGBA物理的PMX文件（可在MMD中使用）"
    bl_options = {'REGISTER'}

    def execute(self, context):
        import os
        try:
            from mmd_tools.core.model import Model
            from mmd_tools.core.pmx.exporter import export as pmx_export
        except ImportError:
            self.report({'ERROR'}, "mmd_tools not installed.")
            return {'CANCELLED'}

        s = context.scene.rgba_mmd
        path = bpy.path.abspath(s.export_path.strip())
        if not path or not path.lower().endswith('.pmx'):
            self.report({'ERROR'}, "Set a valid .pmx export path first.")
            return {'CANCELLED'}

        root = rig_builder.find_mmd_root(context)
        if root is None:
            self.report({'ERROR'}, "No MMD model found.")
            return {'CANCELLED'}

        model = Model(root)
        pmx_export(
            filepath=path, scale=1.0, root=root,
            armature=model.armature(),
            meshes=list(model.meshes()),
            rigid_bodies=list(model.rigidBodies()),
            joints=list(model.joints()),
            copy_textures=False, sort_materials=False,
            disable_specular=False, sort_vertices='NONE',
        )

        size = os.path.getsize(path)
        rb = len(list(model.rigidBodies()))
        jt = len(list(model.joints()))
        s.last_status = f"Exported: {os.path.basename(path)} ({size/1024:.0f}KB, {rb} rigids, {jt} joints)"
        self.report({'INFO'}, s.last_status)
        return {'FINISHED'}


class RGBAMMD_OT_toggle_rigid_vis(Operator):
    bl_idname = "rgba_mmd.toggle_rigid_vis"
    bl_label = "Toggle Rigid Bodies"
    bl_description = "切换刚体/关节在视图中的显示/隐藏"
    bl_options = {'REGISTER'}

    def execute(self, context):
        visible = None
        count = 0
        for o in bpy.data.objects:
            if o.rigid_body or (o.rigid_body_constraint and "胸" in o.name):
                if visible is None:
                    visible = o.hide_viewport
                o.hide_viewport = not visible
                count += 1
            elif hasattr(o, 'mmd_type') and o.mmd_type in ('RIGID_BODY', 'JOINT_GRP_OBJ', 'RIGID_GRP_OBJ'):
                if visible is None:
                    visible = o.hide_viewport
                o.hide_viewport = not visible
                count += 1

        state = "显示" if visible else "隐藏"
        context.scene.rgba_mmd.last_status = f"刚体{state}: {count} objects"
        self.report({'INFO'}, f"Rigid bodies: {state}")
        return {'FINISHED'}


class RGBAMMD_OT_simple_physics(Operator):
    bl_idname = "rgba_mmd.simple_physics"
    bl_label = "Apply Simple Physics"
    bl_description = "简单刚体：每侧 1 个动态球体 + 1 个关节（参考 Purifier Inase 18 方案，Blender 中有效）"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import math
        try:
            from mmd_tools.core.model import Model
        except ImportError:
            self.report({'ERROR'}, "mmd_tools not installed.")
            return {'CANCELLED'}

        s = context.scene.rgba_mmd
        root = rig_builder.find_mmd_root(context)
        if root is None:
            self.report({'ERROR'}, "No MMD model found.")
            return {'CANCELLED'}
        arm = rig_builder.find_armature(root)
        if arm is None:
            self.report({'ERROR'}, "No armature found.")
            return {'CANCELLED'}
        model = Model(root)

        bust_bones = rig_builder.detect_bust_bones(arm)
        if not bust_bones:
            self.report({'ERROR'}, "No bust bones detected.")
            return {'CANCELLED'}

        parent_name = rig_builder.find_parent_bone(arm, s.parent_bone_name)
        if not parent_name:
            self.report({'ERROR'}, "No parent bone found.")
            return {'CANCELLED'}

        def bone_pos(name):
            b = arm.data.bones[name]
            return tuple(arm.matrix_world @ b.head_local)

        grp = s.simple_collision_group - 1
        mask = [True] * 16

        parent_rb = None
        for rb in model.rigidBodies():
            if rb.mmd_rigid.bone == parent_name and rb.mmd_rigid.type == '0':
                parent_rb = rb
                break

        if parent_rb is None:
            parent_rb = model.createRigidBody(
                name=f"{parent_name}_phys",
                shape_type=2,
                location=bone_pos(parent_name),
                rotation=(0, 0, 0),
                size=(1.0, 1.0, 0.0),
                dynamics_type=0,
                collision_group_number=0,
                collision_group_mask=[True]*16,
                bone=parent_name,
                mass=1.0,
                friction=0.5,
                linear_damping=0.5,
                angular_damping=0.5,
            )

        created_rb = 0
        created_j = 0
        ang_limit = math.radians(s.simple_angle_limit)

        for bone_name, side in bust_bones:
            suffix = f".{side}" if side else ""
            rb_name = f"胸{suffix}" if side else bone_name

            rb = model.createRigidBody(
                name=rb_name,
                shape_type=0,
                location=bone_pos(bone_name),
                rotation=(0, 0, 0),
                size=(s.simple_radius, 0.0, 0.0),
                dynamics_type=1,
                collision_group_number=grp,
                collision_group_mask=mask,
                bone=bone_name,
                mass=s.simple_mass,
                friction=0.5,
                linear_damping=s.simple_damping,
                angular_damping=s.simple_damping,
            )
            created_rb += 1

            model.createJoint(
                name=f"J.{rb_name}",
                rigid_a=parent_rb,
                rigid_b=rb,
                location=bone_pos(bone_name),
                rotation=(0, 0, 0),
                maximum_location=(0, 0, 0),
                minimum_location=(0, 0, 0),
                maximum_rotation=(ang_limit, ang_limit, ang_limit),
                minimum_rotation=(-ang_limit, -ang_limit, -ang_limit),
                spring_linear=(0, 0, 0),
                spring_angular=(0, 0, 0),
            )
            created_j += 1

        bpy.context.view_layer.objects.active = root
        bpy.ops.mmd_tools.build_rig()

        w = context.scene.rigidbody_world
        if w is None:
            bpy.ops.rigidbody.world_add()
            w = context.scene.rigidbody_world
        w.enabled = True

        s.last_status = f"Simple physics: {created_rb} rigids + {created_j} joints (type=1 Dynamic, ±{s.simple_angle_limit}°, no spring)"
        self.report({'INFO'}, s.last_status)
        return {'FINISHED'}


class RGBAMMD_OT_remove_simple(Operator):
    bl_idname = "rgba_mmd.remove_simple"
    bl_label = "Remove Simple Physics"
    bl_description = "移除简单刚体物理并清理追踪"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            from mmd_tools.core.model import Model
        except ImportError:
            self.report({'ERROR'}, "mmd_tools not installed.")
            return {'CANCELLED'}

        s = context.scene.rgba_mmd
        root = rig_builder.find_mmd_root(context)
        if root is None:
            self.report({'ERROR'}, "No MMD model found.")
            return {'CANCELLED'}
        arm = rig_builder.find_armature(root)
        model = Model(root)

        bpy.context.view_layer.objects.active = root
        try:
            bpy.ops.mmd_tools.clean_rig()
        except Exception:
            pass

        removed = 0
        for rb in list(model.rigidBodies()):
            bpy.data.objects.remove(rb, do_unlink=True)
            removed += 1
        for j in list(model.joints()):
            bpy.data.objects.remove(j, do_unlink=True)
            removed += 1

        if arm:
            for bone in arm.pose.bones:
                for c in list(bone.constraints):
                    if "mmd_tools_rigid" in c.name:
                        bone.constraints.remove(c)

        for o in list(bpy.data.objects):
            if "mmd_bonetrack" in o.name or "mmd_tools_rigid" in o.name:
                bpy.data.objects.remove(o, do_unlink=True)
                removed += 1

        s.last_status = f"Removed {removed} physics objects"
        self.report({'INFO'}, s.last_status)
        return {'FINISHED'}


class RGBAMMD_OT_wiggle_setup(Operator):
    bl_idname = "rgba_mmd.wiggle_setup"
    bl_label = "Setup Wiggle 2"
    bl_description = "一键配置 Wiggle 2 胸部弹跳（需要先安装 Wiggle 2 插件）"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.rgba_mmd

        if not hasattr(context.scene, 'wiggle_enable'):
            self.report({'ERROR'}, "Wiggle 2 未安装。请先从 GitHub 下载安装：\nhttps://github.com/shteeve3d/blender-wiggle-2")
            s.last_status = "错误: Wiggle 2 未安装"
            return {'CANCELLED'}

        arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
        if arm is None:
            self.report({'ERROR'}, "No armature found.")
            return {'CANCELLED'}

        bust_bones = rig_builder.detect_bust_bones(arm)
        if not bust_bones:
            self.report({'ERROR'}, "No bust bones detected. Run Detect first.")
            return {'CANCELLED'}

        context.scene.wiggle_enable = True
        arm.wiggle_enable = True

        count = 0
        for bone_name, side in bust_bones:
            bone = arm.pose.bones.get(bone_name)
            if bone is None:
                continue

            bone.wiggle_enable = True
            bone.wiggle_tail = True
            bone.wiggle_stiff = s.wiggle_stiffness
            bone.wiggle_damp = s.wiggle_damping
            bone.wiggle_mass = s.wiggle_mass
            bone.wiggle_gravity = s.wiggle_gravity
            bone.wiggle_chain = False
            count += 1

        s.last_status = f"Wiggle 2: configured {count} bust bones (stiff={s.wiggle_stiffness}, damp={s.wiggle_damping}, mass={s.wiggle_mass})"
        self.report({'INFO'}, s.last_status)
        return {'FINISHED'}


class RGBAMMD_OT_wiggle_remove(Operator):
    bl_idname = "rgba_mmd.wiggle_remove"
    bl_label = "Remove Wiggle"
    bl_description = "移除胸部骨骼上的 Wiggle 2 配置"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.rgba_mmd
        arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
        if arm is None:
            self.report({'ERROR'}, "No armature found.")
            return {'CANCELLED'}

        bust_bones = rig_builder.detect_bust_bones(arm)
        count = 0
        for bone_name, side in bust_bones:
            bone = arm.pose.bones.get(bone_name)
            if bone and hasattr(bone, 'wiggle_enable'):
                bone.wiggle_enable = False
                bone.wiggle_tail = False
                bone.wiggle_head = False
                count += 1

        s.last_status = f"Wiggle removed from {count} bones"
        self.report({'INFO'}, s.last_status)
        return {'FINISHED'}


class RGBAMMD_OT_wiggle_bake(Operator):
    bl_idname = "rgba_mmd.wiggle_bake"
    bl_label = "Bake Wiggle"
    bl_description = "将 Wiggle 2 物理烘焙到关键帧"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.rgba_mmd

        if not hasattr(context.scene, 'wiggle_enable'):
            self.report({'ERROR'}, "Wiggle 2 未安装。")
            return {'CANCELLED'}

        try:
            bpy.ops.wiggle.bake()
            s.last_status = "Wiggle baked to keyframes"
            self.report({'INFO'}, s.last_status)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Bake failed: {e}")
            return {'CANCELLED'}


_classes = (RGBAMMD_OT_detect, RGBAMMD_OT_apply, RGBAMMD_OT_remove,
            RGBAMMD_OT_spring_sim, RGBAMMD_OT_clear_sim,
            RGBAMMD_OT_export_pmx, RGBAMMD_OT_toggle_rigid_vis,
            RGBAMMD_OT_simple_physics, RGBAMMD_OT_remove_simple,
            RGBAMMD_OT_wiggle_setup, RGBAMMD_OT_wiggle_remove,
            RGBAMMD_OT_wiggle_bake)


def register():
    for c in _classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
