# Slacker

Automate Slack API calls using your browser session credentials.

## Quick Start

```bash
# 1. Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install dependencies and playwright browser
uv sync
uv run playwright install chromium

# 3. Extract credentials
uv run slacker login https://your-workspace.slack.com

# 4. Test authentication
uv run slacker whoami
```

That's it!

## Commands

### Login
Extract credentials from your browser:
```bash
uv run slacker login https://your-workspace.slack.com

# Save to custom location (default: ~/.config/slacker/credentials)
uv run slacker --auth-file /path/to/custom/location login https://workspace.slack.com
```

### Whoami
Test authentication and show your user info:
```bash
uv run slacker whoami

# Use custom auth file
uv run slacker --auth-file /path/to/custom/location whoami
```

### API
Call any Slack API endpoint:
```bash
# GET request with query parameters
uv run slacker api users.list --params '{"limit": 10}'

# POST request with data
uv run slacker api chat.postMessage --data '{"channel":"general","text":"Hello!"}'

# GET with multiple parameters
uv run slacker api conversations.history --params '{"channel":"C1234567890","limit":50}'

# Specify method explicitly
uv run slacker api conversations.list --method GET
```

### Discover
Explore available Slack API methods:
```bash
# List all API categories
uv run slacker discover

# Show all methods (verbose)
uv run slacker discover --verbose

# Filter by category
uv run slacker discover --category chat
uv run slacker discover --category users
uv run slacker discover --category conversations
```

### Reminder
Create Slack reminders using natural language (just like `/remind` in Slack):
```bash
# Create reminders - Slack parses the text naturally
uv run slacker reminder "me to call mom tomorrow at 9am"
uv run slacker reminder "me to review PR in 30 minutes"
uv run slacker reminder "me to check status next Monday"

# You can omit "me to" if you prefer
uv run slacker reminder "call mom tomorrow"

# Send reminder to specific channel (default: your notes channel)
uv run slacker reminder "team meeting tomorrow at 2pm" --channel C1234567890
```

### Reminders
List your saved reminders and "Later" items:
```bash
# List all saved items (reminders and saved messages)
uv run slacker reminders

# List only reminders (exclude saved messages)
uv run slacker reminders --reminders-only

# Limit number of results
uv run slacker reminders --limit 10
```

## Use Cases

### Explore the API
Discover what's possible:
```bash
# See all available API categories
uv run slacker discover

# Explore chat-related methods
uv run slacker discover --category chat

# Call a specific endpoint
uv run slacker api users.list --params '{"limit": 10}'
```

### Post messages
```bash
uv run slacker api chat.postMessage --data '{"channel":"general","text":"Hello from slacker!"}'
```

### List conversations
```bash
uv run slacker api conversations.list --params '{"limit": 100}'
```

### Search messages
```bash
uv run slacker api search.messages --params '{"query":"important"}'
```

### Upload files
```bash
uv run slacker api files.upload --data '{"channels":"general","content":"File content","filename":"test.txt"}'
```

### Manage reminders
```bash
# Create reminders using natural language
uv run slacker reminder "me to follow up with team tomorrow at 10am"
uv run slacker reminder "check on deployment in 2 hours"

# List all reminders and saved messages
uv run slacker reminders

# List only reminders
uv run slacker reminders --reminders-only
```

### Use with curl
The credentials are saved in shell format for use with curl:
```bash
source ~/.config/slacker/credentials

curl -H "Authorization: Bearer $SLACK_TOKEN" \
     -H "Cookie: d=$SLACK_COOKIE" \
     https://slack.com/api/conversations.list
```

## API Documentation

Full Slack API docs: https://api.slack.com/methods

Use `slacker discover` to explore available methods, or browse the documentation online.

Common categories:
- `chat` - Send and manage messages
- `conversations` - Manage channels and groups
- `users` - User information
- `files` - File uploads and management
- `search` - Search messages and files
- `reactions` - Emoji reactions
- `pins` - Pin messages

## Files

- **src/slacker/** - Python package
- **pyproject.toml** - Project configuration
- **~/.config/slacker/credentials** - Generated credentials file (default location)

## Security

- Credentials are saved to `~/.config/slacker/credentials` by default
- File permissions are set to `0600` (only you can read)
- Credentials expire when you log out of Slack
- Use workspace apps with OAuth for production

## Troubleshooting

### "playwright not installed"
```bash
uv sync
uv run playwright install chromium
```

### "uv not found"
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### "Could not extract token"
Make sure you're fully logged in to Slack before pressing Enter in the terminal.

### Can't install Playwright?
Manual extraction from browser DevTools:
1. Open Slack, press F12
2. Console tab: `JSON.parse(localStorage.getItem('localConfig_v2')).teams` - copy token
3. Application/Storage tab → Cookies → find `d` cookie - copy value
4. Export both: `export SLACK_TOKEN="xoxc-..." SLACK_COOKIE="xoxd-..."`
