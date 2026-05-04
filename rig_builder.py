"""Pure logic for building the RGBA-style bust rig.

Creates 5 rigid bodies + 8 joints per side, faithful to
https://rgba.blog.jp/archives/10475373.html, using mmd_tools' Model API.

Bodies (suffix .L / .R):
    胸_main           bound to bust bone, dynamics_type=2 (physics + bone)
    胸_後              translation lock helper, no bone, dynamics_type=1
    胸_前              rotation helper, no bone, dynamics_type=1
    胸_回転             rotation dummy, no bone, dynamics_type=1
    胸_前後             front/back helper, no bone, dynamics_type=1

Per-side joints attach in pairs: each helper is anchored to the parent
(`上半身2` rigid) and to the main bust rigid, with limits set to 0/0 to clamp
movement — the physics solver still produces oscillations that animate the bone.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

import bpy
from mathutils import Vector


# -- bone naming detection --------------------------------------------------

BUST_KEYWORDS_JP = ("胸", "乳")
BUST_KEYWORDS_EN = ("bust", "breast", "chest", "boob", "oppai", "tit")
PARENT_BONE_CANDIDATES = ("上半身2", "上半身", "Upper body 2", "Upper Body 2", "upper body 2")


def _is_bust_bone(name: str) -> bool:
    if any(k in name for k in BUST_KEYWORDS_JP):
        return True
    ln = name.lower()
    return any(k in ln for k in BUST_KEYWORDS_EN)


def _side_of(name: str) -> Optional[str]:
    """Return 'L' or 'R' or None based on bone naming."""
    if name.endswith(".L") or name.endswith("_L") or name.endswith(" L"):
        return "L"
    if name.endswith(".R") or name.endswith("_R") or name.endswith(" R"):
        return "R"
    if "左" in name:
        return "L"
    if "右" in name:
        return "R"
    ln = name.lower()
    if "left" in ln:
        return "L"
    if "right" in ln:
        return "R"
    return None


def detect_bust_bones(armature_obj) -> List[Tuple[str, Optional[str]]]:
    """Return [(bone_name, side_or_None)] for plausible bust bones, ordered: drive bones first.

    A 'drive bone' is the parent in a chain (e.g. 胸親 vs 胸先, or 'boob left 1' vs 'boob left 2').
    We pick bones whose parent is *not* itself a bust bone."""
    bones = armature_obj.data.bones
    bust = [b for b in bones if _is_bust_bone(b.name)]
    drive = [b for b in bust if not (b.parent and _is_bust_bone(b.parent.name))]
    return [(b.name, _side_of(b.name)) for b in drive]


def find_parent_bone(armature_obj, override: str = "") -> Optional[str]:
    if override:
        return override if override in armature_obj.data.bones else None
    for cand in PARENT_BONE_CANDIDATES:
        if cand in armature_obj.data.bones:
            return cand
    return None


# -- mmd model resolution ---------------------------------------------------

def find_mmd_root(scene_or_active) -> Optional[bpy.types.Object]:
    """Walk up from active object to find an mmd_root EMPTY; fall back to scan."""
    obj = getattr(scene_or_active, "active_object", None) if hasattr(scene_or_active, "active_object") else scene_or_active
    cur = obj
    while cur is not None:
        try:
            if cur.mmd_type == "ROOT":
                return cur
        except AttributeError:
            pass
        cur = cur.parent
    for o in bpy.data.objects:
        if o.type == "EMPTY":
            try:
                if o.mmd_type == "ROOT":
                    return o
            except AttributeError:
                pass
    return None


def find_armature(mmd_root) -> Optional[bpy.types.Object]:
    for c in mmd_root.children:
        if c.type == "ARMATURE":
            return c
    # fallback: any armature whose root walks up to mmd_root
    for o in bpy.data.objects:
        if o.type == "ARMATURE":
            cur = o
            while cur is not None:
                if cur is mmd_root:
                    return o
                cur = cur.parent
    return None


# -- rigid body / joint construction ----------------------------------------

def _make_no_collision_mask(group_index_zero_based: int):
    """Mask that turns OFF collisions with every group (incl. self). 16 booleans."""
    return [True] * 16  # True == "do not collide with this group" in mmd_tools convention


def _bust_bone_world_pos(arm_obj, bone_name: str, t: float = 0.5,
                          z_off: float = 0.0, y_off: float = 0.0) -> Vector:
    """Position along the bust bone in world space.
    t = 0 → bone head (rib cage); t = 0.5 → midpoint (bust volume centre);
    t = 1 → bone tail (nipple). z_off / y_off are manual world offsets."""
    bone = arm_obj.data.bones[bone_name]
    local = bone.head_local.lerp(bone.tail_local, t)
    world = arm_obj.matrix_world @ local
    world.z += z_off
    world.y += y_off
    return world


def _bust_bone_world_rotation(arm_obj, bone_name: str):
    """World-space Euler rotation of the bone's rest matrix. Used so the rigid
    body and joint reference frame are aligned with the bone's local axes,
    otherwise limits are world-axis aligned and the chest tilts visibly."""
    bone = arm_obj.data.bones[bone_name]
    world_mat = arm_obj.matrix_world @ bone.matrix_local
    return tuple(world_mat.to_euler('XYZ'))


def _existing_rigid_for_bone(model, bone_name: str):
    for rb in model.rigidBodies():
        try:
            if rb.mmd_rigid.bone == bone_name:
                return rb
        except Exception:
            continue
    return None


def _ensure_parent_rigid(model, arm_obj, parent_bone_name: str, group_idx_zero: int):
    """Find existing rigid bound to parent_bone_name, else create a STATIC sphere on it."""
    rb = _existing_rigid_for_bone(model, parent_bone_name)
    if rb:
        return rb
    # parent anchor sits at the upper-body bone HEAD (not midpoint) so it
    # tracks the rib-cage origin
    pos = _bust_bone_world_pos(arm_obj, parent_bone_name, t=0.0)
    rb = model.createRigidBody(
        name=f"{parent_bone_name}_RGBAanchor",
        shape_type=0,
        location=tuple(pos),
        rotation=(0, 0, 0),
        size=(0.05, 0.05, 0.05),
        dynamics_type=0,  # STATIC, follows bone
        collision_group_number=group_idx_zero,
        collision_group_mask=_make_no_collision_mask(group_idx_zero),
        bone=parent_bone_name,
        mass=1.0,
    )
    return rb


def _zero_vec3():
    return (0.0, 0.0, 0.0)


def _tiny_lin(r=0.005):
    """Small linear wiggle range — keeps the body inside a few mm of rest while
    letting the spring solver express oscillation."""
    return (r, r, r)


def _tiny_rot(r=0.02):
    return (r, r, r)


def _full_rot():
    # large enough to be effectively unlocked
    return (math.pi, math.pi, math.pi)


# -- main: build one side ---------------------------------------------------

def build_side(
    model,
    arm_obj,
    bust_bone_name: str,
    parent_bone_name: str,
    side_suffix: str,  # ".L" or ".R" or ""  (mirrored from existing names)
    settings,
) -> List[str]:
    """Build the 5 rigid bodies + 8 joints for one side. Returns names of created objects."""
    created: List[str] = []
    grp = settings.collision_group - 1  # UI 1-16 → index 0-15
    mask = _make_no_collision_mask(grp)

    pos = _bust_bone_world_pos(arm_obj, bust_bone_name,
                               t=settings.pos_along_bone,
                               z_off=settings.pos_offset_z,
                               y_off=settings.pos_offset_y)
    main_size = (settings.body_radius,) * 3
    aux_size = (settings.body_radius * 0.4,) * 3

    # parent anchor
    parent_rb = _ensure_parent_rigid(model, arm_obj, parent_bone_name, grp)

    # NOTE: world-axis-aligned rotation (0,0,0). Setting rotation to match the
    # bone's rest orientation makes Dynamic+Bone's COPY_ROTATION cascade explode
    # under animation in the PMX-exported model — chest goes to ±1000m. The
    # axis-aligned trade-off is that the rigid body silhouette doesn't tilt with
    # the bone, but physics stays sane.
    common_rb = dict(
        shape_type=0,
        location=tuple(pos),
        rotation=(0, 0, 0),
        collision_group_number=grp,
        collision_group_mask=mask,
        linear_damping=settings.linear_damping,
        angular_damping=settings.angular_damping,
    )

    # main rigid (bound to bust bone, dynamic+bone)
    main = model.createRigidBody(
        name=f"胸{side_suffix}" if side_suffix else f"{bust_bone_name}_RGBA",
        size=main_size,
        dynamics_type=2,
        bone=bust_bone_name,
        mass=settings.main_mass,
        **common_rb,
    )
    created.append(main.name)

    # auxiliaries
    aux_specs = [
        ("後", "translation_lock"),
        ("前", "rotation_helper"),
        ("回転", "rotation_dummy"),
        ("前後", "front_back_helper"),
    ]
    aux: dict = {}
    for jp, _label in aux_specs:
        rb = model.createRigidBody(
            name=f"胸_{jp}{side_suffix}",
            size=aux_size,
            dynamics_type=1,
            bone="",
            mass=settings.aux_mass,
            **common_rb,
        )
        aux[jp] = rb
        created.append(rb.name)

    # joints
    sl_loose = (settings.spring_stiff_loose,) * 3
    sl_strong = (settings.spring_stiff_strong,) * 3
    sa_loose = (settings.spring_stiff_loose * 0.5,) * 3
    sa_strong = (settings.spring_stiff_strong,) * 3

    common_j = dict(
        location=tuple(pos),
        rotation=(0, 0, 0),  # world-aligned (rotation propagation breaks under animation)
    )
    # Tiny wiggle range for "locked" axes — Blender's Bullet treats limit 0/0
    # with springs as a soft constraint that fast animation will yank apart, so
    # we use a few-mm clamp instead. The strong springs pull back to rest within
    # this window, producing the leak that becomes visible jiggle.
    tlin = _tiny_lin(0.005)
    trot = _tiny_rot(0.02)
    nlin = tuple(-x for x in tlin)
    nrot = tuple(-x for x in trot)
    full = _full_rot()
    nfull = tuple(-x for x in full)

    # 後1: parent → 胸_後  ALL CLAMPED (tight lin/ang wiggle)
    j = model.createJoint(
        name=f"胸_後1{side_suffix}",
        rigid_a=parent_rb, rigid_b=aux["後"],
        maximum_location=tlin, minimum_location=nlin,
        maximum_rotation=trot, minimum_rotation=nrot,
        spring_linear=sl_strong, spring_angular=sa_strong,
        **common_j,
    )
    created.append(j.name)
    # 後2: 胸_後 → 胸  ALL CLAMPED
    j = model.createJoint(
        name=f"胸_後2{side_suffix}",
        rigid_a=aux["後"], rigid_b=main,
        maximum_location=tlin, minimum_location=nlin,
        maximum_rotation=trot, minimum_rotation=nrot,
        spring_linear=sl_strong, spring_angular=sa_strong,
        **common_j,
    )
    created.append(j.name)
    # 前1: parent → 胸_前  rot UNLOCKED, lin tight
    j = model.createJoint(
        name=f"胸_前1{side_suffix}",
        rigid_a=parent_rb, rigid_b=aux["前"],
        maximum_location=tlin, minimum_location=nlin,
        maximum_rotation=full, minimum_rotation=nfull,
        spring_linear=sl_strong, spring_angular=sa_loose,
        **common_j,
    )
    created.append(j.name)
    # 前2: 胸_前 → 胸_回転  ALL CLAMPED
    j = model.createJoint(
        name=f"胸_前2{side_suffix}",
        rigid_a=aux["前"], rigid_b=aux["回転"],
        maximum_location=tlin, minimum_location=nlin,
        maximum_rotation=trot, minimum_rotation=nrot,
        spring_linear=sl_strong, spring_angular=sa_strong,
        **common_j,
    )
    created.append(j.name)
    # 回転1: parent → 胸_回転  rot UNLOCKED, lin tight
    j = model.createJoint(
        name=f"胸_回転1{side_suffix}",
        rigid_a=parent_rb, rigid_b=aux["回転"],
        maximum_location=tlin, minimum_location=nlin,
        maximum_rotation=full, minimum_rotation=nfull,
        spring_linear=sl_strong, spring_angular=sa_loose,
        **common_j,
    )
    created.append(j.name)
    # 回転2: 胸_回転 → 胸  ALL CLAMPED
    j = model.createJoint(
        name=f"胸_回転2{side_suffix}",
        rigid_a=aux["回転"], rigid_b=main,
        maximum_location=tlin, minimum_location=nlin,
        maximum_rotation=trot, minimum_rotation=nrot,
        spring_linear=sl_strong, spring_angular=sa_strong,
        **common_j,
    )
    created.append(j.name)
    # 前後1: parent → 胸_前後  Y a bit looser, X/Z tight
    yfree = settings.body_radius * 0.5
    j = model.createJoint(
        name=f"胸_前後1{side_suffix}",
        rigid_a=parent_rb, rigid_b=aux["前後"],
        maximum_location=(tlin[0], yfree, tlin[2]),
        minimum_location=(nlin[0], -yfree, nlin[2]),
        maximum_rotation=trot, minimum_rotation=nrot,
        spring_linear=sl_strong, spring_angular=sa_strong,
        **common_j,
    )
    created.append(j.name)
    # 前後2: 胸_前後 → 胸  ALL CLAMPED
    j = model.createJoint(
        name=f"胸_前後2{side_suffix}",
        rigid_a=aux["前後"], rigid_b=main,
        maximum_location=tlin, minimum_location=nlin,
        maximum_rotation=trot, minimum_rotation=nrot,
        spring_linear=sl_strong, spring_angular=sa_strong,
        **common_j,
    )
    created.append(j.name)

    return created


# -- name patterns for skip/remove ------------------------------------------

RGBA_NAME_TOKENS = ("胸_後", "胸_前", "胸_回転", "胸_前後", "_RGBA", "_RGBAanchor")


def is_rgba_object(obj) -> bool:
    n = obj.name
    if any(tok in n for tok in RGBA_NAME_TOKENS):
        return True
    # joints are prefixed J. by mmd_tools
    if n.startswith("J.") and any(tok in n for tok in RGBA_NAME_TOKENS):
        return True
    return False


def side_already_built(model, side_suffix: str) -> bool:
    needle = f"胸_後{side_suffix}"
    for rb in model.rigidBodies():
        if needle in rb.name:
            return True
    for j in model.joints():
        if needle in j.name:
            return True
    return False


def iter_rgba_joints():
    """Yield every joint object created by this addon (matched by name pattern)."""
    for o in bpy.data.objects:
        if o.name.startswith("J.") and any(tok in o.name for tok in RGBA_NAME_TOKENS):
            yield o


def remove_rgba_objects(model) -> int:
    rm = []
    for rb in list(model.rigidBodies()):
        if is_rgba_object(rb):
            rm.append(rb)
    for j in list(model.joints()):
        if is_rgba_object(j):
            rm.append(j)
    for o in rm:
        bpy.data.objects.remove(o, do_unlink=True)
    return len(rm)
