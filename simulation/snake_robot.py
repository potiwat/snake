"""
Snake Robot PyBullet MultiBody Model & Fault Injector.
"""

import pybullet as p
import pybullet_data
import numpy as np
from config import RobotConfig, SimConfig

class FaultType:
    NONE = "none"
    LOCKED = "locked"
    FREE = "free"
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
        
        # Fault state tracking
        self.fault_active = False
        self.fault_joint_idx = None
        self.fault_type = FaultType.NONE
        self.fault_params = {}
        self.locked_angle = 0.0
        self.active_faults = {}
        self.last_commanded_torques = [0.0] * self.num_joints

    def _build_snake_model(self, base_position):
        """Build a 9-link snake robot with 8 Yaw revolute joints in PyBullet."""
        link_len = RobotConfig.LINK_LENGTH
        link_rad = RobotConfig.LINK_RADIUS
        link_mass = RobotConfig.LINK_MASS
        
        # Visual & Collision shapes for cylindrical segment
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
        
        # Link positions relative to parent joint
        link_positions = [[0, link_len, 0]] * self.num_joints
        link_orientations = [[0, 0, 0, 1]] * self.num_joints
        parent_indices = list(range(self.num_joints)) # 0 is base, 1 is child of 0, etc.
        
        # Joint types (all Revolute around Z axis for Yaw motion)
        joint_types = [p.JOINT_REVOLUTE] * self.num_joints
        joint_axes = [[0, 0, 1]] * self.num_joints # Yaw axis
        
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
        
        # Set link friction properties for anisotropic snake scale propulsion
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

    def inject_fault(self, joint_idx, fault_type, params=None):
        """Inject a joint failure into the robot model."""
        if joint_idx < 0 or joint_idx >= self.num_joints:
            raise ValueError(f"Invalid joint index: {joint_idx}")
            
        self.fault_active = True
        self.fault_joint_idx = joint_idx
        self.fault_type = fault_type
        self.fault_params = params or {}
        previous_fault = self.active_faults.get(joint_idx, {})
        old_constraint = previous_fault.get("constraint_id")
        if old_constraint is not None:
            p.removeConstraint(old_constraint, physicsClientId=self.pc)
        self.active_faults[joint_idx] = {
            "type": fault_type,
            "params": self.fault_params.copy(),
        }
        
        if fault_type == FaultType.LOCKED:
            joint_state = p.getJointState(self.robot_id, joint_idx, physicsClientId=self.pc)
            self.locked_angle = joint_state[0]
            self.active_faults[joint_idx]["constraint_id"] = p.createConstraint(
                self.robot_id,
                joint_idx - 1,
                self.robot_id,
                joint_idx,
                p.JOINT_FIXED,
                [0, 0, 1],
                [0, RobotConfig.LINK_LENGTH, 0],
                [0, 0, 0],
                parentFrameOrientation=[0, 0, 0, 1],
                childFrameOrientation=p.getQuaternionFromEuler(
                    [0, 0, -self.locked_angle]
                ),
                physicsClientId=self.pc
            )
            self.active_faults[joint_idx]["locked_angle"] = self.locked_angle

    def apply_joint_commands(self, target_angles):
        """Apply high-precision target joint angles via PyBullet motor control with fault injection."""
        applied_torques = []

        if not self.fault_active:
            for fault in self.active_faults.values():
                constraint_id = fault.get("constraint_id")
                if constraint_id is not None:
                    p.removeConstraint(constraint_id, physicsClientId=self.pc)
            self.active_faults.clear()
        
        for i in range(self.num_joints):
            fault = self.active_faults.get(i) if self.fault_active else None
            if fault is not None:
                fault_type = fault["type"]
                if fault_type == FaultType.LOCKED:
                    p.setJointMotorControl2(
                        self.robot_id, i,
                        controlMode=p.VELOCITY_CONTROL,
                        targetVelocity=0.0,
                        force=0.0,
                        physicsClientId=self.pc
                    )
                    applied_torques.append(0.0)
                    continue
                    
                elif fault_type == FaultType.FREE:
                    # Unpowered loose joint: force = 0
                    p.setJointMotorControl2(
                        self.robot_id, i,
                        controlMode=p.VELOCITY_CONTROL,
                        targetVelocity=0,
                        force=0.0,
                        physicsClientId=self.pc
                    )
                    applied_torques.append(0.0)
                    continue
                    
                elif fault_type == FaultType.PARTIAL_TORQUE:
                    gamma_f = fault["params"].get("gamma_f", 0.3)
                    p.setJointMotorControl2(
                        self.robot_id, i,
                        controlMode=p.POSITION_CONTROL,
                        targetPosition=target_angles[i],
                        force=gamma_f * RobotConfig.MAX_TORQUE,
                        physicsClientId=self.pc
                    )
                    applied_torques.append(gamma_f * RobotConfig.MAX_TORQUE)
                    continue

            # High-precision POSITION_CONTROL tracking for active normal joints
            p.setJointMotorControl2(
                self.robot_id, i,
                controlMode=p.POSITION_CONTROL,
                targetPosition=target_angles[i],
                force=RobotConfig.MAX_TORQUE,
                physicsClientId=self.pc
            )
            applied_torques.append(RobotConfig.MAX_TORQUE)
            
        self.last_commanded_torques = applied_torques.copy()
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
            "commanded_torques": self.last_commanded_torques.copy(),
            "base_position": np.array(base_pos),
            "base_orientation": np.array(base_orn),
            "base_velocity": np.array(base_vel),
            "base_angular_velocity": np.array(base_ang_vel)
        }
