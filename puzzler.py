import argparse
import fileinput
import sys

import pyffish as sf

import uci


def move(info_line):
    return info_line['pv'][0] if 'pv' in info_line else None


def format_eval(info_line):
    return ('#' if info_line['score'][0] == 'mate' else '') + info_line['score'][1]


def is_mate(info_line, distance=0):
    return info_line['score'][0] == 'mate' and int(info_line['score'][1]) > distance


def has_cp(info_line, score=0):
    return info_line['score'][0] == 'cp' and int(info_line['score'][1]) > score


def get_puzzle_theme(multipv_info, win_threshold, unclear_threshold):
    candidate = multipv_info[0]
    first_alt = multipv_info[1]

    # mate
    if is_mate(candidate):
        if not is_mate(first_alt) and not has_cp(first_alt, win_threshold):
            return 'mate'

    # big tactics
    if has_cp(candidate, win_threshold):
        if not has_cp(first_alt, unclear_threshold):
            return 'winning'

    # big defensive tactics
    if has_cp(candidate, -unclear_threshold):
        if not has_cp(first_alt, -win_threshold):
            return 'defensive'

    return None


def get_puzzle(variant, fen, moves, engine, depth, win_threshold, unclear_threshold):
    if len(sf.legal_moves(variant, fen, moves)) <= 2:
        return None, None

    engine.setoption('UCI_Variant', variant)
    engine.newgame()
    engine.position(fen, moves)
    _, info = engine.go(depth=depth)

    theme = get_puzzle_theme(info[-1], win_threshold, unclear_threshold)
    return theme, info


def rate_puzzle(info, win_threshold, unclear_threshold):
    bestmove = move(info[-1][0])
    min_depth = None
    stable_depth = None
    solve_depth = None
    difficulty = 0
    for d, multiinf in enumerate(info):
        if move(multiinf[0]) != bestmove:
            stable_depth = d + 1
            solve_depth = d + 1
            difficulty += 1
        else:
            if not min_depth:
                min_depth = d
                stable_depth = d
                solve_depth = d
            if not get_puzzle_theme(multiinf, win_threshold, unclear_threshold):
                solve_depth = d + 1

    # quality is low if the puzzle criteria are only fulfilled
    # much later than finding the stable best move
    return difficulty, 1 - (solve_depth - stable_depth) / len(info)


def generate_puzzles(instream, outstream, engine, variant, req_types, multipv, depth,
                     min_difficulty, max_difficulty, min_quality, win_threshold, unclear_threshold):
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
        qualities = []
        types = []
        while True:
            puzzle_type, info = get_puzzle(current_variant, fen, pv, engine, depth, win_threshold, unclear_threshold)
            if not puzzle_type:
                # trim last opponent move
                if pv:
                    pv.pop()
                break
            evals.append(format_eval(info[-1][0]))
            difficulty, quality = rate_puzzle(info, win_threshold, unclear_threshold)
            difficulties.append(difficulty)
            qualities.append(quality)
            types.append(puzzle_type)
            pv += info[-1][0]['pv'][:2]
            if len(info[-1][0]['pv']) < 2:
                break

        total_difficulty = difficulties[0] if difficulties else 0
        total_quality = sum(qualities) / len(qualities) if qualities else 0
        if (len(pv) > stm_index
                and (not req_types or types[0] in req_types)
                and (max_difficulty >= total_difficulty >= min_difficulty) and (total_quality >= min_quality)):
            sm = 'sm {};'.format(pv[0]) if stm_index == 1 else ''
            outstream.write('{};variant {};{}bm {};eval {};difficulty {};quality {:.2f};type {};pv {}\n'.format(
                fen, current_variant, sm, pv[stm_index], evals[0], total_difficulty, total_quality, types[0], ','.join(pv)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('epd_files', nargs='*')
    parser.add_argument('-e', '--engine', required=True)
    parser.add_argument('-v', '--variant', help='only required if not annotated in input FEN/EPD')
    parser.add_argument('-o', '--ucioptions', type=lambda kv: kv.split("="), action='append', default=[])
    parser.add_argument('-t', '--types', type=str, action='append', default=[], help='mate/winning/defensive')
    parser.add_argument('-m', '--multipv', type=int, default=2)
    parser.add_argument('-d', '--depth', type=int, default=8)
    parser.add_argument('-n', '--min-difficulty', type=int, default=1)
    parser.add_argument('-x', '--max-difficulty', type=int, default=1000)
    parser.add_argument('-q', '--min-quality', type=int, default=0.7)
    parser.add_argument('-w', '--win-threshold', type=int, default=500)
    parser.add_argument('-u', '--unclear-threshold', type=int, default=100)
    args = parser.parse_args()

    engine = uci.Engine([args.engine], dict(args.ucioptions))
    sf.set_option("VariantPath", engine.options.get("VariantPath", ""))
    with fileinput.input(args.epd_files) as instream:
        generate_puzzles(instream, sys.stdout, engine, args.variant, args.types, args.multipv, args.depth,
                         args.min_difficulty, args.max_difficulty, args.min_quality,
                         args.win_threshold, args.unclear_threshold)
