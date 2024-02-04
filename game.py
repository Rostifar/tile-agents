from __future__ import annotations

import ast
from dataclasses import dataclass
from itertools import cycle
from typing import List, Optional, Tuple, Dict
from openai import OpenAI


GAME_CONTEXT = """
You are playing a two player game where the objective is to form the largest connected component 
on an 5x5 grid. The game is turn based and you will be prompted when it's your turn. You will be 
provided the current state of the game board when prompted. 
* Empty cells will be represented by whitespace
* Cells you own will contain an "o" character
* Cells owned by your opponent will contain a `*` character
* The cells you own will contain a `o` character.
* Two cells are connected to each other if there is a path of cells of the same symbol connecting 
  the two cells. Cells diagonal to each other are not connected. 
* The game ends when all cells are taken
"""

PLAY_CONTEXT= """
It's your turn. The curren open positions are: \n {}.
Please enter a position formatted as `row,col` where row and column indexing starts at zero.\n
Here's an example: 0,3 is the cell located at row 0 and column 3.\n
Please enter your move BUT ONLY INPUT A TUPLE, NO EXTRA FORMATTING: 
"""

client = OpenAI()

@dataclass
class Player:
    name: str
    symbol: str
    
    def propose_move(self, **kwargs) -> Tuple[int, int]:
        move = input("Enter row-column move: ")
        row_str, col_str = move.split(",")
        return int(row_str), int(col_str)

class OpenAIPlayer(Player):
    def propose_move(self, board: Board, feedback: Optional[str] = None) -> Tuple[int, int]:
        messages = [
            {"role": "system", "content": GAME_CONTEXT},
            {"role": "system", "content": PLAY_CONTEXT.format(str(board))}
        ]
        if feedback:
            messages += {
                "role": "system", "content": f"Previous move failed due to {feedback}."
            }

        completion = client.chat.completions.create(
            model="gpt-4",
            messages=messages
        )
        return ast.literal_eval(completion.choices[0].message.content)
        
    

@dataclass
class Cell:
    owned_by: Optional[Player] = None


class Board:
    def __init__(self, rows: int, cols: int) -> None:
        self.rows = rows 
        self.cols = cols 
        assert self.rows > 0 and self.cols > 0, f"Invalid grid dimensions ({rows}, {cols})"

        self.n_cells = self.rows * self.cols
        self.cells = [Cell() for _ in range(self.n_cells)]
    
    def get_cell(self, row: int, col: int) -> Cell:
        return self.cells[row * self.cols + col]
    
    def get_neighbors(self, row: int, col: int) -> List[Tuple[int, int]]:
        neighbors = []
        for delta_row in {-1, 1}:
            for delta_col in {-1, 1}:
                new_row = row + delta_row
                new_col = col + delta_col
                if 0 <= new_row < self.rows and 0 <= new_col < self.cols:
                    neighbors.append((new_row, new_col))
        return neighbors

    def get_all(self) -> List[Cell]:
        return self.cells

    def modify(self, row: int, col: int, player: str) -> None:
        assert row >= 0 and col >= 0 and row < self.rows and col < self.cols, \
            f"Invalid position ({row}, {col}) for board with dimensions ({self.rows}, {self.cols})"

        cell = self.get_cell(row, col)

        assert cell.owned_by is None, f"Cell is already owned by player {cell.owned_by.name}."
        cell.owned_by = player

    def is_board_full(self) -> bool:
        return not any(cell.owned_by is None for cell in self.cells)
    
    def __repr__(self) -> str:
        s = ("+-" * self.cols) + "+\n"
        for i, cell in enumerate(self.cells):
            s += "|"
            if cell.owned_by is not None:
                s += cell.owned_by.symbol
            else:
                s += " "
            if (i + 1) % self.cols == 0:
                s += "|\n"
        s += ("+-" * self.cols) + "+"
        return s 


class Game:
    def __init__(self, players: List[Player]) -> None:
        self.players = players
        self.board = Board(rows=5, cols=5)

    
    def take_turn(self, player: Player) -> None:
        print(self.board)

        openai_tries = 0
        error_messages = ''
        while True:
            try:
                row, col = player.propose_move(board=self.board, feedback=error_messages)
                self.board.modify(row, col, player)
                break
            except Exception as e:
                error_messages += "\n" + str(e)
                if isinstance(player, OpenAIPlayer):
                    openai_tries += 1
                    if openai_tries > 3:
                        print("Exiting game due to too many agent retries.")
                        exit(1)
    
    def compute_scores(self) -> int:
        # lol
        scores: Dict[Player, int] = {player: 0 for player in self.players}
        indices = set(
            [(row, col) for row in range(self.board.rows) for col in range(self.board.cols)]
        )
        while len(indices) > 0:
            row, col = indices.pop()
            player = self.board.get_cell(row, col).owned_by
            stack = [(row, col)]
            while len(stack) > 0:
                row, col = stack.pop()
                neighbor = self.board.get_cell(row, col)
                if neighbor.owned_by != player:
                    continue
                scores[player] += 1
                stack += [cell for cell in self.board.get_neighbors(row, col) if cell in indices]
                indices.remove((row, col))
                

    def play(self) -> None:
        print("Starting game.\n")

        player_cycle = cycle(self.players)
        while not self.board.is_board_full():
            player = next(player_cycle)
            print(f"\nPlayer {player.name}'s turn.")
            self.take_turn(player)
        
        print("Game ended.")
        print(f"Final scores: {self.compute_scores()}")

game = Game(players=[Player("human", "*"), OpenAIPlayer("agent", "o")])
game.play()
