"""
PyBullet Simulation Environments for Snake Robot Locomotion with H.264 Video Recording.
"""

import pybullet as p
import pybullet_data
import numpy as np

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
        p.setTimeStep(0.005, physicsClientId=self.physics_client)
        
        # Build floor ground plane
        self.plane_id = self._build_ground()
        
        # Video recorder setup (H.264 MP4 format for universal browser compatibility)
        self.video_writer = None
        self.frame_skip = 6  # Record 1 frame every 6 sim steps (~33.3 fps at 200Hz sim)
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
            
        p.changeDynamics(plane_id, -1, lateralFriction=friction, physicsClientId=self.physics_client)
        return plane_id

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
        # Convert RGBA buffer to RGB numpy array for imageio writer
        rgba_array = np.reshape(rgb_img, (height, width, 4)).astype(np.uint8)
        rgb_array = rgba_array[:, :, :3]
        self.video_writer.append_data(rgb_array)

    def step(self):
        p.stepSimulation(physicsClientId=self.physics_client)

    def close(self):
        if self.video_writer is not None:
            self.video_writer.close()
            print(f"Video saved to {self.video_filepath}")
        p.disconnect(physicsClientId=self.physics_client)
