
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import importutils

from nova.i18n import _,_LW
from audioop import getsample

LOG = logging.getLogger(__name__)

_driver_name_class_mapping = {
    'db': 'nova.servicegroup.drivers.db.DbDriver',
    'zk': 'nova.servicegroup.drivers.zk.ZookeeperDriver',
    'mc': 'nova.servicegroup.drivers.mc.MemcachedDriver'
}
_default_driver='db'
servicegroup_driver_opt = cfg.StrOpt('servicegroup_driver',
                                     default = _default_driver,
                                     help = 'The driver for servicegroup '
                                            'service (valid options are: '
                                            'db, zk, mc)')

CONF = cfg.CONF
CONF.register_opt(servicegroup_driver_opt)

INITIAL_REPORTING_DELAY = 5

class API(object):
    
    def __init__(self, *args, **kwargs):
        '''create an instance of the servicegroup API.
        
        args and kwargs are passed down to the servicegroup driver when it gets
        created.
        '''
        
        #==> 设置service_down_time, 如果不符合，则使用new_service_down_time覆盖原值。
        report_interval = CONF.report_interval
        if CONF.service_down_time <= report_interval:
            new_service_down_time = int(report_interval * 2.5)
            LOG.warning(_LW("Report internal must be less than service down "
                            "time. Current config: <service_down_time: "
                            "%(service_down_time)s, report_interval: "
                            "%(report_interval)s>. Setting service_down_time "
                            "to: %(new_service_down_time)s"),
                        {'service_down_time': CONF.service_down_time,
                         'report_interval': report_interval,
                         'new_service_down_time': new_service_down_time})
            CONF.set_override('service_down_time', new_service_down_time)
        
        #==> 设置 ServiceGroup driver, 然后根据配置文件实例化 ServiceGroup: _driver
        driver_name = CONF.servicegroup_driver
        try:
            driver_class = _driver_name_class_mapping[driver_name]
        except KeyError:
            raise TypeError(_("unknown ServiceGroup driver name: %s")
                            % driver_name)
        self._driver = importutils.import_object(driver_class,
                                                 *args, **kwargs)
        
    
    def join(self, member, group, service=None):
        """Add a new member to a service group.
        
        :param member: the joined member ID/Name
        :param group: the group ID/name， of the joined member
        :param service: a 'nova.service.Service' object
        """
        
        return self._driver.join(member, group, service)
    
    def service_is_up(self, member):
        """Check if the given member is up. """
        
        if member.get('forced_down'):
            return False
        return self._driver.is_up(member)
    
    def get_all(self, group_id):
        """Returns ALL members of the given group."""
        LOG.debug('Return All members of the [%s] '
                  'ServiceGroup', group_id)
        return self._driver.get_all(group_id)
        