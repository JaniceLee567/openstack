

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import timeutils
from datetime import tzinfo
from oslo_messaging as messaging
import six

from nova.i18n import _, _LI, _LW, _LE
from nova.servicegroup import api 
from nova.servicegroup.driver import base

CONF = cfg.CONF 
CONF.import_opt('service_down_time', 'nova.service')

LOG = logging.getLogger(__name__)

class DbDriver(base.Driver):
    
    def __init__(self, *args, **kwargs):
        self.service_down_time = CONF.service_down_time
        
    def join(self, member, group, service=None):
        """ Add a new member to a service group.
        
        :param member: the joined member ID/name 
        :param group: the group ID/name, of the joined member 
        :param service: a 'nova.service.Service' object
        """
        
        LOG.debug('DB_Driver: join new ServiceGroup member %(member)s to '
                  'the %(group)s group, service = %(service)s',
                  {'member': member, 'group': group,
                   'service': service})
        if service is None:
            raise RuntimeError(_('service is a mandatory argument for DB based '
                                 'ServiceGroup driver'))
        report_interval = service.report_interval
        if report_interval:
            service.tg.add_timer(report_interval, self._report_state,
                                 api.INITIAL_REPORTING_DELAY, service)
            
    def is_up(self, service_ref):
        """Moved from nova.utils
        Check whether a service is up based o last hearbeat.
        """
        
        last_heartbeat = (service_ref.get('last_seen_up') or
                          service_ref['updated_at'] or service_ref['created_at'])
        if isinstance(last_heartbeat, six.string_types):
            last_heartbeat = timeutils.parse_strtime(last_heartbeat)
        else:
            last_heartbeat = last_heartbeat.replace(tzinfo=None)
            
        elapsed = timeutils.delta_seconds(last_heartbeat, timeutils.utcnow())
        is_up = abs(elapsed) <= self.service_down_time
        if not is_up:
            LOG.debug('Seems service is down. Last heartbeat was %(lhb)s. '
                      'Elapsed time is %(el)s', 
                      {'lhb': str(last_heartbeat), 'el': str(elapsed)})
        return is_up


    def _report_state(self, service):
        """Update the state of this service in the datastore."""
        
        try:
            #==> 对数据库中字段的操作
            service.service_ref.report_count += 1
            service.service_ref.save()
            
            if getattr(service, 'model_disconnected', False):
                service.model_disconnected = False
                LOG.info()
        except messaging.MessagingTimeout:
            if not getattr(service, 'model_disconnected', False):
                service.model_disconnected = True
                LOG.war()
                
        except Exception:
            LOG.exception()
            service.model_disconnected = True