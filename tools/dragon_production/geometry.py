from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Iterable

import bpy
from mathutils import Matrix, Vector


WeightMap = dict[str, float]
WeightFunction = Callable[[Vector], WeightMap]


@dataclass
class MeshBuildResult:
    object: bpy.types.Object
    triangle_count: int
    vertex_count: int


class MeshAssembler:
    """Deterministic indexed mesh builder with materials, two UV sets and skin weights."""

    def __init__(self, material_names: Iterable[str]):
        self.vertices: list[tuple[float, float, float]] = []
        self.faces: list[tuple[int, ...]] = []
        self.face_materials: list[int] = []
        self.vertex_uvs: list[tuple[float, float]] = []
        self.vertex_weights: list[WeightMap] = []
        self.material_names = list(material_names)
        self.material_index = {name: i for i, name in enumerate(self.material_names)}

    def _append_vertex(self, co: Vector, uv: tuple[float, float], weights: WeightMap) -> int:
        normalized = _normalize_weights(weights)
        self.vertices.append((float(co.x), float(co.y), float(co.z)))
        self.vertex_uvs.append((float(uv[0]), float(uv[1])))
        self.vertex_weights.append(normalized)
        return len(self.vertices) - 1

    def _append_face(self, indices: Iterable[int], material_name: str) -> None:
        face = tuple(indices)
        if len(face) < 3:
            return
        self.faces.append(face)
        self.face_materials.append(self.material_index[material_name])

    def add_uv_ellipsoid(
        self,
        center: Vector,
        radii: Vector,
        rings: int,
        segments: int,
        material: str,
        weights: WeightFunction,
        rotation: Matrix | None = None,
        uv_scale: tuple[float, float] = (1.0, 1.0),
    ) -> None:
        rotation = rotation or Matrix.Identity(3)
        top = self._append_vertex(
            center + rotation @ Vector((0.0, 0.0, radii.z)),
            (0.5, 1.0),
            weights(center + Vector((0.0, 0.0, radii.z))),
        )
        ring_indices: list[list[int]] = []
        for ring in range(1, rings):
            v = ring / rings
            phi = math.pi * v
            sin_phi = math.sin(phi)
            cos_phi = math.cos(phi)
            current: list[int] = []
            for segment in range(segments):
                u = segment / segments
                theta = math.tau * u
                local = Vector((
                    radii.x * sin_phi * math.cos(theta),
                    radii.y * sin_phi * math.sin(theta),
                    radii.z * cos_phi,
                ))
                co = center + rotation @ local
                current.append(self._append_vertex(
                    co,
                    (u * uv_scale[0], v * uv_scale[1]),
                    weights(co),
                ))
            ring_indices.append(current)

        bottom = self._append_vertex(
            center + rotation @ Vector((0.0, 0.0, -radii.z)),
            (0.5, 0.0),
            weights(center + Vector((0.0, 0.0, -radii.z))),
        )

        first = ring_indices[0]
        for i in range(segments):
            self._append_face((top, first[i], first[(i + 1) % segments]), material)

        for ring in range(len(ring_indices) - 1):
            a = ring_indices[ring]
            b = ring_indices[ring + 1]
            for i in range(segments):
                ni = (i + 1) % segments
                self._append_face((a[i], b[i], b[ni], a[ni]), material)

        last = ring_indices[-1]
        for i in range(segments):
            self._append_face((last[(i + 1) % segments], last[i], bottom), material)

    def add_tube(
        self,
        points: list[Vector],
        radii: list[tuple[float, float]],
        segments: int,
        material: str,
        bone_chain: list[str],
        cap_start: bool = True,
        cap_end: bool = True,
        uv_v_scale: float = 1.0,
    ) -> None:
        if len(points) < 2 or len(points) != len(radii) or len(points) != len(bone_chain):
            raise ValueError("Tube points, radii and bone_chain must have equal lengths >= 2")

        rings: list[list[int]] = []
        distances = [0.0]
        for i in range(1, len(points)):
            distances.append(distances[-1] + (points[i] - points[i - 1]).length)
        total_distance = max(distances[-1], 1e-6)

        for i, point in enumerate(points):
            tangent = _path_tangent(points, i)
            side, up = _orthonormal_frame(tangent)
            ring: list[int] = []
            rx, rz = radii[i]
            for segment in range(segments):
                u = segment / segments
                angle = math.tau * u
                co = point + side * (math.cos(angle) * rx) + up * (math.sin(angle) * rz)
                ring.append(self._append_vertex(
                    co,
                    (u, (distances[i] / total_distance) * uv_v_scale),
                    _chain_weights(bone_chain, i, len(points)),
                ))
            rings.append(ring)

        for ring_idx in range(len(rings) - 1):
            a = rings[ring_idx]
            b = rings[ring_idx + 1]
            for segment in range(segments):
                next_segment = (segment + 1) % segments
                self._append_face(
                    (a[segment], b[segment], b[next_segment], a[next_segment]),
                    material,
                )

        if cap_start:
            center_idx = self._append_vertex(points[0], (0.5, 0.0), {bone_chain[0]: 1.0})
            for segment in range(segments):
                self._append_face(
                    (center_idx, rings[0][(segment + 1) % segments], rings[0][segment]),
                    material,
                )
        if cap_end:
            center_idx = self._append_vertex(points[-1], (0.5, 1.0), {bone_chain[-1]: 1.0})
            for segment in range(segments):
                self._append_face(
                    (center_idx, rings[-1][segment], rings[-1][(segment + 1) % segments]),
                    material,
                )

    def add_cylinder_between(
        self,
        start: Vector,
        end: Vector,
        radius_start: tuple[float, float],
        radius_end: tuple[float, float],
        segments: int,
        material: str,
        bone_name: str,
        cap: bool = True,
    ) -> None:
        self.add_tube(
            [start, end],
            [radius_start, radius_end],
            segments,
            material,
            [bone_name, bone_name],
            cap_start=cap,
            cap_end=cap,
        )

    def add_cone(
        self,
        base: Vector,
        tip: Vector,
        radius: float,
        segments: int,
        material: str,
        bone_name: str,
        elliptical: float = 1.0,
    ) -> None:
        direction = (tip - base).normalized()
        side, up = _orthonormal_frame(direction)
        base_indices: list[int] = []
        for i in range(segments):
            u = i / segments
            angle = math.tau * u
            co = base + side * (math.cos(angle) * radius) + up * (math.sin(angle) * radius * elliptical)
            base_indices.append(self._append_vertex(co, (u, 0.0), {bone_name: 1.0}))
        tip_idx = self._append_vertex(tip, (0.5, 1.0), {bone_name: 1.0})
        center_idx = self._append_vertex(base, (0.5, 0.0), {bone_name: 1.0})
        for i in range(segments):
            ni = (i + 1) % segments
            self._append_face((base_indices[i], base_indices[ni], tip_idx), material)
            self._append_face((center_idx, base_indices[ni], base_indices[i]), material)

    def add_scale_plate(
        self,
        center: Vector,
        normal: Vector,
        length: float,
        width: float,
        height: float,
        material: str,
        weights: WeightMap,
        roll: float = 0.0,
    ) -> None:
        normal = normal.normalized()
        tangent, bitangent = _surface_basis(normal)
        if roll:
            rot = Matrix.Rotation(roll, 3, normal)
            tangent = rot @ tangent
            bitangent = rot @ bitangent

        nose = center + tangent * (length * 0.58)
        tail = center - tangent * (length * 0.42)
        left = center + bitangent * (width * 0.5)
        right = center - bitangent * (width * 0.5)
        ridge = center + normal * height + tangent * (length * 0.08)
        ids = [
            self._append_vertex(nose, (0.5, 1.0), weights),
            self._append_vertex(left, (0.0, 0.45), weights),
            self._append_vertex(tail, (0.5, 0.0), weights),
            self._append_vertex(right, (1.0, 0.45), weights),
            self._append_vertex(ridge, (0.5, 0.5), weights),
        ]
        self._append_face((ids[0], ids[1], ids[4]), material)
        self._append_face((ids[1], ids[2], ids[4]), material)
        self._append_face((ids[2], ids[3], ids[4]), material)
        self._append_face((ids[3], ids[0], ids[4]), material)

    def add_membrane_polygon(
        self,
        points: list[Vector],
        uvs: list[tuple[float, float]],
        weights: list[WeightMap],
        material: str,
        thickness: float = 0.035,
    ) -> None:
        if not (len(points) == len(uvs) == len(weights)) or len(points) < 3:
            raise ValueError("Membrane polygon arrays must have equal length >= 3")

        normal = _polygon_normal(points)
        front = [self._append_vertex(p + normal * (thickness * 0.5), uv, w) for p, uv, w in zip(points, uvs, weights)]
        back = [self._append_vertex(p - normal * (thickness * 0.5), uv, w) for p, uv, w in zip(points, uvs, weights)]

        for i in range(1, len(front) - 1):
            self._append_face((front[0], front[i], front[i + 1]), material)
            self._append_face((back[0], back[i + 1], back[i]), material)
        for i in range(len(front)):
            ni = (i + 1) % len(front)
            self._append_face((front[i], back[i], back[ni], front[ni]), material)

    def to_object(
        self,
        name: str,
        collection: bpy.types.Collection,
        materials: dict[str, bpy.types.Material],
        armature: bpy.types.Object | None = None,
    ) -> MeshBuildResult:
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        mesh.from_pydata(self.vertices, [], self.faces)
        mesh.update(calc_edges=True)

        for material_name in self.material_names:
            mesh.materials.append(materials[material_name])
        for polygon, material_index in zip(mesh.polygons, self.face_materials):
            polygon.material_index = material_index
            polygon.use_smooth = True

        uv0 = mesh.uv_layers.new(name="UV0")
        uv1 = mesh.uv_layers.new(name="UV1")
        for loop in mesh.loops:
            uv = self.vertex_uvs[loop.vertex_index]
            uv0.data[loop.index].uv = uv
            uv1.data[loop.index].uv = (uv[0] * 0.5, uv[1] * 0.5)

        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)

        group_vertices: dict[str, list[tuple[int, float]]] = {}
        for vertex_index, weights in enumerate(self.vertex_weights):
            for bone_name, weight in weights.items():
                group_vertices.setdefault(bone_name, []).append((vertex_index, weight))
        for bone_name, entries in group_vertices.items():
            group = obj.vertex_groups.new(name=bone_name)
            for vertex_index, weight in entries:
                group.add([vertex_index], weight, "REPLACE")

        if armature is not None:
            obj.parent = armature
            modifier = obj.modifiers.new(name="Armature", type="ARMATURE")
            modifier.object = armature
            modifier.use_deform_preserve_volume = True

        mesh.calc_loop_triangles()
        return MeshBuildResult(
            object=obj,
            triangle_count=len(mesh.loop_triangles),
            vertex_count=len(mesh.vertices),
        )


def _normalize_weights(weights: WeightMap) -> WeightMap:
    filtered = [(name, max(0.0, float(weight))) for name, weight in weights.items() if weight > 1e-7]
    filtered.sort(key=lambda item: item[1], reverse=True)
    filtered = filtered[:4]
    total = sum(weight for _, weight in filtered)
    if total <= 1e-8:
        return {"Root": 1.0}
    return {name: weight / total for name, weight in filtered}


def _path_tangent(points: list[Vector], index: int) -> Vector:
    if index == 0:
        tangent = points[1] - points[0]
    elif index == len(points) - 1:
        tangent = points[-1] - points[-2]
    else:
        tangent = points[index + 1] - points[index - 1]
    if tangent.length_squared < 1e-10:
        return Vector((0.0, 1.0, 0.0))
    return tangent.normalized()


def _orthonormal_frame(direction: Vector) -> tuple[Vector, Vector]:
    direction = direction.normalized()
    reference = Vector((0.0, 0.0, 1.0))
    if abs(direction.dot(reference)) > 0.92:
        reference = Vector((0.0, 1.0, 0.0))
    side = direction.cross(reference).normalized()
    up = side.cross(direction).normalized()
    return side, up


def _surface_basis(normal: Vector) -> tuple[Vector, Vector]:
    reference = Vector((0.0, 0.0, 1.0))
    if abs(normal.dot(reference)) > 0.9:
        reference = Vector((0.0, 1.0, 0.0))
    tangent = reference.cross(normal).normalized()
    bitangent = normal.cross(tangent).normalized()
    return tangent, bitangent


def _polygon_normal(points: list[Vector]) -> Vector:
    normal = Vector((0.0, 0.0, 0.0))
    for i, current in enumerate(points):
        nxt = points[(i + 1) % len(points)]
        normal.x += (current.y - nxt.y) * (current.z + nxt.z)
        normal.y += (current.z - nxt.z) * (current.x + nxt.x)
        normal.z += (current.x - nxt.x) * (current.y + nxt.y)
    if normal.length_squared < 1e-10:
        return Vector((0.0, 0.0, 1.0))
    return normal.normalized()


def _chain_weights(bones: list[str], index: int, count: int) -> WeightMap:
    if count <= 1:
        return {bones[0]: 1.0}
    if index >= count - 1:
        return {bones[-1]: 1.0}
    return {bones[index]: 0.82, bones[min(index + 1, len(bones) - 1)]: 0.18}


def nearest_chain_weights(point: Vector, chain: list[tuple[str, Vector]]) -> WeightMap:
    distances = sorted(((name, max((point - pos).length, 1e-4)) for name, pos in chain), key=lambda item: item[1])[:2]
    inv = [(name, 1.0 / distance) for name, distance in distances]
    total = sum(weight for _, weight in inv)
    return {name: weight / total for name, weight in inv}
