"""Utility functions for Slack data retrieval"""

import re
import json
import asyncio
import httpx
from .api import call_slack_api, call_slack_api_async


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


def replace_mentions_in_text(text, token, cookie):
    """Replace user and usergroup mentions with readable names

    Args:
        text: Text containing Slack mentions
        token: Slack API token
        cookie: Slack 'd' cookie value

    Returns:
        str: Text with mentions replaced
    """
    if not text:
        return text

    # Find all user mentions in format <@USER_ID>
    user_mentions = re.findall(r'<@([A-Z0-9]+)>', text)
    for user_id in user_mentions:
        username = get_username(user_id, token, cookie)
        text = text.replace(f'<@{user_id}>', f'@{username}')

    # Replace usergroup mentions with group names
    # Format: <!subteam^USERGROUP_ID|@handle> or <!subteam^USERGROUP_ID>
    usergroup_mentions = re.findall(r'<!subteam\^([A-Z0-9]+)(?:\|@([^>]+))?>', text)
    for usergroup_id, handle in usergroup_mentions:
        # If handle is provided in the mention, use it; otherwise use generic @team
        display_name = f'@{handle}' if handle else '@team'
        text = re.sub(rf'<!subteam\^{usergroup_id}(?:\|@[^>]+)?>', display_name, text)

    return text


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

            # Replace user and usergroup mentions with readable names
            text = replace_mentions_in_text(text, token, cookie)

            return text
    except:
        pass
    return None


async def fetch_usernames_async(user_ids, token, cookie, client):
    """Fetch multiple usernames in parallel

    Args:
        user_ids: Set of user IDs to fetch
        token: Slack API token
        cookie: Slack 'd' cookie value
        client: httpx.AsyncClient instance

    Returns:
        dict: Mapping of user_id -> username
    """
    async def fetch_one(user_id):
        result = await call_slack_api_async('users.info', token, cookie, client,
                                           method='GET', params={'user': user_id})
        if result and result.get('ok'):
            user = result.get('user', {})
            return user_id, user.get('name', user_id)
        return user_id, user_id

    tasks = [fetch_one(user_id) for user_id in user_ids]
    results = await asyncio.gather(*tasks)
    return dict(results)


async def fetch_usergroup_names_async(usergroup_ids, token, cookie, client):
    """Fetch multiple user group names using EdgeAPI

    Args:
        usergroup_ids: Set of user group IDs to fetch
        token: Slack API token
        cookie: Slack 'd' cookie value
        client: httpx.AsyncClient instance

    Returns:
        dict: Mapping of usergroup_id -> usergroup_handle
    """
    if not usergroup_ids:
        return {}

    url = "https://edgeapi.slack.com/cache/E030G10V24F/usergroups/info"
    headers = {
        'Content-Type': 'text/plain;charset=UTF-8',
        'Authorization': f'Bearer {token}',
        'Cookie': f'd={cookie}',
    }

    payload = {
        "token": token,
        "ids": list(usergroup_ids),
        "enterprise_token": token
    }

    try:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        if result.get('ok') and result.get('results'):
            usergroup_map = {}
            for ug in result['results']:
                ug_id = ug.get('id')
                handle = ug.get('handle', ug.get('name', ug_id))
                usergroup_map[ug_id] = handle
            return usergroup_map
    except:
        pass

    return {ug_id: ug_id for ug_id in usergroup_ids}


def _find_ids_in_data(data):
    """Recursively find all user IDs and usergroup IDs in JSON data

    Args:
        data: JSON data (dict, list, or primitive)

    Returns:
        tuple: (set of user_ids, set of usergroup_ids)
    """
    user_ids = set()
    usergroup_ids = set()

    if isinstance(data, dict):
        for key, value in data.items():
            # Check for user ID keys
            if key in ('user', 'user_id', 'author_user_id', 'creator') and isinstance(value, str):
                if re.match(r'^U[A-Z0-9]+$', value):
                    user_ids.add(value)
            # Recurse into nested structures
            sub_users, sub_groups = _find_ids_in_data(value)
            user_ids.update(sub_users)
            usergroup_ids.update(sub_groups)
    elif isinstance(data, list):
        for item in data:
            sub_users, sub_groups = _find_ids_in_data(item)
            user_ids.update(sub_users)
            usergroup_ids.update(sub_groups)
    elif isinstance(data, str):
        # Find user mentions in text like <@U12345>
        user_mentions = re.findall(r'<@(U[A-Z0-9]+)>', data)
        user_ids.update(user_mentions)
        # Find usergroup mentions like <!subteam^S12345>
        usergroup_mentions = re.findall(r'<!subteam\^(S[A-Z0-9]+)>', data)
        usergroup_ids.update(usergroup_mentions)

    return user_ids, usergroup_ids


def _substitute_ids_in_data(data, user_cache, usergroup_cache):
    """Recursively substitute user IDs and usergroup IDs with names

    Args:
        data: JSON data (dict, list, or primitive)
        user_cache: dict mapping user_id -> username
        usergroup_cache: dict mapping usergroup_id -> handle

    Returns:
        Modified data with substitutions
    """
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # Substitute user ID values
            if key in ('user', 'user_id', 'author_user_id', 'creator') and isinstance(value, str):
                if value in user_cache:
                    result[key] = user_cache[value]
                    result[f'{key}_id'] = value
                else:
                    result[key] = value
            else:
                result[key] = _substitute_ids_in_data(value, user_cache, usergroup_cache)
        return result
    elif isinstance(data, list):
        return [_substitute_ids_in_data(item, user_cache, usergroup_cache) for item in data]
    elif isinstance(data, str):
        # Replace user mentions in text
        for user_id, username in user_cache.items():
            data = data.replace(f'<@{user_id}>', f'@{username}')
        # Replace usergroup mentions in text
        for ug_id, handle in usergroup_cache.items():
            data = re.sub(rf'<!subteam\^{ug_id}(?:\|@[^>]+)?>', f'@{handle}', data)
        return data
    else:
        return data


async def substitute_users_in_json_async(data, token, cookie):
    """Substitute user IDs and usergroup IDs with names in JSON data

    Uses asyncio to fetch all user/usergroup info in parallel for speed.

    Args:
        data: JSON data (dict or list)
        token: Slack API token
        cookie: Slack 'd' cookie value

    Returns:
        Modified data with user IDs replaced by usernames
    """
    # Find all IDs
    user_ids, usergroup_ids = _find_ids_in_data(data)

    if not user_ids and not usergroup_ids:
        return data

    # Fetch all names in parallel
    async with httpx.AsyncClient() as client:
        tasks = []
        if user_ids:
            tasks.append(fetch_usernames_async(user_ids, token, cookie, client))
        if usergroup_ids:
            tasks.append(fetch_usergroup_names_async(usergroup_ids, token, cookie, client))

        results = await asyncio.gather(*tasks)

        user_cache = results[0] if user_ids else {}
        usergroup_cache = results[1] if usergroup_ids and len(results) > 1 else (results[0] if usergroup_ids else {})

    # Substitute IDs with names
    return _substitute_ids_in_data(data, user_cache, usergroup_cache)
