import argparse
import fileinput
from functools import partial
import sys

from tqdm import tqdm


def line_count(filename):
    f = open(filename, 'rb')
    bufgen = iter(partial(f.raw.read, 1024*1024), b'')
    return sum(buf.count(b'\n') for buf in bufgen)


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


def filter_puzzles(instream, outstream, min, max, values):
    # Before the first line has been read, filename() returns None.
    if instream.filename() is None:
        filenames = instream._files
    else:
        filenames = [instream.filename()]
    # When reading from sys.stdin, filename() is "-"
    total = None if filenames[0] == "-" else sum(line_count(filename) for filename in filenames)

    for epd in tqdm(instream, total=total):
        annotations = dict(token.split(' ', 1) for token in epd.strip().split(';')[1:])
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
    args = parser.parse_args()

    with fileinput.input(args.epd_files) as instream:
        filter_puzzles(instream, sys.stdout, dict(args.min), dict(args.max), dict(args.values))
