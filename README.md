# GenABAP

AI-powered ABAP assistant with real-time chat interface and interaction logging.

## Features

- Real-time chat interface using Flask-SocketIO
- ABAP code formatting and syntax highlighting
- User feedback collection (good/average/bad ratings)
- MongoDB integration for chat logging
- Tabbed view for code and markdown display
- Responsive web interface

## Setup

```bash
pip install -r requirements.txt
# Edit .env with your values
python run.py
```

Or run directly:

```bash
python app.py
```

## Config (.env)

```
MONGO_URI=mongodb://localhost:27017/
MONGO_DB=genabap
API_BASE_URL=http://your-server:port/v1
MODEL_PATH=/path/to/your/model
SECRET_KEY=your-secret-key-change-this-in-production
```

## Usage

1. Start the application with `python run.py`
2. Open your browser to `http://localhost:5000`
3. Start chatting about ABAP!

The application will automatically:

- Format ABAP code responses with syntax highlighting
- Log all interactions to MongoDB
- Allow users to provide feedback on AI responses
- Maintain chat history during the session

Done! 🚀
