


import itertools

from oslo_config import cfg
from oslo_context import context
from oslo_log import log
import oslo_messaging
from stevedore import extension

from ceilometer.agent import plugin_base as base
from ceilometer import coordination
from ceilometer.event import endpoint as event_endpoint
from ceilometer.i18n import _, _LI, _LW
from ceilometer import exchange_control
from ceilometer import messaging
from ceilometer import pipeline
from ceilometer import service_base
from ceilometer import utils


LOG = log.getLogger(__name__)


OPTS = [
    cfg.IntOpt('pipeline_processing_queues',
               default=10,
               min=1,
               help='Number of queues to parallelize workload across. This '
                    'value should be larger than the number of active '
                    'notification agents for optimal results.'),
    cfg.BoolOpt('ack_on_event_error',
                default=True,
                deprecated_group='collector',
                help='Acknowledge message when event persistence fails.'),
    cfg.BoolOpt('store_events',
                deprecated_group='collector',
                default=False,
                help='Save event details.'),
    cfg.BoolOpt('disable_non_metric_meters',
                default=True,
                help='WARNING: Ceilometer historically offered the ability to '
                     'store events as meters. This usage is NOT advised as it '
                     'can flood the metering database and cause performance '
                     'degradation.'),
    #### ==> workload_partitioning == True  ±£¨coordination/group…˙–ß
    cfg.BoolOpt('workload_partitioning',
                default=False,
                help='Enable workload partitioning, allowing multiple '
                     'notification agents to be run simultaneously.'),
    cfg.MultiStrOpt('messaging_urls',
                    default=[],
                    secret=True,
                    help="Messaging URLs to listen for notifications. "
                         "Example: transport://user:pass@host1:port"
                         "[,hostN:portN]/virtual_host "
                         "(DEFAULT/transport_url is used if empty)"),
]

cfg.CONF.register_opts(exchange_control.EXCHANGE_OPTS)
cfg.CONF.register_opts(OPTS, group="notification")
cfg.CONF.import_opt('telemetry_driver', 'ceilometer.publisher.messaging',
                    group='publisher_notifier')


class NotificationService(service_base.BaseService):
    """ Notification service.
    
    when running multiple agents, additional queuing sequence is required for
    inter process communication. Each agent has two listeners: one to listen
    to the main Openstack queue and another listener(and notifier) for IPC to
    divide pipeline sink endpoints. Cooridination should be enabled to have
    proper active/active HA.
    """
    
    NOTIFICATION_NAMESPACE = 'ceilometer.notification'
    NOTIFICATION_IPC = 'ceilometer-pipe'
    
    def start(self):
        super(NotificationService, self).start()

        self.pipeline_manager = pipeline.setup_pipeline()

        if cfg.CONF.notification.store_events:
            self.event_pipeline_manager = pipeline.setup_event_pipeline()

        self.transport = messaging.get_transport()

        if cfg.CONF.notification.workload_partitioning:
            self.ctxt = context.get_admin_context()
            self.group_id = self.NOTIFICATION_NAMESPACE
            self.partition_coordinator = coordination.PartitionCoordinator()
            self.partition_coordinator.start()
            self.partition_coordinator.join_group(self.group_id)
        else:
            # FIXME(sileht): endpoint uses the notification_topics option
            # and it should not because this is an oslo_messaging option
            # not a ceilometer. Until we have something to get the
            # notification_topics in another way, we must create a transport
            # to ensure the option has been registered by oslo_messaging.
            messaging.get_notifier(self.transport, '')
            self.group_id = None

        self.pipe_manager = self._get_pipe_manager(self.transport,
                                                   self.pipeline_manager)
        self.event_pipe_manager = self._get_event_pipeline_manager(
            self.transport)

        self.listeners, self.pipeline_listeners = [], []
        self._configure_main_queue_listeners(self.pipe_manager,
                                             self.event_pipe_manager)

        if cfg.CONF.notification.workload_partitioning:
            self._configure_pipeline_listeners()
            self.partition_coordinator.watch_group(self.group_id,
                                                   self._refresh_agent)

            self.tg.add_timer(cfg.CONF.coordination.heartbeat,
                              self.partition_coordinator.heartbeat)
            self.tg.add_timer(cfg.CONF.coordination.check_watchers,
                              self.partition_coordinator.run_watchers)

        if not cfg.CONF.notification.disable_non_metric_meters:
            LOG.warning(_LW('Non-metric meters may be collected. It is highly '
                            'advisable to disable these meters using '
                            'ceilometer.conf or the pipeline.yaml'))
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

        self.init_pipeline_refresh()

