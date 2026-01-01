import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pygame
import traffic_sim

class TrafficEnv(gym.Env):
    metadata = {"render_modes": ["human"]}

    def __init__(self, s, r, seed=None):
        super(TrafficEnv, self).__init__()

        self.sim = traffic_sim.TrafficSim(s, r, seed=seed)

        """
        3 possible light combinations:
        0 = horizantal green verticle red
        1 = horizontal red verticle green
        2 = both yellow
        """

        self.durations = [1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
        self.action_space = spaces.Discrete(len(self.durations))

        # Observation: [current light state, time remaining, number of cars in each lane (4)]
        self.observation_space = spaces.Box(
            low=np.array([0, 0, 0, 0, 0, 0], dtype=np.float32),
            high=np.array([3, int(max(self.durations)), 300, 300, 300, 300], dtype=np.float32),
            dtype=np.float32
        )

        self.render = False

        self.dt = 1/20

        self.current_phase = 0
        
        self.time_remaining = 0.0


    # Helper functions
    def _get_observation(self):
        num_cars = [min(len(lane), 300) for lane in self.sim.lanes]

        return np.array([self.current_phase, self.time_remaining] + num_cars, dtype=np.float32)

    def _change_lights(self):
        # Map phase number (0-3) to horizontal/vertical colors
        cycle = {
            0: ('g', 'r'),
            1: ('y', 'y'),
            2: ('r', 'g'),
            3: ('y', 'y')
        }

        self.current_phase = (self.current_phase + 1) % 4

        self.sim.horiz_light, self.sim.vert_light = cycle[self.current_phase]

    # Main Gym methods
    def step(self, action):
        if self.time_remaining <= 0:
            self.time_remaining = self.durations[action]

            self._change_lights()

        reward = 0.0

        #while self.time_remaining > 0 and self.sim.num_crashes == 0 and self.sim.total_time < self.sim.trial_time:
        self.sim.time_remaining = self.time_remaining
        r, info = self.sim.step_sim(self.dt, self.render)
        reward += r
        self.time_remaining = max(self.time_remaining - self.dt, 0.0)

        obs = self._get_observation()
        terminated = False #self.sim.num_crashes > 0************************************************
        truncated = self.sim.total_time >= self.sim.trial_time

        if terminated:
            reward = -10000 # heavy crash penalty
        
        return obs, reward, terminated, truncated, info

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.sim.reset_vals()
        self.sim.total_time = 0
        self.time_remaining = 0.0
        self.current_phase = 0
        return self._get_observation(), {}