""" Generates EPD positions from PGN games file saved from lichess.org """

import argparse
import functools
import os
import sys

from tqdm import tqdm
import chess.pgn
from chess.variant import find_variant


def game_count(filename):
    f = open(filename, "rb")
    bufgen = iter(functools.partial(f.raw.read, 1024 * 1024), b"")
    return sum(buf.count(b"[Event") for buf in bufgen)


class PrintAllFensVisitor(chess.pgn.BaseVisitor):
    def __init__(self, variant=None, mate=False):
        super(PrintAllFensVisitor, self).__init__()
        self.variant = variant
        self.mate = mate

    def begin_game(self):
        self.uci_variant = ""
        self.fens = []
        self.relevant = True
        self.site = ""
        self.board_eval = ""

    def visit_header(self, name, value):
        if name == "Variant":
            self.uci_variant = find_variant(value.removesuffix("960")).uci_variant
            if self.variant is not None and self.uci_variant != self.variant:
                self.relevant = False

        if name == "Site":
            self.site = value

    def end_headers(self):
        if not self.relevant:
            # Optimization hint: Do not even bother parsing the moves.
            return chess.pgn.SKIP

    def visit_comment(self, comment):
        if comment.startswith("[%eval"):
            self.board_eval = comment
        else:
            self.board_eval = None
            self.relevant = False

    def visit_move(self, board, move):
        if self.relevant and self.mate:
            ev = self.board_eval
            if ev is None:
                self.relevant = False
            else:
                if ev.startswith("[%eval #"):
                    self.fens.append(
                        "{};variant {};site {}".format(board.fen(), self.uci_variant, self.site)
                    )

    def visit_board(self, board):
        if self.relevant and not self.mate:
            # python-chess can't recognize 960 in non Chess960 games
            # but using it for non 960 games as well doesn't hurt
            board.chess960 = True
            self.fens.append(
                "{};variant {};site {}".format(board.fen(), self.uci_variant, self.site)
            )

    def begin_variation(self):
        return chess.pgn.SKIP

    def result(self):
        return self.fens


def write_fens(pgn_file, stream, variant, count, mate):
    visitor = functools.partial(PrintAllFensVisitor, variant=variant, mate=mate)
    with open(pgn_file) as pgn:
        with tqdm(total=game_count(pgn_file)) as pbar:
            cnt = 0
            while True:
                fens = chess.pgn.read_game(pgn, Visitor=visitor)
                pbar.update(1)
                if fens is None:
                    break
                elif len(fens) == 0 and not mate:
                    continue
                else:
                    cnt += 1

                for fen in fens:
                    stream.write(fen + os.linesep)

                if cnt > count:
                    break


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input-file", help="pgn file containing lichess games")
    parser.add_argument("-v", "--variant", help="variant to generate positions for")
    parser.add_argument("-c", "--count", type=int, default=1000, help="number of games")
    parser.add_argument("-m", "--mate", action="store_true", help="only mate positions")

    args = parser.parse_args()
    write_fens(args.input_file, sys.stdout, args.variant, args.count, args.mate)
