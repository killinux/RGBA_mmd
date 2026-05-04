# RGBA-Style MMD Bust Rig (Blender addon)

Reproduces the **"RGBA式おっぱい剛体 Ver1.5β"** physics rig from
<https://rgba.blog.jp/archives/10475373.html> inside Blender, on top of
**mmd_tools**. Works on any MMD model loaded via mmd_tools.

## Requirements

- Blender 3.6 LTS or newer (tested on 3.6.15).
- **mmd_tools** addon installed and enabled (any modern build; tested on 1.0.2).
- An MMD model imported into the scene (mmd_tools creates the `mmd_root` empty
  and the bone names this addon detects).

## Install

1. Compress the `RGBA_mmd/` folder into `RGBA_mmd.zip`.
2. Blender → *Edit* → *Preferences* → *Add-ons* → *Install...* → pick the zip.
3. Tick **RGBA-Style MMD Bust Rig** in the list.

## Usage

1. Click any object inside your MMD model (mesh, bone, root empty — anything).
2. Open the 3D View N-panel → **RGBA MMD** tab.
3. *Detect* — verifies that bust bones and the parent bone (`上半身2`) are found.
4. *Apply RGBA Rig* — creates 5 rigid bodies + 8 joints per side under the
   model's `rigidbodies` / `joints` empties.
5. Press the *Play* button in the timeline; the chest should oscillate naturally
   under the model's own movement.

To revert: *Remove RGBA Rig* deletes only the objects this addon created
(matched by their `胸_…` / `_RGBAanchor` name pattern).

## What it builds, per side

| Object | Role | Dynamics | Bone link |
|---|---|---|---|
| `胸.L`           | main visible bust body | DYNAMIC + bone | bust bone |
| `胸_後.L`        | translation lock helper | DYNAMIC | none |
| `胸_前.L`        | rotation helper | DYNAMIC | none |
| `胸_回転.L`      | rotation dummy | DYNAMIC | none |
| `胸_前後.L`      | front/back helper | DYNAMIC | none |
| `J.胸_後1.L`, `J.胸_後2.L`     | rigid–helper–main bind, all axes locked | – | – |
| `J.胸_前1.L`, `J.胸_前2.L`     | rotation chain | – | – |
| `J.胸_回転1.L`, `J.胸_回転2.L` | rotation chain | – | – |
| `J.胸_前後1.L`, `J.胸_前後2.L` | front/back chain (Y free) | – | – |

(Mirror set with `.R` for the right side. Suffix style — `.L`/`.R`,
`左`/`右`, etc. — is mirrored from your model's existing bone names where
possible.)

All RGBA bodies live in **MMD collision group 15** (configurable) with the
"collide with nothing" mask, so they don't interfere with the rest of the
model's physics.

## Bust bone detection

Matches any bone whose name contains:

- Japanese: `胸`, `乳`
- English: `bust`, `breast`, `chest`, `boob`, `oppai`, `tit`

If the model has a chain (e.g. `胸親` → `胸先`, or `boob left 1` → `boob left 2`),
the addon drives the **parent** of the chain only. Children of bust bones are
skipped automatically.

The parent anchor bone defaults to `上半身2`, falling back to `上半身`. Override
in the panel's *Parent Bone* field if your model uses different names.

## Tunables (panel)

- **Body Radius** — sphere size of the main bust rigid; auxiliaries are 0.4×.
- **Main / Aux Mass** — physical mass.
- **Linear / Angular Damping** — Bullet damping per body (blog suggests 0.5–0.999).
- **Strong / Loose Spring k** — spring stiffness for locked vs free joints.
- **Spring Damping** — joint spring damping.
- **Collision Group** — 1–16 (UI numbering); the mask is auto-set to "no collisions".

## Verified end-to-end

Tested on Blender 3.6.15 + mmd_tools 1.0.2 with an MMD model that has bust bones
named `boob left 1` / `boob right 1` (parent: `上半身2`):

- *Apply RGBA Rig* creates 11 rigid bodies + 16 joints (5 + 8 per side, plus 1
  shared parent anchor `上半身2_RGBAanchor`).
- After applying, animate `上半身2` (e.g. rotate on X over 30 frames). The chest
  rigid body lags the upper body by ~1 frame and oscillates ±0.05–0.5m in Z.
- `mmd_bonetrack` (mmd_tools' bone-tracking empty) picks up rotation and feeds
  it back into the bust bone via its existing `COPY_ROTATION` constraint
  (`mmd_tools_rigid_track`).

If you don't see bouncing on playback:

1. Make sure the **scene has a rigid body world** (Properties → Scene → Rigid
   Body World). The addon creates one if missing, but it can be removed by undo.
2. Make sure the **world is enabled** and the cache range covers your timeline.
3. Make sure something is **animating the upper body** — the bust bones jiggle in
   reaction to motion. With a static pose nothing happens.
4. If the bodies fall under gravity instead of staying anchored, raise *Strong
   Spring k* (default 5000). With Bullet, you typically need 1000–10000× the
   PMX equivalent.

## Caveats

- The original RGBA technique relies on small inaccuracies in Bullet's
  zero-limit constraint — settings that work on PMXEditor's Bullet may need
  tweaking in Blender. If the bust doesn't visibly bounce, raise *Loose Spring k*
  or lower *Damping*.
- If your model's bust bones don't match the keyword list, rename them or add
  a manual mapping in `rig_builder.py` (`BUST_KEYWORDS_*`).
- This addon does not delete or modify any rigid body / joint it didn't create
  unless you tick *Overwrite Existing*.

## License

MIT — do whatever, just don't blame us when bones explode.
