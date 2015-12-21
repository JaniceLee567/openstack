
import os

import eventlet
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import importutils

from nova import exception
from nova.i18n import _LE, _LW
from nova.servicegroup.driver import base

evzookeeper = importutils.try_import('evzookeeper')
membership = importutils.try_import('evzookeeper.membership')
zookeeper = importutils.try_import('zookeeper')


zk_driver_opts = [
    cfg.StrOpt('address',
               help='The Zookeeper addresses for servicegroup service in the '
                    'format of host1:port, host2:port, host3:port'),
    cfg.IntOpt('recv_timeout',
               default=4000,
               help='The recv_timeout parameter for the zk session'),
    cfg.StrOpt('sg_prefix',
               default="/servicegroups",
               help='The prefix used in Zookeeper to store ephemeral nodes'),
    cfg.IntOpt('sg_retry_interval',
               default=5,
               help='Number of seconds to wait until retrying to join the '
                    'session'),
    ]

CONF = cfg.CONF
CONF.register_opts(zk_driver_opts, group="zookeeper")


LOG = logging.getLogger(__name__)


class ZookeeperDriver(base.Driver):
    """Zookeeper driver for the servie group API. """
    
    def __init__(self, *args, **kwargs):
        """create the zk session object."""
        if not all([evzookeeper, membership, zookeeper]):
            raise ImportError('zookeeper module not found')
        self._memberships = {}
        self._monitors = {}
        super(ZookeeperDriver, self).__init__()
        self._cached_session = None
        
    
    @property
    def _session(self):
        """create zookeeper session in lazy manner.
        
        Session is created in lazy manner to mitigate lock problem
        in zookeeper.
        
        Lock happens when many processes try to use the same zk handle.
        lazy creation allows to deffer initialization of session until
        is really required by worker (child process)
        
        :returns: ZKSession -- new or created earlier
        """
        
        if self._cached_session is None:
            self._cached_session = self._init_session()
        return self._cached_session
    
    def _init_session(self):
        """Initializes new session.
        
        Optionally creates required servicegroup prefix.
        
        :returns ZKSession - newly created session
        """
        with open(os.devnull, "w") as null:
            session = evzookeeper.ZKSession(
                CONF.zookeeper.address,
                recv_timeout=CONF.zookeeper.recv_timeout,
                zklog_fd=null)
        
        try:
            session.create(CONF.zookeeper.sg_prefix, "",
                                acl=[evzookeeper.ZOO_OPEN_ACL_UNSAFE])
        except zookeeper.NodeExistsException:
            pass
        
        LOG.warning()
        return session
            
        
    def join(self, member, group, service=None):
        """Add a new member to a service group.
        
        :param member: the joined member ID/name
        :param group: the group ID/name, of the joined member
        :param service: a 'nova.service.Servie' object
        """
        
        process_id = str(os.getpid())
        LOG.debug('ZookeeperDriver: join new member %(id)s(%(pid)s) to the '
                  '%(gr)s group, service=%(sr)s',
                  {'id': member, 'pid': process_id,
                   'gr': group, 'sr': service})
        member = self._memberships.get((group, member), None)
        if member is None:
            # the firest time to join. Generate a new object
            path = "%s/%s/%s" % (CONF.zookeeper.sg_prefix, group, member)
            try:
                zk_member = membership.Membership(self._session, path,
                                                  process_id)
            except RuntimeError:
                LOG.exception(_LE("Unalbe to join."))
                eventlet.sleep(CONF.zookeeper.sg_retry_interval)
                zk_member = membership.Membership(self._session, path, member)
            self._memberships[(group, member)] = zk_member
    
    
    def is_up(self, service_ref):
        group_id = service_ref['topic']
        member_id = service_ref['host']
        all_members = self._get_all(group_id)
        return member_id in all_members
    
    def _get_all(self, group_id):
        """Return all members in a list, or a ServiceGroupUnavailable
        exception.
        """
        
        monitor = self._monitors.get(group_id, None)
        if monitor is None:
            path = "%s/%s" % (CONF.zookeeper.sg_prefix, group_id)
            
            with open(os.devnull, "w") as null:
                local_session = evzookeeper.ZKSession(
                    CONF.zookeeper.address,
                    recv_timeout=CONF.zookeeper.recv_timeout,
                    zklog_fd=null)
                
            monitor = membership.MembershipMonitor(local_session, path)
            self._monitors[group_id] = monitor
            # Note(maoy): When initialized for the first time, it takes a
            # while to retrieve all members from zookeeper. To prevent
            # None to be returned, we sleep 5 sec max to wait for data to
            # be ready.
            timeout = 5
            interval = 0.1
            tries = int(timeout / interval)
            for _retry in range(tries):
                eventlet.sleep(interval)
                all_members = monitor.get_all()
                if all_members is not None:
                    LOG.debug()
                    break
            else:
                LOG.warning()
        else:
            all_members = monitor.get_all()
                
        if all_members is None:
            raise exception.ServiceGroupUnavailable(driver="ZooKeeperDriver")
            
        def have_processes(member):
            """ Predicate that given member has processes (subnode exists). """
                
            value, stat = monitor.get_member_details(member)
                
            if value == 'ZKMembers':
                num_children = stat['numChildren']
                return num_children > 0
            else:
                return False
        all_members = filter(have_processes, all_members)
 
        return all_members
                