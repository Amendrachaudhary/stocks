"""
Unit Tests: Regex Normalizer & Signal Extraction
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.regex_parser import parse_signal, parse_targets


class TestRegexParser(unittest.TestCase):

    def test_banknifty_entry_standard(self):
        text = "BANKNIFTY 48000 CE BUY ABOVE 220 SL 190 TARGET 260 / 290 / 330"
        sig = parse_signal(text)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "ENTRY")
        self.assertEqual(sig.underlying, "BANKNIFTY")
        self.assertEqual(sig.strike, 48000)
        self.assertEqual(sig.option_type, "CE")
        self.assertEqual(sig.entry_price, 220.0)
        self.assertEqual(sig.stop_loss, 190.0)
        self.assertEqual(sig.targets, [260.0, 290.0, 330.0])

    def test_nifty_entry_spaced_name(self):
        text = "BANK NIFTY 48500 PE CMP 140 SL 110 T1: 170, T2: 200"
        sig = parse_signal(text)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "ENTRY")
        self.assertEqual(sig.underlying, "BANKNIFTY")
        self.assertEqual(sig.strike, 48500)
        self.assertEqual(sig.option_type, "PE")
        self.assertEqual(sig.entry_price, 140.0)
        self.assertEqual(sig.stop_loss, 110.0)
        self.assertIn(170.0, sig.targets)
        self.assertIn(200.0, sig.targets)

    def test_finnifty_entry(self):
        text = "FIN NIFTY 21200 CE BUY AT 85 SL 70 TARGET 100/120"
        sig = parse_signal(text)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "ENTRY")
        self.assertEqual(sig.underlying, "FINNIFTY")
        self.assertEqual(sig.strike, 21200)
        self.assertEqual(sig.entry_price, 85.0)

    def test_target_hit_detection(self):
        text = "BANKNIFTY 48000 CE TARGET 1 HIT BOOK PARTIAL CMP 265"
        sig = parse_signal(text)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "TARGET_HIT")
        self.assertEqual(sig.underlying, "BANKNIFTY")
        self.assertEqual(sig.exit_price, 265.0)
        self.assertEqual(sig.target_tier, 1)

    def test_target_hit_colloquial(self):
        text = "BANKNIFTY 48000 CE BOOM BLAST 320+++ BOOK FULL PROFITS!"
        sig = parse_signal(text)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "TARGET_HIT")
        self.assertEqual(sig.underlying, "BANKNIFTY")

    def test_first_target_achieved(self):
        for msg in ["1st target done", "First target hit", "T1 done", "Tag 1 done", "Target 1 achieved"]:
            sig = parse_signal(msg)
            self.assertIsNotNone(sig, f"Failed for {msg}")
            self.assertEqual(sig.action, "TARGET_HIT")
            self.assertEqual(sig.target_tier, 1)

    def test_channel_colloquial_target_booking(self):
        sig1 = parse_signal("270 cmp jissko krna hai krlo book😇")
        self.assertIsNotNone(sig1)
        self.assertEqual(sig1.action, "TARGET_HIT")
        self.assertEqual(sig1.exit_price, 270.0)

        sig2 = parse_signal("230😍 Costo to cost sl krdo")
        self.assertIsNotNone(sig2)
        self.assertEqual(sig2.action, "TARGET_HIT")
        self.assertEqual(sig2.exit_price, 230.0)

    def test_sl_hit_detection(self):
        text = "NIFTY 22500 PE SL HIT EXIT AT 94.50"
        sig = parse_signal(text)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "SL_HIT")
        self.assertEqual(sig.underlying, "NIFTY")
        self.assertEqual(sig.exit_price, 94.50)

    def test_target_parsing_utility(self):
        targets = parse_targets("T1: 240, T2: 260, T3: 300")
        self.assertEqual(targets, [240.0, 260.0, 300.0])

        slash_targets = parse_targets("240/270/310")
        self.assertEqual(slash_targets, [240.0, 270.0, 310.0])

    def test_insider_traderoom_real_call(self):
        text = "Last trade 23700 call @12\nSl 7\nTag 28/35/5/80/120"
        sig = parse_signal(text)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.action, "ENTRY")
        self.assertEqual(sig.underlying, "NIFTY")
        self.assertEqual(sig.strike, 23700)
        self.assertEqual(sig.option_type, "CE")
        self.assertEqual(sig.entry_price, 12.0)
        self.assertEqual(sig.stop_loss, 7.0)
        self.assertEqual(sig.targets, [28.0, 35.0, 80.0, 120.0])

    def test_noise_rejection(self):
        self.assertIsNone(parse_signal("Good morning members, market is looking volatile today!"))
        self.assertIsNone(parse_signal("Join our VIP group for 99% accuracy!"))


if __name__ == "__main__":
    unittest.main()
