import argparse
import math
import os
import subprocess

import numpy as np
import scipy.stats
import simpy
from matplotlib import pyplot as plt
from prettytable import PrettyTable

N_DAYS = 100
N_COUNTERS = 2
IDLE_TIMES = [0]
MAX_QUEUE_SIZES = [0]
AVG_QUEUE_SIZES = [0]


INTERARRIVAL_DISTRIBUTION = [
    5.7,
    3.3,
    1.8,
    2.5,
    4.8,
    6.2,
    10.7
]

def init_global():
    global QUEUE, INTERARRIVAL_TIMES, WAIT_TIMES, SERVICE_TIMES, FINISHING_TIMES, TIME_SPENT, TOTAL_IDLE_TIME, LAST_DEPARTURE
    QUEUE = {}
    INTERARRIVAL_TIMES = [np.empty((0, 1)) for _ in range(len(INTERARRIVAL_DISTRIBUTION))]
    WAIT_TIMES = np.empty((0, 1))
    SERVICE_TIMES = np.empty((0, 1))
    FINISHING_TIMES = np.empty((0, 1))
    TIME_SPENT = np.empty((0, 1))
    IDLE_TIMES.append(0)
    LAST_DEPARTURE = 0

def parse_arguments():
    argparser = argparse.ArgumentParser(description='Library simulation attributes')
    argparser.add_argument(
        '-d', '--days',
        dest='n_days',
        default=100,
        help='total number of days to simulate',
        type=int
    )
    argparser.add_argument(
        '-cnt', '--counters',
        dest='n_counters',
        default=2,
        help='total number of counters in library',
        type=int
    )
    return argparser.parse_args()

def generate_interarrival_time(slot):
    return int(math.ceil(np.random.exponential(scale=INTERARRIVAL_DISTRIBUTION[slot])))

def generate_service_time():
    return np.random.choice(range(1, 6))

def get_time_in_clock_format(time):
    hours, minutes = 8 + time // 60, time % 60
    if hours < 12:
        return '{0:02d}:{1:02d} AM'.format(hours, minutes,)
    elif hours == 12:
        return '{0:02d}:{1:02d} PM'.format(hours, minutes,)
    else:
        return '{0:02d}:{1:02d} PM'.format(hours % 12, minutes,)

class Library(object):
    def __init__(self, env):
        self.env = env
        self.counters = simpy.Resource(env, capacity=N_COUNTERS)
        self.is_idle = True
    
    def serve(self, service_duration):
        yield self.env.timeout(service_duration)

def student(name, env, arrival_time, day, library):
    global QUEUE, WAIT_TIMES, SERVICE_TIMES, FINISHING_TIMES, TIME_SPENT, LAST_DEPARTURE, IS_IDLE
    QUEUE[arrival_time] = QUEUE.get(arrival_time, 0) + 1
    with library.counters.request() as request:
        yield request
        with open('logs/eventlog_day_{}.log'.format(day), 'a+') as file:
            file.write('{} arrived at {} and started service at {} in counter {}\n'.format(name,
                                                                                get_time_in_clock_format(arrival_time),
                                                                                get_time_in_clock_format(env.now),
                                                                                library.counters.count))
        WAIT_TIMES = np.append(WAIT_TIMES, [[env.now - arrival_time]], axis=0)

        service_duration = generate_service_time()
        SERVICE_TIMES = np.append(SERVICE_TIMES, [[service_duration]], axis=0)

        FINISHING_TIMES = np.append(FINISHING_TIMES, [[env.now + service_duration]], axis=0)
        TIME_SPENT = np.append(TIME_SPENT, [[env.now + service_duration - arrival_time]], axis=0)
        yield env.process(library.serve(service_duration))
        with open('logs/eventlog_day_{}.log'.format(day), 'a+') as file:
            file.write('{} departed at {}\n'.format(name, get_time_in_clock_format(env.now)))
        LAST_DEPARTURE = env.now
        library.is_idle = True
        QUEUE[env.now] = QUEUE.get(env.now, 0) - 1

def simulator(env, day):
    global INTERARRIVAL_TIMES, TOTAL_IDLE_TIME
    arrival_time, index = 0, 1
    library = Library(env)
    while True:
        env.process(student('Student {}'.format(index), env, arrival_time, day, library))
        current_slot = env.now // 120
        interarrival_time = generate_interarrival_time(slot=current_slot)
        INTERARRIVAL_TIMES[current_slot] = np.append(INTERARRIVAL_TIMES[current_slot], [[interarrival_time]], axis=0)
        if library.is_idle and LAST_DEPARTURE < env.now:
            library.is_idle = False
            idle_time = env.now - LAST_DEPARTURE
            IDLE_TIMES[-1] += idle_time
            with open('logs/eventlog_day_{}.log'.format(day), 'a+') as file:
                file.write('\nCounters were idle for {} min, total idle time = {} min\n\n'.format(idle_time, IDLE_TIMES[-1]))
        arrival_time += interarrival_time
        yield env.timeout(interarrival_time)
        index += 1

def show_results(table):
    print('Daily data:', table, sep='\n', end='\n\n')
    
    print('ACROSS {} DAYS OF SIMULATED DATA:'.format(N_DAYS))
    print('Maximum queue size = {}'.format(max(MAX_QUEUE_SIZES)))
    print('Average queue size = {0:.3f}'.format(np.mean(AVG_QUEUE_SIZES)))
    print('Total idle time = {} min'.format(sum(IDLE_TIMES)))

def plot_graphs(day):
    plt.style.use('fivethirtyeight')

    fig = plt.figure(figsize=(20, 20))
    grid = plt.GridSpec(4, 4)
    prob_ax = fig.add_subplot(grid[0, 0:2])
    int_ax = fig.add_subplot(grid[1, 0:2], sharex=prob_ax)
    fin_ax = fig.add_subplot(grid[0, 2:])
    n_cust_ax = fig.add_subplot(grid[1, 2:])
    time_ax = fig.add_subplot(grid[2:, :])

    x = np.linspace(0, 30, 30, endpoint=True)
    for slot in INTERARRIVAL_DISTRIBUTION:
        prob_ax.plot(x, scipy.stats.norm.pdf(x, slot, slot*slot))
    prob_ax.set_xlim([0, 30])
    prob_ax.set_xlabel('Inter-arrival Time (in min)')
    prob_ax.set_ylabel('Probability')

    n_students = len(SERVICE_TIMES)
    x = np.linspace(1, n_students, n_students, endpoint=True)

    fin_ax.scatter(FINISHING_TIMES, x)
    fin_ax.set_xlabel('Departure Time (in min)')
    fin_ax.set_ylabel('Student')

    for slot in INTERARRIVAL_TIMES:    
        int_ax.hist(slot, bins=30)
    int_ax.set_xlim([0, 30])
    int_ax.set_xlabel('Inter-arrival Time (in min)')
    int_ax.set_ylabel('Occurrences')

    clock_time, queue_event = zip(*sorted(QUEUE.items()))
    queue_size = np.cumsum(queue_event)
    n_cust_ax.plot(clock_time, queue_size)
    n_cust_ax.set_xlabel('Clock Time (in min)')
    n_cust_ax.set_ylabel('Number of students in queue')

    time_ax.plot(x, WAIT_TIMES, label='Waiting Duration')
    time_ax.plot(x, SERVICE_TIMES, label='Service Duration')
    time_ax.plot(x, TIME_SPENT, label='Time Spent')
    time_ax.set_xlabel('Student')
    time_ax.set_ylabel('Time (in min)')
    time_ax.legend()

    fig.savefig('img/data_viz_day_{}.png'.format(day), dpi=50)
    plt.close()

def main():
    global N_DAYS, N_COUNTERS, MAX_QUEUE_SIZES, AVG_QUEUE_SIZES
    args = parse_arguments()
    N_DAYS = args.n_days
    N_COUNTERS = args.n_counters

    np.random.seed(0)
    
    if not os.path.isdir('logs'):
        subprocess.call(['mkdir', 'logs'])
    
    if not os.path.isdir('img'):
        subprocess.call(['mkdir', 'img'])

    table =  PrettyTable(['Day', 'Max. Queue Size', 'Avg. Queue Size', 'Total Idle Time (in min)'])
    for day in range(1, N_DAYS + 1):
        init_global()
        open('logs/eventlog_day_{}.log'.format(day), 'w').close()
        env = simpy.Environment()
        env.process(simulator(env, day))
        env.run(until=60*14)
        
        clock_time, queue_event = zip(*sorted(QUEUE.items()))
        queue_sizes = np.cumsum(queue_event)
        intervals = np.insert(np.diff(np.array(clock_time)), 0, 0)
        max_queue_size = queue_sizes.max()
        avg_queue_size = np.mean(intervals * np.array(queue_sizes))
        
        table.add_row([day, max_queue_size, round(avg_queue_size, 3), IDLE_TIMES[day]])
        
        MAX_QUEUE_SIZES.append(max_queue_size)
        AVG_QUEUE_SIZES.append(avg_queue_size)

        plot_graphs(day)

    show_results(table)

if __name__ == '__main__':
    main()
