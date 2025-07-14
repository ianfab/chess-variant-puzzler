import argparse
import fileinput
from functools import partial
import sys

from tqdm import tqdm
import pyffish


def line_count(filename):
    f = open(filename, 'rb')
    bufgen = iter(partial(f.raw.read, 1024*1024), b'')
    return sum(buf.count(b'\n') for buf in bufgen)


def get_fen(variant, fen, moves):
    return pyffish.get_fen(variant, fen, moves)


def net_material(piece_values, fen):
    default_value = 0 if piece_values else 1
    player_to_move = fen.split()[1]
    board = fen.split()[0]
    white_total = 0
    black_total = 0
    for c in board:
        if c.isupper():
            white_total += piece_values.get(c.lower(), default_value)
        elif c.islower():
            black_total += piece_values.get(c.lower(), default_value)
    if player_to_move == 'w':
        return white_total - black_total
    else:
        return black_total - white_total


def final_net_material(piece_values, fen, annotations):
    fen = get_fen(annotations['variant'], fen, annotations['pv'].split(',')) if 'pv' in annotations else fen
    return net_material(piece_values, fen)


def filter(annotations, min, max, values):
    for k, v in min.items():
        if k == 'pv':
            if len(annotations.get(k, '').split(',')) < int(v):
                return True
        elif float(annotations.get(k, 0)) < float(v):
            return True
    for k, v in max.items():
        if float(annotations.get(k, 0)) > float(v):
            return True
    for k, v in values.items():
        if annotations.get(k, 0) not in v.split(','):
            return True
    return False


def filter_puzzles(instream, outstream, min, max, values, inferred_annotations):
    # Before the first line has been read, filename() returns None.
    if instream.filename() is None:
        filenames = instream._files
    else:
        filenames = [instream.filename()]
    # When reading from sys.stdin, filename() is "-"
    total = None if filenames[0] == "-" else sum(line_count(filename) for filename in filenames)

    for epd in tqdm(instream, total=total):
        fen = epd.split(';')[0]
        annotations = dict(token.split(' ', 1) for token in epd.strip().split(';')[1:])
        for k, v in inferred_annotations.items():
            annotations[k] = v(fen, annotations)
        if not filter(annotations, min, max, values):
            outstream.write(epd)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('epd_files', nargs='*')
    parser.add_argument('-n', '--min', type=lambda kv: kv.split("="), action='append', default=[],
                        help='Minimums as key=value pair. Repeat to add more options.')
    parser.add_argument('-x', '--max', type=lambda kv: kv.split("="), action='append', default=[],
                        help='Maximums as key=value pair. Repeat to add more options.')
    parser.add_argument('-v', '--values', type=lambda kv: kv.split("="), action='append', default=[],
                        help='Set as comma separated list in key=value1,value2 pair. Repeat to add more options.')
    parser.add_argument('-p', '--piece-values', nargs='+', action='append', default=[],
                        help='Piece values mapping, e.g. P=1 N=3 B=3 R=5 Q=9')
    args = parser.parse_args()
    try:
        piece_values_dict = {k.lower(): int(v) for k, v in (item.split('=') for sublist in args.piece_values for item in sublist)}
    except Exception as e:
        parser.error(f"Error parsing --piece-values: {e}")

    inferred_annotations = {
        'material': lambda fen, annotations: net_material(piece_values_dict, fen),
        'finalmaterial': lambda fen, annotations: -final_net_material(piece_values_dict, fen, annotations),
        'materialdiff': lambda fen, annotations: -final_net_material(piece_values_dict, fen, annotations) - net_material(piece_values_dict, fen),
    }

    with fileinput.input(args.epd_files) as instream:
        filter_puzzles(instream, sys.stdout, dict(args.min), dict(args.max), dict(args.values), inferred_annotations)
