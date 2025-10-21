"""Activity command - show Slack activity feed"""

import sys
import asyncio
import httpx
from ..auth import read_auth_file
from ..api import call_slack_api, call_slack_api_async
from ..formatters import get_formatter


async def fetch_message_content(channel_id, timestamp, token, cookie, client):
    """Fetch message content from channel and timestamp

    Args:
        channel_id: Slack channel ID
        timestamp: Message timestamp
        token: Slack API token
        cookie: Slack 'd' cookie value
        client: httpx.AsyncClient instance

    Returns:
        str: Message text or None if lookup fails
    """
    result = await call_slack_api_async('conversations.history', token, cookie, client,
                                       method='GET',
                                       params={'channel': channel_id, 'latest': timestamp,
                                              'inclusive': True, 'limit': 1})
    if result and result.get('ok') and result.get('messages'):
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
    return None


async def fetch_usernames(user_ids, token, cookie, client):
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


async def fetch_channel_names(channel_ids, token, cookie, client):
    """Fetch multiple channel names in parallel

    Args:
        channel_ids: Set of channel IDs to fetch
        token: Slack API token
        cookie: Slack 'd' cookie value
        client: httpx.AsyncClient instance

    Returns:
        dict: Mapping of channel_id -> channel_name
    """
    async def fetch_one(channel_id):
        result = await call_slack_api_async('conversations.info', token, cookie, client,
                                           method='GET', params={'channel': channel_id})
        if result and result.get('ok'):
            channel = result.get('channel', {})
            # For DMs, use the user's name if available
            if channel.get('is_im'):
                user_id = channel.get('user')
                if user_id:
                    user_result = await call_slack_api_async('users.info', token, cookie, client,
                                                            method='GET', params={'user': user_id})
                    if user_result and user_result.get('ok'):
                        user = user_result.get('user', {})
                        return channel_id, f"@{user.get('name', channel_id)}"
            return channel_id, channel.get('name', channel_id)
        return channel_id, channel_id

    tasks = [fetch_one(channel_id) for channel_id in channel_ids]
    results = await asyncio.gather(*tasks)
    return dict(results)


async def fetch_usergroup_names(usergroup_ids, token, cookie, client, workspace_url):
    """Fetch multiple user group names using EdgeAPI

    Args:
        usergroup_ids: Set of user group IDs to fetch
        token: Slack API token
        cookie: Slack 'd' cookie value
        client: httpx.AsyncClient instance
        workspace_url: Workspace URL to extract enterprise ID

    Returns:
        dict: Mapping of usergroup_id -> usergroup_handle
    """
    if not usergroup_ids:
        return {}

    # Extract enterprise ID from workspace URL
    # e.g., https://redhat.enterprise.slack.com -> E030G10V24F
    # We'll try to get it from auth.test or workspace_url
    # For now, we'll hardcode the pattern and extract from workspace_url
    # The EdgeAPI URL format is: https://edgeapi.slack.com/cache/{ENTERPRISE_ID}/usergroups/info

    # Call EdgeAPI in batch
    url = "https://edgeapi.slack.com/cache/E030G10V24F/usergroups/info"  # TODO: Get enterprise ID dynamically
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
                usergroup_map[ug_id] = f'@{handle}'
            return usergroup_map
    except:
        pass

    # Fallback: return @team for all
    return {ug_id: '@team' for ug_id in usergroup_ids}


async def enrich_items_async(items, token, cookie, workspace_url):
    """Enrich activity items with usernames, channel names, and message content in parallel

    Args:
        items: List of activity items
        token: Slack API token
        cookie: Slack 'd' cookie value
        workspace_url: Workspace URL

    Returns:
        list: Enriched activity items
    """
    import re

    # Collect all unique user IDs, channel IDs, and messages to fetch
    user_ids = set()
    channel_ids = set()
    messages_to_fetch = []  # List of (item_index, channel_id, timestamp) tuples

    for idx, item in enumerate(items):
        item_data = item.get('item', {})
        item_type = item_data.get('type')

        # Get channel ID and message timestamp
        if item_type == 'thread_v2':
            bundle_info = item_data.get('bundle_info', {})
            payload = bundle_info.get('payload', {})
            thread_entry = payload.get('thread_entry', {})
            channel_id = thread_entry.get('channel_id')
            # For threads, get the latest message in the thread
            ts = thread_entry.get('latest_ts')
            if channel_id and ts:
                messages_to_fetch.append((idx, channel_id, ts))
        else:
            message = item_data.get('message', {})
            channel_id = message.get('channel')
            ts = message.get('ts')
            # Fetch message content for mentions and other types
            if channel_id and ts:
                messages_to_fetch.append((idx, channel_id, ts))

        if channel_id:
            channel_ids.add(channel_id)

        # Get user ID
        if item_type == 'message_reaction':
            reaction = item_data.get('reaction', {})
            user_id = reaction.get('user')
            if user_id:
                user_ids.add(user_id)
        elif item_type in ['at_user', 'at_user_group', 'at_channel', 'at_everyone', 'keyword']:
            message = item_data.get('message', {})
            user_id = message.get('author_user_id')
            if user_id:
                user_ids.add(user_id)

    # Fetch all data in parallel
    async with httpx.AsyncClient() as client:
        # Create tasks for all fetches
        tasks = [
            fetch_usernames(user_ids, token, cookie, client),
            fetch_channel_names(channel_ids, token, cookie, client),
        ]

        # Add message fetch tasks
        message_tasks = [
            fetch_message_content(channel_id, ts, token, cookie, client)
            for _, channel_id, ts in messages_to_fetch
        ]

        # Gather all results
        all_results = await asyncio.gather(*tasks, *message_tasks)
        username_cache = all_results[0]
        channel_cache = all_results[1]
        message_contents = all_results[2:]  # Remaining results are message contents

        # Build message cache indexed by item index
        message_cache = {}
        for i, (item_idx, _, _) in enumerate(messages_to_fetch):
            if i < len(message_contents):
                message_cache[item_idx] = message_contents[i]

        # Extract additional user IDs and usergroup IDs from message texts
        additional_user_ids = set()
        usergroup_ids = set()
        for msg_text in message_cache.values():
            if msg_text:
                # Find all user mentions in format <@USER_ID>
                user_mentions = re.findall(r'<@([A-Z0-9]+)>', msg_text)
                additional_user_ids.update(user_mentions)

                # Find all user group mentions in format <!subteam^USERGROUP_ID>
                usergroup_mentions = re.findall(r'<!subteam\^([A-Z0-9]+)>', msg_text)
                usergroup_ids.update(usergroup_mentions)

        # Remove user IDs we already fetched
        additional_user_ids -= user_ids

        # Fetch additional usernames and usergroup names if needed
        fetch_tasks = []
        if additional_user_ids:
            fetch_tasks.append(fetch_usernames(additional_user_ids, token, cookie, client))
        if usergroup_ids:
            fetch_tasks.append(fetch_usergroup_names(usergroup_ids, token, cookie, client, workspace_url))

        if fetch_tasks:
            fetch_results = await asyncio.gather(*fetch_tasks)
            if additional_user_ids:
                username_cache.update(fetch_results[0])
                usergroup_cache = fetch_results[1] if len(fetch_results) > 1 else {}
            else:
                usergroup_cache = fetch_results[0]
        else:
            usergroup_cache = {}

    # Enrich items using cached data
    enriched_items = []
    for idx, item in enumerate(items):
        enriched = item.copy()
        item_data = item.get('item', {})
        item_type = item_data.get('type')

        # Get channel name from cache
        channel_id = None
        if item_type == 'thread_v2':
            bundle_info = item_data.get('bundle_info', {})
            payload = bundle_info.get('payload', {})
            thread_entry = payload.get('thread_entry', {})
            channel_id = thread_entry.get('channel_id')
        else:
            message = item_data.get('message', {})
            channel_id = message.get('channel')

        if channel_id:
            enriched['channel_name'] = channel_cache.get(channel_id, 'unknown')
        else:
            enriched['channel_name'] = 'unknown'

        # Get message content from cache and replace user/group IDs with names
        if idx in message_cache:
            msg_text = message_cache[idx]
            if msg_text:
                # Replace user mentions with actual usernames
                def replace_user_mention(match):
                    user_id = match.group(1)
                    username = username_cache.get(user_id, 'user')
                    return f'@{username}'

                msg_text = re.sub(r'<@([A-Z0-9]+)>', replace_user_mention, msg_text)

                # Replace usergroup mentions with actual group names
                def replace_usergroup_mention(match):
                    usergroup_id = match.group(1)
                    return usergroup_cache.get(usergroup_id, '@team')

                msg_text = re.sub(r'<!subteam\^([A-Z0-9]+)>', replace_usergroup_mention, msg_text)
            enriched['message_text'] = msg_text

        # Get username from cache and reaction details
        if item_type == 'message_reaction':
            reaction = item_data.get('reaction', {})
            user_id = reaction.get('user')
            if user_id:
                enriched['username'] = username_cache.get(user_id, user_id)
            enriched['emoji'] = reaction.get('name', 'unknown')
        elif item_type in ['at_user', 'at_user_group', 'at_channel', 'at_everyone', 'keyword']:
            message = item_data.get('message', {})
            user_id = message.get('author_user_id')
            if user_id:
                enriched['username'] = username_cache.get(user_id, user_id)

        enriched_items.append(enriched)

    return enriched_items


def cmd_activity(args):
    """Show activity feed (mentions, threads, reactions)

    Args:
        args: Parsed command-line arguments
            - auth_file: Path to authentication file
            - output: Output format ('text' or 'json')
            - tab: Which activity tab to show (all, mentions, threads, reactions)
    """
    creds = read_auth_file(args.auth_file)
    formatter = get_formatter(args.output)

    # Get workspace URL from auth.test
    auth_result = call_slack_api('auth.test', creds['token'], creds['cookie'])
    if not auth_result.get('ok'):
        formatter.format_error("Failed to authenticate")
        sys.exit(1)

    workspace_url = auth_result.get('url', '').rstrip('/')

    # Determine which types to fetch based on tab
    tab = getattr(args, 'tab', 'all')

    if tab == 'mentions':
        types = "at_user,at_user_group,at_channel,at_everyone,keyword,list_user_mentioned"
    elif tab == 'threads':
        types = "thread_v2"
    elif tab == 'reactions':
        types = "message_reaction"
    else:  # all
        types = "thread_v2,message_reaction,internal_channel_invite,list_record_edited,bot_dm_bundle,at_user,at_user_group,at_channel,at_everyone,keyword,list_record_assigned,list_user_mentioned,list_todo_notification,list_approval_request,list_approval_reviewed,unjoined_channel_mention,external_channel_invite,external_dm_invite"

    # Call activity.feed API with form data
    data = {
        "limit": "50",
        "types": types,
        "mode": "priority_reads_and_unreads_v1",
        "archive_only": "false",
        "snooze_only": "false",
        "unread_only": "false",
        "priority_only": "false",
        "is_activity_inbox": "false"
    }

    result = call_slack_api(
        'activity.feed',
        creds['token'],
        creds['cookie'],
        method='POST',
        data=data,
        workspace_url=workspace_url,
        use_form_data=True
    )

    if not result.get('ok'):
        formatter.format_error(f"Failed to fetch activity: {result.get('error')}")
        sys.exit(1)

    items = result.get('items', [])

    # Enrich items with channel names and usernames using async
    enriched_items = asyncio.run(enrich_items_async(items, creds['token'], creds['cookie'], workspace_url))

    # Format and output
    formatter.format_activity(enriched_items, tab)
