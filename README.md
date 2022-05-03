# Chess variant puzzle generator

This is a simple puzzle generator for chess variants based on [Fairy-Stockfish](https://github.com/ianfab/Fairy-Stockfish) and its python binding pyffish.

## Process

Generating puzzles in PGN format currently consists of running the following scripts
1. `generator.py` to generate a set of positions in FEN/EPD format from playing engine games. This step can be skipped if positions are extracted from other sources such as databases of human games.
2. `puzzler.py` to identify puzzles within those positions and store them as EPD with annotations. This step can be re-run on the resulting EPD to re-evaluate the puzzles, e.g., at higher depth.
3. `pgn.py` to convert the EPD to a PGN.

## Setup
The scripts require at least python3.2 as well as the dependencies from the `requirements.txt`. Install them using
```
pip3 install -r requirements.txt
```

## Usage
A simple example of running the scripts with default settings is:
```
python3 generator.py -e fairy-stockfish -v crazyhouse > positions.epd
python3 puzzler.py -e fairy-stockfish positions.epd > puzzles.epd
python3 pgn.py puzzles.epd > puzzles.pgn
```
Run the scripts with `-h` to get help on the supported parameters.

Instead of input from files the scripts can also take input from stdin, so two or more commands can optionally be piped together if the intermediate files are not of interest.
```
python3 generator.py -e fairy-stockfish -v crazyhouse | python3 puzzler.py -e fairy-stockfish | python3 pgn.py
```
