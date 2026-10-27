import os
import sys
import json
import urllib.request
import random

REPO = os.environ.get("REPOSITORY", "kurui-ian/kurui-ian")
ISSUE_TITLE = os.environ.get("EVENT_ISSUE_TITLE", "").strip()
ISSUE_NUMBER = os.environ.get("EVENT_ISSUE_NUMBER", "").strip()
USER_LOGIN = os.environ.get("EVENT_USER_LOGIN", "").strip()
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

STATE_FILE = "connect4_games/game.json"
README_FILE = "README.md"

EMPTY = "⚪"
PLAYER = "🔴"
BOT = "🟡"

def post_github(url, data=None, method="POST"):
    if not TOKEN:
        print("No GITHUB_TOKEN present, skipping API call.")
        return
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "GitHub-Action-Connect4"
    }
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read()
    except Exception as e:
        print(f"Error calling GitHub API {url}: {e}")

def notify_and_close_issue(comment):
    if ISSUE_NUMBER:
        comment_url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUMBER}/comments"
        close_url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUMBER}"
        post_github(comment_url, {"body": comment})
        post_github(close_url, {"state": "closed"}, method="PATCH")

def empty_board():
    return [[EMPTY for _ in range(7)] for _ in range(6)]

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "board": empty_board(),
        "game_number": 1,
        "status": "in_progress",
        "last_player": "",
        "last_player_col": None,
        "last_bot_col": None
    }

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def get_available_row(board, col):
    for r in range(5, -1, -1):
        if board[r][col] == EMPTY:
            return r
    return -1

def check_win(board, piece):
    # Horizontal
    for r in range(6):
        for c in range(4):
            if all(board[r][c+i] == piece for i in range(4)):
                return True
    # Vertical
    for r in range(3):
        for c in range(7):
            if all(board[r+i][c] == piece for i in range(4)):
                return True
    # Diagonal \
    for r in range(3):
        for c in range(4):
            if all(board[r+i][c+i] == piece for i in range(4)):
                return True
    # Diagonal /
    for r in range(3, 6):
        for c in range(4):
            if all(board[r-i][c+i] == piece for i in range(4)):
                return True
    return False

def is_board_full(board):
    return all(board[0][c] != EMPTY for c in range(7))

def choose_bot_move(board):
    valid_cols = [c for c in range(7) if get_available_row(board, c) != -1]
    if not valid_cols:
        return None

    # 1. Winning move for Bot
    for c in valid_cols:
        r = get_available_row(board, c)
        board[r][c] = BOT
        if check_win(board, BOT):
            board[r][c] = EMPTY
            return c
        board[r][c] = EMPTY

    # 2. Block Player winning move
    for c in valid_cols:
        r = get_available_row(board, c)
        board[r][c] = PLAYER
        if check_win(board, PLAYER):
            board[r][c] = EMPTY
            return c
        board[r][c] = EMPTY

    # 3. Prefer center columns
    preference = [3, 2, 4, 1, 5, 0, 6]
    for c in preference:
        if c in valid_cols:
            return c

    return random.choice(valid_cols)

def generate_markdown(state):
    board = state["board"]
    status = state.get("status", "in_progress")

    lines = []
    lines.append("<details open>")
    lines.append("<summary><h3> 🔴 <b>Play Connect Four vs Ian's AI Bot!</b> <i>(Click a column to drop a chip)</i></h3></summary>")
    lines.append("<br/>\n")
    lines.append("<div align=\"center\">\n")

    # Clickable Drop Buttons
    if status == "in_progress":
        drop_buttons = []
        for c in range(7):
            if get_available_row(board, c) != -1:
                link = f"https://github.com/{REPO}/issues/new?title=connect4%7Cdrop%7C{c+1}&body=Click+%27Submit+new+issue%27+to+make+your+move!"
                drop_buttons.append(f"[ **Drop {c+1} 🔴** ]({link})")
            else:
                drop_buttons.append("**FULL**")

        lines.append("| " + " | ".join(drop_buttons) + " |")
        lines.append("|" + "|".join([":---:" for _ in range(7)]) + "|")
    
    # Board Visual
    lines.append("| 1 | 2 | 3 | 4 | 5 | 6 | 7 |")
    lines.append("|" + "|".join([":---:" for _ in range(7)]) + "|")
    for r in range(6):
        lines.append("| " + " | ".join(board[r]) + " |")

    lines.append("<br/>\n")

    # Game Status Messages
    new_game_link = f"https://github.com/{REPO}/issues/new?title=connect4%7Cnew&body=Click+%27Submit+new+issue%27+to+start+a+new+game!"
    if status == "player_won":
        winner = state.get("last_player", "Player")
        lines.append(f"<h3>🏆 <b>@{winner} WINS against the Bot!</b> 🎉</h3>")
        lines.append(f"<p><a href=\"{new_game_link}\">🔄 <strong>Click here to Start a New Game</strong></a></p>")
    elif status == "bot_won":
        lines.append("<h3>🤖 <b>Ian's Bot won this round!</b> ⚡</h3>")
        lines.append(f"<p><a href=\"{new_game_link}\">🔄 <strong>Click here to Rematch the Bot</strong></a></p>")
    elif status == "draw":
        lines.append("<h3>🤝 <b>It's a draw! The board is full!</b></h3>")
        lines.append(f"<p><a href=\"{new_game_link}\">🔄 <strong>Click here to Start a New Game</strong></a></p>")
    else:
        last_info = ""
        if state.get("last_player_col") is not None:
            last_p = state.get("last_player", "Player")
            last_info = f"Last move: @{last_p} dropped in <b>Col {state['last_player_col']}</b> | Bot dropped in <b>Col {state.get('last_bot_col', '?')}</b>"
        lines.append(f"<p><b>You:</b> 🔴 You (Visitor) &nbsp;|&nbsp; <b>Opponent:</b> 🟡 Ian's AI Bot</p>")
        if last_info:
            lines.append(f"<p><i>{last_info}</i></p>")
        lines.append(f"<p>Need a reset? <a href=\"{new_game_link}\">🔄 <strong>Start a New Game</strong></a></p>")

    lines.append("\n<p><sub>⚡ Interactive GitHub Action Game: Clicking a column opens an issue that automatically drops your chip & triggers a counter-move!</sub></p>")
    lines.append("\n</div>")
    lines.append("\n</details>")

    return "\n".join(lines)

def update_readme(content):
    if not os.path.exists(README_FILE):
        return
    with open(README_FILE, "r", encoding="utf-8") as f:
        readme = f.read()

    start_tag = "<!-- START GAME -->"
    end_tag = "<!-- END GAME -->"

    if start_tag in readme and end_tag in readme:
        parts = readme.split(start_tag)
        before = parts[0]
        after = parts[1].split(end_tag)[1]
        new_readme = f"{before}{start_tag}\n\n{content}\n\n{end_tag}{after}"
    else:
        new_readme = readme + f"\n\n{start_tag}\n\n{content}\n\n{end_tag}\n"

    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write(new_readme)

def main():
    state = load_state()

    if ISSUE_TITLE == "connect4|new":
        state["game_number"] = state.get("game_number", 1) + 1
        state["board"] = empty_board()
        state["status"] = "in_progress"
        state["last_player"] = USER_LOGIN
        state["last_player_col"] = None
        state["last_bot_col"] = None
        save_state(state)
        md = generate_markdown(state)
        update_readme(md)
        notify_and_close_issue(f"🎉 @{USER_LOGIN} has started a fresh game of Connect Four (Game #{state['game_number']})! Go drop a chip!")
        return

    if ISSUE_TITLE.startswith("connect4|drop|"):
        if state.get("status") != "in_progress":
            notify_and_close_issue("⚠️ This game has already finished. Please start a new game by clicking the reset link!")
            return

        parts = ISSUE_TITLE.split("|")
        if len(parts) >= 3 and parts[2].isdigit():
            col = int(parts[2]) - 1
            if 0 <= col <= 6:
                row = get_available_row(state["board"], col)
                if row == -1:
                    notify_and_close_issue(f"❌ Column {col + 1} is already full! Please pick another column.")
                    return

                # Player move
                state["board"][row][col] = PLAYER
                state["last_player"] = USER_LOGIN
                state["last_player_col"] = col + 1

                # Check player win
                if check_win(state["board"], PLAYER):
                    state["status"] = "player_won"
                    save_state(state)
                    md = generate_markdown(state)
                    update_readme(md)
                    notify_and_close_issue(f"🏆 BOOM! @{USER_LOGIN} connected four and won the game against the Bot!")
                    return

                # Check board full (draw)
                if is_board_full(state["board"]):
                    state["status"] = "draw"
                    save_state(state)
                    md = generate_markdown(state)
                    update_readme(md)
                    notify_and_close_issue("🤝 The board is full — it's a draw!")
                    return

                # Bot counter-move
                bot_col = choose_bot_move(state["board"])
                if bot_col is not None:
                    bot_row = get_available_row(state["board"], bot_col)
                    state["board"][bot_row][bot_col] = BOT
                    state["last_bot_col"] = bot_col + 1

                    if check_win(state["board"], BOT):
                        state["status"] = "bot_won"
                        save_state(state)
                        md = generate_markdown(state)
                        update_readme(md)
                        notify_and_close_issue(f"🔴 You dropped in Col {col + 1}, but 🤖 Ian's Bot dropped in Col {bot_col + 1} and connected four! Bot wins!")
                        return

                save_state(state)
                md = generate_markdown(state)
                update_readme(md)
                notify_and_close_issue(f"✅ @{USER_LOGIN} dropped 🔴 in Col {col + 1}! 🤖 Bot responded with 🟡 in Col {bot_col + 1}. Your turn!")
                return

    # Default run
    md = generate_markdown(state)
    update_readme(md)
    print("Initial Connect 4 board generated.")

if __name__ == "__main__":
    main()
