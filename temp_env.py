import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pygame
import traffic_sim

class TrafficEnv(gym.Env):
    metadata = {"render_modes": ["human"]}

    def __init__(self, s, r, seed=None):
        super(TrafficEnv, self).__init__()

        """
        9 possible light combinations:
        0 = red red
        1 = red yellow
        2 = red green
        3 = yellow red
        4 = yellow yellow
        5 = yellow green
        6 = green red
        7 = green yellow
        8 = green green
        """
        self.sim = traffic_sim.TrafficSim(s, r, seed=seed)

        self.action_space = spaces.Discrete(9)

        # Observation: [number of cars in each lane (4), speed of first 3 cars before the stop blocks (4), distance of first 3 cars before the stop blocks (4)]
        self.observation_space = spaces.Box(
            low=np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -300, -300, -300, -300, -300, -300, -300, -300, -300, -300, -300, -300], dtype=np.float32),
            high=np.array([300, 300, 300, 300, 457, 457, 457, 457, 457, 457, 457, 457, 457, 457, 457, 457, 900, 900, 900, 900, 900, 900, 900, 900, 900, 900, 900, 900], dtype=np.float32),
            dtype=np.float32
        )
    # Helper functions
    def _get_observation(self):
        num_cars = [min(len(lane), 300) for lane in self.sim.lanes]
        speeds, distances = [], []
        for lane in self.sim.lanes:
            num_done = 0
            for car in lane:
                if num_done >= 3:
                    break
                if car.distance < car.stop_pos:
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
        return np.array(num_cars + speeds + distances, dtype=np.float32)

    def _apply_action(self, action):
        # Map action number (1–9) to horizontal/vertical colors
        action_to_lights = {
            0: ('r', 'r'),
            1: ('r', 'y'),
            2: ('r', 'g'),
            3: ('y', 'r'),
            4: ('y', 'y'),
            5: ('y', 'g'),
            6: ('g', 'r'),
            7: ('g', 'y'),
            8: ('g', 'g')
        }

        self.sim.horiz_light, self.sim.vert_light = action_to_lights[action]

    # Main Gym methods
    def step(self, action):
        self._apply_action(int(action))
        reward, _ = self.sim.step_sim(1/60, False)

        obs = self._get_observation()
        info = {"total wait time": self.sim.total_wait_time, "crashes": self.sim.num_crashes}

        terminated = False
        truncated = self.sim.total_time >= self.sim.trial_time
        
        return obs, reward, terminated, truncated, info
    
    def step_render(self, action, dt):
        self._apply_action(int(action))
        reward, info = self.sim.step_sim(dt, True)

        obs = self._get_observation()
        
        terminated = False
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