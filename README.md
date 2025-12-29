# Chess AI Coach ♟️🤖

A powerful, educational Chess AI that doesn't just play—it **teaches**.

Built with a custom Minimax engine and **RAG (Retrieval-Augmented Generation)**, this AI explains its moves in natural language, cites key chess principles, and references similar historical master games to help you improve.

## ✨ Features

*   **🧠 RAG AI Coach**:
    *   Explains "Why" a move is good or bad using Google Gemini.
    *   **Key Principles**: Distills complex tactics into one-sentence "Mindsets" (e.g., "Control the Center", "Knight Outpost").
    *   **Engine Internals**: Exposes raw calculation data (Score, PV) to show you the computer's thought process.
    *   **Context Aware**: Knows whose turn it is and analyzes from the correct perspective.

*   **⚡ Strong Chess Engine**:
    *   **Minimax Algorithm** with Alpha-Beta Pruning.
    *   **Quiescence Search**: Prevents the "Horizon Effect" by searching deeper in tactical exchanges.
    *   **Dynamic Endgame Depth**: Automatically searches deeper (up to Depth 8) in endgames to find checkmates.
    *   **Opening Book**: Uses `gm2001.bin` for diverse and professional openings.

*   **🤖 Lichess Bot Integration**:
    *   Can connect to Lichess.org as a Bot account.
    *   Auto-accepts challenges and plays using the engine.
    *   Includes auto-reconnect and retry logic for stability.

*   **📊 Interactive Web UI**:
    *   React-based frontend with a chessboard.
    *   Real-time evaluation chart (CP Loss).
    *   Chat interface to ask the AI Coach questions.

## 🛠️ Tech Stack

*   **Backend**: Python, FastAPI, python-chess, SQLAlchemy
*   **AI/RAG**: Google Gemini API, ChromaDB (Vector Database)
*   **Frontend**: React, Vite, chess.js, react-chessboard, Recharts
*   **Infrastructure**: Docker, Docker Compose

## 🚀 Getting Started

### Prerequisites

*   Docker & Docker Compose
*   [Google Gemini API Key](https://aistudio.google.com/) (for RAG Coach)
*   [Lichess API Token](https://lichess.org/account/oauth/token) (optional, for Bot)

### Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/pollop123/chess_coach.git
    cd chess_coach
    ```

2.  **Configure Environment Variables**
    Create a `.env` file in the `backend/` directory:
    ```bash
    # backend/.env
    GOOGLE_API_KEY=your_google_api_key_here
    LICHESS_API_TOKEN=your_lichess_token_here
    ```

3.  **Run with Docker Compose**
    ```bash
    docker-compose up --build
    ```

    The app should now be running at:
    *   **Frontend**: http://localhost:5173
    *   **Backend API**: http://localhost:8000/docs

## 🎮 Usage

### Playing & Analysis (Web UI)
1.  Open http://localhost:5173.
2.  Play against the AI or analyze a position.
3.  Click **"Ask AI Coach"** to get a detailed explanation of the current board state.

### Running the Lichess Bot
To bring your bot online on Lichess:

1.  Ensure `LICHESS_API_TOKEN` is set in `.env`.
2.  Run the bot script inside the container:
    ```bash
    docker-compose exec backend python lichess_bot.py
    ```
3.  Challenge your bot on Lichess!

*(Note: If your account is not a Bot account yet, run `docker-compose exec backend python upgrade_bot.py` first.)*

## 📂 Project Structure

```
.
├── backend/
│   ├── chess_engine.py  # Core Minimax Engine & Evaluation Logic
│   ├── rag.py           # RAG Logic (Gemini + ChromaDB)
│   ├── lichess_bot.py   # Lichess Bot Client
│   ├── api.py           # FastAPI Endpoints
│   └── ...
├── frontend/
│   ├── src/             # React Source Code
│   └── ...
├── docker-compose.yml
└── README.md
```

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## 📄 License

[MIT](https://choosealicense.com/licenses/mit/)