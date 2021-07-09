import json
import time
from datetime import datetime
from threading import Thread
import yaml
from collections import deque

import redis

from node import Node
from helpers.belady_freq import BeladyFreq

config = yaml.safe_load(open("./config.yml"))

class Simulator():
  def __init__(self):
    self.wf_key = 1
    self.keys_in = []
    self.keys_out = []
    self.r = redis.StrictRedis(host=config['redis']['address'], port=config['redis']['port'], db=0)
    self.BeladyFreq = BeladyFreq()
    #self.nodes = [Node(0, self.BeladyFreq), Node(1, self.BeladyFreq), Node(2, self.BeladyFreq)]
    self.p = self.r.pubsub()
    self.flag = True
    self.prepare_nodes()
    self.queue = deque([])
    self.thread_sleep_interval = 0.001

  def prepare_nodes(self):
    nodes = []
    for i in range(config['simulator']['nodes']):
      nodes.append(Node(i, self.BeladyFreq))

    self.nodes = nodes

  def bytes_to_string(self, byte_obj):
    return byte_obj.decode("utf-8")

  def get_most_accurate_node(self):
    best_node = None
    for node in self.nodes:
      if not best_node:
        best_node = node
      else:
        if node.get_avalaible_cpu() > best_node.get_avalaible_cpu():
          best_node = node

    return best_node

  def scheduler_routine(self, job_id, data, node):
    node.execute(job_id, data)

    self.r.publish(job_id, 'Processed')

    if job_id.split(":")[2] == config['simulator']['last_id']:
      self.print_output()

  def schedule(self):
    while True:
      if self.queue:
        job = self.queue.popleft()
        job_id = job['key']
        data = job['data']

        node = self.get_most_accurate_node()
        print('[%s] Job %s scheduled on node %s' % (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), job_id, node.id))
        t = Thread(target = self.scheduler_routine, daemon=True, args=(job_id, data, node))
        t.start()
      else:
        time.sleep(self.thread_sleep_interval)

  def print_output(self):
    print('--- HIT ---')
    hit_count = [0, 0, 0, 0, 0]
    for node in self.nodes:
      hit_count = [x+y for x, y in zip(hit_count, node.get_hit())]
      #print(node.get_hit())
    print("Total hit_count " + str(hit_count))

    print('--- MISS ---')
    miss_count = [0, 0, 0, 0, 0]
    for node in self.nodes:
      miss_count = [x+y for x, y in zip(miss_count, node.get_miss())]
      #print(node.get_miss())
    print("Total miss_count " + str(miss_count))

    print('--- SWAP ---')
    swap_count = [0, 0, 0, 0, 0]
    for node in self.nodes:
      swap_count = [x+y for x, y in zip(swap_count, node.get_swap())]
      #print(node.get_swap())
    print("Total swap_count " + str(swap_count))

  def thread_routine(self, msg):
    data = json.loads(self.bytes_to_string(msg.get('data')))
    key = data.get('key')
    # if key.split(":")[2] == "619":
    #   print(json.dumps(data, indent=4))
    
    self.queue.append({
      'key': key,
      'data': data
    })
    #self.schedule(key, data)
    #self.r.publish(key, 'Processed')

  def routine(self, msg):
    if msg.get('type') != 'subscribe':
      #TODO Schedule and mock execution
      thread = Thread(target = self.thread_routine, args=(msg, ))
      thread.start()

  def subscribe(self):
    try:
      self.p.subscribe(**{config['redis']['channel']:self.routine})
      t = self.p.run_in_thread(sleep_time = self.thread_sleep_interval)
      scheduler = Thread(target = self.schedule, daemon=True)
      scheduler.start()
      while True:
        pass
    except KeyboardInterrupt:
      print('Keyboard Interrupt')
      t.stop()

if __name__ == "__main__":
  simulator = Simulator()
  simulator.subscribe()
