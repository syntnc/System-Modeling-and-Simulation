from collections import OrderedDict
import argparse

import numpy as np
import simpy
from matplotlib import pyplot as plt

N_CUSTOMERS = 100

QUEUE = {}
INTERARRIVAL_TIMES = np.empty((0, 1))
WAIT_TIMES = np.empty((0, 1))
SERVICE_TIMES = np.empty((0, 1))
FINISHING_TIMES = np.empty((0, 1))
TIME_SPENT = np.empty((0, 1))
TOTAL_IDLE_TIME = 0

SERVICE_DISTRIBUTION = [
    0.10,
    0.07,
    0.08,
    0.5,
    0.06,
    0.07,
    0.07,
    0.05
]

INTERARRIVAL_TABLE = [
    913,
    727,
    15,
    948,
    309,
    922,
    413,
    20
]

SERVICE_TABLE = [
    84,
    10,
    74,
    53,
    17,
    79,
    45,
    98
]

def parse_arguments():
    argparser = argparse.ArgumentParser(description='Total number of customers to simulate')
    argparser.add_argument(
        '-c', '--cust',
        dest='n_customers',
        default=100,
        help='total customers to simulate',
        type=int
    )
    argparser.add_argument(
        '-t', '--table',
        dest='use_table',
        default=False,
        help='total customers to simulate',
        action='store_true' 
    )
    return argparser.parse_args()

def generate_arrival_time():
    while True:
        for _ in range(N_CUSTOMERS):
            yield np.random.choice(list(range(1, 9)))

def generate_arrival_time_from_table():
    while True:
        for _ in range(N_CUSTOMERS):
            yield (np.random.choice(INTERARRIVAL_TABLE) // (1000 // N_CUSTOMERS)) + 1

def generate_service_time():
    while True:
        for _ in range(N_CUSTOMERS):
            yield np.random.choice(
                a=list(range(1, 9)),
                p=SERVICE_DISTRIBUTION
            )

def generate_service_time_from_table():
    while True:
        for _ in range(N_CUSTOMERS):
            yield np.searchsorted(np.cumsum(SERVICE_DISTRIBUTION) * 100, np.random.choice(SERVICE_TABLE), side='right') + 1

class Customer(object):
    def __init__(self, name, env, arrival_time):
        self.name = name
        self.env = env
        self.arrival_time = arrival_time

    def run(self, use_table=False):
        global N_QUEUE, QUEUE, WAIT_TIMES, SERVICE_TIMES, FINISHING_TIMES, TIME_SPENT
        QUEUE[self.arrival_time] = QUEUE.get(self.arrival_time, 0) + 1
        with open('eventlog.log', 'a+') as file:
            file.write('{} arrived at {} min and started service at {} min\n'.format(self.name, self.arrival_time, self.env.now))
        WAIT_TIMES = np.append(WAIT_TIMES, [[self.env.now - self.arrival_time]], axis=0)

        service_duration = next(generate_service_time_from_table()) if use_table else next(generate_service_time())
        SERVICE_TIMES = np.append(SERVICE_TIMES, [[service_duration]], axis=0)

        FINISHING_TIMES = np.append(FINISHING_TIMES, [[self.env.now + service_duration]], axis=0)
        TIME_SPENT = np.append(TIME_SPENT, [[self.env.now + service_duration - self.arrival_time]], axis=0)
        yield self.env.process(self.serve(service_duration))
        with open('eventlog.log', 'a+') as file:
            file.write('{} departed at {} min\n'.format(self.name, self.env.now))
        QUEUE[self.env.now] = QUEUE.get(self.env.now, 0) - 1

    def serve(self, service_duration):
        yield self.env.timeout(service_duration)

def bank(env, use_table=False):
    global INTERARRIVAL_TIMES, TOTAL_IDLE_TIME
    if use_table:
        global N_CUSTOMERS
        N_CUSTOMERS = 8
    arrival_time = 0
    for index in range(N_CUSTOMERS):
        customer = Customer('Customer {}'.format(index), env, arrival_time)
        yield env.process(customer.run(use_table))
        interarrival_time = next(generate_arrival_time_from_table()) if use_table else next(generate_arrival_time())
        INTERARRIVAL_TIMES = np.append(INTERARRIVAL_TIMES, [[interarrival_time]], axis=0)
        arrival_time += interarrival_time
        if arrival_time > env.now:
            idle_time = arrival_time - env.now
            TOTAL_IDLE_TIME += idle_time
            yield env.timeout(idle_time)

def show_results():
    waiters = WAIT_TIMES[np.nonzero(WAIT_TIMES)]
    print('Average waiting time = {0:.3f} min'.format(np.mean(WAIT_TIMES)))
    print('Probability that a customer has to wait in the queue = {0:.3f}%'.format(100 * waiters.shape[0] / WAIT_TIMES.shape[0]))
    print('Fraction of idle time of the server = {0:.3f}%'.format(100 * TOTAL_IDLE_TIME / np.int(FINISHING_TIMES[-1])))
    print('Average service time = {0:.3f} min'.format(np.mean(SERVICE_TIMES)))
    print('Average time between arrivals = {0:.3f} min'.format(np.mean(INTERARRIVAL_TIMES)))
    print('Average waiting time of those who wait = {0:.3f} min'.format(np.mean(waiters)))
    print('Average time a customer spends in the system = {0:.3f} min'.format(np.mean(TIME_SPENT)))

def plot_graphs():
    plt.style.use('fivethirtyeight')
    unique, counts = np.unique(SERVICE_TIMES, return_counts=True)

    fig = plt.figure(figsize=(20, 20))
    grid = plt.GridSpec(4, 4)
    prob_ax = fig.add_subplot(grid[0, 0:2])
    occ_ax = fig.add_subplot(grid[1, 0:2], sharex=prob_ax)
    fin_ax = fig.add_subplot(grid[0, 2:])
    n_cust_ax = fig.add_subplot(grid[1, 2:])
    time_ax = fig.add_subplot(grid[2:, :])

    prob_ax.bar(range(1, 9), SERVICE_DISTRIBUTION)
    prob_ax.set_xlabel('Service Time (in min)')
    prob_ax.set_ylabel('Probability')

    occ_ax.bar(unique, counts)
    occ_ax.set_xlabel('Service Time (in min)')
    occ_ax.set_ylabel('Occurrences')

    x = np.linspace(1, N_CUSTOMERS, N_CUSTOMERS, endpoint=True)

    fin_ax.scatter(FINISHING_TIMES, x)
    fin_ax.set_xlabel('Departure Time (in min)')
    fin_ax.set_ylabel('Customer')

    x_, y_ = zip(*sorted(QUEUE.items()))
    n_cust_ax.plot(x_, np.cumsum(y_))
    n_cust_ax.set_xlabel('Clock Time (in min)')
    n_cust_ax.set_ylabel('Number of customers')

    time_ax.plot(x, WAIT_TIMES, label='Waiting Duration')
    time_ax.plot(x, INTERARRIVAL_TIMES, label='Inter-arrival Duration')
    time_ax.plot(x, SERVICE_TIMES, label='Service Duration')
    time_ax.plot(x, TIME_SPENT, label='Time Spent')
    time_ax.set_xlabel('Customer')
    time_ax.set_ylabel('Time (in min)')
    time_ax.legend()

    fig.savefig('data_viz.png')

def main():
    global N_CUSTOMERS
    args = parse_arguments()
    N_CUSTOMERS = args.n_customers

    env = simpy.Environment()
    np.random.seed(0)
    open('eventlog.log', 'w' ).close()
    env.process(bank(env, use_table=args.use_table))
    env.run(until=8 * N_CUSTOMERS)

    show_results()
    plot_graphs()

if __name__ == '__main__':
    main()
