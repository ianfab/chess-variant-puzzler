# Chess variant puzzle generator

This is a simple puzzle generator for chess variants based on [Fairy-Stockfish](https://github.com/ianfab/Fairy-Stockfish) and its python binding pyffish.

## Process

Generating puzzles in PGN format currently consists of running the following scripts
1. `generator.py` to generate a set of positions in FEN/EPD format from playing engine games. This step can be skipped if positions are extracted from other sources such as databases of human games.
    * If you download games from lichess in `.pgn` format, you can use `pgn2epd.py` to generate FENs.
    * If you download games from pychess in `.json` format, you can use `json2epd.py` to generate FENs.
2. `puzzler.py` to identify puzzles within those positions and store them as EPD with annotations. This step can be re-run on the resulting EPD to re-evaluate the puzzles, e.g., at higher depth.
3. `filter.py` to optionally narrow down the set of puzzles according to difficulty, type, etc.
4. `pgn.py` to convert the EPD to a PGN.

## Setup
The scripts require at least python3.2 as well as the dependencies from the `requirements.txt`. Install them using
```
pip3 install -r requirements.txt
```

## Usage
A simple example of running the scripts with default settings is:
```
# generate positions
python3 generator.py --engine fairy-stockfish --variant crazyhouse > positions.epd
# extract puzzles
python3 puzzler.py --engine fairy-stockfish positions.epd > puzzles.epd
# convert EPD to PGN
python3 pgn.py puzzles.epd > puzzles.pgn
```
Run the scripts with `--help` to get help on the supported parameters.

Usually it makes sense to first run the puzzler with a lower depth but loose filter criteria to pre-filter the positions, followed by a more strict validation at higher depth.

## Evaluate
The puzzle generator can be evaluated against an existing database of curated puzzles. E.g., for the example of lichess:
```
# Download puzzles from https://database.lichess.org/#puzzles
curl -O https://database.lichess.org/lichess_db_puzzle.csv.bz2
# Unpack
bzip2 -dk lichess_db_puzzle.csv.bz2
# Extract subset
head -100 lichess_db_puzzle.csv > test.csv
# Prepare input FENs
cut -d " " -f 1-6 test.csv | cut -d "," -f 2,3 --output-delimiter=";sm " > test.fen
# Run puzzler
python puzzler.py --engine fairy-stockfish -d 10 --variant chess test.fen > test.epd
# Run evaluation
python evaluate.py test.csv test.epd
```
