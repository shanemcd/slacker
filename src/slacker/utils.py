"""Utility functions for Slack data retrieval"""

from .api import call_slack_api


def get_username(user_id, token, cookie):
    """Get username (Slack handle) from user ID

    Args:
        user_id: Slack user ID
        token: Slack API token
        cookie: Slack 'd' cookie value

    Returns:
        str: Username or user_id if lookup fails
    """
    try:
        result = call_slack_api('users.info', token, cookie, method='GET', params={'user': user_id})
        if result.get('ok'):
            user = result.get('user', {})
            return user.get('name', user_id)
    except:
        pass
    return user_id


def get_channel_name(channel_id, token, cookie):
    """Get channel name from channel ID

    Args:
        channel_id: Slack channel ID
        token: Slack API token
        cookie: Slack 'd' cookie value

    Returns:
        str: Channel name or user name (for DMs) or channel_id if lookup fails
    """
    try:
        result = call_slack_api('conversations.info', token, cookie, method='GET', params={'channel': channel_id})
        if result.get('ok'):
            channel = result.get('channel', {})
            # For DMs, use the user's name if available
            if channel.get('is_im'):
                user_id = channel.get('user')
                if user_id:
                    user_result = call_slack_api('users.info', token, cookie, method='GET', params={'user': user_id})
                    if user_result.get('ok'):
                        user = user_result.get('user', {})
                        return f"@{user.get('name', channel_id)}"
            return channel.get('name', channel_id)
    except:
        pass
    return channel_id


def get_message_content(channel_id, timestamp, token, cookie):
    """Get message content from channel and timestamp

    Args:
        channel_id: Slack channel ID
        timestamp: Message timestamp
        token: Slack API token
        cookie: Slack 'd' cookie value

    Returns:
        str: Message text or None if lookup fails
    """
    try:
        result = call_slack_api('conversations.history', token, cookie, method='GET',
                               params={'channel': channel_id, 'latest': timestamp,
                                      'inclusive': True, 'limit': 1})
        if result.get('ok') and result.get('messages'):
            message = result['messages'][0]
            # Extract text from message
            text = message.get('text', '')

            # If message has blocks, try to extract rich text
            if not text and message.get('blocks'):
                for block in message['blocks']:
                    if block.get('type') == 'rich_text':
                        for element in block.get('elements', []):
                            if element.get('type') == 'rich_text_section':
                                for elem in element.get('elements', []):
                                    if elem.get('type') == 'text':
                                        text += elem.get('text', '')

            return text
    except:
        pass
    return None
