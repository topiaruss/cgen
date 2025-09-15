# Campaign Generator

GenAI-powered campaign asset generation for multiple aspect ratios.

## Quick Start

**Prerequisites:** Install [uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash

# clone the repo
git clone https://github.com/topiaruss/cgen.git

# Environment setup
cp .env.example .env
# Edit .env to add your OPENAI_API_KEY - obtain a key for this purpose. Delete when done.

# Install dependencies and setup database
uv sync --extra dev

# create the database and add some initial data
uv run python app/manage.py migrate
uv run python app/manage.py loaddata app/campaign_generator/fixtures/*.json

# Run development server
uv run python app/manage.py runserver
```

Visit http://localhost:8000

## Features

- **Campaign brief management** with product and audience targeting
- **AI image generation** using DALL-E 3 for missing product assets
- **Multi-aspect ratio output** (1:1, 9:16, 16:9) for social platforms
- **Text overlay system** with campaign messaging
- **Web gallery** for viewing generated assets
- **Organized file structure** by product and aspect ratio

## Project Structure

```
app/
├── campaign_generator/        # Main Django app
│   ├── models.py             # Brief, GeneratedAsset models
│   ├── ai_service.py         # DALL-E integration
│   ├── views.py              # Web interface
│   ├── fixtures/             # Sample data
│   └── templates/            # HTML templates
├── config/                   # Django settings
├── media/                    # Generated assets
└── static/                   # CSS/JS assets
```

## Development

```bash
# Run tests
uv run pytest
```