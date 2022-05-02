import argparse
import sys

import pyffish as sf

import uci


def move(info_line):
    return info_line['pv'][0] if 'pv' in info_line else None


def format_eval(info_line):
    return '#' if info_line['score'][0] == 'mate' else '' + info_line['score'][1]


def is_mate(info_line, distance=0):
    return info_line['score'][0] == 'mate' and int(info_line['score'][1]) > distance


def has_cp(info_line, score=0):
    return info_line['score'][0] == 'cp' and int(info_line['score'][1]) > score


def get_puzzle(variant, fen, moves, engine, depth, win_threshold, unclear_threshold):
    if len(sf.legal_moves(variant, fen, moves)) <= 2:
        return None, None

    engine.setoption('UCI_Variant', variant)
    engine.newgame()
    engine.position(fen, moves)
    _, info = engine.go(depth=depth)

    last_depth = info[-1]
    candidate = last_depth[0]
    first_alt = last_depth[1]

    # mate
    if is_mate(candidate):
        if not is_mate(first_alt) and not has_cp(first_alt, win_threshold):
            return 'mate', info

    # big tactics
    if has_cp(candidate, win_threshold):
        if not has_cp(first_alt, unclear_threshold):
            return 'winning', info

    # big defensive tactics
    if has_cp(candidate, -unclear_threshold):
        if not has_cp(first_alt, -win_threshold):
            return 'defensive', info

    return None, None


def rate_puzzle(info):
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


def generate_puzzles(instream, outstream, engine, variant, req_types, multipv, depth, min_difficulty, max_difficulty, win_threshold, unclear_threshold):
    engine.setoption('multipv', multipv)
    for epd in instream:
        tokens = epd.strip().split(';')
        fen = tokens[0]
        annotations = dict(token.split(' ', 1) for token in tokens[1:])
        current_variant = annotations.get('variant', variant)
        if not current_variant:
            raise Exception('Variant neither provided in EPD nor as argument')
        pv = []
        if 'sm' in annotations and annotations['sm'] in sf.legal_moves(current_variant, fen, []):
            pv.append(annotations['sm'])
        stm_index = len(pv)
        evals = []
        difficulties = []
        types = []
        while True:
            puzzle_type, info = get_puzzle(current_variant, fen, pv, engine, depth, win_threshold, unclear_threshold)
            if not puzzle_type:
                # trim last opponent move
                if pv:
                    pv.pop()
                break
            evals.append(format_eval(info[-1][0]))
            difficulties.append(rate_puzzle(info))
            types.append(puzzle_type)
            pv += info[-1][0]['pv'][:2]
            if len(info[-1][0]['pv']) < 2:
                break

        total_difficulty = sum(difficulties)
        if pv and (not req_types or types[0] in req_types) and (max_difficulty >= total_difficulty >= min_difficulty):
            sm = 'sm {};'.format(pv[0]) if stm_index == 1 else ''
            outstream.write('{};variant {};{}bm {};eval {};difficulty {};type {};pv {}\n'.format(fen, current_variant, sm, pv[stm_index], evals[0], total_difficulty, types[0], ','.join(pv)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file')
    parser.add_argument('-e', '--engine', required=True)
    parser.add_argument('-v', '--variant', help='only required if not annotated in input FEN/EPD')
    parser.add_argument('-o', '--ucioptions', type=lambda kv: kv.split("="), action='append', default=[])
    parser.add_argument('-t', '--types', type=str, action='append', default=[], help='mate/winning/defensive')
    parser.add_argument('-m', '--multipv', type=int, default=2)
    parser.add_argument('-d', '--depth', type=int, default=10)
    parser.add_argument('-n', '--min-difficulty', type=int, default=2)
    parser.add_argument('-x', '--max-difficulty', type=int, default=1000)
    parser.add_argument('-w', '--win-threshold', type=int, default=500)
    parser.add_argument('-u', '--unclear-threshold', type=int, default=100)
    args = parser.parse_args()

    engine = uci.Engine([args.engine], dict(args.ucioptions))
    sf.set_option("VariantPath", engine.options.get("VariantPath", ""))
    with open(args.input_file) as fens:
        generate_puzzles(fens, sys.stdout, engine, args.variant, args.types, args.multipv, args.depth,
                         args.min_difficulty, args.max_difficulty, args.win_threshold, args.unclear_threshold)
