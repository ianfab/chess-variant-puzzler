import argparse
from collections import defaultdict
from functools import partial
import fileinput
from math import log
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


def deduplicate(instream, outstream, king, sort_criteria=None, board_similarity_threshold=0.8, move_similarity_threshold=0.8, overall_similarity_threshold=0.5, verbosity=0):
    epds = [epd for epd in instream]
    if sort_criteria:
        epds.sort(key=lambda x: get_sort_key(sort_criteria, x))

    patterns = defaultdict(list)
    unique = list()
    for epd in tqdm(epds, total=len(epds)):
        fen = epd.split(';')[0]
        annotations = dict(token.split(' ', 1) for token in epd.strip().split(';')[1:])
        variant = annotations.get('variant')
        moves = [m for m in annotations.get('pv', '').split(",") if m]
        final_fen = pyffish.get_fen(variant, fen, moves)
        pieces = fen_to_square_map(final_fen)
        board = frozenset(pieces.items())

        # find king
        side_to_move = final_fen.split()[1]
        king_piece = king.upper() if side_to_move == 'w' else king.lower()
        king_squares = "".join([k for k, v in pieces.items() if v == king_piece])

        # Convert PV to LAN
        lans = pyffish.get_san_moves(variant, fen, moves, False, pyffish.NOTATION_LAN)
        piece, _, to_sq = parse_lan_move(lans[-1])
        sans = tuple(pyffish.get_san_moves(variant, fen, moves, False, pyffish.NOTATION_SAN))

        # Determine mating pattern
        pattern = f"{piece}-{to_sq}-{king_piece}-{king_squares}"

        # similarity check
        for puzzle2 in unique:
            matching_pairs = sum(1 for item in board if item in puzzle2['board'])
            board_similarity = 2 * matching_pairs / (len(board) + len(puzzle2['board']))

            # Compare SANs from the back
            min_len = min(len(sans), len(puzzle2['sans']))
            matching_sans = 0
            for i in range(1, min_len + 1):
                if sans[-i] == puzzle2['sans'][-i]:
                    matching_sans += 1
            move_similarity = matching_sans / min_len

            overall_similarity = board_similarity * move_similarity

            if (board_similarity > board_similarity_threshold or
               move_similarity > move_similarity_threshold or
               overall_similarity > overall_similarity_threshold):
                if verbosity > 1:
                    sys.stderr.write(f"Pattern: {pattern}, Board similarity: {board_similarity:.2f}, Move similarity: {move_similarity:.2f}, Overall similarity: {overall_similarity:.2f}\n{epd}{puzzle2['epd']}\n")
                break
        else:
            if pattern not in patterns:
                # If this is the first occurrence of the pattern, write it
                outstream.write(epd)
                unique.append({'board': board, 'sans': sans, 'epd': epd})
            patterns[pattern].append(epd)

    if verbosity:
        for pattern, epd_list in sorted(patterns.items(), key=lambda x: len(x[1]), reverse=True):
            if len(epd_list) > 1:
                sys.stderr.write(f"{pattern}: {len(epd_list)} -> 1\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser('Deduplicate EPD files based on mating patterns. Input needs to be sorted by priority.')
    parser.add_argument('epd_files', nargs='*')
    parser.add_argument('-k', '--king', default='k', help='King piece character (default: k)')
    parser.add_argument('-s', '--sort', type=lambda kv: kv.split("="), action='append', default=[],
                        help='Sorting criteria as key=value pair. value=asc/desc/a/d.')
    parser.add_argument('-b', '--board-similarity', type=float, default=0.8, help='Similarity threshold for board deduplication (default: 0.8)')
    parser.add_argument('-m', '--move-similarity', type=float, default=0.8, help='Similarity threshold for SAN deduplication (default: 0.8)')
    parser.add_argument('-o', '--overall-similarity', type=float, default=0.5, help='Similarity threshold for the product of board and move similarity (default: 0.5)')
    parser.add_argument('-v', '--verbosity', type=int, default=0, help='Enable verbose output for similarity checks')
    args = parser.parse_args()

    with fileinput.input(args.epd_files) as instream:
        deduplicate(
            instream, sys.stdout, args.king, args.sort,
            board_similarity_threshold=args.board_similarity,
            move_similarity_threshold=args.move_similarity,
            overall_similarity_threshold=args.overall_similarity,
            verbosity=args.verbosity
        )
