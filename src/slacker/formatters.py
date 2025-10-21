"""Output formatters using Strategy Pattern"""

import json
from abc import ABC, abstractmethod


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
