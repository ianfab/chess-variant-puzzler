import argparse
import os
import random
import sys

from tqdm import tqdm
import pyffish as sf

import uci


def generate_fens(engine, variant, min_depth, max_depth, add_move, required_pieces):
    if variant not in sf.variants():
        raise Exception("Unsupported variant: {}".format(variant))

    start_fen = sf.start_fen(variant)

    engine.setoption('UCI_Variant', variant)

    fens = set()
    while True:
        engine.newgame()
        move_stack = []
        while (sf.legal_moves(variant, start_fen, move_stack)
               and not sf.is_optional_game_end(variant, start_fen, move_stack)[0]):
            engine.position(start_fen, move_stack)
            bestmove, _ = engine.go(depth=random.randint(min_depth, max_depth))
            move_stack.append(bestmove)
            if not add_move:
                fen = sf.get_fen(variant, start_fen, move_stack)
                bestmove = None
            else:
                fen = sf.get_fen(variant, start_fen, move_stack[:-1])
            if (fen, bestmove) not in fens and (not required_pieces or any(p in fen.split(' ')[0].lower() for p in required_pieces.lower())):
                fens.add((fen, bestmove))
                yield fen, bestmove


def write_fens(stream, engine, variant, count, min_depth, max_depth, add_move, required_pieces):
    generator = generate_fens(engine, variant, min_depth, max_depth, add_move, required_pieces)
    for _ in tqdm(range(count)):
        fen, move = next(generator)
        stream.write('{};variant {}'.format(fen, variant) + (';sm {}'.format(move) if move else '') + os.linesep)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--engine', required=True, help='chess variant engine path, e.g., to Fairy-Stockfish')
    parser.add_argument('-o', '--ucioptions', type=lambda kv: kv.split("="), action='append', default=[],
                        help='UCI option as key=value pair. Repeat to add more options.')
    parser.add_argument('-v', '--variant', default='chess', help='variant to generate positions for')
    parser.add_argument('-c', '--count', type=int, default=1000, help='number of positions')
    parser.add_argument('-s', '--skill-level', type=int, default=10, help='engine skill level setting [-20,20]')
    parser.add_argument('-d', '--max-depth', type=int, default=6, help='maximum search depth')
    parser.add_argument('-m', '--min-depth', type=int, default=1, help='minimum search depth')
    parser.add_argument('-a', '--add-move', action='store_true', help='add initial move for opposing side')
    parser.add_argument('-p', '--pieces', default=None, help='only return positions containing one of these piece chars (case insensitive)')
    args = parser.parse_args()

    ucioptions = dict(args.ucioptions)
    ucioptions.update({'Skill Level': args.skill_level})

    engine = uci.Engine([args.engine], ucioptions)
    sf.set_option("VariantPath", engine.options.get("VariantPath", ""))
    write_fens(sys.stdout, engine, args.variant, args.count, args.min_depth, args.max_depth, args.add_move, args.pieces)
