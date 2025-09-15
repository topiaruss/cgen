# Creative Automation Pipeline - FDE Proof of Concept

> **6-8 Hour Implementation**: GenAI-powered social campaign asset generation

## 🎯 What This Demo Does

1. **Accepts campaign briefs** (JSON/YAML) with products, target audience, and campaign message
2. **Generates hero images** using DALL-E 3 for missing assets
3. **Creates 3 aspect ratios** (1:1, 9:16, 16:9) for each product
4. **Adds text overlays** with campaign messaging
5. **Organizes outputs** in folders by product/aspect ratio

## Pre-req - install uv for your platform
https://docs.astral.sh/uv/getting-started/installation/

## 🚀 Quick Start

```bash
# Clone and setup
git clone [repo-url]
cd cgen

# Set OpenAI API key
echo "OPENAI_API_KEY=your_key_here" > .env

# setup the environment
cd app
uv sync


# Setup database and run
uv run python manage.py migrate
uv run python manage.py loaddata initial_languages.json 
uv run python manage.py loaddata demo_briefs.json 
uv run python manage.py loaddata demo_briefs_languages.json
uv run python manage.py runserver

# Visit http://localhost:8000
```

## 📁 Project Structure

```
adobe_demo/
├── app/
│   ├── campaign_generator/     # Core MVP app
│   │   ├── models.py          # Brief, GeneratedAsset models  
│   │   ├── ai_service.py      # DALL-E integration
│   │   └── views.py           # Simple web interface
│   └── config/                # Django settings
├── docs/
│   ├── MVP_EXTRACTION.md      # Implementation plan
│   ├── initial_doc.md         # Original brief context
│   └── FDE Take Home Instructions.txt
├── seeds/
│   └── demo_briefs.json       # Sample campaign data
└── FOCUSED_README.md          # Detailed documentation
```

## 📊 Demo Flow

1. Upload campaign brief via web form
2. System generates missing product images via DALL-E
3. Adds campaign message overlay for each aspect ratio  
4. Downloads organized ZIP file with all assets
5. View generated images in web gallery

## 🎨 Example Output

For "Pacific Pulse Energy Drink":
```
outputs/
├── pacific_pulse_original/
│   ├── 1x1/campaign_20241213_143052.jpg    # Instagram feed
│   ├── 9x16/campaign_20241213_143053.jpg   # Stories/TikTok  
│   └── 16x9/campaign_20241213_143054.jpg   # YouTube/video
└── pacific_pulse_zero/
    ├── 1x1/campaign_20241213_143055.jpg
    ├── 9x16/campaign_20241213_143056.jpg
    └── 16x9/campaign_20241213_143057.jpg
```

## 🔧 Key Design Decisions

- **Django Framework**: Rapid development, built-in admin
- **DALL-E 3**: State-of-the-art image generation  
- **Comparable Images**: Same core scene, aspect-optimized framing
- **Simple File Storage**: Direct filesystem organization
- **Focused Scope**: Core requirements only, no over-engineering

## ⚡ Performance Notes

- **Generation Time**: ~30 seconds per product (3 images)
- **Cost**: ~$0.12 per image via DALL-E 3
- **Output Quality**: 1024x1024 base resolution, scaled to aspect ratios

---

**Built for FDE Interview Exercise** | Demonstrates GenAI creative automation in 6-8 hours