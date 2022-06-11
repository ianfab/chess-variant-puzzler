import argparse
from collections import defaultdict
import csv

import numpy as np


def evaluate_puzzles(csv_stream, epd_files):
    fieldnames = ['PuzzleId', 'FEN', 'Moves', 'Rating', 'RatingDeviation', 'Popularity', 'NbPlays', 'Themes', 'GameUrl']
    reader = csv.DictReader(csv_stream, fieldnames=fieldnames, delimiter=',', quoting=csv.QUOTE_NONE)
    puzzles = dict()
    for row in reader:
        puzzles[row['FEN']] = row

    print('File\t\trecall\tlength\tR/D\tR/V\tR/A\tP/C\tP/L\tP/-V2')
    for epd_file in epd_files:
        with open(epd_file) as epd_stream:
            count = 0
            solution_length = list()
            rating = list()
            popularity = list()
            values = defaultdict(list)
            pv_length = list()
            for epd in epd_stream:
                tokens = epd.strip().split(';')
                fen = tokens[0]
                annotations = dict(token.split(' ', 1) for token in tokens[1:])
                ref_puzzle = puzzles[fen]
                rating.append(float(ref_puzzle['Rating']))
                popularity.append(float(ref_puzzle['Popularity']))
                for k in ('volatility', 'volatility2', 'accuracy', 'accuracy2', 'content', 'difficulty', 'quality', 'std'):
                    values[k].append(float(annotations.get(k, 0)))
                pv_length.append(len(annotations.get('pv', '').split(',')))
                solution_length.append(len(ref_puzzle['Moves'].split()))
                count += 1

            ll = np.corrcoef(solution_length, pv_length)[0, 1]
            rd = np.corrcoef(rating, values['difficulty'])[0, 1]
            rv = np.corrcoef(rating, values['volatility'])[0, 1]
            ra = np.corrcoef(rating, values['accuracy'])[0, 1]
            pc = np.corrcoef(popularity, values['content'])[0, 1]
            pl = np.corrcoef(popularity, pv_length)[0, 1]
            pv2 = -np.corrcoef(popularity, values['volatility2'])[0, 1]
            print(epd_file + ''.join('\t{:.2f}'.format(i) for i in (count / len(puzzles), ll, rd, rv, ra, pc, pl, pv2)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_file')
    parser.add_argument('epd_files', nargs='*')
    args = parser.parse_args()

    with open(args.csv_file) as csv_file:
        evaluate_puzzles(csv_file, args.epd_files)
