# Chess variant puzzle generator

This is a simple puzzle generator for chess variants based on [Fairy-Stockfish](https://github.com/ianfab/Fairy-Stockfish) and its python binding pyffish.

## Process

Generating puzzles in PGN format currently consists of running the following scripts
1. `generator.py` to generate a set of FENs.
2. `puzzler.py` to identify puzzles within those FENs and store them as EPD with annotations. This step can be run on the EPD to re-evaluate the puzzles, e.g., at higher depth.
3. `pgn.py` to convert the EPD to a PGN.

## Setup

```
pip install -r requirements.txt
```

## Usage
A simple example of running the tool with default settings is:
```
python generator.py -e fairy-stockfish -v crazyhouse > positions.epd
python puzzler.py -e fairy-stockfish positions.epd > puzzles.epd
python pgn.py puzzles.epd > puzzles.pgn
```
