import argparse
import os
import random
import sys

import pyffish as sf

import uci


def move(info_line):
    return info_line['pv'][0] if 'pv' in info_line else None

def is_mate(info_line, distance=0):
    return info_line['score'][0] == 'mate' and int(info_line['score'][1]) > distance


def has_cp(info_line, score=0):
    return info_line['score'][0] == 'cp' and int(info_line['score'][1]) > score


def get_puzzle(variant, fen, moves, engine, depth):
    if len(sf.legal_moves(variant, fen, moves)) <= 2:
        return None, None

    engine.newgame()
    engine.position(fen, moves)
    _, info = engine.go(depth=depth)

    last_depth = info[-1]
    candidate = last_depth[0]
    first_alt = last_depth[1]

    # mate
    if is_mate(candidate):
        if not is_mate(first_alt) and not has_cp(first_alt, 300):
            return 'mate', info

    # big tactics
    if has_cp(candidate, 500):
        if not has_cp(first_alt, 100):
            return 'winning', info

    # big defensive tactics
    if has_cp(candidate, -100):
        if not has_cp(first_alt, -500):
            return 'defensive', info

    return None, None


def score_puzzle(info):
    bestmove = move(info[-1][0])
    min_depth = None
    stable_depth = None
    for d, multiinf in enumerate(info):
        if move(multiinf[0]) != bestmove:
            stable_depth = d + 1
        elif not min_depth:
            min_depth = d
            stable_depth = d

    return (min_depth + stable_depth) / 2


def generate_puzzles(instream, outstream, engine, variant, multipv, depth, min_score, evalfile):
    engine.setoption('UCI_Variant', variant)
    engine.setoption('multipv', multipv)
    engine.setoption('EvalFile', evalfile)
    for fen in instream:
        fen = fen.strip().split(';')[0]  # also support EPD
        pv = []
        scores = []
        types = []
        while True:
            puzzle_type, info = get_puzzle(variant, fen, pv, engine, depth, evalfile)
            if not puzzle_type:
                # trim last opponent move
                if pv:
                    pv.pop()
                break
            scores.append(score_puzzle(info))
            types.append(puzzle_type)
            pv += info[-1][0]['pv'][:2]
            if len(pv) % 2:
                break

        total_score = sum(scores)
        if pv and (total_score >= min_score or 'mate' in types):
            outstream.write('{};bm {};difficulty {};type {};pv {}\n'.format(fen, pv[0], total_score, types[0], ','.join(pv)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file')
    parser.add_argument('-e', '--engine', required=True)
    parser.add_argument('-v', '--variant', default='chess')
    parser.add_argument('-m', '--multipv', type=int, default=3)
    parser.add_argument('-d', '--depth', type=int, default=10)
    parser.add_argument('-s', '--min-score', type=int, default=2)
    parser.add_argument('-ev', '--evalfile', type=string, default='')
    args = parser.parse_args()

    engine = uci.Engine([args.engine])
    with open(args.input_file) as fens:
        generate_puzzles(fens, sys.stdout, engine, args.variant, args.multipv, args.depth, args.min_score, args.evalfile)
