bl_info = {
    "name": "RGBA-Style MMD Bust Rig",
    "author": "RGBA-MMD addon (port of rgba.blog.jp/archives/10475373.html)",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > N-Panel > RGBA MMD",
    "description": "Build the RGBA-style 5-rigid-body / 8-joint bust physics rig for any MMD model loaded via mmd_tools.",
    "category": "Physics",
    "warning": "Requires the mmd_tools addon to be installed and enabled.",
}

from . import properties, operators, ui


_modules = (properties, operators, ui)


def register():
    for m in _modules:
        m.register()


def unregister():
    for m in reversed(_modules):
        m.unregister()


if __name__ == "__main__":
    register()
