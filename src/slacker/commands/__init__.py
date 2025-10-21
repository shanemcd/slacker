"""Command implementations for slacker CLI"""

# Import all commands for easy access
from .whoami import cmd_whoami
from .dms import cmd_dms
from .reminders import cmd_reminders_list
from .api_call import cmd_api
from .reminder import cmd_reminder
from .discover import cmd_discover
from .record import cmd_record
from .login import cmd_login
from .activity import cmd_activity

__all__ = [
    'cmd_whoami',
    'cmd_dms',
    'cmd_reminders_list',
    'cmd_api',
    'cmd_reminder',
    'cmd_discover',
    'cmd_record',
    'cmd_login',
    'cmd_activity',
]
