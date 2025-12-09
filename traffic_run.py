"""
to run:
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
C:/users/asher/onedrive/desktop/traffic_env/Scripts/Activate.ps1
python traffic_run.py

when done:
deactivate
"""

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from traffic_env import TrafficEnv
import pygame


def make_env():
    # 1 - normal
    # 2 - rush hour
    # 3 - big event
    return TrafficEnv(1, 'normal')

venv = DummyVecEnv([lambda: make_env()])

venv = VecNormalize.load("data/#6 100 million on VM more obs/traffic_env_norm_more_obs_100M.pkl", venv)
venv.training = False
venv.norm_reward = False

model = PPO.load("data/#6 100 million on VM more obs/traffic_ppo_more_obs_100M.zip", env=venv)

obs = venv.reset()

inner = venv.envs[0]
inner.sim.init_pygame()
inner.render = True

running = True
while running:
    inner.dt = inner.sim.clock.tick(60) / 1000.0

    action, _ = model.predict(obs, deterministic=True)

    obs, reward, done, info = venv.step(action)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            break

    if done:
        obs = venv.reset()

pygame.quit()