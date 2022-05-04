import subprocess
import threading
from collections.abc import Iterable
from collections import defaultdict


class Engine():
    def __init__(self, args, options=None):
        self.process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True)
        self.lock = threading.Lock()
        self.options = options or {}
        self._init()

    def write(self, message):
        with self.lock:
            self.process.stdin.write(message)
            self.process.stdin.flush()

    def setoption(self, name, value):
        self.write('setoption name {} value {}\n'.format(name, value))

    def _init(self):
        self.write('uci\n')
        self.read('uciok')
        for option, value in self.options.items():
            self.setoption(option, value)

    def newgame(self):
        self.write('ucinewgame\n')
        self.write('isready\n')
        self.read('readyok')

    def position(self, fen=None, moves=None):
        sfen = 'fen {}'.format(fen) if fen else 'startpos'
        moves = 'moves {}'.format(' '.join(moves)) if moves else ''
        self.write('position {} {}\n'.format(sfen, moves))

    def go(self, **limits):
        self.write('go {}\n'.format(' '.join(str(item) for key_value in limits.items() for item in key_value)))
        bestmove = None
        infos = defaultdict(dict)
        KEYWORDS = {'depth': int, 'seldepth': int, 'multipv': int, 'nodes': int,
                    'nps': int, 'time': int, 'score': list, 'pv': list}

        for line in self.read('bestmove'):
            items = line.split()
            if not items:
                continue
            elif items[0] == 'bestmove':
                bestmove = items[1]
            elif items[0] == 'info' and len(items) > 1 and items[1] != 'string' and 'score' in items:
                key = None
                values = []
                info = {}
                for i in items[1:] + ['']:
                    if not i or i in KEYWORDS:
                        if key:
                            if values and not issubclass(KEYWORDS[key], Iterable):
                                values = values[0]
                            info[key] = KEYWORDS[key](values)
                        key = i
                        values = []
                    else:
                        values.append(i)
                infos[info.get('depth')][info.get('multipv', 1)] = info
        infos = [[infos[d][m] for m in sorted(infos[d].keys())] for d in sorted(infos.keys())]
        return bestmove, infos

    def stop(self):
        self.write('stop\n')

    def read(self, keyword):
        output = []
        while True:
            line = self.process.stdout.readline()
            if not line and self.process.poll() is not None:
                break
            output.append(line)
            if line.startswith(keyword):
                break
        return output


if __name__ == '__main__':
    import sys
    e = Engine(sys.argv[1:])
    e.newgame()
    e.position()
    bestmove, infos = e.go(depth=10)
    print(bestmove)
    print(infos[-1])
