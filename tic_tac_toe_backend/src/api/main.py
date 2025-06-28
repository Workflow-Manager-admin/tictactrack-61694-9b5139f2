from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from uuid import uuid4
from typing import List, Dict, Optional
import copy

app = FastAPI(
    title="Tic Tac Toe Backend API",
    description="FastAPI backend for Tic Tac Toe with REST endpoints for gameplay and history.",
    version="1.0.0",
    openapi_tags=[
        {"name": "game", "description": "Endpoints to manage Tic Tac Toe games."},
        {"name": "history", "description": "Endpoints to retrieve game history."}
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
# Two blank lines required before top-level class definition
# (Added blank line above to ensure exactly two blank lines here.)
 

class StartGameRequest(BaseModel):
    player_x: Optional[str] = Field(
        default=None,
        description="Identifier for Player X (optional, can be anonymous)"
    )
    player_o: Optional[str] = Field(
        default=None,
        description="Identifier for Player O (optional, can be anonymous)"
    )
    first_player: str = Field(
        default="X",
        description="Who goes first: 'X' or 'O' (default 'X')"
    )



class MoveRequest(BaseModel):
    game_id: str = Field(
        ...,
        description="Game identifier returned by /game/start"
    )
    player: str = Field(
        ...,
        description="'X' or 'O'"
    )
    position: int = Field(
        ...,
        ge=0,
        le=8,
        description="Index of the position on the board (0-8)"
    )



class GameStateResponse(BaseModel):
    game_id: str
    board: List[Optional[str]] = Field(
        ...,
        description="Current board state (list of 9 elements: 'X', 'O', or None)"
    )
    current_player: str = Field(
        ...,
        description="Whose turn it is: 'X' or 'O'"
    )
    winner: Optional[str] = Field(
        default=None,
        description="'X', 'O', 'Draw', or None if ongoing"
    )
    is_over: bool = Field(
        ...,
        description="Has the game ended?"
    )
    moves: List[Dict] = Field(
        ...,
        description="A chronologically ordered list of moves (position, player)"
    )
    player_x: Optional[str] = Field(default=None)
    player_o: Optional[str] = Field(default=None)



class GameHistoryItem(BaseModel):
    game_id: str
    player_x: Optional[str]
    player_o: Optional[str]
    winner: Optional[str]
    moves: List[Dict]


class GameHistoryResponse(BaseModel):
    history: List[GameHistoryItem]


# --- In-memory "database" ---
games: Dict[str, dict] = {}  # Ongoing and completed games, keyed by game_id
game_history: List[dict] = []  # List of finished games for /api/game/history

# --- Helper Logic ---


# PUBLIC_INTERFACE
def check_winner(board: List[Optional[str]]) -> Optional[str]:
    """
    Check board for a winner. Returns 'X', 'O', 'Draw', or None if game continues.
    """
    win_indices = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # columns
        [0, 4, 8], [2, 4, 6]              # diagonals
    ]
    for indices in win_indices:
        line = [board[i] for i in indices]
        if line[0] and line.count(line[0]) == 3:
            return line[0]
    if all(cell is not None for cell in board):
        return "Draw"
    return None

# --- Endpoints ---


# PUBLIC_INTERFACE
@app.post(
    "/api/game/start",
    response_model=GameStateResponse,
    tags=["game"],
    summary="Start a new game"
)
def start_game(body: StartGameRequest):
    """
    Start a new Tic Tac Toe game.

    - **player_x**: Identifier for Player X (optional)
    - **player_o**: Identifier for Player O (optional)
    - **first_player**: 'X' or 'O' (default: 'X')
    """
    game_id = str(uuid4())
    first = body.first_player.upper()
    if first not in ("X", "O"):
        raise HTTPException(status_code=400, detail="first_player must be 'X' or 'O'")
    game_data = {
        "game_id": game_id,
        "board": [None] * 9,
        "moves": [],
        "current_player": first,
        "player_x": body.player_x,
        "player_o": body.player_o,
        "winner": None,
        "is_over": False,
    }
    games[game_id] = game_data
    return GameStateResponse(**game_data)


# PUBLIC_INTERFACE
@app.post(
    "/api/game/move",
    response_model=GameStateResponse,
    tags=["game"],
    summary="Make a move"
)
def make_move(request: MoveRequest):
    """
    Make a move in a Tic Tac Toe game.

    - **game_id**: Game identifier
    - **player**: 'X' or 'O'
    - **position**: 0-8 (board index)
    """
    game = games.get(request.game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game['is_over']:
        raise HTTPException(status_code=400, detail="Game is already over")
    if request.player != game['current_player']:
        raise HTTPException(status_code=400, detail="Not this player's turn")
    if not (0 <= request.position <= 8):
        raise HTTPException(status_code=400, detail="Position out of range")
    if game['board'][request.position] is not None:
        raise HTTPException(status_code=400, detail="Cell already taken")

    # Make the move
    game['board'][request.position] = request.player
    game['moves'].append(
        {"position": request.position, "player": request.player}
    )

    # Check for winner or draw
    winner = check_winner(game['board'])
    if winner:
        game['is_over'] = True
        game['winner'] = winner
        # Save to game history and remove from ongoing
        game_history.append(
            {
                "game_id": game['game_id'],
                "player_x": game['player_x'],
                "player_o": game['player_o'],
                "winner": winner,
                "moves": copy.deepcopy(game['moves'])
            }
        )
    else:
        # Switch player
        game['current_player'] = "O" if request.player == "X" else "X"
    return GameStateResponse(**game)


# PUBLIC_INTERFACE
@app.get(
    "/api/game/state",
    response_model=GameStateResponse,
    tags=["game"],
    summary="Get current game state"
)
def get_game_state(game_id: str):
    """
    Retrieve the current state of a game.

    - **game_id**: Game identifier
    """
    game = games.get(game_id)
    if not game:
        # Check in history (for completed games)
        for hist in reversed(game_history):
            if hist['game_id'] == game_id:
                # reconstruct final board
                board = [None] * 9
                for move in hist["moves"]:
                    board[move["position"]] = move["player"]
                return GameStateResponse(
                    game_id=hist["game_id"],
                    board=board,
                    current_player=None,
                    winner=hist["winner"],
                    is_over=True,
                    moves=hist["moves"],
                    player_x=hist["player_x"],
                    player_o=hist["player_o"]
                )
        raise HTTPException(status_code=404, detail="Game not found")
    return GameStateResponse(**game)


# PUBLIC_INTERFACE
@app.get(
    "/api/game/history",
    response_model=GameHistoryResponse,
    tags=["history"],
    summary="Retrieve game history"
)
def get_game_history():
    """
    Retrieve a list of historical completed games.
    """
    res = [
        GameHistoryItem(
            game_id=g["game_id"],
            player_x=g["player_x"],
            player_o=g["player_o"],
            winner=g["winner"],
            moves=g["moves"],
        )
        for g in game_history
    ]
    return GameHistoryResponse(history=res)


@app.get("/")
def health_check():
    """Basic health check endpoint."""
    return {"message": "Healthy"}


# --- Error handling for OpenAPI/Swagger UI clarity ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
