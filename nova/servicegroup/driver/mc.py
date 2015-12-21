

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import timeutils

from nova.i18n import _, _LW, _LI
from nova.openstack.common import memorycache
from nova.servicegroup import api
from nova.servicegroup.driver import base

CONF = cfg.CONF
CONF.import_opt('service_down_time', 'nova.service')

LOG = logging.getLogger(__name__)

class MemcachedDriver(base.Driver):
    
    def __init__(self, *args, **kwargs):
        if not CONF.memcached_servers:
            raise RuntimeError()
        self.mc = memorycache.get_client()
 
    def join(self, member_id, group_id, service=None):
        """join the given service with its group."""
        
        LOG.debug('Memcached_Driver: join new ServiceGroup member'
                  '%(member_id)s to the %(group_id)s group, '
                  'service = %(service)s',
                  {'member_id': member_id,
                   'group_id': group_id,
                   'service': service})
        if service is None:
            raise RuntimeError(_())
        report_interval = service.report_interval
        if report_interval:
            service.tg.add_timer(report_interval, self._report_state,
                                 api.INITIAL_REPORTING_DELAY, service)
        
    def is_up(self, service_ref):
        """Moved from nova.utils
        Check whether a service is up based on last heartbeat.
        """
        key = "%(topic)s:%(host)s" %service_ref
        is_up = self.mc.get(str(key)) is not None
        if not is_up:
            LOG.debug('Seem service %s is down' %key)
            
        return is_up
    
    def _report_state(self, service):
        """Update the state of this service in the datastore. """
        try:
            key = "%(topic)s:%(host)s" %service.service_ref
            
            self.mc.set(str(key),
                        timeutils.utcnow(),
                        time=CONF.service_down_time)
            
            if getattr(service, 'model_disconnected', False):
                service.model_disconnected = False
                LOG.info()
                
        except Exception:
            if not getattr(service, 'model_disconnected', False):
                service.model_disconnected = True
                LOG.warn()