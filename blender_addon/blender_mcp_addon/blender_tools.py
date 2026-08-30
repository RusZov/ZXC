"""
Инструменты для работы с Blender API.

Все функции используют bpy и должны вызываться только из главного потока Blender.
Используются CommandDispatcher для регистрации команд.
"""

import os
import base64
import tempfile
from typing import Optional, Any


def _get_eevee_engine_name() -> str:
    """Получить правильное имя движка EEVEE для текущей версии Blender."""
    import bpy
    
    # Проверить доступные значения enum
    render_engine_props = bpy.types.Scene.render.bl_rna.properties["engine"]
    available_engines = [item.identifier for item in render_engine_props.enum_items]
    
    if "BLENDER_EEVEE" in available_engines:
        return "BLENDER_EEVEE"
    elif "BLENDER_EEVEE_NEXT" in available_engines:
        return "BLENDER_EEVEE_NEXT"
    else:
        return "BLENDER_WORKBENCH"  # Fallback


class BlenderTools:
    """Инструменты для работы с Blender API."""
    
    def create_object(
        self,
        object_type: str = "cube",
        name: Optional[str] = None,
        location: list[float] = [0.0, 0.0, 0.0],
        rotation: list[float] = [0.0, 0.0, 0.0],
        scale: list[float] = [1.0, 1.0, 1.0],
    ) -> dict[str, Any]:
        """Создать 3D объект."""
        import bpy
        
        bpy.ops.object.select_all(action="DESELECT")
        
        type_map = {
            "cube": bpy.ops.mesh.primitive_cube_add,
            "sphere": bpy.ops.mesh.primitive_uv_sphere_add,
            "cylinder": bpy.ops.mesh.primitive_cylinder_add,
            "cone": bpy.ops.mesh.primitive_cone_add,
            "plane": bpy.ops.mesh.primitive_plane_add,
            "torus": bpy.ops.mesh.primitive_torus_add,
            "empty": bpy.ops.object.empty_add,
        }
        
        if object_type not in type_map:
            object_type = "cube"
        
        op_func = type_map[object_type]
        op_func(location=location, rotation=rotation)
        
        obj = bpy.context.active_object
        if obj is None:
            raise RuntimeError("Не удалось создать объект")
        
        if name:
            obj.name = name
        
        obj.scale = scale
        
        return {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation": list(obj.rotation_euler),
            "scale": list(obj.scale),
        }
    
    def apply_material(
        self,
        object_name: str,
        base_color: list[float] = [0.8, 0.8, 0.8, 1.0],
        roughness: float = 0.5,
        metallic: float = 0.0,
        material_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Применить PBR материал к объекту."""
        import bpy
        
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Объект '{object_name}' не найден")
        
        if material_name is None:
            material_name = f"{obj.name}_Material"
        
        mat = bpy.data.materials.new(name=material_name)
        mat.use_nodes = True
        
        nodes = mat.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        
        if bsdf:
            bsdf.inputs["Base Color"].default_value = base_color
            bsdf.inputs["Roughness"].default_value = roughness
            bsdf.inputs["Metallic"].default_value = metallic
        
        if len(obj.data.materials) == 0:
            obj.data.materials.append(mat)
        else:
            obj.data.materials[0] = mat
        
        return {
            "object_name": object_name,
            "material_name": mat.name,
            "base_color": base_color,
            "roughness": roughness,
            "metallic": metallic,
        }
    
    def add_light(
        self,
        light_type: str = "POINT",
        name: Optional[str] = None,
        location: list[float] = [0.0, 0.0, 5.0],
        energy: float = 100.0,
        color: list[float] = [1.0, 1.0, 1.0],
    ) -> dict[str, Any]:
        """Добавить источник света."""
        import bpy
        
        bpy.ops.object.light_add(type=light_type, location=location)
        
        light_obj = bpy.context.active_object
        if light_obj is None:
            raise RuntimeError("Не удалось создать источник света")
        
        if name:
            light_obj.name = name
        
        light = light_obj.data
        light.energy = energy
        light.color = color[:3]
        
        return {
            "name": light_obj.name,
            "type": light.type,
            "location": list(light_obj.location),
            "energy": light.energy,
            "color": list(light.color),
        }
    
    def set_camera(
        self,
        location: list[float] = [0.0, -10.0, 5.0],
        target: Optional[list[float]] = None,
        rotation: Optional[list[float]] = None,
        lens: float = 35.0,
    ) -> dict[str, Any]:
        """Настроить камеру."""
        import bpy
        from mathutils import Vector
        
        bpy.ops.object.camera_add(location=location)
        
        cam_obj = bpy.context.active_object
        if cam_obj is None:
            raise RuntimeError("Не удалось создать камеру")
        
        cam_obj.data.lens = lens
        
        if target is not None:
            direction = Vector(target) - Vector(location)
            direction.normalize()
            rot_quat = direction.to_track_quat("-Z", "Y")
            cam_obj.rotation_euler = rot_quat.to_euler()
        elif rotation is not None:
            cam_obj.rotation_euler = rotation
        
        bpy.context.scene.camera = cam_obj
        
        return {
            "name": cam_obj.name,
            "location": list(cam_obj.location),
            "rotation": list(cam_obj.rotation_euler),
            "lens": cam_obj.data.lens,
        }
    
    def render_scene(
        self,
        filepath: str,
        resolution_x: int = 1920,
        resolution_y: int = 1080,
        engine: str = "EEVEE",
        samples: int = 128,
        overwrite: bool = True,
    ) -> dict[str, Any]:
        """Выполнить рендер сцены."""
        import bpy
        
        scene = bpy.context.scene
        
        if not overwrite and os.path.exists(filepath):
            raise FileExistsError(f"Файл уже существует: {filepath}")
        
        scene.render.resolution_x = resolution_x
        scene.render.resolution_y = resolution_y
        scene.render.resolution_percentage = 100
        
        if engine.upper() == "CYCLES":
            scene.render.engine = "BLENDER_CYCLES"
            scene.cycles.samples = samples
        else:
            eevee_name = _get_eevee_engine_name()
            scene.render.engine = eevee_name
        
        abs_path = os.path.abspath(filepath)
        scene.render.filepath = abs_path
        
        bpy.ops.render.render(write_still=True)
        
        return {
            "filepath": abs_path,
            "resolution": [resolution_x, resolution_y],
            "engine": scene.render.engine,
        }
    
    def export_fbx(
        self,
        filepath: str,
        objects: Optional[list[str]] = None,
        apply_transform: bool = True,
        overwrite: bool = True,
    ) -> dict[str, Any]:
        """Экспортировать в FBX."""
        import bpy
        
        if not overwrite and os.path.exists(filepath):
            raise FileExistsError(f"Файл уже существует: {filepath}")
        
        abs_path = os.path.abspath(filepath)
        
        if objects:
            objs_to_export = [bpy.data.objects[name] for name in objects if name in bpy.data.objects]
            if not objs_to_export:
                raise ValueError("Ни один объект не найден")
            
            for obj in bpy.data.objects:
                obj.select_set(obj in objs_to_export)
        else:
            bpy.ops.object.select_all(action="SELECT")
        
        bpy.ops.export_scene.fbx(
            filepath=abs_path,
            use_selection=bool(objects),
            apply_unit_scale=True,
            apply_scale_options="FBX_SCALE_ALL",
            bake_space_transform=True,
        )
        
        return {"filepath": abs_path}
    
    def export_gltf(
        self,
        filepath: str,
        objects: Optional[list[str]] = None,
        export_format: str = "GLB",
        overwrite: bool = True,
    ) -> dict[str, Any]:
        """Экспортировать в glTF/GLB."""
        import bpy
        
        if not overwrite and os.path.exists(filepath):
            raise FileExistsError(f"Файл уже существует: {filepath}")
        
        abs_path = os.path.abspath(filepath)
        fmt = "GLB" if export_format.upper() == "GLB" else "GLTF_SEPARATE"
        
        if objects:
            objs_to_export = [bpy.data.objects[name] for name in objects if name in bpy.data.objects]
            for obj in bpy.data.objects:
                obj.select_set(obj in objs_to_export)
        else:
            bpy.ops.object.select_all(action="SELECT")
        
        bpy.ops.export_scene.gltf(
            filepath=abs_path,
            export_format=fmt,
            use_selection=bool(objects),
        )
        
        return {"filepath": abs_path, "format": fmt}
    
    def get_scene_info(self) -> dict[str, Any]:
        """Получить информацию о сцене."""
        import bpy
        
        objects_info = []
        for obj in bpy.data.objects:
            objects_info.append({
                "name": obj.name,
                "type": obj.type,
                "location": list(obj.location),
                "rotation": list(obj.rotation_euler),
                "scale": list(obj.scale),
            })
        
        return {
            "objects_count": len(objects_info),
            "objects": objects_info,
        }
    
    def execute_batch(
        self,
        commands: list[dict[str, Any]],
        stop_on_error: bool = True,
    ) -> dict[str, Any]:
        """Выполнить пакет команд."""
        results = []
        errors = []
        
        for i, cmd in enumerate(commands):
            try:
                command_name = cmd.get("command")
                args = cmd.get("args", {})
                
                if command_name not in COMMAND_REGISTRY:
                    raise ValueError(f"Неизвестная команда: {command_name}")
                
                handler = COMMAND_REGISTRY[command_name]
                result = handler(args)
                results.append({"index": i, "success": True, "result": result})
                
            except Exception as e:
                error_info = {"index": i, "success": False, "error": str(e)}
                errors.append(error_info)
                
                if stop_on_error:
                    break
        
        return {
            "total": len(commands),
            "executed": len(results),
            "errors": len(errors),
            "results": results,
            "error_details": errors,
        }
    
    def transform_object(
        self,
        object_name: str,
        location: Optional[list[float]] = None,
        rotation: Optional[list[float]] = None,
        scale: Optional[list[float]] = None,
        mode: str = "absolute",
    ) -> dict[str, Any]:
        """Изменить трансформацию объекта."""
        import bpy
        
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Объект '{object_name}' не найден")
        
        if mode == "relative":
            if location:
                obj.location += Vector(location)
            if rotation:
                obj.rotation_euler.rotate(Rotation(tuple(rotation)).to_matrix())
            if scale:
                obj.scale *= Vector(scale)
        else:
            if location:
                obj.location = location
            if rotation:
                obj.rotation_euler = rotation
            if scale:
                obj.scale = scale
        
        return {
            "name": obj.name,
            "location": list(obj.location),
            "rotation": list(obj.rotation_euler),
            "scale": list(obj.scale),
        }
    
    def delete_objects(self, object_names: list[str]) -> dict[str, Any]:
        """Удалить объекты."""
        import bpy
        
        deleted = []
        not_found = []
        
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj:
                bpy.data.objects.remove(obj, do_unlink=True)
                deleted.append(name)
            else:
                not_found.append(name)
        
        return {
            "deleted": deleted,
            "not_found": not_found,
        }
    
    def render_preview(
        self,
        resolution: int = 512,
        engine: str = "EEVEE",
    ) -> dict[str, Any]:
        """Выполнить превью-рендер и вернуть изображение в base64."""
        import bpy
        import io
        
        scene = bpy.context.scene
        
        old_res_x = scene.render.resolution_x
        old_res_y = scene.render.resolution_y
        old_engine = scene.render.engine
        
        scene.render.resolution_x = resolution
        scene.render.resolution_y = resolution
        scene.render.resolution_percentage = 100
        
        if engine.upper() == "CYCLES":
            scene.render.engine = "BLENDER_CYCLES"
        else:
            scene.render.engine = _get_eevee_engine_name()
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        
        scene.render.filepath = tmp_path
        bpy.ops.render.render(write_still=True)
        
        with open(tmp_path, "rb") as f:
            image_data = f.read()
        
        os.unlink(tmp_path)
        
        scene.render.resolution_x = old_res_x
        scene.render.resolution_y = old_res_y
        scene.render.engine = old_engine
        
        image_base64 = base64.b64encode(image_data).decode("utf-8")
        
        return {
            "format": "png",
            "width": resolution,
            "height": resolution,
            "image_base64": image_base64,
        }


# Импортировать реестр команд
from .dispatcher import COMMAND_REGISTRY
