import threading

class Sync():
  def __init__(self, container):
    self.lock = threading.Lock()
    self.container = container

  def __getitem__(self, key):
    #self.lock.acquire()
    item = self.container[key]
    #self.lock.release()
    return item

  def __setitem__(self, key, value):
    self.lock.acquire()
    self.container.__setitem__(key, value)
    self.lock.release()

  def __delitem__(self, key):
    self.lock.acquire()
    self.container.__delitem__(key)
    self.lock.release()

  def __contains__(self, key):
    return self.container.__contains__(key)

  def items(self):
    return self.container.items()

  def get(self, key, default):
    if key in self.container:
      return self.__getitem__(key)
    else: 
      return default
