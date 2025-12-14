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
        self.action_space = spaces.Discrete(3)

        # Observation: [current light state, number of cars in each lane (4), speed of first 3 cars (4), distance of first 3 cars (4)]
        self.observation_space = spaces.Box(
            low=np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -300, -300, -300, -300, -300, -300, -300, -300, -300, -300, -300, -300], dtype=np.float32),
            high=np.array([2, 300, 300, 300, 300, 457, 457, 457, 457, 457, 457, 457, 457, 457, 457, 457, 457, 900, 900, 900, 900, 900, 900, 900, 900, 900, 900, 900, 900], dtype=np.float32),
            dtype=np.float32
        )

        self.render = False

        self.dt = 1/20

        self.time_since_change = 0.0

    # Helper functions
    def _get_observation(self):
        light_state = 0 if self.sim.horiz_light == 'g' else 1 if self.sim.vert_light == 'g' else 2
        num_cars = [min(len(lane), 300) for lane in self.sim.lanes]
        speeds, distances = [], []
        for lane in self.sim.lanes:
            num_done = 0
            for car in lane:
                if num_done >= 3:
                    break
                speeds.append(car.speed)
                distances.append(car.distance)
                num_done += 1
            if num_done < 3:
                while num_done < 3:
                    num_done += 1
                    speeds.append(0.0)
                    distances.append(900.0)
        speeds = [min(s, 457) for s in speeds]
        speeds = [max(s, 0) for s in speeds]
        distances = [min(d, 900) for d in distances]
        distances = [max(d, -300) for d in distances]
        return np.array([light_state] + num_cars + speeds + distances, dtype=np.float32)

    def _apply_action(self, action):
        light_state = 0 if self.sim.horiz_light == 'g' else 1 if self.sim.vert_light == 'g' else 2
        if action != light_state:
            self.time_since_change = 0.0
        else:
            self.time_since_change += self.dt
        # Map action number (0-2) to horizontal/vertical colors
        action_to_lights = {
            0: ('g', 'r'),
            1: ('r', 'g'),
            2: ('y', 'y'),
        }

        self.sim.horiz_light, self.sim.vert_light = action_to_lights[action]

    # Main Gym methods
    def step(self, action):
        self._apply_action(int(action))
        reward, info = self.sim.step_sim(self.dt, self.render)

        obs = self._get_observation()
        terminated = self.sim.num_crashes > 0
        truncated = self.sim.total_time >= self.sim.trial_time
        
        return obs, reward, terminated, truncated, info

    def render(self):
        if not pygame.get_init():
            self.sim.init_pygame()
        self.sim.draw_screen()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.sim.reset_vals()
        self.sim.total_time = 0
        return self._get_observation(), {}