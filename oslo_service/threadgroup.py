
import logging
import threading

import eventlet
from eventlet import greenpool

from oslo_service.i18n import _LE
from oslo_service import loopingcall

LOG = logging.getLogger(__name__)