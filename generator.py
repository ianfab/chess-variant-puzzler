import argparse
import os
import random
import sys

import pyffish as sf

import uci


def generate_fens(engine, variant, skill_level, evalfile):
    if not variant in sf.variants():
        raise Exception("Unsupported variant: {}".format(variant))

    fen = sf.start_fen(variant)

    engine.setoption('Skill Level', skill_level)
    engine.setoption('UCI_Variant', variant)
    engine.setoption('EvalFile', evalfile)
    while True:
        engine.newgame()
        move_stack = []
        while sf.legal_moves(variant, fen, move_stack) and not sf.is_optional_game_end(variant, fen, move_stack)[0]:
            engine.position(fen, move_stack)
            bestmove, _ = engine.go(depth=random.randint(1, 6))
            move_stack.append(bestmove)
            yield sf.get_fen(variant, fen, move_stack)


def write_fens(stream, engine, variant, count, skill_level, evalfile):
    generator = generate_fens(engine, variant, skill_level, evalfile)
    for _ in range(count):
        stream.write(next(generator) + os.linesep)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('engine')
    parser.add_argument('-v', '--variant', default='chess')
    parser.add_argument('-c', '--count', type=int, default=10)
    parser.add_argument('-s', '--skill-level', type=int, default=15)
    parser.add_argument('-ev', '--evalfile', default='')
    parser.add_argument('-o', '--ucioptions', type=lambda kv: kv.split("="), action='append', default=[])
    args = parser.parse_args()

    engine = uci.Engine([args.engine], dict(args.ucioptions))
    sf.set_option("VariantPath", engine.options.get("VariantPath", ""))
    write_fens(sys.stdout, engine, args.variant, args.count, args.skill_level, args.evalfile)
