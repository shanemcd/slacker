"""Output formatters using Strategy Pattern"""

import json
import emoji
import re
from abc import ABC, abstractmethod


def clean_slack_message(text):
    """Clean up Slack markup from message text

    Args:
        text: Raw Slack message text with markup

    Returns:
        str: Cleaned message text
    """
    if not text:
        return text

    # Note: User mentions <@USER_ID> and usergroup mentions <!subteam^ID>
    # are already replaced with actual names in enrichment, so we don't convert them here

    # Convert special mentions
    text = text.replace('<!channel>', '@channel')
    text = text.replace('<!here>', '@here')
    text = text.replace('<!everyone>', '@everyone')

    # Convert links <https://url|text> to just text or <https://url> to url
    text = re.sub(r'<(https?://[^|>]+)\|([^>]+)>', r'\2', text)  # <url|text> -> text
    text = re.sub(r'<(https?://[^>]+)>', r'\1', text)  # <url> -> url

    # Convert emoji codes to actual emojis (keep custom emoji codes as-is)
    def replace_emoji(match):
        emoji_code = match.group(0)
        # Try to convert to actual emoji
        converted = emoji.emojize(emoji_code, language='alias')
        # If it didn't convert (custom emoji), keep the original code
        return converted

    text = re.sub(r':[\w\-+]+:', replace_emoji, text)

    return text.strip()


class OutputFormatter(ABC):
    """Abstract base class for output formatters"""

    @abstractmethod
    def format_auth_test(self, result, auth_file=None):
        """Format authentication test results"""
        pass

    @abstractmethod
    def format_reminders(self, items, counts):
        """Format reminders/saved items list"""
        pass

    @abstractmethod
    def format_discover(self, methods, categories, total, category_filter=None, verbose=False):
        """Format API methods discovery results"""
        pass

    @abstractmethod
    def format_dms(self, dms, group_dms, counts):
        """Format DM list"""
        pass

    @abstractmethod
    def format_activity(self, items, tab):
        """Format activity feed"""
        pass

    @abstractmethod
    def format_error(self, message):
        """Format error message"""
        pass


class TextFormatter(OutputFormatter):
    """Human-readable text output formatter"""

    def format_auth_test(self, result, auth_file=None):
        if auth_file:
            print(f"Testing authentication from {auth_file}...\n")

        if result.get('ok'):
            print("✓ Authentication successful!\n")
            print(f"  User:      {result.get('user')}")
            print(f"  User ID:   {result.get('user_id')}")
            print(f"  Team:      {result.get('team')}")
            print(f"  Team ID:   {result.get('team_id')}")
            print(f"  URL:       {result.get('url')}")
        else:
            print(f"✗ Authentication failed: {result.get('error')}")
            print("\nYour credentials may have expired. Run 'slacker login' again.")

    def format_reminders(self, items, counts):
        if not items:
            print("No saved items found.")
            return

        print(f"Found {len(items)} saved items:\n")

        for item_data in items:
            if item_data['type'] == 'reminder':
                print(f"[{item_data['state']}] Reminder: {item_data['text']}")
                print(f"  Due: {item_data['due_date']}")
                print()
            else:
                print(f"[{item_data['state']}] Saved message in #{item_data['channel_name']}")
                print(f"  Date: {item_data['date']}")
                if item_data['message']:
                    print(f"  Message: {item_data['message']}")
                print(f"  Link: {item_data['link']}")
                print()

        print(f"Summary:")
        print(f"  Total: {counts.get('total_count', 0)}")
        print(f"  Uncompleted: {counts.get('uncompleted_count', 0)}")
        print(f"  Overdue: {counts.get('uncompleted_overdue_count', 0)}")
        print(f"  Completed: {counts.get('completed_count', 0)}")

    def format_discover(self, methods, categories, total, category_filter=None, verbose=False):
        print(f"\nFound {total} API methods:\n")

        if category_filter:
            if category_filter in categories:
                print(f"Category: {category_filter}")
                for method in categories[category_filter]:
                    print(f"  - {method}")
            else:
                print(f"Category '{category_filter}' not found.")
                print(f"Available categories: {', '.join(sorted(categories.keys()))}")
        else:
            for category in sorted(categories.keys()):
                print(f"{category} ({len(categories[category])} methods)")
                if verbose:
                    for method in categories[category]:
                        print(f"  - {method}")

    def format_dms(self, dms, group_dms, counts):
        if not dms and not group_dms:
            print("No DMs found for today.")
            return

        print(f"Today's DM Activity ({counts['dms']} individual + {counts['group_dms']} group):\n")

        if dms:
            print("Individual DMs:")
            for dm in dms:
                direction = "→ You" if dm['from_you'] else f"← @{dm['username']}"
                text_preview = dm['text'][:80] if dm['text'] else "[no text]"
                if dm.get('has_files'):
                    text_preview = "[file attachment]"
                print(f"  {dm['time']} {direction}: {text_preview}")
            print()

        if group_dms:
            print("Group DMs:")
            for dm in group_dms:
                direction = "You" if dm['from_you'] else f"@{dm['username']}"
                text_preview = dm['text'][:80] if dm['text'] else "[no text]"
                print(f"  {dm['time']} {direction}: {text_preview}")

    def format_activity(self, items, tab):
        if not items:
            print(f"No {tab} activity found.")
            return

        # Map types to human-readable names
        type_names = {
            'at_user': 'mention',
            'at_user_group': 'group mention',
            'at_channel': '@channel',
            'at_everyone': '@everyone',
            'keyword': 'keyword',
            'message_reaction': 'reaction',
            'thread_v2': 'thread reply',
        }

        print(f"Activity Feed - {tab.title()} ({len(items)} items):\n")

        for item in items:
            is_unread = "●" if item.get('is_unread') else " "
            item_data = item.get('item', {})
            item_type = item_data.get('type', 'unknown')
            type_name = type_names.get(item_type, item_type)

            # Get enriched data
            channel_name = item.get('channel_name', 'unknown')
            username = item.get('username', '')
            emoji_name = item.get('emoji', '')
            message_text = item.get('message_text', '')

            # Different structure for thread_v2
            if item_type == 'thread_v2':
                bundle_info = item_data.get('bundle_info', {})
                payload = bundle_info.get('payload', {})
                thread_entry = payload.get('thread_entry', {})
                ts = thread_entry.get('latest_ts', '')
            else:
                message = item_data.get('message', {})
                ts = message.get('ts', '')

            # Format timestamp if available
            if ts:
                import datetime
                try:
                    dt = datetime.datetime.fromtimestamp(float(ts))
                    time_str = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    time_str = ts
            else:
                time_str = 'unknown'

            # Build detailed output
            details = []
            if item_type == 'message_reaction' and emoji_name:
                # Convert emoji code to actual emoji
                emoji_code = f":{emoji_name}:"
                emoji_str = emoji.emojize(emoji_code, language='alias')
                # If it didn't convert (custom emoji), show name without colons
                if emoji_str == emoji_code:
                    emoji_str = emoji_name  # Just show the name
                details.append(emoji_str)
                if username:
                    details.append(f"from @{username}")
            elif item_type in ['at_user', 'at_user_group', 'at_channel', 'at_everyone', 'keyword'] and username:
                details.append(f"by @{username}")

            detail_str = " ".join(details)

            # Build output line
            output_parts = [f"{is_unread} [{type_name}] {time_str} in #{channel_name}"]
            if detail_str:
                output_parts.append(f"- {detail_str}")

            # Add message preview if available (truncate to 80 chars)
            if message_text:
                # Clean up Slack markup
                cleaned = clean_slack_message(message_text)
                preview = cleaned.replace('\n', ' ')[:80]
                if len(cleaned) > 80:
                    preview += "..."
                output_parts.append(f"\n    {preview}")

            print(" ".join(output_parts))

    def format_error(self, message):
        print(f"✗ {message}")


class JSONFormatter(OutputFormatter):
    """JSON output formatter"""

    def format_auth_test(self, result, auth_file=None):
        print(json.dumps(result, indent=2))

    def format_reminders(self, items, counts):
        output = {
            'items': items,
            'counts': counts
        }
        print(json.dumps(output, indent=2))

    def format_discover(self, methods, categories, total, category_filter=None, verbose=False):
        if category_filter:
            if category_filter in categories:
                output = {
                    'category': category_filter,
                    'methods': categories[category_filter]
                }
            else:
                output = {
                    'error': f"Category '{category_filter}' not found",
                    'available_categories': sorted(categories.keys())
                }
        else:
            output = {
                'total_methods': total,
                'categories': categories
            }
        print(json.dumps(output, indent=2))

    def format_dms(self, dms, group_dms, counts):
        output = {
            'today_dms': dms,
            'today_group_dms': group_dms,
            'count': counts
        }
        print(json.dumps(output, indent=2))

    def format_activity(self, items, tab):
        # Include message_text in JSON output for consumers
        output = {
            'tab': tab,
            'count': len(items),
            'items': items
        }
        print(json.dumps(output, indent=2))

    def format_error(self, message):
        print(json.dumps({'error': message}, indent=2))


def get_formatter(output_format):
    """Factory function to get the appropriate formatter"""
    formatters = {
        'text': TextFormatter,
        'json': JSONFormatter,
    }

    formatter_class = formatters.get(output_format)
    if not formatter_class:
        raise ValueError(f"Unknown output format: {output_format}")

    return formatter_class()
