# Form Filler with AI

An intelligent form filling application built with Streamlit that uses Google's Gemini AI to help users fill out forms with natural language processing and validation.

## Features

- Upload JSON form definitions
- Intelligent question generation using Gemini AI
- Smart input validation with AI-powered feedback
- Progress tracking and form completion
- Support for various input types:
  - Text fields
  - Radio buttons
  - Checkboxes
  - Email addresses
  - Phone numbers
  - Dates
  - Numbers
- Form data persistence
- Download completed forms as JSON

## Setup

1. Clone the repository:
```bash
git clone https://github.com/HB9398/Form_Filler_Hitachi.git
cd Form_Filler_Hitachi
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your Google API key:
```
GOOGLE_API_KEY=your_api_key_here
```

4. Run the application:
```bash
streamlit run app.py
```

## Usage

1. Prepare your form definition in JSON format (see sample_form.json for example)
2. Upload the JSON file through the web interface
3. Follow the guided form filling process
4. Download the completed form as JSON

## Requirements

- Python 3.7+
- Streamlit >= 1.32.0
- Google Generative AI (Gemini) >= 0.3.2
- python-dotenv >= 1.0.0

## Project Structure

```
Form_Filler_Hitachi/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
├── sample_form.json    # Example form definition
└── .env               # Environment variables (create this)
```

## License

MIT 
