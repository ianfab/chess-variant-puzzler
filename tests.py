from io import StringIO
import unittest

import pgn


class TestPgn(unittest.TestCase):
    TEST_PUZZLE = '3r4/2Rpk1pp/p2pp1b1/3p2N1/1Q1PnBPn/3bPP1n/P2Q3P/R6K[RBPPP] b - - 4 31;variant crazyhouse;pv e4f2,d2f2,h3f2'

    def test_variant(self):
        instream = StringIO(self.TEST_PUZZLE)
        outstream = StringIO()
        pgn.epd_to_pgn(instream, outstream)
        self.assertIn('[Variant "Crazyhouse"]', outstream.getvalue())

    def test_fen(self):
        instream = StringIO(self.TEST_PUZZLE)
        outstream = StringIO()
        pgn.epd_to_pgn(instream, outstream)
        self.assertIn('[FEN "3r4/2Rpk1pp/p2pp1b1/3p2N1/1Q1PnBPn/3bPP1n/P2Q3P/R6K[RBPPP] b - - 4 31"]', outstream.getvalue())

    def test_san(self):
        instream = StringIO(self.TEST_PUZZLE)
        outstream = StringIO()
        pgn.epd_to_pgn(instream, outstream)
        self.assertIn('31... Nef2+ 32. Qxf2 Nxf2+', outstream.getvalue())


if __name__ == '__main__':
    unittest.main()
