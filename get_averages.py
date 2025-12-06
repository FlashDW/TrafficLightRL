"""
to run:
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
./traffic_env/Scripts/Activate.ps1
python get_averages.py

when done:
deactivate
"""

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from temp_env import TrafficEnv


def make_env():
    # 1 - normal
    # 2 - rush hour
    # 3 - big event
    return TrafficEnv(1, 'normal')

venv = DummyVecEnv([lambda: make_env()])

venv = VecNormalize.load("data/50 million on VM/traffic_env_norm.pkl", venv)
venv.training = False
venv.norm_reward = False

model = PPO.load("data/50 million on VM/traffic_ppo.zip", env=venv)

obs = venv.reset()

inner = venv.envs[0]
inner.render = False
inner.dt = 1/60

running = True

total_crashes = 0
wait_time_per_car = 0
count = 0
max_episodes = 15
num_cars = 0
prev_cars = 0
while count<max_episodes and running:
    action, _ = model.predict(obs, deterministic=True)

    obs, reward, done, info = venv.step(action)

    prev_cars = num_cars
    num_cars = inner.sim.num_cars

    if done:
        total_crashes += info[0]["crashes"]
        wait_time_per_car += info[0]["average_wait_time"]
        num_cars = 0
        prev_cars = 0
        count += 1
        print(f"{round(count / max_episodes * 100)}% Complete")
        obs = venv.reset()

print()

print(f"Average crashes per episode: {total_crashes / max_episodes}")
print(f"Average wait time per car: {wait_time_per_car / max_episodes} seconds")