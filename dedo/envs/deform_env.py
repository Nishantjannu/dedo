#
# Dynamic environments with deformable objects.
#
# @contactrika, @pyshi
#
import os
import time

import numpy as np
import gym
import pybullet
import pybullet_data

from ..utils.anchor_utils import (
    attach_anchor, create_anchor, command_anchor_velocity)
from ..utils.init_utils import (
    init_bullet, load_rigid_object, load_soft_object)
from ..utils.gen_cloth import create_cloth_obj
from ..utils.mesh_utils import get_mesh_data
from ..utils.task_info import DEFORM_INFO, SCENE_INFO, TASK_TYPES


class DeformEnv(gym.Env):
    ANCHOR_OBS_SIZE = 3  # 3D velocity for anchors
    MAX_VEL = 100.0  # max vel (in m/s) for the anchors
    NUM_ANCHORS = 2
    WORKSPACE_BOX_SIZE = 2.0  # workspace box limits (needs to be >=1)

    def __init__(self, version, args):
        self.args = args
        self.version = version
        self.max_episode_len = args.max_episode_len
        self.cam_on = args.cam_resolution is not None
        self.cam_args = {
            'cameraDistance': 1.2,
            'cameraYaw': 140,
            'cameraPitch': -40,
            'cameraTargetPosition': np.array([0.0, 0, 0])
        }
        self.sim = init_bullet(
            self.args, cam_on=self.cam_on, cam_args=self.cam_args)
        self.rigid_ids, self.deform_id, self.goal_pos = self.load_objects(
            self.sim, version, self.args)
        # Define sizes of observation and action spaces.
        if args.cam_resolution is None:
            state_sz = DeformEnv.NUM_ANCHORS*DeformEnv.ANCHOR_OBS_SIZE
            self.observation_space = gym.spaces.Box(
                -1.0*DeformEnv.WORKSPACE_BOX_SIZE*np.ones(state_sz),
                DeformEnv.WORKSPACE_BOX_SIZE*np.ones(state_sz))
        else:  # RGB
            self.observation_space = gym.spaces.Box(
                np.zeros((args.cam_resolution, args.cam_resolution, 3)),
                np.ones((args.cam_resolution, args.cam_resolution, 3)))
        self.action_space = gym.spaces.Box(  # has to be [-1,1] (for tanh)
            -1.0*np.ones(DeformEnv.NUM_ANCHORS*3),
            np.ones(DeformEnv.NUM_ANCHORS*3))
        # Loading done, turn on visualizer if needed
        if self.args.viz:
            self.sim.configureDebugVisualizer(pybullet.COV_ENABLE_RENDERING, 1)

    @staticmethod
    def clip_pts(pts, bound, debug_msg=None):
        done = False
        if (np.abs(pts)>bound).any():
            if debug_msg is not None: print(debug_msg)
            pts = np.clip(pts, -1.0*bound, bound)
            done = True  # terminate episode if outside workspace boundaries
        return pts, done

    def load_objects(self, sim, version, args):
        assert(args.task in TASK_TYPES)
        assert(version == 0), 'Only v0 available for now'
        scene_name = args.task.lower()
        if scene_name.startswith('hang'):
            scene_name = 'hang'  # same scene for 'HangBag', 'HangCloth'
        data_path = os.path.join(os.path.split(__file__)[0], '..', 'data')
        sim.setAdditionalSearchPath(data_path)
        rigid_ids = []
        #
        # Load rigid objects.
        #
        for name, kwargs in SCENE_INFO[scene_name]['entities'].items():
            pth = os.path.join(args.data_path, name)
            id = load_rigid_object(
                sim, pth, kwargs['globalScaling'],
                kwargs['basePosition'], kwargs['baseOrientation'])
            if name == 'torso.urdf':
                torso_id = id
            rigid_ids.append(id)
        if args.task.startswith('Hang'):
            if args.task == 'HangBag':
                args.deform_obj = 'bags/ts_purse_bag_resampled.obj'
            else:
                args.deform_obj = 'cloth/ts_apron_twoloops.obj'
            for arg_nm, arg_val in DEFORM_INFO[args.deform_obj].items():
                setattr(args, arg_nm, arg_val)
        #
        # Load deformable object.
        #
        args.texture_path = os.path.join(
            data_path, 'textures', 'blue_bright.png')
        deform_id = load_soft_object(
            sim, args.deform_obj,  args.texture_path, args.deform_scale,
            args.deform_init_pos, args.deform_init_ori,
            args.deform_bending_stiffness, args.deform_damping_stiffness,
            args.deform_elastic_stiffness, args.deform_friction_coeff,
            args.debug)
        #
        # Mark the goal.
        #
        goal_pos = SCENE_INFO[scene_name]['goal_pos']
        if args.viz:
            viz_tgt_id = create_anchor(
                sim, [0,0,0], mass=0.0, radius=0.01, rgba=(0,1,0,1))
            sim.resetBasePositionAndOrientation(viz_tgt_id, goal_pos, [0,0,0,1])
        return rigid_ids, deform_id, np.array(goal_pos)

    def seed(self, seed):
        np.random.seed(seed)

    def reset(self):
        self.stepnum = 0
        self.episode_reward = 0.0
        self.anchor_ids = []
        self.topo_generators = []
        init_bullet(self.args, self.sim, self.cam_on, self.cam_args)
        self.rigid_ids, self.deform_id, self.goal_pos = self.load_objects(
            self.sim, self.version, self.args)
        for i in range(DeformEnv.NUM_ANCHORS):  # make anchors
            anchor_init_pos = self.args.anchor_init_pos if (i%2)==0 else \
                self.args.other_anchor_init_pos
            anchor_id = create_anchor(self.sim, anchor_init_pos)
            attach_anchor(self.sim, anchor_id, self.deform_id)  # grasp
            self.anchor_ids.append(anchor_id)
        if self.args.viz:  # loading done, so enable debug rendering if needed
            self.sim.configureDebugVisualizer(pybullet.COV_ENABLE_RENDERING, 1)

        obs, _ = self.get_obs()
        return obs

    def step(self, action):
        # action is num_anchors x 3 for 3D velocity for anchors/grippers.
        action = action.reshape(DeformEnv.NUM_ANCHORS, 3)
        for i in range(DeformEnv.NUM_ANCHORS):
            command_anchor_velocity(self.sim, self.anchor_ids[i], action[i])
        self.sim.stepSimulation()
        next_obs, done = self.get_obs()
        reward = self.get_reward(action)
        self.episode_reward += reward
        done = (done or self.stepnum >= self.max_episode_len)
        info = {}
        if self.args.debug or self.args.viz:
            print(f'step {self.stepnum:d} reward {reward:0.4f}')
            if done: print(f'episode reward {self.episode_reward:0.4f}')
        self.stepnum += 1

        return next_obs, reward, done, info

    def get_obs(self):
        ancr_obs = []
        done = False
        for i in range(DeformEnv.NUM_ANCHORS):
            pos, ori = self.sim.getBasePositionAndOrientation(self.anchor_ids[i])
            vel, ang_vel = self.sim.getBaseVelocity(self.anchor_ids[i])
            pos, pos_done = DeformEnv.clip_pts(
                np.array(pos), DeformEnv.WORKSPACE_BOX_SIZE,
                'anchor pos outside bounds' if self.args.debug else None)
            vel, vel_done = DeformEnv.clip_pts(
                np.array(vel), DeformEnv.MAX_VEL,
                'anchor vel outside bounds' if self.args.debug else None)
            ancr_obs.extend(pos.tolist())
            ancr_obs.extend((vel/DeformEnv.MAX_VEL).tolist())
            done = pos_done or vel_done
        if self.args.cam_resolution is None:
            obs = np.array(ancr_obs)
        else:
            w, h, rgba_px, _, _ = self.sim.getCameraImage(
                width=self.args.cam_resolution,
                height=self.args.cam_resolution,
                renderer=pybullet.ER_BULLET_HARDWARE_OPENGL)
            obs = rgba_px[:,:,0:3]
        return obs, done

    def get_reward(self, action):
        _, vertex_positions = get_mesh_data(self.sim, self.deform_id)
        accum = np.zeros(3)
        true_loop_vertices = self.args.deform_true_loop_vertices[0]
        for v in true_loop_vertices:
            accum += np.array(vertex_positions[v])
        loop_centroid = accum/len(true_loop_vertices)
        dist = np.linalg.norm(loop_centroid-self.goal_pos)
        rwd = -1.0*dist
        return rwd
