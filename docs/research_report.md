# MMD 胸部物理在 Blender 中的技术调研报告

> 调研日期：2026-05-04

## 目录

1. [调研背景](#1-调研背景)
2. [MMD 与 Blender Bullet 引擎差异](#2-mmd-与-blender-bullet-引擎差异)
3. [RGBA 方案在 Blender 中的应用现状](#3-rgba-方案在-blender-中的应用现状)
4. [mmd_tools 物理系统分析](#4-mmd_tools-物理系统分析)
5. [行业主流解决方案](#5-行业主流解决方案)
6. [参考模型逆向分析](#6-参考模型逆向分析)
7. [实验验证结果](#7-实验验证结果)
8. [结论与建议](#8-结论与建议)
9. [参考资料](#9-参考资料)

---

## 1. 调研背景

### 1.1 目标

为 MMD 模型在 Blender 中实现可见的胸部弹跳物理效果，并确保导出 PMX 后在 MMD 中也能正常工作。

### 1.2 原始方案

RGBA 式おっぱい剛体 Ver1.5β（https://rgba.blog.jp/archives/10475373.html），使用 5 个刚体 + 8 个关节的链式结构，通过 Bullet 求解器的零限制技巧产生振荡。

### 1.3 问题

在 Blender 中应用该方案后，胸部物理不产生可见弹跳。

---

## 2. MMD 与 Blender Bullet 引擎差异

### 2.1 刚体类型映射

| MMD 类型 | 值 | Blender 映射 | 行为 |
|----------|---|-------------|------|
| 骨骼追随（Bone/Static） | 0 | kinematic=True, CHILD_OF 约束 | 完全跟随骨骼，不受物理影响 |
| 物理演算（Dynamic） | 1 | kinematic=False, 约束 Muted | 完全物理驱动，骨骼跟随刚体 |
| 物理+骨骼（Dynamic+Bone） | 2 | kinematic=False, DAMPED_TRACK | 物理驱动但保持骨骼位置约束 |

### 2.2 碰撞组机制（完全相反）

- **MMD**：勾选的组之间**不碰撞**（定义非碰撞组）
- **Blender**：共享组的刚体**会碰撞**（定义碰撞组）
- mmd_tools 通过为每对需要禁用碰撞的刚体创建临时 NON_COLLISION_CONSTRAINT 来模拟 MMD 行为
- 距离判定公式：`distance(A, B) < 1.5 × (getRigidRange(A) + getRigidRange(B)) × 0.5`

### 2.3 关节类型映射

- MMD 的 **Spring 6DOF 关节**映射到 Blender 的 **GENERIC_SPRING** 约束
- 角度限制映射存在方向反转：MMD 的 minimum_rotation → Blender 的 limit_ang_upper

### 2.4 零限制技巧差异（核心问题）

**MMD Bullet：**
- 关节限制设为 0 时，求解器精度误差产生微小振荡
- RGBA 方案利用此特性：零限制的刚体会"移动"（位移）而非旋转
- 多个辅助刚体的链式结构放大振荡效果

**Blender Bullet：**
- 零限制真正锁死，不产生振荡
- 求解器精度更高，数值泄漏极小（实测 ~0.01 单位位移）
- 即使调整弹簧、阻尼、质量等参数，物理位移仍然不可见

### 2.5 物理世界设置差异

| 参数 | MMD 默认 | Blender 推荐 |
|------|---------|-------------|
| FPS | 30 | 需手动配置 |
| Substeps Per Frame | - | 10~30（越高越精确） |
| Solver Iterations | - | 与 Substeps 相同 |

---

## 3. RGBA 方案在 Blender 中的应用现状

### 3.1 社区调研结论

**未找到 RGBA 式 5 刚体方案在 Blender 中成功实现可见弹跳的案例。** 日文、中文、英文社区的讨论一致指向同一问题：Blender Bullet 不支持零限制技巧。

### 3.2 RGBA 方案技术细节

#### 5 个刚体的作用

| 刚体 | 作用 | 动力学类型 |
|------|------|-----------|
| 胸（主体） | 绑定到胸部骨骼 | Dynamic+Bone (2) |
| 胸_後 | 上下左右移动辅助 | Dynamic (1) |
| 胸_前 | 带旋转的移动辅助 | Dynamic (1) |
| 胸_回転 | 旋转虚拟体 | Dynamic (1) |
| 胸_前後 | 前后移动辅助 | Dynamic (1) |

#### 8 个关节的连接方式

| 关节 | 连接 | 作用 |
|------|------|------|
| 胸_後1 | 上半身2 → 胸_後 | 全轴锁定 |
| 胸_後2 | 胸_後 → 胸 | 全轴锁定 |
| 胸_前1 | 上半身2 → 胸_前 | 旋转自由 |
| 胸_前2 | 胸_前 → 胸_回転 | 全轴锁定 |
| 胸_回転1 | 上半身2 → 胸_回転 | 旋转自由 |
| 胸_回転2 | 胸_回転 → 胸 | 全轴锁定 |
| 胸_前後1 | 上半身2 → 胸_前後 | Y 轴自由 |
| 胸_前後2 | 胸_前後 → 胸 | 全轴锁定 |

#### 参数调节要点（原博客）

- **刚体大小**：越小振荡越大（最小建议 0.1）
- **质量**：越大摆动越慢（"ゆっさゆっさ"），越小越容易抖动
- **阻尼**：0.5~0.999，接近 1.0 产生蓬松感（"ふわふわ"）
- **刚体/关节顺序**：在 PMX 列表中尽量靠后放置
- **Y 轴旋转**：实际最大约 ±30°（虽然设置可到 ±60°）

### 3.3 在 Blender 中失败的原因

1. **零限制技巧不适用**：Blender Bullet 精度更高
2. **COPY_ROTATION 只传旋转**：RGBA 振荡本质是位移，不是旋转
3. **Dynamic+Bone 循环依赖**：骨骼驱动刚体，刚体又复制回骨骼，物理偏移被抵消
4. **COPY_TRANSFORMS 传递不足**：父子关系在物理烘焙后的位移传递极小（实测 ~0.01 单位）

---

## 4. mmd_tools 物理系统分析

### 4.1 build_rig 工作流程

```
Model.build()
  ├── __preBuild()         → 准备数据
  ├── buildRigids()        → 处理每个刚体
  │   └── updateRigid()    → 根据类型设置约束
  │       ├── type=0: kinematic=True, 父级到骨骼
  │       ├── type=1: kinematic=False, 创建 COPY_TRANSFORMS
  │       └── type=2: kinematic=False, 创建 COPY_ROTATION
  ├── buildJoints()        → 设置关节位置
  └── __postBuild()        → 重新父级 bonetrack empty, 取消 mute 约束
```

### 4.2 关键发现

**Type 1 (Dynamic) 使用 COPY_TRANSFORMS**（位移+旋转全追踪）
**Type 2 (Dynamic+Bone) 使用 COPY_ROTATION**（仅旋转）

这是一个重要区别：Type 1 能传递位移，Type 2 不能。

### 4.3 已知问题

- mmd_tools 源码中有 TODO 注释："Dynamic+Bone 的实现被认为不正确，可能在未来版本中移除"
- Blender 2.90~2.92 版本刚体模拟结果与 2.83 不同
- 碰撞组转换性能问题（大量 NON_COLLISION_CONSTRAINT）

---

## 5. 行业主流解决方案

社区的普遍做法：**放弃 mmd_tools 自带的刚体物理，转用专门的骨骼物理插件。**

### 5.1 Wiggle 2（免费，推荐度最高）

| 项目 | 说明 |
|------|------|
| 原理 | 骨骼级弹簧物理，每帧计算拖拽/回弹 |
| 安装 | GitHub 下载 → 偏好设置安装 |
| 兼容 | Blender 4.x / 5.0，兼容 MMD 模型 |
| 价格 | 免费开源（GPL-3.0） |
| GitHub | https://github.com/shteeve3d/blender-wiggle-2 |

**使用流程：**
1. Scene Properties → 启用 Wiggle
2. 选择骨架 → 启用 Armature Wiggle
3. Pose Mode → 选择胸部骨骼
4. 启用 Bone Tail（旋转物理）
5. 调整参数 → 播放动画测试
6. 烘焙到关键帧

**推荐胸部参数：**

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| Stiffness | 200~600 | 越高越硬，越低越软 |
| Mass | 1.0~2.0 | 控制弹性 |
| Damp | 0.3~0.8 | 越高越快停止 |
| Gravity | 0.5~1.0 | 向下力 |

**注意：** v2.15 重新校准了物理属性灵敏度，修复了阻尼 >0.5 时模拟冻结的问题。选择胸部骨骼本身，不要选父骨骼。

### 5.2 BoneDynamics（Free 版免费 / Pro 版 $15）

| 项目 | 说明 |
|------|------|
| 原理 | 软体物理修改器附着在骨骼上的立方体 |
| 优势 | 预设参数（Stiff/Organic/Hair），效果更稳定一致 |
| Free 版 | 基本设置、动态旋转和拉伸、整骨碰撞 |
| Pro 版额外 | 批量调参、骨骼链创建、增强烘焙、快速预设 |
| Free 下载 | https://morelewd.gumroad.com/l/LhbhP |
| Pro 下载 | https://superhivemarket.com/products/bonedynamics |

**使用流程：**
1. 选择胸部骨骼 → Add Bone Dynamics
2. 只在骨骼尖端启用（根部不要加）
3. 调整 Mass / Stiffness / Damping
4. 播放测试 → 烘焙

### 5.3 Wobbly Wiggler（付费，最方便）

| 项目 | 说明 |
|------|------|
| 独特优势 | **不播放动画也能预览**，可直接拖拽测试 |
| 另一优势 | **可在已有动画骨骼上叠加抖动** |
| 碰撞 | 支持骨骼间碰撞和骨骼-网格碰撞 |
| 下载 | https://bartoszstyperek.gumroad.com/l/wobbly_wiggler |

### 5.4 UuuNyaa Tools 刚体转布料

| 项目 | 说明 |
|------|------|
| 原理 | 将 MMD 刚体物理转换为 Blender 布料模拟 |
| 胸部预设 | **Breast Pyramid**：高质量 + 低弯曲阻力 |
| 转换模式 | AUTO / BONE_CONSTRAINT / SURFACE_DEFORM |
| 优势 | 专门适配 MMD 模型 |

### 5.5 Jiggle Physics（Blender 官方扩展）

| 项目 | 说明 |
|------|------|
| 安装 | 直接从 Blender Extensions 平台安装 |
| 兼容 | Blender 4.2+ 到 5.0 |
| 价格 | 免费 |
| 链接 | https://extensions.blender.org/add-ons/jiggle-physics/ |

### 5.6 JiggleArmature（免费开源）

| 项目 | 说明 |
|------|------|
| 原理 | 基于位置动力学（Position Based Dynamics），无条件稳定 |
| 特性 | 帧率无关模拟，所有属性可动画化 |
| GitHub | https://github.com/cheece/JiggleArmature |

### 5.7 Rigid Body Bones（免费开源）

| 项目 | 说明 |
|------|------|
| 原理 | 利用 Blender 内置刚体引擎为骨骼添加物理 |
| 特性 | 弹簧行为、碰撞检测、文件无插件也能工作 |
| 注意 | Blender 经常崩溃，播放前务必保存 |
| GitHub | https://github.com/Pauan/blender-rigid-body-bones |

### 5.8 方案对比

| 方案 | 难度 | MMD 兼容 | 实时预览 | 碰撞 | 免费 | 推荐度 |
|------|------|---------|---------|------|------|--------|
| **Wiggle 2** | 低 | 好 | 播放时 | 有 | 免费 | ★★★★★ |
| **BoneDynamics Free** | 低 | 好 | 播放时 | 有 | 免费 | ★★★★★ |
| **Wobbly Wiggler** | 最低 | 好 | 不播放也行 | 有 | 付费 | ★★★★☆ |
| **简单物理** | 低 | 好 | 播放时 | 无 | 免费 | ★★★★☆ |
| **弹簧模拟** | 低 | 需重运行 | 播放时 | 无 | 免费 | ★★★★☆ |
| **UuuNyaa Tools** | 中 | 专用 | 播放时 | 有 | 免费 | ★★★☆☆ |
| **JiggleArmature** | 中 | 好 | 实时 | 无 | 免费 | ★★★☆☆ |
| **Rigid Body Bones** | 中 | 需注意 | 播放时 | 有 | 免费 | ★★★☆☆ |
| **RGBA 5刚体** | 高 | 仅MMD | 不可见 | 无 | 免费 | ★★☆☆☆ |

---

## 6. 参考模型逆向分析

### 6.1 Purifier Inase 18 V1.pmx（已验证在 Blender 中有效）

**胸部刚体：**

| 参数 | 值 |
|------|-----|
| 名称 | 左乳奶 / 右乳奶 |
| 类型 | type=1（Dynamic） |
| 形状 | SPHERE |
| 质量 | 1.0 |
| 摩擦 | 0.5 |
| 弹性 | 0.0 |
| 线性阻尼 | 0.5 |
| 角度阻尼 | 0.5 |
| 球半径 | 0.597 |
| 碰撞组 | 15 |
| kinematic | False |

**胸部关节：**

| 参数 | 值 |
|------|-----|
| 连接 | 上半身2（Static） → 胸（Dynamic） |
| 类型 | GENERIC_SPRING |
| 线性限制 | (0, 0, 0) — 锁定 |
| 角度限制 | ±10° 全轴 |
| 弹簧线性 | (0, 0, 0) — 无弹簧 |
| 弹簧角度 | (0, 0, 0) — 无弹簧 |

### 6.2 与 RGBA 方案对比

| 对比项 | 参考模型（有效） | RGBA 方案（无效） |
|--------|-----------------|------------------|
| 刚体数量 | 2 个 | 11 个 |
| 关节数量 | 2 个 | 16 个 |
| 刚体类型 | type=1（Dynamic） | type=2（Dynamic+Bone） |
| 关节角度 | ±10° | 0（零限制） |
| 弹簧 | 无（全 0） | 有（20~300） |
| 阻尼 | 0.5 | 0.7~0.95 |
| 结构 | 直连（父→子） | 链式（5体串联） |

### 6.3 关键结论

**简单结构 > 复杂结构**：参考模型只用 2 个刚体 + 2 个关节就实现了弹跳，RGBA 的 11 刚体 + 16 关节反而因为链式约束互相限制。

**type=1 > type=2**：type=1 (Dynamic) 通过 COPY_TRANSFORMS 传递位移+旋转；type=2 (Dynamic+Bone) 通过 COPY_ROTATION 只传旋转，且存在循环依赖。

**无弹簧 > 有弹簧**：弹簧会将刚体拉回中心位置，减少可见位移。无弹簧时刚体在角度限制内自由运动，惯性产生自然摆动。

---

## 7. 实验验证结果

### 7.1 测试模型

- 源模型：inase (purifier)_lezisell-A / inase54.pmx（原始无物理）
- 参考模型：Purifier Inase 18 V1.pmx（胸部物理有效）
- 动作：yaoxiang.vmd（295 帧舞蹈动作）

### 7.2 测试方案及结果

| 方案 | 物理位移 | 可见性 | 备注 |
|------|---------|--------|------|
| RGBA 5刚体 (type=2) | ~0.003mm | 不可见 | 零限制+COPY_ROTATION |
| RGBA 5刚体 + 软弹簧 | ~0.01mm | 不可见 | 弹簧拉回效果 |
| type=1 + COPY_TRANSFORMS | ~0.08mm (恒定偏移) | 不可见 | 非振荡 |
| type=1 + handler | 大幅旋转但变形 | 变形 | 旋转矩阵转换错误 |
| 数学弹簧模拟 | 最大 44°/66° | **可见** | 烘焙到关键帧 |
| 简单物理（参考模型方式） | 依赖播放 | **可见** | type=1 + ±10° + 无弹簧 |

### 7.3 并排对比测试

将 inase54_simple_phys.pmx 和 Purifier Inase 18 V1.pmx 并排导入，同时加载 VMD，物理参数完全一致，验证了简单物理方案的有效性。

---

## 8. 结论与建议

### 8.1 当前可用方案

| 方案 | 状态 | 适用场景 |
|------|------|---------|
| 简单物理 | ✅ 可用 | Blender 预览 + PMX 导出 |
| 弹簧模拟 | ✅ 可用 | Blender 预览（效果最可控） |
| RGBA 5刚体 | ✅ 可导出 | 仅 MMD 中有效 |

### 8.2 后续改进建议

| 优先级 | 建议 |
|--------|------|
| **高** | 集成 Wiggle 2 插件支持到面板（一键配置胸部骨骼） |
| **高** | 弹簧模拟增加烘焙为 VMD 导出功能 |
| **中** | 研究 UuuNyaa Tools 的 Breast Pyramid 布料方案 |
| **中** | 简单物理方案补全身体碰撞刚体（参考 Target 的完整结构） |
| **中** | 弹簧模拟增加按轴独立控制（X/Y/Z 各自的参数） |
| **低** | RGBA 5刚体在 Blender 中的改进（受限于引擎底层） |

### 8.3 最终推荐

**对于 Blender 中的 MMD 胸部物理，推荐组合使用：**

1. **简单物理**（type=1 Dynamic）作为基础物理层，导出 PMX 保留
2. **弹簧模拟**或 **Wiggle 2** 作为 Blender 预览增强层
3. **RGBA 5刚体**仅在需要导出到 MMD 使用零限制技巧时启用

---

## 9. 参考资料

### 原始方案
- [RGBA式おっぱい剛体の作り方](https://rgba.blog.jp/archives/10475373.html)
- [MMD物理演算ジョイント設定Tips](https://q-ku.blog.jp/archives/11315481.html)

### mmd_tools
- [blender_mmd_tools - GitHub](https://github.com/MMD-Blender/blender_mmd_tools)
- [MMD Tools Manual - Fandom Wiki](https://mmd-blender.fandom.com/wiki/MMD_Tools/Manual)
- [MMD Tools Physics System - DeepWiki](https://deepwiki.com/sugiany/blender_mmd_tools/4.3-physics-system)
- [How to setup physics - Fandom Wiki](https://mmd-blender.fandom.com/wiki/How_to_setup_physics)

### 社区方案
- [MMD physics in Blender - vasilnatalie (DeviantArt)](https://www.deviantart.com/vasilnatalie/art/MMD-physics-in-Blender-735322732)
- [Integrating soft body breast physics - vasilnatalie (DeviantArt)](https://www.deviantart.com/vasilnatalie/art/Integrating-soft-body-breast-physics-for-Blender-826963174)
- [MMD PMX Physics Settings - Amenrenet (DeviantArt)](https://www.deviantart.com/amenrenet/art/MMD-PMX-Physics-Settings-Part-5-921771191)
- [PMX Editor Physics Tutorials (Tumblr)](https://pmxeditortutorials.tumblr.com/post/172655831495/physics-in-mmd)
- [Blender胸揺れセットアップ](https://takashi2021.hatenablog.com/entry/2024/02/27/012101)
- [MMDモデルの胸を揺らす - とある紳士MMDer Wiki](https://shinshimmder.memo.wiki/)

### 插件
- [Wiggle 2 - GitHub](https://github.com/shteeve3d/blender-wiggle-2)
- [BoneDynamics - Gumroad](https://morelewd.gumroad.com/l/LhbhP)
- [Wobbly Wiggler - Gumroad](https://bartoszstyperek.gumroad.com/l/wobbly_wiggler)
- [JiggleArmature - GitHub](https://github.com/cheece/JiggleArmature)
- [Rigid Body Bones - GitHub](https://github.com/Pauan/blender-rigid-body-bones)
- [Jiggle Physics - Blender Extensions](https://extensions.blender.org/add-ons/jiggle-physics/)
- [UuuNyaa Tools - DeepWiki](https://deepwiki.com/MMD-Blender/blender_mmd_uuunyaa_tools/6-physics-system)
- [Bonex Parameters](https://oimoyu.github.io/blender_bonex_document/en/example.html)

### 其他
- [Bullet Physics Engine](https://bulletphysics.org/)
- [VPVP Wiki](https://w.atwiki.jp/vpvpwiki/)
- [物理演算/剛体/ジョイントの設定](https://site-builder.wiki/posts/21917)
