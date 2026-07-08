bl_info = {
    "name": "Finger Bone Collision & Grabbing",
    "blender": (3, 6, 0),
    "version": (1, 0, 0),
    "location": "Properties > Armature",
    "description": "Lightweight addon for posing hands with clean object contact. Finger bones stop on mesh collision.",
    "author": "Your Name",
    "category": "Rigging",
}

import bpy
import bmesh
from mathutils import Vector, Matrix
from bpy.props import BoolProperty, FloatProperty, StringProperty, EnumProperty
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
        
        # Get collision target
        target = None
        if scene.finger_collision_props.target_object:
            target = bpy.data.objects.get(scene.finger_collision_props.target_object)
        
        collision_margin = scene.finger_collision_props.collision_margin
        
        # Process each selected bone
        for bone in selected_bones:
            self._apply_collision_to_bone(obj, bone, target, collision_margin, context)
        
        self.report({'INFO'}, f"Collision applied to {len(selected_bones)} bones")
        return {'FINISHED'}
    
    def _apply_collision_to_bone(self, armature_obj, bone, target, margin, context):
        """Apply collision constraints to a single bone"""
        
        # Get bone in edit mode to work with it
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode='EDIT')
        
        edit_bone = armature_obj.data.edit_bones.get(bone.name)
        if not edit_bone:
            return
        
        # Calculate collision point
        collision_point = self._raycast_collision(
            armature_obj, bone, target, context
        )
        
        if collision_point:
            # Switch to pose mode and add constraint
            bpy.ops.object.mode_set(mode='POSE')
            pose_bone = armature_obj.pose.bones[bone.name]
            
            # Add Limit Location constraint
            limit_constraint = pose_bone.constraints.new(type='LIMIT_LOCATION')
            limit_constraint.name = "Finger_Collision"
            limit_constraint.use_min_x = True
            limit_constraint.use_min_y = True
            limit_constraint.use_min_z = True
            limit_constraint.use_max_x = True
            limit_constraint.use_max_y = True
            limit_constraint.use_max_z = True
            limit_constraint.influence = 1.0
        else:
            bpy.ops.object.mode_set(mode='OBJECT')
    
    def _raycast_collision(self, armature_obj, bone, target, context):
        """Cast ray from bone to find collision point"""
        
        # Get bone world position
        pose_bone = armature_obj.pose.bones.get(bone.name)
        if not pose_bone:
            return None
        
        bone_pos = armature_obj.matrix_world @ pose_bone.head
        bone_tail = armature_obj.matrix_world @ pose_bone.tail
        
        # Direction from head to tail
        direction = (bone_tail - bone_pos).normalized()
        
        # Raycast to find collision
        objects_to_check = [target] if target else context.scene.objects
        
        for obj in objects_to_check:
            if obj == armature_obj or obj.type != 'MESH':
                continue
            
            # Use built-in raycast
            result, location, normal, index = obj.ray_cast(
                origin=bone_pos,
                direction=direction,
                distance=10.0
            )
            
            if result:
                return location
        
        return None


class FINGERBONE_OT_GrabPose(Operator):
    """Auto-pose fingers around selected object"""
    bl_idname = "wm.finger_grab_pose"
    bl_label = "Auto Grab"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        armature_obj = context.active_object
        
        if not armature_obj or armature_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Select an armature")
            return {'CANCELLED'}
        
        # Get grab target
        grab_target = None
        for obj in context.selected_objects:
            if obj != armature_obj and obj.type == 'MESH':
                grab_target = obj
                break
        
        if not grab_target:
            self.report({'ERROR'}, "Select both armature and target mesh")
            return {'CANCELLED'}
        
        # Get selected finger bones
        arm = armature_obj.data
        finger_bones = [b for b in arm.bones if b.select]
        
        if not finger_bones:
            self.report({'ERROR'}, "Select finger bones first")
            return {'CANCELLED'}
        
        # Apply grab pose
        bpy.ops.object.mode_set(mode='POSE')
        self._apply_grab_pose(armature_obj, finger_bones, grab_target)
        
        self.report({'INFO'}, f"Grab pose applied to {len(finger_bones)} bones")
        return {'FINISHED'}
    
    def _apply_grab_pose(self, armature_obj, bones, target_obj):
        """Position bones to wrap around target object"""
        
        # Get target object center and bounds
        target_center = target_obj.location
        target_bound = max(target_obj.dimensions) / 2
        
        for bone in bones:
            pose_bone = armature_obj.pose.bones.get(bone.name)
            if not pose_bone:
                continue
            
            # Get bone world position
            bone_world_pos = armature_obj.matrix_world @ pose_bone.head
            
            # Direction towards target
            to_target = (target_center - bone_world_pos).normalized()
            
            # Raycast to find surface point
            result, location, normal, index = target_obj.ray_cast(
                origin=bone_world_pos,
                direction=to_target,
                distance=100.0
            )
            
            if result:
                # Move bone slightly away from surface (collision margin)
                offset = normal * 0.01
                target_pos = location + offset
                
                # Convert to local space
                local_pos = armature_obj.matrix_world.inverted() @ target_pos
                
                # Apply location
                pose_bone.location = local_pos - (armature_obj.matrix_world.inverted() @ armature_obj.matrix_world @ pose_bone.head)


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
            
            # Remove collision constraints
            for constraint in pose_bone.constraints:
                if "Collision" in constraint.name or "Limit" in constraint.type:
                    pose_bone.constraints.remove(constraint)
                    count += 1
        
        self.report({'INFO'}, f"Removed {count} constraints")
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
        
        # Title
        layout.label(text="Finger Collision Settings", icon='BONE_DATA')
        
        # Settings
        box = layout.box()
        box.prop(props, "enabled")
        box.prop(props, "collision_margin")
        box.prop(props, "use_debug_display")
        box.prop(props, "target_object")
        
        # Main buttons
        layout.separator()
        layout.label(text="Quick Tools", icon='TOOL_BRUSH')
        
        col = layout.column(align=True)
        col.scale_y = 1.5
        col.operator("wm.finger_auto_collide", icon='PHYSICS')
        col.operator("wm.finger_grab_pose", icon='HAND')
        col.operator("wm.finger_clear_collision", icon='X')
        
        # Instructions
        layout.separator()
        layout.label(text="Instructions:", icon='INFO')
        box = layout.box()
        box.label(text="1. Select armature & finger bones", icon='NONE')
        box.label(text="2. Click 'Auto Collide' or 'Auto Grab'", icon='NONE')
        box.label(text="3. Adjust margin for fine-tuning", icon='NONE')


class FINGERBONE_PT_AdvancedPanel(Panel):
    """Advanced settings panel"""
    bl_label = "Advanced"
    bl_idname = "FINGERBONE_PT_advanced"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "FINGERBONE_PT_main"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="Experimental features coming soon")


# Registration
classes = (
    FingerCollisionProperties,
    FINGERBONE_OT_AutoCollide,
    FINGERBONE_OT_GrabPose,
    FINGERBONE_OT_ClearCollision,
    FINGERBONE_PT_MainPanel,
    FINGERBONE_PT_AdvancedPanel,
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
    
    del bpy.types.Scene.finger_collision_props


if __name__ == "__main__":
    register()
