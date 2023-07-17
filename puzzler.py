import argparse
import fileinput
from functools import partial
import math
import sys
import threading
import time
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


def is_shortest_win(candidate, first_alt, mate_distance_ratio):
    return is_mate(candidate) and (not is_mate(first_alt) or mate_distance(first_alt) >= mate_distance(candidate) * mate_distance_ratio)


def get_puzzle_theme(multipv_info, win_threshold, unclear_threshold, mate_distance_ratio):
    scale = win_threshold * 0.8
    min_diff = sigmoid(win_threshold / scale) - sigmoid(unclear_threshold / scale)

    candidate = multipv_info[0]
    first_alt = multipv_info[1]

    if value(candidate, scale) - value(first_alt, scale) >= min_diff or is_shortest_win(candidate, first_alt, mate_distance_ratio):
        if is_mate(candidate):
            return 'mate'
        elif has_cp(candidate, win_threshold):
            return 'winning'
        elif has_cp(candidate, unclear_threshold):
            return 'turnaround'
        else:
            return 'defensive'

    return None

def timeout_monitor(engine: uci.Engine, timeout, count_time: threading.Event):
    while True:
        count_time.wait()
        start_time = time.time()
        lock = threading.Lock()
        while time.time() < start_time + timeout:
            if not count_time.is_set():
                break
        else:
            with lock:
                engine.write('stop\n')
                count_time.clear()
        

def get_puzzle(variant, fen, moves, engine, depth, win_threshold, unclear_threshold, mate_distance_ratio, count_time: threading.Event):
    if len(sf.legal_moves(variant, fen, moves)) <= 2:
        return None, None
    engine.setoption('UCI_Variant', variant)
    engine.newgame()
    engine.position(fen, moves)
    _, info = engine.go(depth=depth)
    if count_time.is_set():
        theme = get_puzzle_theme(info[-1], win_threshold, unclear_threshold, mate_distance_ratio)
        return theme, info
    raise TimeoutError


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
    if is_mate(multiinf[0]) and is_mate(multiinf[1]):
        mate_distance_fraction = mate_distance(multiinf[0]) / mate_distance(multiinf[1])
    else:
        mate_distance_fraction = 0

    return volatility / len(info), volatility2 / len(info),  accuracy / len(info),  accuracy2 / len(info), quality / len(info), mate_distance_fraction


def generate_puzzles(instream, outstream, engine, variant, depth, win_threshold, unclear_threshold, mate_distance_ratio, failed_file, timeout):
    if failed_file:
        ff = open(failed_file, "w")

    # Before the first line has been read, filename() returns None.
    if instream.filename() is None:
        filename = instream._files[0]
    else:
        filename = instream.filename()

    # When reading from sys.stdin, filename() is "-"
    total = None if (filename == "-") else line_count(filename)

    count_time = threading.Event()
    monitor_thread = threading.Thread(target=timeout_monitor, daemon=True, args=[engine, timeout, count_time])
    monitor_thread.start()
    
    
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
        mate_distance_fractions = []
        types = []
        
        is_timed_out = False	
        count_time.set()
        while True:	
            try:
                puzzle_type, info = get_puzzle(current_variant, fen, pv, engine, depth, win_threshold, unclear_threshold, mate_distance_ratio, count_time)
            except TimeoutError:
                is_timed_out = True
                break
            if not puzzle_type:
                # trim last opponent move
                if pv:
                    pv.pop()
                # re-tag incomplete mates
                if types and types[0] == 'mate':
                    types[0] = 'partial-mate'
                break
            evals.append(info[-1][0])
            volatility, volatility2, accuracy, accuracy2, quality, mate_distance_fraction = rate_puzzle(info, win_threshold)
            qualities.append(quality)
            volatilities.append(volatility)
            volatilities2.append(volatility2)
            accuracies.append(accuracy)
            accuracies2.append(accuracy2)
            mate_distance_fractions.append(mate_distance_fraction)
            types.append(puzzle_type)
            pv += info[-1][0]['pv'][:2]
            if len(info[-1][0]['pv']) < 2:
                break

        count_time.clear()
        if is_timed_out:
            continue

        if len(pv) > stm_index:
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
            annotations['ambiguity'] = '{:.3f}'.format(max(mate_distance_fractions))
            annotations['type'] = types[0]
            annotations['pv'] = ','.join(pv)
            ops = ';'.join('{} {}'.format(k, v) for k, v in annotations.items())
            outstream.write('{};{}\n'.format(fen, ops))
        elif failed_file:
            ff.write_file(epd)

    if failed_file:
        ff.close()


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
    parser.add_argument('-r', '--mate-distance-ratio', type=float, default=1.5, help='minimum ratio of second best to best mate distance')
    parser.add_argument('-f', '--failed-file', help='output file name for epd lines producing no puzzle')
    parser.add_argument('-t', '--timeout', type=int, default=600, help='maximum time to analysis a single fen in secound')
    args = parser.parse_args()

    engine = uci.Engine([args.engine], dict(args.ucioptions))
    engine.setoption('multipv', args.multipv)
    sf.set_option("VariantPath", engine.options.get("VariantPath", ""))
    with fileinput.input(args.epd_files) as instream:
        generate_puzzles(instream, sys.stdout, engine, args.variant, args.depth, args.win_threshold, args.unclear_threshold, args.mate_distance_ratio, args.failed_file, args.timeout)
