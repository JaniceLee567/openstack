
from oslo_config import cfg
from oslo_service import service as os_service

from ceilometer import notification
from ceilometer import service

CONF = cfg.CONF


def main():
    service.prepare_service()
    os_service.launch(CONF, notification.NotificationService(),
                      workers=CONF.notification.workers).wait()