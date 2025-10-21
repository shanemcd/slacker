"""DMs command - list today's DM conversations"""

import sys
import datetime
from ..auth import read_auth_file
from ..api import call_slack_api
from ..utils import get_username
from ..formatters import get_formatter


def cmd_dms(args):
    """List today's DM conversations

    Args:
        args: Parsed command-line arguments
            - auth_file: Path to authentication file
            - output: Output format ('text' or 'json')
    """
    creds = read_auth_file(args.auth_file)
    formatter = get_formatter(args.output)

    # Get today's start timestamp
    today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_ts = today_start.timestamp()

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

        # Filter to today's messages
        if msg_ts < today_ts:
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

        # Filter to today's messages
        if msg_ts < today_ts:
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
