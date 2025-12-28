# to run: nohup python3 traffic_train.py > training_log.txt 2>&1 &


from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize
from stable_baselines3.common.callbacks import CheckpointCallback
from traffic_env import TrafficEnv
import torch
import torch.nn as nn
import time

# Make sure to use GPU if available
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

def make_env(id=0):
    def _init():
        # 1 - normal
        # 2 - rush hour
        # 3 - big event
        env = TrafficEnv(1, 'normal', seed=id)
        return Monitor(env)
    return _init

if __name__ == "__main__":
    # Use all 8 CPU cores
    num_envs = 8

    checkpoint_callback = CheckpointCallback(
        save_freq=1_000_000,  # every 100k steps
        save_path="./checkpoints/",
        name_prefix="traffic_ppo"
    )

    # Vectorized environments for parallel training
    env = SubprocVecEnv([make_env(i) for i in range(num_envs)])
    env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_obs=10.)

    policy_kwargs = dict(
        net_arch=[256, 256, 128],
        activation_fn=nn.ReLU
    )

    initial_lr = 5e-4

    lr_schedule = lambda progress_remaining: max(initial_lr * progress_remaining, 1e-5)


    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=lr_schedule,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        vf_coef=0.5,
        max_grad_norm=0.5,
        policy_kwargs=policy_kwargs,
        verbose=1,
        tensorboard_log="./traffic_logs/",
        device=device           # ensures GPU usage
    )

    start = time.time()
    model.learn(total_timesteps=10_000_000, callback=checkpoint_callback)
    end = time.time()

    print(f"Training took {end - start:.2f} seconds")
    print("or")
    print(f"{(end - start)/60:.2f} minutes")
    print("or")
    print(f"{(end - start)/3600:.2f} hours")

    # Save normalized environment and trained model
    env.save("traffic_env_norm_small_test.pkl")
    model.save("traffic_ppo_small_test.zip")

    env.close()

    print("Training complete! You can run 'tensorboard --logdir traffic_logs' to see reward curves.")
