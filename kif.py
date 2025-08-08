import argparse
import fileinput
import os
import sys

import pyffish as sf
import shogi
import shogi.KIF


def get_board_dimensions(variant):
    """Get board dimensions for a shogi variant."""
    try:
        start_fen = sf.start_fen(variant)
        board_part = start_fen.split()[0]
        ranks = board_part.split('/')
        return len(ranks), len(ranks)  # Assuming square boards for shogi variants
    except:
        return 9, 9  # Default to standard shogi


def pyffish_to_usi_square(pyffish_square, variant):
    """Convert pyffish square notation to USI square notation.
    
    Pyffish uses: files a-... (left to right), ranks 1-... (bottom to top)
    USI uses: files ...-1 (left to right), ranks a-... (top to bottom)
    
    Board size is determined dynamically based on the variant.
    """
    if len(pyffish_square) != 2:
        return None
        
    pyffish_file = pyffish_square[0]  # a-...
    pyffish_rank = pyffish_square[1]  # 1-...
    
    # Get board dimensions
    board_width, board_height = get_board_dimensions(variant)
    
    # Create dynamic file mapping: a->board_width, b->board_width-1, ...
    file_chars = [chr(ord('a') + i) for i in range(board_width)]
    file_map = {file_chars[i]: str(board_width - i) for i in range(board_width)}
    
    # Create dynamic rank mapping: 1->last_rank_char, 2->second_last_rank_char, ...
    rank_chars = [chr(ord('a') + i) for i in range(board_height)]
    rank_digits = [str(i + 1) for i in range(board_height)]
    rank_map = {rank_digits[i]: rank_chars[board_height - 1 - i] for i in range(board_height)}
    
    usi_file = file_map.get(pyffish_file)
    usi_rank = rank_map.get(pyffish_rank)
    
    if usi_file and usi_rank:
        return usi_file + usi_rank
    return None


def pyffish_to_usi_move(pyffish_move, variant):
    """Convert pyffish UCI move to USI move."""
    if '@' in pyffish_move:
        # Drop move: piece@square -> piece*square in USI
        parts = pyffish_move.split('@')
        if len(parts) == 2:
            piece = parts[0]
            square = pyffish_to_usi_square(parts[1], variant)
            if square:
                return piece.upper() + '*' + square
    elif len(pyffish_move) == 4:
        # Normal move
        from_square = pyffish_to_usi_square(pyffish_move[:2], variant)
        to_square = pyffish_to_usi_square(pyffish_move[2:], variant)
        if from_square and to_square:
            return from_square + to_square
    return None


def is_shogi_variant(variant):
    """Check if variant is shogi-related."""
    shogi_variants = ['shogi', 'minishogi', 'kyotoshogi', 'euroshogi', 'torishogi', 'yarishogi', 'okisakishogi', 'shoshogi']
    return variant.lower() in shogi_variants


def epd_to_kif(epd_stream, kif_stream):
    """Convert EPD puzzle format to KIF format."""
    for epd in epd_stream:
        tokens = epd.strip().split(';')
        if not tokens:
            continue
            
        fen = tokens[0]
        annotations = dict(token.strip().split(' ', 1) for token in tokens[1:] if ' ' in token.strip())
        variant = annotations.get('variant', '')

        # Only process shogi variants for KIF export
        if not is_shogi_variant(variant):
            print(f"Skipping non-shogi variant: {variant}", file=sys.stderr)
            continue

        if variant not in sf.variants():
            raise Exception("Unsupported variant: {}".format(variant))

        # Get the move sequence from pv annotation
        moves = annotations.get('pv', '').split(',')
        if not moves or moves == ['']:
            print(f"No moves found in puzzle, skipping", file=sys.stderr)
            continue

        try:
            # Convert pyffish UCI moves to USI moves
            usi_moves = []
            for pyffish_move in moves:
                pyffish_move = pyffish_move.strip()
                if not pyffish_move:
                    continue
                usi_move = pyffish_to_usi_move(pyffish_move, variant)
                if usi_move:
                    usi_moves.append(usi_move)
                else:
                    print(f"Failed to convert move: {pyffish_move}", file=sys.stderr)

            if not usi_moves:
                print(f"No valid USI moves found, skipping puzzle", file=sys.stderr)
                continue

            # Convert pyffish FEN to python-shogi SFEN format using pyffish
            try:
                start_sfen = sf.get_fen(variant, fen, [], False, True)
                board = shogi.Board(sfen=start_sfen)
            except (ValueError, IndexError):
                # If parsing fails, start with default position
                board = shogi.Board()

            # Apply the moves to build the game
            valid_moves = []
            for usi_move in usi_moves:
                try:
                    board.push_usi(usi_move)
                    valid_moves.append(usi_move)
                except ValueError as e:
                    print(f"Invalid USI move {usi_move}: {e}", file=sys.stderr)
                    break

            if not valid_moves:
                print(f"No valid moves found, skipping puzzle", file=sys.stderr)
                continue

            # Create sfen_summary for KIF export
            sfen_summary = {
                'names': ['先手', '後手'],  # First player, Second player
                'sfen': start_sfen,  # Starting position
                'moves': valid_moves,
                'win': '先手',  # First player wins (puzzle solver)
                'endgame': '詰み',  # Checkmate
                'starttime': '2024/01/01 10:00:00',
            }

            # Export to KIF format
            exporter = shogi.KIF.Exporter()
            kif_content = exporter.kif(sfen_summary)
            
            # Add puzzle metadata as comments
            kif_stream.write(f"# Puzzle Type: {annotations.get('type', 'Unknown')}\n")
            kif_stream.write(f"# Site: {annotations.get('site', 'https://github.com/ianfab/Fairy-Stockfish')}\n")
            kif_stream.write(f"# Variant: {variant}\n")
            kif_stream.write(kif_content)
            kif_stream.write(os.linesep)

        except Exception as e:
            print(f"Error processing puzzle: {e}", file=sys.stderr)
            continue


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Convert EPD puzzles to KIF format for shogi variants")
    parser.add_argument('epd_files', nargs='*', help='EPD input files generated by puzzler.py')
    parser.add_argument('-p', '--variant-path', default='', help='custom variants definition file path')
    args = parser.parse_args()

    sf.set_option("VariantPath", args.variant_path)
    with fileinput.input(args.epd_files) as instream:
        epd_to_kif(instream, sys.stdout)