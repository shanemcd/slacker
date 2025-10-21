"""Reminders command - list saved reminders and later items"""

import sys
import datetime
from ..auth import read_auth_file
from ..api import call_slack_api
from ..utils import get_channel_name, get_message_content
from ..formatters import get_formatter


def cmd_reminders_list(args):
    """List saved reminders and later items

    Args:
        args: Parsed command-line arguments
            - auth_file: Path to authentication file
            - output: Output format ('text' or 'json')
            - limit: Maximum number of items to list
            - reminders_only: Show only reminders (exclude saved messages)
    """
    creds = read_auth_file(args.auth_file)
    formatter = get_formatter(args.output)

    # Call saved.list API
    data = {
        "filter": "saved",
        "limit": args.limit,
        "include_tombstones": True
    }

    result = call_slack_api('saved.list', creds['token'], creds['cookie'], method='POST', data=data)

    if not result.get('ok'):
        formatter.format_error(f"Failed to list reminders: {result.get('error')}")
        sys.exit(1)

    saved_items = result.get('saved_items', [])

    # Filter to reminders only if requested
    if args.reminders_only:
        saved_items = [item for item in saved_items if item.get('item_type') == 'reminder']

    # Get workspace URL for building links
    auth_result = call_slack_api('auth.test', creds['token'], creds['cookie'])
    workspace_url = auth_result.get('url', 'https://slack.com') if auth_result.get('ok') else 'https://slack.com'

    # Build structured output
    output_items = []

    for item in saved_items:
        item_type = item.get('item_type', 'unknown')
        state = item.get('state', 'unknown')

        if item_type == 'reminder':
            # Extract description text
            desc_blocks = item.get('description', [])
            text = "Unknown"
            if desc_blocks:
                try:
                    text = desc_blocks[0]['elements'][0]['elements'][0]['text']
                except (KeyError, IndexError):
                    pass

            # Format due date
            due_ts = item.get('date_due', 0)
            due_date = datetime.datetime.fromtimestamp(due_ts).strftime('%Y-%m-%d %H:%M')

            output_items.append({
                'type': 'reminder',
                'state': state,
                'text': text,
                'due_date': due_date,
                'due_timestamp': due_ts
            })
        else:
            # Saved message
            channel_id = item.get('item_id', 'unknown')
            ts = item.get('ts', 'unknown')

            # Get channel name
            channel_name = get_channel_name(channel_id, creds['token'], creds['cookie'])

            # Get message content
            message_text = get_message_content(channel_id, ts, creds['token'], creds['cookie'])

            # Format timestamp
            try:
                msg_ts = float(ts)
                msg_date = datetime.datetime.fromtimestamp(msg_ts).strftime('%Y-%m-%d %H:%M')
            except:
                msg_date = ts
                msg_ts = None

            # Build message link
            ts_link = ts.replace('.', '')
            message_link = f"{workspace_url}archives/{channel_id}/p{ts_link}"

            output_items.append({
                'type': 'message',
                'state': state,
                'channel_id': channel_id,
                'channel_name': channel_name,
                'message': message_text,
                'date': msg_date,
                'timestamp': msg_ts,
                'link': message_link
            })

    # Format and output results
    formatter.format_reminders(output_items, result.get('counts', {}))
