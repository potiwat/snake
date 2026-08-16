"""
Snake Robot PyBullet MultiBody Model & Fault Injector.
Supports multi-joint simultaneous faults, explicit locked angles, limp/free modes,
and dynamic friction adaptation.
"""

import pybullet as p
import pybullet_data
import numpy as np
from config import RobotConfig, SimConfig

class FaultType:
    NONE = "none"
    LOCKED = "locked"
    FREE = "free"
    LIMP = "free"  # Alias for unpowered passive joint
    PARTIAL_TORQUE = "partial_torque"

class SnakeRobot:
    def __init__(self, physics_client, base_position=(0, 0, 0.05)):
        self.pc = physics_client
        self.num_segments = RobotConfig.NUM_SEGMENTS
        self.num_joints = RobotConfig.NUM_JOINTS
        
        # Build multi-body snake model
        self.robot_id = self._build_snake_model(base_position)
        
        # Setup joint indices & motor parameters
        self.joint_indices = list(range(self.num_joints))
        self._setup_motors()
        
        # Multi-joint fault storage dictionary:
        # mapping: joint_idx -> {'type': fault_type, 'params': dict(locked_angle=..., gamma_f=...)}
        self.active_faults = {}

    @property
    def fault_active(self):
        """Returns True if any joint fault is active."""
        return len(self.active_faults) > 0

    @fault_active.setter
    def fault_active(self, val):
        if not val:
            self.clear_faults()

    @property
    def fault_joint_idx(self):
        """Primary/latest active fault joint index (backward compatibility)."""
        if self.active_faults:
            return list(self.active_faults.keys())[-1]
        return None

    @property
    def fault_joint_indices(self):
        """List of all active faulty joint indices."""
        return list(self.active_faults.keys())

    @property
    def fault_type(self):
        """Primary/latest active fault type (backward compatibility)."""
        if self.active_faults:
            return list(self.active_faults.values())[-1]["type"]
        return FaultType.NONE

    @property
    def fault_params(self):
        """Primary/latest active fault params (backward compatibility)."""
        if self.active_faults:
            return list(self.active_faults.values())[-1]["params"]
        return {}

    @property
    def locked_angle(self):
        """Primary/latest locked angle (backward compatibility)."""
        if self.active_faults:
            info = list(self.active_faults.values())[-1]
            if info["type"] == FaultType.LOCKED:
                return info["params"].get("locked_angle", 0.0)
        return 0.0

    def _build_snake_model(self, base_position):
        """Build a 9-link snake robot with 8 Yaw revolute joints in PyBullet."""
        link_len = RobotConfig.LINK_LENGTH
        link_rad = RobotConfig.LINK_RADIUS
        link_mass = RobotConfig.LINK_MASS
        
        visual_shape = p.createVisualShape(
            shapeType=p.GEOM_CYLINDER,
            radius=link_rad,
            length=link_len,
            rgbaColor=[0.2, 0.6, 0.9, 1.0],
            visualFrameOrientation=p.getQuaternionFromEuler([np.pi/2, 0, 0])
        )
        collision_shape = p.createCollisionShape(
            shapeType=p.GEOM_CYLINDER,
            radius=link_rad,
            height=link_len,
            collisionFrameOrientation=p.getQuaternionFromEuler([np.pi/2, 0, 0])
        )
        
        link_masses = [link_mass] * self.num_joints
        link_collision_shapes = [collision_shape] * self.num_joints
        link_visual_shapes = [visual_shape] * self.num_joints
        link_positions = [[0, link_len, 0]] * self.num_joints
        link_orientations = [[0, 0, 0, 1]] * self.num_joints
        parent_indices = list(range(self.num_joints))
        joint_types = [p.JOINT_REVOLUTE] * self.num_joints
        joint_axes = [[0, 0, 1]] * self.num_joints
        
        robot_id = p.createMultiBody(
            baseMass=link_mass,
            baseCollisionShapeIndex=collision_shape,
            baseVisualShapeIndex=visual_shape,
            basePosition=base_position,
            baseOrientation=p.getQuaternionFromEuler([0, 0, 0]),
            linkMasses=link_masses,
            linkCollisionShapeIndices=link_collision_shapes,
            linkVisualShapeIndices=link_visual_shapes,
            linkPositions=link_positions,
            linkOrientations=link_orientations,
            linkInertialFramePositions=[[0, 0, 0]] * self.num_joints,
            linkInertialFrameOrientations=[[0, 0, 0, 1]] * self.num_joints,
            linkParentIndices=parent_indices,
            linkJointTypes=joint_types,
            linkJointAxis=joint_axes,
            physicsClientId=self.pc
        )
        
        # Set anisotropic friction on base and all links
        for link_idx in range(-1, self.num_joints):
            p.changeDynamics(
                robot_id, link_idx,
                lateralFriction=SimConfig.LATERAL_FRICTION,
                anisotropicFriction=[SimConfig.FORWARD_FRICTION, SimConfig.SIDEWAYS_FRICTION, 0.01],
                spinningFriction=0.001,
                rollingFriction=0.001,
                restitution=0.0,
                physicsClientId=self.pc
            )
            
        return robot_id

    def _setup_motors(self):
        """Configure motor limits and parameters."""
        for j_idx in self.joint_indices:
            p.changeDynamics(
                self.robot_id, j_idx,
                maxJointVelocity=RobotConfig.MAX_VELOCITY,
                physicsClientId=self.pc
            )

    def set_friction(self, lateral_friction=0.8, anisotropic_friction=None):
        """Update friction dynamics for base and all links."""
        if anisotropic_friction is None:
            anisotropic_friction = [SimConfig.FORWARD_FRICTION, SimConfig.SIDEWAYS_FRICTION, 0.01]
        for link_idx in range(-1, self.num_joints):
            p.changeDynamics(
                self.robot_id, link_idx,
                lateralFriction=lateral_friction,
                anisotropicFriction=anisotropic_friction,
                physicsClientId=self.pc
            )

    def inject_fault(self, joint_idx, fault_type, params=None):
        """Inject a joint failure into the robot model. Supports simultaneous multi-joint faults."""
        if joint_idx < 0 or joint_idx >= self.num_joints:
            raise ValueError(f"Invalid joint index: {joint_idx}")
            
        if fault_type == FaultType.NONE:
            self.clear_fault(joint_idx)
            return
            
        fault_params = dict(params or {})
        
        if fault_type == FaultType.LOCKED:
            if "locked_angle" not in fault_params or fault_params["locked_angle"] is None:
                joint_state = p.getJointState(self.robot_id, joint_idx, physicsClientId=self.pc)
                fault_params["locked_angle"] = float(joint_state[0])
            else:
                fault_params["locked_angle"] = float(fault_params["locked_angle"])
                
        self.active_faults[joint_idx] = {
            "type": fault_type,
            "params": fault_params
        }

    def clear_faults(self):
        """Clear all active joint faults."""
        self.active_faults.clear()

    def clear_fault(self, joint_idx):
        """Clear fault for a specific joint."""
        if joint_idx in self.active_faults:
            del self.active_faults[joint_idx]

    def inject_faults(self, faults_spec):
        """Batch inject multiple faults simultaneously."""
        if isinstance(faults_spec, dict):
            for j_idx, info in faults_spec.items():
                self.inject_fault(j_idx, info.get("type", FaultType.LOCKED), info.get("params", {}))
        elif isinstance(faults_spec, (list, tuple)):
            for item in faults_spec:
                if isinstance(item, int):
                    self.inject_fault(item, FaultType.LOCKED)
                elif isinstance(item, (tuple, list)):
                    j_idx = item[0]
                    ftype = item[1] if len(item) > 1 else FaultType.LOCKED
                    fparams = item[2] if len(item) > 2 else {}
                    self.inject_fault(j_idx, ftype, fparams)
                elif isinstance(item, dict):
                    j_idx = item["joint_idx"]
                    ftype = item.get("fault_type", item.get("type", FaultType.LOCKED))
                    fparams = item.get("params", {})
                    self.inject_fault(j_idx, ftype, fparams)

    def apply_joint_commands(self, target_angles):
        """Apply high-precision target joint angles via PyBullet motor control with fault injection."""
        applied_torques = []
        
        for i in range(self.num_joints):
            if i in self.active_faults:
                fault_info = self.active_faults[i]
                ftype = fault_info["type"]
                fparams = fault_info.get("params", {})
                
                if ftype == FaultType.LOCKED:
                    target_q = fparams.get("locked_angle", 0.0)
                    p.setJointMotorControl2(
                        self.robot_id, i,
                        controlMode=p.POSITION_CONTROL,
                        targetPosition=target_q,
                        force=RobotConfig.MAX_TORQUE,
                        physicsClientId=self.pc
                    )
                    applied_torques.append(RobotConfig.MAX_TORQUE)
                    continue
                    
                elif ftype in [FaultType.FREE, FaultType.LIMP, "limp"]:
                    # Unpowered loose joint: zero motor force
                    p.setJointMotorControl2(
                        self.robot_id, i,
                        controlMode=p.VELOCITY_CONTROL,
                        targetVelocity=0,
                        force=0.0,
                        physicsClientId=self.pc
                    )
                    applied_torques.append(0.0)
                    continue
                    
                elif ftype == FaultType.PARTIAL_TORQUE:
                    gamma_f = fparams.get("gamma_f", 0.3)
                    p.setJointMotorControl2(
                        self.robot_id, i,
                        controlMode=p.POSITION_CONTROL,
                        targetPosition=target_angles[i],
                        force=gamma_f * RobotConfig.MAX_TORQUE,
                        physicsClientId=self.pc
                    )
                    applied_torques.append(gamma_f * RobotConfig.MAX_TORQUE)
                    continue

            # Normal intact joint control
            p.setJointMotorControl2(
                self.robot_id, i,
                controlMode=p.POSITION_CONTROL,
                targetPosition=target_angles[i],
                force=RobotConfig.MAX_TORQUE,
                physicsClientId=self.pc
            )
            applied_torques.append(RobotConfig.MAX_TORQUE)
            
        return applied_torques

    def get_sensory_feedback(self):
        """Read joint positions, velocities, reaction forces, and head position."""
        joint_states = p.getJointStates(self.robot_id, self.joint_indices, physicsClientId=self.pc)
        angles = np.array([s[0] for s in joint_states])
        velocities = np.array([s[1] for s in joint_states])
        torques = np.array([s[3] for s in joint_states])
        
        base_pos, base_orn = p.getBasePositionAndOrientation(self.robot_id, physicsClientId=self.pc)
        base_vel, base_ang_vel = p.getBaseVelocity(self.robot_id, physicsClientId=self.pc)
        
        return {
            "joint_angles": angles,
            "joint_velocities": velocities,
            "joint_torques": torques,
            "base_position": np.array(base_pos),
            "base_orientation": np.array(base_orn),
            "base_velocity": np.array(base_vel),
            "base_angular_velocity": np.array(base_ang_vel)
        }
