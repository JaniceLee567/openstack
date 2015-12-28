import uuid 

from oslo_config import cfg
from oslo_log import log
import tooz.coordination

from ceilometer.i18n import _LE, _LI
from ceilometer import utils

LOG = log.getLogger()


OPTS = [
    cfg.StrOpt('backend_url',
               default=None,
               help='The backend URL to use for distributed'
                    ' coordination. If left empty, '
                    'per-deployment central agent and '
                    'per-host compute agent won\'t to '
                    'do workload partitioning and will only'
                    'function correctly if a single instance'
                    'of that service is running.'),
    cfg.FloatOpt('heartbeat',
                 default=1.0,
                 help='Number of seconds between heartbeats for distributed '
                      'coordination.'),
    cfg.FloatOpt('check_watchers',
                 default=10.0,
                 help='Number of seconds between checks to see if group '
                      'membership has changed'),
]

cfg.CONF.register_opts(OPTS, group='coordination')

class PartitionCoordinator(object):
    """Workload partitioning coordinator.
    
    This class uses the `tooz` library to manage group membership.
    To ensure that the other agents know this agent is still alive,
    the `heartbeat` method should be called periodically.
    Coordination errors and reconnects are handled under the hood, so the
    service using the partition coordinator need not care whether the
    coordination backend is down. The `extract_my_subset` will simply return an
    empty iterable in this case.
    """
    

