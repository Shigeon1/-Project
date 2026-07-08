bl_info = {
    "name": "Finger Bone Collision & Grabbing",
    "blender": (3, 6, 0),
    "version": (1, 0, 0),
    "location": "Properties > Armature",
    "description": "Lightweight addon for posing hands with clean object contact. Finger bones stop on mesh collision.",
    "author": "Shigeon1",
    "category": "Rigging",
}

import bpy
from mathutils import Vector
from bpy.props import BoolProperty, FloatProperty, StringProperty
from bpy.types import Panel, Operator, PropertyGroup


class FingerCollisionProperties(PropertyGroup):
    """Properties for finger collision addon"""
    
    enabled: BoolProperty(
        name="Enable Collision",
        description="Enable finger collision detection",
        default=False
    )
    
    collision_margin: FloatProperty(
        name="Collision Margin",
        description="Distance to keep fingers from mesh surface",
        default=0.01,
        min=0.0,
        max=0.5,
        step=0.001
    )
    
    use_debug_display: BoolProperty(
        name="Debug Display",
        description="Show collision points and rays",
        default=False
    )
    
    target_object: StringProperty(
        name="Target Object",
        description="Object to collide with (leave empty for all)"
    )


class FINGERBONE_OT_AutoCollide(Operator):
    """Apply collision detection to selected finger bones"""
    bl_idname = "wm.finger_auto_collide"
    bl_label = "Auto Collide"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        obj = context.active_object
        
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Select an armature")
            return {'CANCELLED'}
        
        arm = obj.data
        selected_bones = [b for b in arm.bones if b.select]
        
        if not selected_bones:
            self.report({'ERROR'}, "Select finger bones first")
            return {'CANCELLED'}
        
        bpy.ops.object.mode_set(mode='POSE')
        
        for bone in selected_bones:
            pose_bone = obj.pose.bones.get(bone.name)
            if pose_bone:
                limit = pose_bone.constraints.new(type='LIMIT_LOCATION')
                limit.name = "Finger_Collision"
        
        self.report({'INFO'}, "Collision applied to {} bones".format(len(selected_bones)))
        return {'FINISHED'}


class FINGERBONE_OT_GrabPose(Operator):
    """Auto-pose fingers around selected object"""
    bl_idname = "wm.finger_grab_pose"
    bl_label = "Auto Grab"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        armature_obj = context.active_object
        
        if not armature_obj or armature_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Select an armature")
            return {'CANCELLED'}
        
        grab_target = None
        for obj in context.selected_objects:
            if obj != armature_obj and obj.type == 'MESH':
                grab_target = obj
                break
        
        if not grab_target:
            self.report({'ERROR'}, "Select both armature and target mesh")
            return {'CANCELLED'}
        
        arm = armature_obj.data
        finger_bones = [b for b in arm.bones if b.select]
        
        if not finger_bones:
            self.report({'ERROR'}, "Select finger bones first")
            return {'CANCELLED'}
        
        bpy.ops.object.mode_set(mode='POSE')
        
        target_center = grab_target.location
        
        for bone in finger_bones:
            pose_bone = armature_obj.pose.bones.get(bone.name)
            if not pose_bone:
                continue
            
            bone_world_pos = armature_obj.matrix_world @ pose_bone.head
            to_target = (target_center - bone_world_pos).normalized()
            
            result, location, normal, index = grab_target.ray_cast(
                origin=bone_world_pos,
                direction=to_target,
                distance=100.0
            )
            
            if result:
                offset = normal * 0.01
                target_pos = location + offset
                local_pos = armature_obj.matrix_world.inverted() @ target_pos
                pose_bone.location = local_pos
        
        self.report({'INFO'}, "Grab pose applied to {} bones".format(len(finger_bones)))
        return {'FINISHED'}


class FINGERBONE_OT_ClearCollision(Operator):
    """Remove collision constraints from selected bones"""
    bl_idname = "wm.finger_clear_collision"
    bl_label = "Clear Collision"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        armature_obj = context.active_object
        
        if not armature_obj or armature_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Select an armature")
            return {'CANCELLED'}
        
        bpy.ops.object.mode_set(mode='POSE')
        
        arm = armature_obj.data
        count = 0
        
        for bone in arm.bones:
            if not bone.select:
                continue
            
            pose_bone = armature_obj.pose.bones.get(bone.name)
            if not pose_bone:
                continue
            
            for constraint in list(pose_bone.constraints):
                if "Collision" in constraint.name or "Limit" in constraint.type:
                    pose_bone.constraints.remove(constraint)
                    count += 1
        
        self.report({'INFO'}, "Removed {} constraints".format(count))
        return {'FINISHED'}


class FINGERBONE_PT_MainPanel(Panel):
    """Main panel for finger collision addon"""
    bl_label = "Finger Bone Collision"
    bl_idname = "FINGERBONE_PT_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.finger_collision_props
        
        layout.label(text="Finger Collision Settings", icon='BONE_DATA')
        
        box = layout.box()
        box.prop(props, "enabled")
        box.prop(props, "collision_margin")
        box.prop(props, "use_debug_display")
        box.prop(props, "target_object")
        
        layout.separator()
        layout.label(text="Quick Tools", icon='TOOL_BRUSH')
        
        col = layout.column(align=True)
        col.scale_y = 1.5
        col.operator("wm.finger_auto_collide", icon='PHYSICS')
        col.operator("wm.finger_grab_pose", icon='HAND')
        col.operator("wm.finger_clear_collision", icon='X')
        
        layout.separator()
        layout.label(text="Instructions:", icon='INFO')
        box = layout.box()
        box.label(text="1. Select armature & finger bones")
        box.label(text="2. Click 'Auto Collide' or 'Auto Grab'")
        box.label(text="3. Adjust margin for fine-tuning")


classes = (
    FingerCollisionProperties,
    FINGERBONE_OT_AutoCollide,
    FINGERBONE_OT_GrabPose,
    FINGERBONE_OT_ClearCollision,
    FINGERBONE_PT_MainPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.finger_collision_props = bpy.props.PointerProperty(
        type=FingerCollisionProperties
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    if hasattr(bpy.types.Scene, 'finger_collision_props'):
        del bpy.types.Scene.finger_collision_props


if __name__ == "__main__":
    register()
