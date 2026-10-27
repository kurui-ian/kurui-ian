import os
import sys
import json
import urllib.request
import chess

REPO = os.environ.get("REPOSITORY", "kurui-ian/kurui-ian")
ISSUE_TITLE = os.environ.get("EVENT_ISSUE_TITLE", "").strip()
ISSUE_NUMBER = os.environ.get("EVENT_ISSUE_NUMBER", "").strip()
USER_LOGIN = os.environ.get("EVENT_USER_LOGIN", "").strip()
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

STATE_FILE = "chess_games/game.json"
README_FILE = "README.md"

PIECE_ICONS = {
    'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',
    'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚',
}

def post_github(url, data=None, method="POST"):
    if not TOKEN:
        print("No GITHUB_TOKEN present, skipping API call.")
        return
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "GitHub-Action-Chess"
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

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "fen": chess.STARTING_FEN,
        "moves": [],
        "game_number": 1,
        "status": "in_progress"
    }

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def generate_markdown(board, state):
    turn_color = "White (⚪)" if board.turn == chess.WHITE else "Black (⚫)"
    
    # Board ASCII / Unicode Table
    lines = []
    lines.append("### ♟️ Live Community Chess Game")
    lines.append(f"**Turn:** {turn_color} | **Game:** #{state['game_number']}")
    lines.append("")
    
    # Markdown Table of the Board
    lines.append("| | A | B | C | D | E | F | G | H | |")
    lines.append("|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    for rank in range(7, -1, -1):
        row = [f"**{rank + 1}**"]
        for file in range(8):
            sq = chess.square(file, rank)
            piece = board.piece_at(sq)
            if piece:
                icon = PIECE_ICONS.get(piece.symbol(), piece.symbol())
                row.append(f"<b>{icon}</b>")
            else:
                row.append("·")
        row.append(f"**{rank + 1}**")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("| | **A** | **B** | **C** | **D** | **E** | **F** | **G** | **H** | |")
    lines.append("")

    # Check status
    if board.is_checkmate():
        winner = "Black" if board.turn == chess.WHITE else "White"
        lines.append(f"🏆 **Checkmate! {winner} wins!**")
        new_game_link = f"https://github.com/{REPO}/issues/new?title=chess%7Cnew&body=Click+%22Submit+new+issue%22+to+start+a+new+game!"
        lines.append(f"👉 [**Start a New Game**]({new_game_link})")
    elif board.is_stalemate() or board.is_insufficient_material():
        lines.append("🤝 **Game drawn!**")
        new_game_link = f"https://github.com/{REPO}/issues/new?title=chess%7Cnew&body=Click+%22Submit+new+issue%22+to+start+a+new+game!"
        lines.append(f"👉 [**Start a New Game**]({new_game_link})")
    else:
        if board.is_check():
            lines.append("⚠️ **CHECK!**")
            
        # Legal Moves Table
        lines.append("#### 🎯 Choose a move:")
        moves_by_origin = {}
        for m in board.legal_moves:
            from_sq = chess.square_name(m.from_square).upper()
            to_sq = chess.square_name(m.to_square).upper()
            uci = m.uci()
            piece = board.piece_at(m.from_square)
            piece_sym = PIECE_ICONS.get(piece.symbol(), "") if piece else ""
            key = f"{piece_sym} **{from_sq}**"
            
            link = f"[{to_sq}](https://github.com/{REPO}/issues/new?title=chess%7Cmove%7C{uci}&body=Click+%22Submit+new+issue%22+to+play+this+move!)"
            moves_by_origin.setdefault(key, []).append(link)
            
        lines.append("| Piece | Destinations |")
        lines.append("| :--- | :--- |")
        for key, dests in sorted(moves_by_origin.items()):
            lines.append(f"| {key} | {', '.join(dests)} |")
        
        lines.append("")
        new_game_link = f"https://github.com/{REPO}/issues/new?title=chess%7Cnew&body=Click+%22Submit+new+issue%22+to+start+a+new+game!"
        lines.append(f"🔄 Need a reset? [**Start New Game**]({new_game_link})")

    lines.append("")
    # Last 5 moves
    recent = state.get("moves", [])[-5:]
    if recent:
        lines.append("<details><summary><b>📜 Recent Moves</b></summary>")
        lines.append("")
        lines.append("| Move | Player |")
        lines.append("| :---: | :---: |")
        for m in reversed(recent):
            lines.append(f"| `{m['uci']}` | @{m['by']} |")
        lines.append("</details>")
        lines.append("")

    return "\n".join(lines)

def update_readme(content):
    if not os.path.exists(README_FILE):
        return
    with open(README_FILE, "r", encoding="utf-8") as f:
        readme = f.read()

    start_tag = "<!-- START CHESS -->"
    end_tag = "<!-- END CHESS -->"

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
    board = chess.Board(state.get("fen", chess.STARTING_FEN))

    if ISSUE_TITLE == "chess|new":
        state["game_number"] = state.get("game_number", 1) + 1
        state["moves"] = []
        state["fen"] = chess.STARTING_FEN
        board = chess.Board(chess.STARTING_FEN)
        save_state(state)
        md = generate_markdown(board, state)
        update_readme(md)
        notify_and_close_issue(f"🎉 @{USER_LOGIN} has started a fresh game of Chess (Game #{state['game_number']})!")
        return

    if ISSUE_TITLE.startswith("chess|move|"):
        parts = ISSUE_TITLE.split("|")
        if len(parts) >= 3:
            uci_str = parts[2].lower().strip()
            try:
                move = chess.Move.from_uci(uci_str)
                if move in board.legal_moves:
                    board.push(move)
                    state["moves"].append({"uci": uci_str, "by": USER_LOGIN})
                    state["fen"] = board.fen()
                    save_state(state)
                    md = generate_markdown(board, state)
                    update_readme(md)
                    
                    status_msg = f"✅ Move `{uci_str}` was played by @{USER_LOGIN}!"
                    if board.is_checkmate():
                        status_msg += " 🏆 **Checkmate! Game Over!**"
                    elif board.is_check():
                        status_msg += " ⚠️ **Check!**"
                    notify_and_close_issue(status_msg)
                    return
                else:
                    notify_and_close_issue(f"❌ Move `{uci_str}` is not a legal move on the current board.")
                    return
            except Exception as e:
                notify_and_close_issue(f"⚠️ Could not parse move: {e}")
                return

    # Default run (initialize board in README if needed)
    md = generate_markdown(board, state)
    update_readme(md)
    print("Initial chess markdown generated.")

if __name__ == "__main__":
    main()
