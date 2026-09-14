# Waleed Zone Bot

[العربية](README_AR.md) · [Quick start](QUICK_START.md) · [Documentation](DOCUMENTATION_INDEX.md)

A production-oriented Telegram bot for publishing and managing apps and games in the Waleed Zone community. It provides a searchable catalog for users, an admin workflow for uploads and publishing, request management, favorites, group moderation, and optional external storage/link integrations.

## Features

- Browse, search, and save apps
- Submit and manage app requests
- Admin panel for creating, editing, deleting, and publishing entries
- Telegram file download and external upload workflow
- Optional DevUploads, ShrinkMe, and ImgBB integrations
- SteamRIP game-link extraction
- Welcome messages, anti-flood controls, blocked-word filters, warnings, mute, and ban tools
- SQLite for local development and PostgreSQL support for deployment
- Docker and Docker Compose support
- Async architecture built with aiogram and SQLAlchemy

## Tech stack

- Python 3.12
- aiogram 3
- SQLAlchemy 2
- SQLite / PostgreSQL
- httpx and aiohttp
- Docker

## Quick start

### 1. Clone the repository

```bash
git clone https://github.com/waleednjlaty/MyTelegramBot.git
cd MyTelegramBot
```


### 2. Create a virtual environment

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure the bot

```bash
cp .env.example .env
```

On Windows:

```powershell
Copy-Item .env.example .env
```

Open `.env` and provide at least:

```env
BOT_TOKEN=your_bot_token
ADMIN_IDS=123456789
DATABASE_URL=sqlite+aiosqlite:///data/bot.db
```

Never commit your real `.env` file or API tokens.

### 5. Run

```bash
python main.py
```

Then open the bot in Telegram and send `/start`.

## Configuration

| Variable | Required | Purpose |
|---|---:|---|
| `BOT_TOKEN` | Yes | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS` | Recommended | Comma-separated Telegram user IDs allowed to use admin features |
| `DATABASE_URL` | Yes | SQLAlchemy database URL |
| `CHANNEL_ID` / `CHANNEL_USERNAME` | For publishing | Target Telegram channel |
| `GROUP_ID` / `GROUP_USERNAME` | For moderation | Community group |
| `DEVUPLOAD_API_KEY` | Optional | Upload files to DevUploads |
| `SHRANKME_API_KEY` | Optional | Shorten published download links |
| `IMGBB_API_KEY` | Optional | Host or migrate images |
| `MAX_UPLOAD_BYTES` | Optional | Maximum accepted upload size |
| `DOWNLOAD_DIR` | Optional | Temporary upload directory |

See [`.env.example`](.env.example) for every supported setting.

## Docker

```bash
cp .env.example .env
mkdir -p data tmp/uploads logs
docker compose up --build -d
docker compose logs -f
```

Stop the service with:

```bash
docker compose down
```

## Tests and linting

```bash
pip install pytest pytest-asyncio ruff
pytest
ruff check .
```

## Project structure

```text
.
├── app/
│   ├── handlers/       # Telegram commands, messages, and callbacks
│   ├── keyboards/      # Inline and reply keyboards
│   ├── middlewares/    # Database, access, and throttling layers
│   ├── services/       # Application logic
│   ├── states/         # FSM states
│   └── utils/          # Text, constants, logging, and helpers
├── config/             # Environment-backed settings
├── database/           # Models, sessions, and repositories
├── integrations/       # DevUploads, ImgBB, ShrinkMe, SteamRIP, Telegram
├── scripts/            # Maintenance and migration scripts
├── tests/              # Automated tests
├── deploy/             # Deployment configuration
├── main.py             # Application entry point
└── docker-compose.yml
```

## Documentation

- [Start here](START_HERE.md)
- [Beginner's guide](BEGINNERS_GUIDE.md)
- [Local development](LOCAL_DEVELOPMENT.md)
- [Bot architecture](BOT_ARCHITECTURE.md)
- [Visual architecture map](ARCHITECTURE_VISUAL_MAP.md)
- [Advanced usage](ADVANCED_USAGE.md)
- [Local testing checklist](LOCAL_TESTING_CHECKLIST.md)
- [Railway deployment](RAILWAY_DEPLOYMENT.md)
- [Pre-deployment checklist](PRE_DEPLOYMENT_CHECKLIST.md)

## Security notes

- Keep bot tokens and API keys only in environment variables.
- Rotate a token immediately if it is exposed in a commit, log, screenshot, or chat.
- Review admin IDs and Telegram permissions before deploying.
- Back up persistent database data before upgrades.

## Contributing

Issues and pull requests are welcome. For large changes, open an issue first and describe the proposed behavior.

---

Built and maintained by [Waleed Al-Najlat](https://github.com/waleednjlaty).
