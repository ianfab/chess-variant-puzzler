from io import StringIO
import unittest
import sys

import pgn
import kif


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


class TestKif(unittest.TestCase):
    # Shogi puzzle in EPD format - using default start position with some moves
    TEST_SHOGI_PUZZLE = 'lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL[-] w 0 1;variant shogi;pv h2c2,g7g6,c2c6'

    def test_coordinate_mapping(self):
        """Test pyffish to USI coordinate conversion"""
        # Test square conversion
        self.assertEqual(kif.pyffish_to_usi_square('h2'), '2h')
        self.assertEqual(kif.pyffish_to_usi_square('c2'), '7h')
        self.assertEqual(kif.pyffish_to_usi_square('a1'), '9i')
        self.assertEqual(kif.pyffish_to_usi_square('i9'), '1a')
        
        # Test invalid squares
        self.assertIsNone(kif.pyffish_to_usi_square('z1'))
        self.assertIsNone(kif.pyffish_to_usi_square('a0'))
        self.assertIsNone(kif.pyffish_to_usi_square(''))

    def test_move_conversion(self):
        """Test pyffish UCI to USI move conversion"""
        # Normal moves
        self.assertEqual(kif.pyffish_to_usi_move('h2c2'), '2h7h')
        self.assertEqual(kif.pyffish_to_usi_move('g7g6'), '3c3d')
        
        # Drop moves (if supported)
        self.assertEqual(kif.pyffish_to_usi_move('P@e4'), 'P*5f')
        
        # Invalid moves
        self.assertIsNone(kif.pyffish_to_usi_move(''))
        self.assertIsNone(kif.pyffish_to_usi_move('xyz'))

    def test_shogi_variant_detection(self):
        """Test detection of shogi variants"""
        self.assertTrue(kif.is_shogi_variant('shogi'))
        self.assertTrue(kif.is_shogi_variant('minishogi'))
        self.assertTrue(kif.is_shogi_variant('SHOGI'))  # case insensitive
        self.assertFalse(kif.is_shogi_variant('chess'))
        self.assertFalse(kif.is_shogi_variant('crazyhouse'))

    def test_kif_export_shogi(self):
        """Test KIF export for shogi puzzle"""
        instream = StringIO(self.TEST_SHOGI_PUZZLE)
        outstream = StringIO()
        
        # Capture stderr to check for error messages
        stderr_capture = StringIO()
        original_stderr = sys.stderr
        sys.stderr = stderr_capture
        
        try:
            kif.epd_to_kif(instream, outstream)
            result = outstream.getvalue()
            
            # Check that KIF content was generated
            self.assertIn('# Variant: shogi', result)
            self.assertIn('# Puzzle Type:', result)
            
            # Check that some KIF-like content was generated (moves, board position, etc.)
            self.assertGreater(len(result.strip()), 50, "KIF output should contain substantial content")
            
        finally:
            sys.stderr = original_stderr

    def test_kif_export_non_shogi(self):
        """Test KIF export skips non-shogi variants"""
        non_shogi_puzzle = '3r4/2Rpk1pp/p2pp1b1/3p2N1/1Q1PnBPn/3bPP1n/P2Q3P/R6K[RBPPP] b - - 4 31;variant crazyhouse;pv e4f2,d2f2,h3f2'
        
        instream = StringIO(non_shogi_puzzle)
        outstream = StringIO()
        
        # Capture stderr to check for skip message
        stderr_capture = StringIO()
        original_stderr = sys.stderr
        sys.stderr = stderr_capture
        
        try:
            kif.epd_to_kif(instream, outstream)
            result = outstream.getvalue()
            stderr_result = stderr_capture.getvalue()
            
            # Should skip non-shogi variant
            self.assertEqual(result.strip(), '', "Non-shogi puzzles should not generate KIF output")
            self.assertIn('Skipping non-shogi variant: crazyhouse', stderr_result)
            
        finally:
            sys.stderr = original_stderr

    def test_kif_export_empty_moves(self):
        """Test KIF export handles puzzles with no moves"""
        empty_puzzle = 'lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL[-] w 0 1;variant shogi;pv '
        
        instream = StringIO(empty_puzzle)
        outstream = StringIO()
        
        # Capture stderr to check for error message
        stderr_capture = StringIO()
        original_stderr = sys.stderr
        sys.stderr = stderr_capture
        
        try:
            kif.epd_to_kif(instream, outstream)
            result = outstream.getvalue()
            stderr_result = stderr_capture.getvalue()
            
            # Should skip puzzles with no moves
            self.assertEqual(result.strip(), '', "Empty move puzzles should not generate KIF output")
            self.assertIn('No moves found in puzzle', stderr_result)
            
        finally:
            sys.stderr = original_stderr


if __name__ == '__main__':
    unittest.main()
