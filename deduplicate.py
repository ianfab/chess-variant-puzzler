import argparse
from collections import defaultdict
from functools import partial
import fileinput
import re
import sys

import pyffish
from tqdm import tqdm


def line_count(filename):
    f = open(filename, 'rb')
    bufgen = iter(partial(f.raw.read, 1024*1024), b'')
    return sum(buf.count(b'\n') for buf in bufgen)


def get_sort_key(sort_criteria, epd):
    annotations = dict(token.split(' ', 1) for token in epd.strip().split(';')[1:])
    key = []
    if sort_criteria:
        for crit, direction in sort_criteria:
            val = annotations.get(crit, '')
            try:
                v = float(val)
            except Exception:
                v = val
            if direction in ('d', 'desc'):
                if isinstance(v, (int, float)):
                    v = -v
                else:
                    v = ''.join(chr(255 - ord(c)) for c in str(v))
            key.append(v)
    return tuple(key)


LAN_REGEX = re.compile(r'([A-Z])?([a-l][0-9]+)[-x]([a-l][0-9]+)')

def parse_lan_move(move):
    """
    Parses a LAN move string and returns the piece type, from square, and to square.
    Example: "Rh6-h8+" -> ('R', 'h6', 'h8')
    """
    match = LAN_REGEX.match(move)
    if match:
        piece = match.group(1) if match.group(1) else 'P'  # Default to Pawn if no piece specified
        from_sq = match.group(2)
        to_sq = match.group(3)
        return piece, from_sq, to_sq
    else:
        raise ValueError(f"Invalid LAN move format: {move}")


def fen_to_square_map(fen):
    """
    Converts a FEN string to a mapping of square (e.g., 'e4') to piece (e.g., 'K', 'p', etc.).
    Only the board part of the FEN is used.
    """
    board_part = fen.split()[0]
    square_map = {}
    rows = board_part.split('/')
    ranks = len(rows)
    for r, row in enumerate(rows):
        file_idx = 0
        for char in row:
            if char.isdigit():
                file_idx += int(char)
            elif char.isalpha():
                square = chr(ord('a') + file_idx) + str(ranks - r)
                square_map[square] = char
                file_idx += 1
    return square_map


def deduplicate(instream, outstream, king, sort_criteria=None):
    # Before the first line has been read, filename() returns None.
    if instream.filename() is None:
        filenames = instream._files
    else:
        filenames = [instream.filename()]
    # When reading from sys.stdin, filename() is "-"
    total = None if filenames[0] == "-" else sum(line_count(filename) for filename in filenames)

    patterns = defaultdict(list)

    for epd in tqdm(instream, total=total):
        fen = epd.split(';')[0]
        annotations = dict(token.split(' ', 1) for token in epd.strip().split(';')[1:])
        variant = annotations.get('variant')
        moves = [m for m in annotations.get('pv', '').split(",") if m]
        final_fen = pyffish.get_fen(variant, fen, moves)
        pieces = fen_to_square_map(final_fen)

        # find king
        side_to_move = final_fen.split()[1]
        king_piece = king.upper() if side_to_move == 'w' else king.lower()
        king_squares = "".join([k for k, v in pieces.items() if v == king_piece])

        # Convert PV to LAN
        lans = pyffish.get_san_moves(variant, fen, moves, False, pyffish.NOTATION_LAN)
        piece, _, to_sq = parse_lan_move(lans[-1])

        # Determine mating pattern
        pattern = f"{piece}-{to_sq}-{king_piece}-{king_squares}"
        patterns[pattern].append(epd)

    for pattern, epd_list in sorted(patterns.items(), key=lambda x: len(x[1]), reverse=True):
        if len(epd_list) > 1:
            sys.stderr.write(f"{pattern}: {len(epd_list)} -> 1\n")
        if sort_criteria:
            epd_list.sort(key=lambda x: get_sort_key(sort_criteria, x))
        outstream.write(epd_list[0])


if __name__ == '__main__':
    parser = argparse.ArgumentParser('Deduplicate EPD files based on mating patterns. Input needs to be sorted by priority.')
    parser.add_argument('epd_files', nargs='*')
    parser.add_argument('-k', '--king', default='k', help='King piece character (default: k)')
    parser.add_argument('-s', '--sort', type=lambda kv: kv.split("="), action='append', default=[],
                        help='Sorting criteria as key=value pair. value=asc/desc/a/d.')
    args = parser.parse_args()

    with fileinput.input(args.epd_files) as instream:
        deduplicate(instream, sys.stdout, args.king, args.sort)
