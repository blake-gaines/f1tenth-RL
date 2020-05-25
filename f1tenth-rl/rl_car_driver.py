#!/usr/bin/env python3
#
from threading import Thread
import sys
import numpy as np
import os
import random
import replay
import time
import argparse
import datetime

import dqn
from car_env import CarEnv
from state import State

#################################
# parameters
#################################

parser = argparse.ArgumentParser()
# real car or simulator
parser.add_argument("--simulator", action='store_true', help="to set the use of the simulator")
# agent parameters
parser.add_argument("--learning-rate", type=float, default=0.0004, help="learning rate (step size for optimization algo)")
parser.add_argument("--gamma", type=float, default=0.996, help="gamma [0, 1] is the discount factor. It determines the importance of future rewards. A factor of 0 will make the agent consider only immediate reward, a factor approaching 1 will make it strive for a long-term high reward")
parser.add_argument("--epsilon", type=float, default=1, help="]0, 1]for epsilon greedy train")
parser.add_argument("--epsilon-decay", type=float, default=0.99988, help="]0, 1] every step epsilon = epsilon * decay, in order to decrease constantly")
parser.add_argument("--epsilon-min", type=float, default=0.1, help="epsilon with decay doesn't fall below epsilon min")

parser.add_argument("--observation-steps", type=int, default=350, help="train only after this many stesp (=X frames)")
parser.add_argument("--target-model-update-freq", type=int, default=300, help="how often (in steps) to update the target model")
parser.add_argument("--model", help="tensorflow model checkpoint file to initialize from")
parser.add_argument("--frame", type=int, default=2, help="frame per step")
# train parameters
parser.add_argument("--train-epoch-steps", type=int, default=5000, help="how many steps (=X frames) to run during a training epoch")
parser.add_argument("--eval-epoch-steps", type=int, default=500, help="how many steps (=X frames) to run during an eval epoch")
parser.add_argument("--replay-capacity", type=int, default=100000, help="how many states to store for future training")
parser.add_argument("--prioritized-replay", action='store_true', help="Prioritize interesting states when training (e.g. terminal or non zero rewards)")
parser.add_argument("--compress-replay", action='store_true', help="if set replay memory will be compressed with blosc, allowing much larger replay capacity")
parser.add_argument("--normalize-weights", action='store_true', help="if set weights/biases are normalized like torch, with std scaled by fan in to the node")
parser.add_argument("--save-model-freq", type=int, default=2000, help="save the model once per X training sessions")
parser.add_argument("--tensorboard-logging-freq", type=int, default=300, help="save training statistics once every X steps")
args = parser.parse_args()

print('Arguments: ', (args))

#################################
# stop handler
#################################

stop = False

def stop_handler():
  global stop
  while not stop:
    user_input = input()
    if user_input == 'q':
      print("Stopping...")
      stop = True

process = Thread(target=stop_handler)
process.start()

#################################
# setup
#################################

base_output_dir = 'run-out-' + time.strftime("%Y-%m-%d-%H-%M-%S")
os.makedirs(base_output_dir)

State.setup(args)

environment = CarEnv(args)
dqn = dqn.DeepQNetwork(environment.get_num_actions(), environment.get_state_size(), base_output_dir, args)
replay_memory = replay.ReplayMemory(args)

train_epsilon = args.epsilon #don't want to reset epsilon between epoch
start_time = datetime.datetime.now()

#################################
# training cycle definition
#################################

def run_epoch(min_epoch_steps, eval_with_epsilon=None):
    global train_epsilon
    is_training = True if eval_with_epsilon is None else False
    step_start = environment.get_step_number()
    start_game_number = environment.get_game_number()
    epoch_total_score = 0

    while environment.get_step_number() - step_start < min_epoch_steps and not stop:
        state_reward = 0
        state = None
        
        while not environment.is_game_over() and not stop:
            # epsilon selection and update
            if is_training:
                epsilon = train_epsilon
                if train_epsilon > args.epsilon_min:
                    train_epsilon = train_epsilon * args.epsilon_decay
                    if train_epsilon < args.epsilon_min:
                        train_epsilon = args.epsilon_min
            else:
                epsilon = eval_with_epsilon

            # action selection
            if state is None or random.random() < epsilon:
                action = random.randrange(environment.get_num_actions())
            else:
                action = dqn.inference(state.get_data())

            # Make the move
            old_state = state
            reward, state, is_terminal = environment.step(action)
            
            # Record experience in replay memory and train
            if is_training and old_state is not None:
                replay_memory.add_sample(replay.Sample(old_state, action, reward, state, is_terminal))

                if environment.get_step_number() > args.observation_steps and environment.get_episode_step_number() % args.frame == 0:
                    batch = replay_memory.draw_batch(32)
                    dqn.train(batch, environment.get_step_number())

            if is_terminal:
                state = None

        episode_time = datetime.datetime.now() - start_time
        print('%s %d ended with score: %d (%s elapsed)' %
            ('Episode' if is_training else 'Eval', environment.get_game_number(), environment.get_game_score(), str(episode_time)))
        if is_training:
          print("epsilon " + str(train_epsilon))
        epoch_total_score += environment.get_game_score()
        environment.reset_game()
    
    # return the average score
    if environment.get_game_number() - start_game_number == 0:
        return 0
    return epoch_total_score / (environment.get_game_number() - start_game_number)

#################################
# main
#################################

while not stop:
    avg_score = run_epoch(args.train_epoch_steps) # train
    print('Average training score: %d' % (avg_score))
    avg_score = run_epoch(args.eval_epoch_steps, eval_with_epsilon=.0) # eval
    print('Average eval score: %d' % (avg_score))
