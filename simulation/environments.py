"""
PyBullet Simulation Environments for Snake Robot Locomotion with H.264 Video Recording.
"""

import pybullet as p
import pybullet_data
import numpy as np

from config import SimConfig

class EnvironmentType:
    FLAT = "flat"
    LOW_FRICTION = "low_friction"
    VARIABLE_FRICTION = "variable_friction"
    INCLINE = "incline"

class SimulationEnvironment:
    def __init__(self, gui=False, env_type=EnvironmentType.FLAT, incline_deg=0.0, record_video=False, video_filepath="results/videos/simulation.mp4"):
        self.gui = gui
        self.env_type = env_type
        self.incline_deg = incline_deg
        self.record_video = record_video
        self.video_filepath = video_filepath
        
        # Connect to PyBullet engine
        connection_mode = p.GUI if self.gui else p.DIRECT
        self.physics_client = p.connect(connection_mode)
        
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=self.physics_client)
        p.setGravity(0, 0, -9.81, physicsClientId=self.physics_client)
        p.setTimeStep(SimConfig.TIMESTEP, physicsClientId=self.physics_client)
        p.setPhysicsEngineParameter(
            numSolverIterations=SimConfig.NUM_SOLVER_ITERATIONS,
            physicsClientId=self.physics_client,
        )
        
        # Build floor ground plane
        self.plane_id = self._build_ground()
        
        # Video recorder setup (H.264 MP4 format for universal browser compatibility)
        self.video_writer = None
        self.video_backend = None
        self.record_fps = 30
        self.step_counter = 0
        if self.record_video:
            import imageio
            import os
            os.makedirs(os.path.dirname(self.video_filepath), exist_ok=True)
            try:
                self.video_writer = imageio.get_writer(
                    self.video_filepath, fps=30, format='FFMPEG', codec='libx264'
                )
                self.video_backend = "imageio_ffmpeg"
            except ImportError:
                import cv2
                self.video_writer = cv2.VideoWriter(
                    self.video_filepath,
                    cv2.VideoWriter_fourcc(*"mp4v"),
                    30.0,
                    (640, 480),
                )
                if not self.video_writer.isOpened():
                    raise RuntimeError("Neither imageio-FFMPEG nor OpenCV MP4 writer is available")
                self.video_backend = "opencv_mp4v"

    def _build_ground(self):
        """Load ground plane with specific friction / geometry according to environment type."""
        if self.env_type == EnvironmentType.VARIABLE_FRICTION:
            # Use adjacent surface tiles so the robot experiences spatially
            # varying friction instead of an alias for FLAT.
            tile_shape = p.createCollisionShape(
                p.GEOM_BOX,
                halfExtents=[2.5, 2.5, 0.05],
                physicsClientId=self.physics_client
            )
            frictions = [0.25, 0.8, 1.2]
            self.surface_ids = []
            for index, friction in enumerate(frictions):
                tile_id = p.createMultiBody(
                    baseMass=0.0,
                    baseCollisionShapeIndex=tile_shape,
                    basePosition=[(index - 1) * 5.0, 0.0, -0.05],
                    physicsClientId=self.physics_client
                )
                p.changeDynamics(
                    tile_id, -1, lateralFriction=friction,
                    physicsClientId=self.physics_client
                )
                self.surface_ids.append(tile_id)
            return self.surface_ids[0]

        if self.env_type == EnvironmentType.INCLINE and self.incline_deg != 0.0:
            rad = np.deg2rad(self.incline_deg)
            orn = p.getQuaternionFromEuler([0, -rad, 0])
            plane_id = p.loadURDF("plane.urdf", [0, 0, 0], orn, physicsClientId=self.physics_client)
        else:
            plane_id = p.loadURDF("plane.urdf", [0, 0, 0], physicsClientId=self.physics_client)
            
        friction = 0.8
        if self.env_type == EnvironmentType.LOW_FRICTION:
            friction = 0.25
            
        p.changeDynamics(plane_id, -1, lateralFriction=friction, physicsClientId=self.physics_client)
        self.surface_ids = [plane_id]
        return plane_id

    def capture_frame(self, target_pos=(0, 0, 0)):
        """Capture RGB camera frame tracking the robot position."""
        if not self.record_video or self.video_writer is None:
            return
        self.step_counter += 1
        if not self._should_capture_frame(self.step_counter):
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
        # Convert RGBA buffer to RGB numpy array for imageio writer
        rgba_array = np.asarray(rgb_img, dtype=np.uint8).reshape((height, width, 4))
        rgb_array = rgba_array[:, :, :3]
        if self.video_backend == "imageio_ffmpeg":
            self.video_writer.append_data(rgb_array)
        else:
            import cv2
            self.video_writer.write(cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR))

    def _should_capture_frame(self, step_number):
        """Return whether this simulation step crosses the next video-frame time."""
        physics_hz = int(round(1.0 / SimConfig.TIMESTEP))
        previous_frames = ((step_number - 1) * self.record_fps) // physics_hz
        current_frames = (step_number * self.record_fps) // physics_hz
        return current_frames > previous_frames

    def step(self):
        p.stepSimulation(physicsClientId=self.physics_client)

    def close(self):
        if self.video_writer is not None:
            if self.video_backend == "imageio_ffmpeg":
                self.video_writer.close()
            else:
                self.video_writer.release()
            print(f"Video saved to {self.video_filepath}")
        p.disconnect(physicsClientId=self.physics_client)
