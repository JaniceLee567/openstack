

import random
import sys

import eventlet
from eventlet import greenthread
from oslo_log import log as logging
from oslo_utils import exctuils
from oslo_utils import reflection
from oslo_utils import timeutils
import six

from oslo_service.i18n import _LE, _LW

LOG = logging.getLogger(__name__)


class LoopingCallDone(Exception):
      