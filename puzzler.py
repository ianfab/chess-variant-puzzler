import argparse
import fileinput
from functools import partial
import math
import sys

from tqdm import tqdm
import pyffish as sf
import numpy as np

import uci


def line_count(filename):
    f = open(filename, 'rb')
    bufgen = iter(partial(f.raw.read, 1024*1024), b'')
    return sum(buf.count(b'\n') for buf in bufgen)


def move(info_line):
    return info_line['pv'][0] if 'pv' in info_line else None


def format_eval(info_line):
    return ('#' if info_line['score'][0] == 'mate' else '') + info_line['score'][1]


def is_mate(info_line, distance=0):
    return info_line['score'][0] == 'mate' and int(info_line['score'][1]) > distance


def mate_distance(info_line):
    assert info_line['score'][0] == 'mate'
    return int(info_line['score'][1])


def has_cp(info_line, score=0):
    return info_line['score'][0] == 'cp' and int(info_line['score'][1]) > score


def sigmoid(x):
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    else:
        z = math.exp(x)
        return z / (1 + z)


def value(info_line, scale):
    if info_line['score'][0] == 'mate':
        return 1 if int(info_line['score'][1]) >= 0 else 0
    elif info_line['score'][0] == 'cp':
        return sigmoid(float(info_line['score'][1]) / scale)


def is_shortest_win(candidate, first_alt):
    return is_mate(candidate) and not (is_mate(first_alt) and mate_distance(first_alt) < mate_distance(candidate) * 2)


def get_puzzle_theme(multipv_info, win_threshold, unclear_threshold):
    scale = win_threshold * 0.8
    min_diff = sigmoid(win_threshold / scale) - sigmoid(unclear_threshold / scale)

    candidate = multipv_info[0]
    first_alt = multipv_info[1]

    if value(candidate, scale) - value(first_alt, scale) >= min_diff or is_shortest_win(candidate, first_alt):
        if is_mate(candidate):
            return 'mate'
        elif has_cp(candidate, win_threshold):
            return 'winning'
        elif has_cp(candidate, unclear_threshold):
            return 'turnaround'
        else:
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


def rate_puzzle(info, win_threshold):
    bestmove = move(info[-1][0])
    bestscore = value(info[-1][0], win_threshold)
    bestscore2 = value(info[-1][1], win_threshold)
    quality = 0
    last_score = None
    last_second_score = None
    volatility = 0
    volatility2 = 0
    accuracy = 0
    accuracy2 = 0
    for multiinf in info:
        v0 = value(multiinf[0], win_threshold)
        v1 = value(multiinf[1], win_threshold)
        if move(multiinf[0]) == bestmove:
            quality += abs(v0 - v1)
        accuracy += abs(v0 - bestscore)
        accuracy2 += abs(v1 - bestscore2)
        if last_score is not None:
            volatility += abs(v0 - last_score)
            volatility2 += abs(v1 - last_second_score)
        last_score = v0
        last_second_score = v1

    return volatility / len(info), volatility2 / len(info),  accuracy / len(info),  accuracy2 / len(info), quality / len(info)


def generate_puzzles(instream, outstream, engine, variant, depth, win_threshold, unclear_threshold):
    # Before the first line has been read, filename() returns None.
    if instream.filename() is None:
        filename = instream._files[0]
    else:
        filename = instream.filename()

    # When reading from sys.stdin, filename() is "-"
    total = None if (filename == "-") else line_count(filename)

    for epd in tqdm(instream, total=total):
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
        qualities = []
        volatilities = []
        volatilities2 = []
        accuracies = []
        accuracies2 = []
        types = []
        mate_pvs = []
        while True:
            puzzle_type, info = get_puzzle(current_variant, fen, pv, engine, depth, win_threshold, unclear_threshold)
            if puzzle_type == "mate":
                mate_pvs.append(info[-1][0]['pv'])
            if not puzzle_type:
                # trim last opponent move
                if pv:
                    pv.pop()
                break
            evals.append(info[-1][0])
            volatility, volatility2, accuracy, accuracy2, quality = rate_puzzle(info, win_threshold)
            qualities.append(quality)
            volatilities.append(volatility)
            volatilities2.append(volatility2)
            accuracies.append(accuracy)
            accuracies2.append(accuracy2)
            types.append(puzzle_type)
            pv += info[-1][0]['pv'][:2]
            if len(info[-1][0]['pv']) < 2:
                break

        if len(pv) > stm_index:
            # cover the whole mate sequence
            if types[0] == "mate":
                mate_pv_length = (int(evals[0]["score"][1]) * 2) - 1
                if len(pv) < mate_pv_length:
                    mate_pv = next((x for x in mate_pvs if len(x) == mate_pv_length), None)
                    if mate_pv is not None:
                        pv = mate_pv
            std = np.std([value(e, win_threshold) for e in evals])
            difficulty = 4 * volatilities[0] + 2 * std + accuracies[0]
            content = len(pv) - stm_index - 40 * volatilities2[0]
            total_quality = sum(qualities) / len(qualities)
            # output
            annotations['variant'] = current_variant
            if stm_index == 1:
                annotations['sm'] = pv[0]
            annotations['bm'] = pv[stm_index]
            annotations['eval'] = format_eval(evals[0])
            annotations['difficulty'] = '{:.3f}'.format(difficulty)
            annotations['content'] = '{:.3f}'.format(content)
            annotations['quality'] = '{:.3f}'.format(total_quality)
            annotations['volatility'] = '{:.3f}'.format(volatilities[0])
            annotations['volatility2'] = '{:.3f}'.format(volatilities2[0])
            annotations['accuracy'] = '{:.3f}'.format(accuracies[0])
            annotations['accuracy2'] = '{:.3f}'.format(accuracies2[0])
            annotations['std'] = '{:.3f}'.format(std)
            annotations['type'] = types[0]
            annotations['pv'] = ','.join(pv)
            ops = ';'.join('{} {}'.format(k, v) for k, v in annotations.items())
            outstream.write('{};{}\n'.format(fen, ops))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('epd_files', nargs='*')
    parser.add_argument('-e', '--engine', required=True)
    parser.add_argument('-o', '--ucioptions', type=lambda kv: kv.split("="), action='append', default=[],
                        help='UCI option as key=value pair. Repeat to add more options.')
    parser.add_argument('-v', '--variant', help='only required if not annotated in input FEN/EPD')
    parser.add_argument('-m', '--multipv', type=int, default=2)
    parser.add_argument('-d', '--depth', type=int, default=8, help='Engine search depth. Important for puzzle accuracy.')
    parser.add_argument('-w', '--win-threshold', type=int, default=400, help='centipawn threshold for winning positions')
    parser.add_argument('-u', '--unclear-threshold', type=int, default=100, help='centipawn threshold for unclear positions')
    args = parser.parse_args()

    engine = uci.Engine([args.engine], dict(args.ucioptions))
    engine.setoption('multipv', args.multipv)
    sf.set_option("VariantPath", engine.options.get("VariantPath", ""))
    with fileinput.input(args.epd_files) as instream:
        generate_puzzles(instream, sys.stdout, engine, args.variant, args.depth, args.win_threshold, args.unclear_threshold)
