# Milestone 1 Investigation & Implementation Strategy Report
**Simulation Engine & Benchmark Pipeline (Multi-Joint Faults, Dynamic Friction, Scaled Parallel Benchmarking)**

---

## 1. Observation

Direct investigation of the codebase revealed the following structural observations and limitations across simulation and experimental scripts:

### 1.1 `simulation/snake_robot.py`
- **Fault State Representation (Lines 29–35)**:
  ```python
  # Fault state tracking
  self.fault_active = False
  self.fault_joint_idx = None
  self.fault_type = FaultType.NONE
  self.fault_params = {}
  self.locked_angle = 0.0
  ```
  *Observation*: Fault state is stored in scalar attributes. Injecting a second fault overwrites `self.fault_joint_idx` and `self.fault_type`, making simultaneous multi-joint faults impossible.
- **Fault Injection Logic (Lines 112–125)**:
  ```python
  def inject_fault(self, joint_idx, fault_type, params=None):
      if joint_idx < 0 or joint_idx >= self.num_joints:
          raise ValueError(f"Invalid joint index: {joint_idx}")
      self.fault_active = True
      self.fault_joint_idx = joint_idx
      self.fault_type = fault_type
      self.fault_params = params or {}
      if fault_type == FaultType.LOCKED:
          joint_state = p.getJointState(self.robot_id, joint_idx, physicsClientId=self.pc)
          self.locked_angle = joint_state[0]
  ```
  *Observation*: If `fault_type == FaultType.LOCKED`, the method always captures current `joint_state[0]` and completely ignores explicit locked angles provided in `params` (e.g. `params={'locked_angle': 0.0}` or `params={'locked_angle': 0.2618}`).
- **Motor Control Dispatch (Lines 130–167)**:
  ```python
  for i in range(self.num_joints):
      if self.fault_active and i == self.fault_joint_idx:
          # Only executes for a single joint index self.fault_joint_idx
  ```
  *Observation*: Only one faulty joint can ever be intercepted during motor actuation. Simultaneous consecutive (J3+J4), non-consecutive (J2+J5), head (J0/J1), mid (J3/J4), and tail (J6/J7) faults are not actuated properly. Furthermore, `FaultType.LIMP` is not defined in `FaultType` (only `FREE` exists).

### 1.2 `simulation/environments.py`
- **Environment Types (Lines 9–13)**:
  ```python
  class EnvironmentType:
      FLAT = "flat"
      LOW_FRICTION = "low_friction"
      VARIABLE_FRICTION = "variable_friction"
      INCLINE = "incline"
  ```
  *Observation*: `EnvironmentType` lacks explicit definitions for `HIGH_SLIP` isotropic friction.
- **Ground Dynamics & Runtime Transitions (Lines 44–58, 97–99)**:
  ```python
  def _build_ground(self):
      ...
      friction = 0.8
      if self.env_type == EnvironmentType.LOW_FRICTION:
          friction = 0.25
      p.changeDynamics(plane_id, -1, lateralFriction=friction, physicsClientId=self.physics_client)
      return plane_id
  ```
  *Observation*: Ground friction is statically configured at initialization. There is no mid-run transition callback, trigger logic, or helper method to alter ground plane lateral friction and snake robot link anisotropic friction during simulation execution at $t_{trans}$.

### 1.3 `experiments/run_publication_experiments.py` & `run_publication_experiments_parallel.py`
- **Benchmark Seed Configuration & Multi-Joint Coverage**:
  - `run_publication_experiments_parallel.py` currently configures:
    ```python
    NUM_SEEDS_BENCHMARK = 5      # Only 5 seeds
    NUM_SEEDS_GENERALIZATION = 5 # Only 5 seeds
    ```
    *Observation*: Project specifications (R2, PROJECT.md) require $N \ge 10$ independent random seeds per scenario for journal publication.
  - The benchmark suite in `run_publication_experiments.py` only tests 3 single-joint locations (`PUB_FAULT_JOINTS = [1, 3, 5]`) and standard locked/free/partial modes, omitting explicit locked 0 rad, locked non-zero offsets (+15°), consecutive dual faults (J3+J4), non-consecutive dual faults (J2+J5), head (J1), mid (J3), and tail (J7) full matrix evaluations.
  - The generalization suite does not test the dynamic mid-run friction transition scenario (`EnvironmentType.VARIABLE_FRICTION` transitioning from anisotropic to high-slip isotropic at $t_{trans}=30.0$ s).

---

## 2. Logic Chain

From these direct observations, the reasoning leading to the required implementation strategy is structured as follows:

1. **Multi-Joint Fault Dictionary (`self.active_faults`)**:
   - *Premise*: To support simultaneous multi-joint faults (consecutive J3+J4, non-consecutive J2+J5, head, mid, tail), each joint must maintain independent fault status and parameters.
   - *Mechanism*: Replace scalar fault tracking in `SnakeRobot` with `self.active_faults = {}` where keys are `joint_idx` (0 to 7) and values are dictionaries: `{'type': fault_type, 'params': params}`.
   - *Backward Compatibility*: Provide `@property` getters for `fault_active` (`len(self.active_faults) > 0`), `fault_joint_idx` (first active key or None), `fault_type`, and `fault_params`. This guarantees that legacy single-joint consumers (e.g. C4 Oracle controller, logging routines) continue functioning without breaking.
   - *Locked Angle Specification*: When `inject_fault(joint_idx, FaultType.LOCKED, params)` is called, if `params` contains `'locked_angle'`, store that float value; if omitted or None, capture the joint's instantaneous physical angle from `p.getJointState(...)`.
   - *Limp Mode*: Alias `FaultType.LIMP = "free"` and `FaultType.FREE = "free"` in `FaultType`. In `apply_joint_commands`, set motor control to `VELOCITY_CONTROL` with `targetVelocity=0, force=0.0`, resulting in a completely unpowered, freely rotating joint under external contact forces.

2. **Dynamic Mid-Run Friction Transition Handler**:
   - *Premise*: Simulating realistic environmental shifts (e.g. entering icy or mud terrain) requires altering ground and link contact dynamics during runtime at $t_{trans}$ (e.g. 30.0 s).
   - *Mechanism*: In `SimulationEnvironment`, implement `check_and_apply_transition(current_time, robot=None)` and `apply_friction_transition(robot=None, ...)`.
   - *Link Dynamics Update*: When transitioning to `HIGH_SLIP` or `LOW_FRICTION`, update ground plane `lateralFriction` (e.g. $0.8 \to 0.15$) and call `robot.set_friction(lateral_friction=0.20, anisotropic_friction=[0.15, 0.15, 0.01])` across all 9 snake segments.

3. **Scaled Parallel Benchmark Matrix ($N \ge 10$ Seeds)**:
   - *Premise*: Rigorous statistical validation (Wilcoxon signed-rank, Mann-Whitney U, Cliff's delta, ANOVA) demands $N \ge 10$ independent random seeds across all 6 controllers (C1–C6) and comprehensive fault/environmental configurations.
   - *Benchmark Matrix ($480$ episodes)*:
     - 6 Controllers: C1 (Fixed), C2 (Error-Adaptive), C3 (Shape-Recovery), C4 (Oracle), C5 (Proposed AHM-CPG), C6 (AHM w/o Bypass).
     - 8 Fault Scenarios:
       1. `locked_0rad_head`: Joint 1 locked at 0.0 rad.
       2. `locked_0rad_mid`: Joint 3 locked at 0.0 rad.
       3. `locked_0rad_tail`: Joint 7 locked at 0.0 rad.
       4. `locked_offset_mid`: Joint 3 locked at +15° (+0.2618 rad).
       5. `limp_mid`: Joint 3 unpowered / limp mode.
       6. `dual_consecutive_j3_j4`: Consecutive dual faults on J3 and J4 locked at 0.0 rad.
       7. `dual_nonconsecutive_j2_j5`: Non-consecutive dual faults on J2 and J5 locked at 0.0 rad.
       8. `partial_torque_mid`: Joint 3 with 30% torque capability ($\gamma_f=0.3$).
     - 10 Seeds per scenario $\implies 6 \times 8 \times 10 = 480$ episodes.
   - *Generalization & Environmental Matrix ($420$ episodes)*:
     - 6 Controllers (C1–C6) $\times$ 7 Stress Modes $\times$ 10 Seeds $\implies 420$ episodes.
     - Modes: `intermittent`, `incline_10deg`, `sensor_noise`, `mass_perturbation`, `high_slip`, `low_friction`, `dynamic_friction`.
   - *Parallel Architecture*: Use `multiprocessing.Pool(processes=min(cpu_count() - 1, 8))` with deterministic seed perturbation (initial joint pose $\pm 2^\circ$, link friction $\pm 10\%$, fault timing jitter $\pm 0.5$ s, mass scale $\pm 3\%$) to guarantee statistical independence in PyBullet DIRECT mode.

4. **Data Persistence Schema**:
   - All results formatted into JSON records containing `controller`, `fault_type`, `joint_idx`, `fault_scenario`, `joints`, `seed`, and the complete `LocomotionMetrics` dictionary.
   - Save targets:
     - `results/publication/data/benchmark_results.json`
     - `results/publication/data/generalization_results.json`
     - `results/publication/data/detail_histories/` (full time-series trajectory and state history for C1–C6 under locked J3, dynamic friction, and dual locked J3+J4).

---

## 3. Caveats

- **PyBullet Multiprocessing Constraints**: PyBullet instances cannot share memory across process boundaries. Each multiprocessing worker in `run_publication_experiments_parallel.py` must independently initialize `SimulationEnvironment(gui=False)` in `DIRECT` mode and disconnect cleanly upon episode completion.
- **Physics Determinism**: Because PyBullet in DIRECT mode is deterministic for fixed initial states, seed perturbation (via `np.random.seed(seed)` injecting micro-variations into initial joint poses, link friction, mass, and fault timing) is required to produce true empirical distribution variance for $N \ge 10$ seeds.
- **Intact Joint Metric Filtering**: During multi-joint faults (e.g. J3+J4 or J2+J5), dynamic RMS torque calculation ($\tau_{RMS}$) and power computation in `LocomotionMetrics` must account for multiple locked or unpowered actuators.

---

## 4. Conclusion & Recommended Implementation Strategy

### 4.1 Exact Code Specification for `simulation/snake_robot.py`

#### Module Changes:
```python
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
    LIMP = "free"                 # Alias for unpowered passive joint
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

    @property
    def fault_joint_idx(self):
        """Primary/first active fault joint index (backward compatibility)."""
        if self.active_faults:
            return next(iter(self.active_faults.keys()))
        return None

    @property
    def fault_joint_indices(self):
        """List of all active faulty joint indices."""
        return list(self.active_faults.keys())

    @property
    def fault_type(self):
        """Primary active fault type (backward compatibility)."""
        if self.active_faults:
            return next(iter(self.active_faults.values()))["type"]
        return FaultType.NONE

    @property
    def fault_params(self):
        """Primary active fault params (backward compatibility)."""
        if self.active_faults:
            return next(iter(self.active_faults.values()))["params"]
        return {}

    @property
    def locked_angle(self):
        """Primary locked angle (backward compatibility)."""
        if self.active_faults:
            info = next(iter(self.active_faults.values()))
            if info["type"] == FaultType.LOCKED:
                return info["params"].get("locked_angle", 0.0)
        return 0.0

    def _build_snake_model(self, base_position):
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
        """Apply target joint angles via PyBullet motor control with multi-joint fault injection."""
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
                    # Unpowered loose / limp joint: zero motor force
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
        """Read joint positions, velocities, reaction forces, and base pose/velocity."""
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
```

---

### 4.2 Exact Code Specification for `simulation/environments.py`

#### Module Changes:
```python
"""
PyBullet Simulation Environments for Snake Robot Locomotion with H.264 Video Recording
and Dynamic Friction Transition Handling.
"""

import pybullet as p
import pybullet_data
import numpy as np

class EnvironmentType:
    FLAT = "flat"                           # Standard anisotropic ground (mu_lat=0.95, mu_fwd=0.05)
    HIGH_SLIP = "high_slip"                 # High-slip isotropic terrain (mu_lat=0.15, mu_fwd=0.15)
    LOW_FRICTION = "low_friction"           # Low-friction terrain (plane mu=0.25, mu_fwd=0.05)
    VARIABLE_FRICTION = "variable_friction" # Dynamic transition at t_trans
    INCLINE = "incline"                     # Sloped ground (incline_deg)

class SimulationEnvironment:
    def __init__(
        self,
        gui=False,
        env_type=EnvironmentType.FLAT,
        incline_deg=0.0,
        record_video=False,
        video_filepath="results/videos/simulation.mp4",
        transition_time=30.0,
        target_transition_env=EnvironmentType.HIGH_SLIP,
        transition_callback=None
    ):
        self.gui = gui
        self.env_type = env_type
        self.incline_deg = incline_deg
        self.record_video = record_video
        self.video_filepath = video_filepath
        self.transition_time = transition_time
        self.target_transition_env = target_transition_env
        self.transition_callback = transition_callback
        self.transition_applied = False
        
        # Connect to PyBullet engine
        connection_mode = p.GUI if self.gui else p.DIRECT
        self.physics_client = p.connect(connection_mode)
        
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=self.physics_client)
        p.setGravity(0, 0, -9.81, physicsClientId=self.physics_client)
        p.setTimeStep(0.005, physicsClientId=self.physics_client)
        
        # Build floor ground plane
        self.plane_id = self._build_ground()
        
        # Video recorder setup
        self.video_writer = None
        self.frame_skip = 6
        self.step_counter = 0
        if self.record_video:
            import imageio
            import os
            os.makedirs(os.path.dirname(self.video_filepath), exist_ok=True)
            self.video_writer = imageio.get_writer(self.video_filepath, fps=30, format='FFMPEG', codec='libx264')

    def _build_ground(self):
        """Load ground plane with specific friction / geometry according to environment type."""
        if self.env_type == EnvironmentType.INCLINE and self.incline_deg != 0.0:
            rad = np.deg2rad(self.incline_deg)
            orn = p.getQuaternionFromEuler([0, -rad, 0])
            plane_id = p.loadURDF("plane.urdf", [0, 0, 0], orn, physicsClientId=self.physics_client)
        else:
            plane_id = p.loadURDF("plane.urdf", [0, 0, 0], physicsClientId=self.physics_client)
            
        friction = 0.8
        if self.env_type == EnvironmentType.LOW_FRICTION:
            friction = 0.25
        elif self.env_type == EnvironmentType.HIGH_SLIP:
            friction = 0.15
            
        p.changeDynamics(plane_id, -1, lateralFriction=friction, physicsClientId=self.physics_client)
        return plane_id

    def check_and_apply_transition(self, current_time, robot=None):
        """Check if simulation time has reached transition_time in VARIABLE_FRICTION mode, and apply dynamics change."""
        if self.env_type == EnvironmentType.VARIABLE_FRICTION and not self.transition_applied:
            if current_time >= self.transition_time:
                self.apply_friction_transition(robot=robot)
                self.transition_applied = True
                return True
        return False

    def apply_friction_transition(self, robot=None, plane_friction=None, link_lateral_friction=None, link_anisotropic_friction=None):
        """Apply friction transition to ground plane and snake robot links."""
        if self.transition_callback is not None:
            self.transition_callback(self, robot)
            return

        target = self.target_transition_env
        if plane_friction is None:
            plane_friction = 0.15 if target == EnvironmentType.HIGH_SLIP else 0.25
            
        p.changeDynamics(self.plane_id, -1, lateralFriction=plane_friction, physicsClientId=self.physics_client)

        if robot is not None:
            if link_lateral_friction is None:
                link_lateral_friction = 0.20 if target == EnvironmentType.HIGH_SLIP else 0.30
            if link_anisotropic_friction is None:
                if target == EnvironmentType.HIGH_SLIP:
                    link_anisotropic_friction = [0.15, 0.15, 0.01]  # Isotropic high slip
                else:
                    link_anisotropic_friction = [0.05, 0.25, 0.01]  # Low lateral resistance
                    
            robot.set_friction(
                lateral_friction=link_lateral_friction,
                anisotropic_friction=link_anisotropic_friction
            )

    def capture_frame(self, target_pos=(0, 0, 0)):
        """Capture RGB camera frame tracking the robot position."""
        if not self.record_video or self.video_writer is None:
            return
            
        self.step_counter += 1
        if self.step_counter % self.frame_skip != 0:
            return
            
        view_matrix = p.computeViewMatrixFromYawPitchRoll(
            cameraTargetPosition=target_pos,
            distance=2.2,
            yaw=45,
            pitch=-35,
            roll=0,
            upAxisIndex=2,
            physicsClientId=self.physics_client
        )
        proj_matrix = p.computeProjectionMatrixFOV(
            fov=60,
            aspect=1.33,
            nearVal=0.1,
            farVal=100.0,
            physicsClientId=self.physics_client
        )
        width, height, rgb_img, _, _ = p.getCameraImage(
            width=640,
            height=480,
            viewMatrix=view_matrix,
            projectionMatrix=proj_matrix,
            physicsClientId=self.physics_client
        )
        rgba_array = np.reshape(rgb_img, (height, width, 4)).astype(np.uint8)
        rgb_array = rgba_array[:, :, :3]
        self.video_writer.append_data(rgb_array)

    def step(self):
        p.stepSimulation(physicsClientId=self.physics_client)

    def close(self):
        if self.video_writer is not None:
            self.video_writer.close()
        p.disconnect(physicsClientId=self.physics_client)
```

---

### 4.3 Exact Code Specification for `experiments/run_publication_experiments.py` & `run_publication_experiments_parallel.py`

#### 1. Parameterization & `run_episode` Function Signature:
```python
def run_episode(
    controller_type,
    fault_type=FaultType.LOCKED,
    fault_joint_idx=3,
    fault_time=PUB_FAULT_TIME,
    duration=PUB_DURATION,
    seed=42,
    env_type=EnvironmentType.FLAT,
    incline_deg=0.0,
    mass_scale=1.0,
    sensor_noise_std=0.0,
    intermittent=False,
    multi_joint_faults=None,          # List of ints or list of (joint_idx, fault_type, params)
    fault_params=None,                # e.g. {"locked_angle": 0.0} or {"locked_angle": 0.2618}
    transition_time=30.0,
    target_transition_env=EnvironmentType.HIGH_SLIP,
    save_history=False
):
```

#### 2. Fault Injection Handling inside Simulation Loop:
```python
    # Simulation loop
    for step in range(sim_steps):
        current_time = step * SimConfig.TIMESTEP
        
        # Check dynamic environmental transition
        env.check_and_apply_transition(current_time, robot=robot)
        
        # Fault Injection Logic
        if current_time >= fault_time_actual:
            if intermittent:
                if current_time >= next_toggle_time:
                    intermittent_state = not intermittent_state
                    next_toggle_time = current_time + np.random.uniform(1.5, 3.0)
                    if intermittent_state:
                        robot.inject_fault(joint_idx=fault_joint_idx, fault_type=fault_type, params=fault_params)
                    else:
                        robot.clear_faults()
            elif multi_joint_faults is not None:
                if not fault_injected:
                    robot.inject_faults(multi_joint_faults)
                    fault_injected = True
            elif not fault_injected and fault_type != FaultType.NONE:
                robot.inject_fault(joint_idx=fault_joint_idx, fault_type=fault_type, params=fault_params)
                fault_injected = True
```

#### 3. Controller Fault Info Dispatch for C4 Oracle:
```python
    if controller_type in ["C4", "oracle"]:
        fault_info = {
            "active": robot.fault_active,
            "joint_idx": robot.fault_joint_idx,
            "active_faults": robot.active_faults
        }
        target_angles, ctrl_info = controller.step(sensory, fault_info=fault_info)
    else:
        target_angles, ctrl_info = controller.step(sensory)
```

#### 4. Scaled Parallel Matrix Definitions:
```python
NUM_SEEDS_BENCHMARK = 10       # 10 seeds x 6 ctrls x 8 fault scenarios = 480 episodes
NUM_SEEDS_GENERALIZATION = 10  # 10 seeds x 6 ctrls x 7 stress modes = 420 episodes

BENCHMARK_SCENARIOS = [
    {"name": "locked_0rad_head", "fault_type": FaultType.LOCKED, "joints": [1], "params": {"locked_angle": 0.0}},
    {"name": "locked_0rad_mid", "fault_type": FaultType.LOCKED, "joints": [3], "params": {"locked_angle": 0.0}},
    {"name": "locked_0rad_tail", "fault_type": FaultType.LOCKED, "joints": [7], "params": {"locked_angle": 0.0}},
    {"name": "locked_offset_mid", "fault_type": FaultType.LOCKED, "joints": [3], "params": {"locked_angle": 0.2618}},
    {"name": "limp_mid", "fault_type": FaultType.FREE, "joints": [3], "params": {}},
    {"name": "dual_consecutive_j3_j4", "fault_type": FaultType.LOCKED, "joints": [3, 4], "params": {"locked_angle": 0.0}},
    {"name": "dual_nonconsecutive_j2_j5", "fault_type": FaultType.LOCKED, "joints": [2, 5], "params": {"locked_angle": 0.0}},
    {"name": "partial_torque_mid", "fault_type": FaultType.PARTIAL_TORQUE, "joints": [3], "params": {"gamma_f": 0.3}}
]

GENERALIZATION_MODES = [
    "intermittent",
    "incline_10deg",
    "sensor_noise",
    "mass_perturbation",
    "high_slip",
    "low_friction",
    "dynamic_friction"
]
```

---

## 5. Verification Method

To independently verify the implementation of Milestone 1, execute the following automated validation tests:

### 5.1 Multi-Joint Fault Injection Unit Test
Run the following verification snippet:
```python
import pybullet as p
from simulation.environments import SimulationEnvironment, EnvironmentType
from simulation.snake_robot import SnakeRobot, FaultType
from config import RobotConfig

env = SimulationEnvironment(gui=False, env_type=EnvironmentType.FLAT)
robot = SnakeRobot(physics_client=env.physics_client)

# Test 1: Inject Consecutive Dual Fault J3+J4
robot.inject_fault(3, FaultType.LOCKED, params={"locked_angle": 0.0})
robot.inject_fault(4, FaultType.LOCKED, params={"locked_angle": 0.2618})
assert robot.fault_active == True
assert len(robot.active_faults) == 2
assert robot.active_faults[3]["params"]["locked_angle"] == 0.0
assert abs(robot.active_faults[4]["params"]["locked_angle"] - 0.2618) < 1e-4

# Test 2: Apply commands and verify applied torques & motor states
target_angles = [0.1] * 8
torques = robot.apply_joint_commands(target_angles)
assert len(torques) == 8
assert torques[3] == RobotConfig.MAX_TORQUE
assert torques[4] == RobotConfig.MAX_TORQUE

# Test 3: Inject Limp/Free fault on J2
robot.inject_fault(2, FaultType.FREE)
assert len(robot.active_faults) == 3
torques = robot.apply_joint_commands(target_angles)
assert torques[2] == 0.0

# Test 4: Clear faults
robot.clear_faults()
assert robot.fault_active == False
assert len(robot.active_faults) == 0

env.close()
print("MULTI-JOINT FAULT TEST: PASSED")
```

### 5.2 Dynamic Friction Mid-Run Transition Test
```python
from simulation.environments import SimulationEnvironment, EnvironmentType
from simulation.snake_robot import SnakeRobot

env = SimulationEnvironment(gui=False, env_type=EnvironmentType.VARIABLE_FRICTION, transition_time=5.0, target_transition_env=EnvironmentType.HIGH_SLIP)
robot = SnakeRobot(physics_client=env.physics_client)

# Pre-transition check (t=4.0)
applied = env.check_and_apply_transition(4.0, robot=robot)
assert not applied
assert not env.transition_applied

# Transition trigger (t=5.0)
applied = env.check_and_apply_transition(5.05, robot=robot)
assert applied
assert env.transition_applied

# Post-transition check (t=6.0 should not re-trigger)
applied_again = env.check_and_apply_transition(6.0, robot=robot)
assert not applied_again

env.close()
print("DYNAMIC FRICTION TRANSITION TEST: PASSED")
```

### 5.3 Parallel Benchmark Execution Test
Execute the master parallel pipeline in test mode (or full mode):
```powershell
python experiments/run_publication_experiments_parallel.py
```
**Verification Criteria**:
1. Zero crashes or unhandled exceptions across all multiprocessing worker pools.
2. `results/publication/data/benchmark_results.json` contains $N \ge 10$ records per scenario with non-null `metrics` fields.
3. `results/publication/data/generalization_results.json` contains records for all 7 stress modes across C1–C6.
4. `results/publication/data/detail_histories/` contains full time-series logs for C1–C6 under locked, dynamic friction, and dual fault scenarios.
5. Invalidation conditions: Any `None` metrics records, empty JSON files, or missing keys in `metrics` (`v_pre_fwd`, `v_post_fwd`, `recovery_ratio`, `cost_of_transport`, `t_adapt`, `tau_rms`).
