# CG Geek 1-minute Blender low-poly tree — original implementation

**Tutorial reference:** https://www.youtube.com/watch?v=y7PdiGXbrD0 (CG Geek, 2019). This is an original procedural asset **inspired by** its cube/extrude branching + leaf-texture-card approach; it is not a copy/extraction of the creator's mesh or textures.

## Ready to use

- `output/Tree_LowPoly_LOD0.glb`: full tree with leaf-placeholder and bark baked into GLB, 1,732 triangles, ~6.7 m tall.
- `output/Tree_LowPoly_LOD1.glb`: simpler distant tree, 916 triangles.
- `scripts/build_blend.py`: creates two editable `.blend` projects (one per LOD) in Blender with separate trunk/branches, leaf cards, UVs, packed materials. GitHub Actions builds them if Blender is unavailable on Android.
- `assets/bark_original_256.png`: original 256×512 temporary bark bitmap.
- `assets/leaf_PLACEHOLDER.png`: original temporary transparent foliage sprig bitmap. **Not the final leaf texture.**
- `scripts/tree_geometry.py`: deterministic build logic, no Blender dependency.
- `scripts/export_glb.py`: no-Blender GLB exporter using Python/Trimesh.

## Replacing leaves later

1. Supply the final leaf PNG (preferably RGBA with a transparent background). The transparency **must not be a white background**.
2. Save it to `assets/leaf_texture.png`. It takes precedence over the placeholder automatically.
3. To create GLB files outside Blender: `python scripts/export_glb.py` (needs numpy, trimesh, Pillow).
4. To create Blender sources: `blender -b --python scripts/build_blend.py -- --lod=0` (and `--lod=1` for the lighter version). The leaf cards already have full 0–1 UV mapping; the Blender leaf material has an image texture node named `REPLACE_THIS_LEAF_IMAGE`.
5. Replace/update the GLB file in Godot, then check transparency from several angles.

## Godot and mobile

- Import GLB in Godot 4 as 3D scene. 1 unit ≈ 1 metre; root at soil level, Z-up in Blender (glTF converts for Godot).
- Prefer LOD1 for forests / distance, LOD0 for close individual trees.
- Leaf image uses alpha *mask* to avoid transparent sorting; double-sided cards. This prevents common sorting problems but edges may appear sharp on mobile, depending on alpha cut-off.
- Make only the trunk collidable; don't give each leaf a collision body. Tree has no rig/animation.
- Embedded placeholder PNG must be replaced and re-exported to make final foliage correct. The model is not final before you send the leaf texture.

## Video fidelity

Video's actual steps use cube edits and repeated extrusions to form the trunk and branches, then branch/leaf textures. This procedural implementation uses low-sided tube rings (equivalent faceted extrusions) and baked leaf cards instead of a live particle system, because baked cards are exportable to Godot GLB and cheaper than a Blender particle system.
**GitHub note:** source scripts and workflow are version-controlled; placeholder images and output GLB/BLEND files are generated as workflow artifacts. The downloadable local ZIP includes prebuilt GLBs and images.
