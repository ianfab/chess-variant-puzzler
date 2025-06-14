import argparse
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

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


def generate_fens_worker(engine_path, ucioptions, variant, min_depth, max_depth, add_move, required_pieces, count):
    engine = uci.Engine([engine_path], ucioptions)
    generator = generate_fens(engine, variant, min_depth, max_depth, add_move, required_pieces)
    results = []
    for _ in range(count):
        results.append(next(generator))
    return results


def write_fens_parallel(stream, engine_path, ucioptions, variant, count, min_depth, max_depth, add_move, required_pieces, workers):
    batch_size = 1000
    total_batches = (count + batch_size - 1) // batch_size
    submitted = 0
    written = 0
    with ProcessPoolExecutor(max_workers=workers) as executor, tqdm(total=count, desc="Generating positions") as pbar:
        futures = []
        # Submit initial batches
        for _ in range(min(workers, total_batches)):
            submit_count = min(batch_size, count - submitted * batch_size)
            futures.append(executor.submit(
                generate_fens_worker,
                engine_path,
                ucioptions,
                variant,
                min_depth,
                max_depth,
                add_move,
                required_pieces,
                submit_count
            ))
            submitted += 1
        while futures:
            for future in as_completed(futures):
                results = future.result()
                for fen, move in results:
                    stream.write('{};variant {}'.format(fen, variant) + (';sm {}'.format(move) if move else '') + os.linesep)
                    written += 1
                    pbar.update(1)
                    if written >= count:
                        stream.flush()
                        return
                stream.flush()  # Flush after each batch
                futures.remove(future)
                # Submit next batch if needed
                if submitted < total_batches:
                    submit_count = min(batch_size, count - submitted * batch_size)
                    futures.append(executor.submit(
                        generate_fens_worker,
                        engine_path,
                        ucioptions,
                        variant,
                        min_depth,
                        max_depth,
                        add_move,
                        required_pieces,
                        submit_count
                    ))
                    submitted += 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--engine', required=True, help='chess variant engine path, e.g., to Fairy-Stockfish')
    parser.add_argument('-o', '--ucioptions', type=lambda kv: kv.split("="), action='append', default=[],
                        help='UCI option as key=value pair. Repeat to add more options.')
    parser.add_argument('-v', '--variant', default='chess', help='variant to generate positions for')
    parser.add_argument('-c', '--count', type=int, default=1000, help='number of positions')
    parser.add_argument('-s', '--skill-level', type=int, default=10, help='engine skill level setting [-20,20]')
    parser.add_argument('-d', '--max-depth', type=int, default=5, help='maximum search depth')
    parser.add_argument('-m', '--min-depth', type=int, default=1, help='minimum search depth')
    parser.add_argument('-a', '--add-move', action='store_true', help='add initial move for opposing side')
    parser.add_argument('-p', '--pieces', default=None, help='only return positions containing one of these piece chars (case insensitive)')
    parser.add_argument('-w', '--workers', type=int, default=1, help='number of parallel workers')
    args = parser.parse_args()

    ucioptions = dict(args.ucioptions)
    ucioptions.update({'Skill Level': args.skill_level})

    write_fens_parallel(
        sys.stdout,
        args.engine,
        ucioptions,
        args.variant,
        args.count,
        args.min_depth,
        args.max_depth,
        args.add_move,
        args.pieces,
        args.workers
    )
