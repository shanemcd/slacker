"""DMs command - list DM conversations since a given time"""

import sys
import datetime
import dateparser
from ..auth import read_auth_file
from ..api import call_slack_api
from ..utils import get_username
from ..formatters import get_formatter


def cmd_dms(args):
    """List DM conversations since a given time

    Args:
        args: Parsed command-line arguments
            - auth_file: Path to authentication file
            - output: Output format ('text' or 'json')
            - since: Natural language time expression (default: 'today')
    """
    creds = read_auth_file(args.auth_file)
    formatter = get_formatter(args.output)

    # Parse the --since parameter
    since_text = getattr(args, 'since', 'today')
    since_dt = dateparser.parse(since_text, settings={'PREFER_DATES_FROM': 'past'})

    if since_dt is None:
        formatter.format_error(f"Could not parse time expression: '{since_text}'. Try: '8 days ago', 'yesterday', '2025-10-20'")
        sys.exit(1)

    # If parsing "today", make it start of day
    if since_text.lower() == 'today':
        since_dt = since_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    since_ts = since_dt.timestamp()

    # Call client.dms API
    data = {
        "count": 250,
        "include_closed": True,
        "include_channel": True,
        "exclude_bots": True,
        "priority_mode": "priority"
    }

    result = call_slack_api('client.dms', creds['token'], creds['cookie'], method='POST', data=data)

    if not result.get('ok'):
        formatter.format_error(f"Failed to list DMs: {result.get('error')}")
        sys.exit(1)

    # Get auth info for filtering own messages
    auth_result = call_slack_api('auth.test', creds['token'], creds['cookie'])
    own_user_id = auth_result.get('user_id', '') if auth_result.get('ok') else ''

    # Process individual DMs
    dms = []
    for im in result.get('ims', []):
        message = im.get('message', {})
        msg_ts = float(message.get('ts', 0))

        # Filter to messages since the specified time
        if msg_ts < since_ts:
            continue

        user_id = message.get('user', '')
        from_you = (user_id == own_user_id)

        # Get username (Slack handle)
        username = get_username(user_id, creds['token'], creds['cookie'])

        # Format timestamp
        msg_time = datetime.datetime.fromtimestamp(msg_ts).strftime('%H:%M')

        dms.append({
            'dm_id': im.get('id', ''),
            'time': msg_time,
            'from_you': from_you,
            'username': username,
            'text': message.get('text', ''),
            'has_files': bool(message.get('files'))
        })

    # Process group DMs
    group_dms = []
    for mpim in result.get('mpims', []):
        message = mpim.get('message', {})
        msg_ts = float(message.get('ts', 0))

        # Filter to messages since the specified time
        if msg_ts < since_ts:
            continue

        user_id = message.get('user', '')
        from_you = (user_id == own_user_id)

        # Get username (Slack handle)
        username = get_username(user_id, creds['token'], creds['cookie'])

        # Format timestamp
        msg_time = datetime.datetime.fromtimestamp(msg_ts).strftime('%H:%M')

        group_dms.append({
            'mpim_id': mpim.get('id', ''),
            'time': msg_time,
            'from_you': from_you,
            'username': username,
            'text': message.get('text', '')
        })

    # Counts
    counts = {
        'dms': len(dms),
        'group_dms': len(group_dms)
    }

    # Format and output
    formatter.format_dms(dms, group_dms, counts)
