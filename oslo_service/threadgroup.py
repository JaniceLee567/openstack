
import logging
import threading

import eventlet
from eventlet import greenpool

from oslo_service.i18n import _LE
from oslo_service import loopingcall
<<<<<<< HEAD

LOG = logging.getLogger(__name__)
=======
from sre_constants import GROUPREF_IGNORE

LOG = logging.getLogger(__name__)


def _on_thread_done(_greenthread, group, thread):
    """Callback function to be passed to GreenThread.link() when we spaw().
    
    Calls the :class: `ThreadGroup` to notify it to remove this thread from
    the associated group.
    """
    
    group.thread_done(thread)
    
class Thread(object):
    """Wrapper around a greenthread.
    
    Holds a reference to the :class:`ThreadGroup`.
    The Thread will notify the :class:`ThreadGroup`
    when it has done so it can be removed from the
    threads list.
    """
    def __init__(self, thread, group):
        self.thread = thread
        self.thread.link(_on_thread_done, group, self)
        self._ident = id(thread)
        
    @property
    def ident(self):
        return self._ident
    
    def stop(self):
        self.thread.kill()
        
    def wait(self):
        return self.thread.wait()
    
    def link(self, func, *args, **kwargs):
        self.thread.link(func, *args, **kwargs)
        
        
class ThreadGroup(object):
    """The point of the ThreadGroup class is to:
    
    * keep track of timers and greenthreads (making it easiler to stop them
      when need be).
    * provide an easy API to add timers.
    """
    
    def __init__(self, thread_pool_size=10):
        self.pool = greenpool.GreenPool(thread_pool_size)
        self.threads = []
        self.timers = []
        
    def add_dynamic_timer(self, callback, initial_delay=None,
                          periodic_interval_max=None, *args, **kwargs):
        timer = loopingcall.DynamicLoopingCall(callback, *args, **kwargs)
        timer.start(initial_delay=initial_delay,
                    periodic_interval_max=periodic_interval_max)
        self.timers.append(timer)
        
    def add_timer(self, interval, callback, initial_delay=None,
                  *args, **kwargs):
        pulse = loopingcall.FixedIntervalLoopingCall(callback, *args, **kwargs)
        pulse.start(interval=interval,
                    initial_delay=initial_delay)
        self.timers.append(pulse)
    
>>>>>>> origin/olso_service
