"""Testes do job de geração automática de listas.

Uso:
    cd backend
    python test_auto_separation.py

Ou via unittest:
    cd backend
    python -m unittest test_auto_separation -v
"""
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

# Garante imports do backend
sys.path.insert(0, os.path.dirname(__file__))


class TestShouldRunNow(unittest.TestCase):
    """Testa o predicate de horário."""

    def setUp(self):
        from services.auto_separation import should_run_now
        self.should_run_now = should_run_now

    @patch("services.auto_separation.datetime")
    def test_segunda_06h15_BR_returns_true(self, mock_dt):
        # 09:15 UTC = 06:15 BR, segunda-feira (weekday 0)
        mock_dt.utcnow.return_value = datetime(2026, 5, 18, 9, 15)
        # Garante que outras chamadas a datetime ainda funcionem
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        # timedelta também precisa funcionar
        from datetime import timedelta as real_td
        with patch("services.auto_separation.timedelta", real_td):
            self.assertTrue(self.should_run_now())

    @patch("services.auto_separation.datetime")
    def test_sabado_returns_false(self, mock_dt):
        # 06:15 BR num sábado
        mock_dt.utcnow.return_value = datetime(2026, 5, 16, 9, 15)
        from datetime import timedelta as real_td
        with patch("services.auto_separation.timedelta", real_td):
            self.assertFalse(self.should_run_now())

    @patch("services.auto_separation.datetime")
    def test_segunda_05h59_returns_false(self, mock_dt):
        # 08:59 UTC = 05:59 BR
        mock_dt.utcnow.return_value = datetime(2026, 5, 18, 8, 59)
        from datetime import timedelta as real_td
        with patch("services.auto_separation.timedelta", real_td):
            self.assertFalse(self.should_run_now())

    @patch("services.auto_separation.datetime")
    def test_segunda_06h30_returns_false(self, mock_dt):
        # 09:30 UTC = 06:30 BR (limite superior — exclusivo)
        mock_dt.utcnow.return_value = datetime(2026, 5, 18, 9, 30)
        from datetime import timedelta as real_td
        with patch("services.auto_separation.timedelta", real_td):
            self.assertFalse(self.should_run_now())


class TestAlreadyRanToday(unittest.TestCase):
    """Testa o predicate de idempotência."""

    def test_state_sem_last_run_returns_false(self):
        from services.auto_separation import _already_ran_today
        from models import AutoSeparationState
        state = AutoSeparationState(id=1, last_run_at=None)
        self.assertFalse(_already_ran_today(state))

    def test_state_last_run_hoje_returns_true(self):
        from services.auto_separation import _already_ran_today
        from models import AutoSeparationState
        state = AutoSeparationState(id=1, last_run_at=datetime.utcnow())
        self.assertTrue(_already_ran_today(state))

    def test_state_last_run_ontem_returns_false(self):
        from services.auto_separation import _already_ran_today
        from models import AutoSeparationState
        state = AutoSeparationState(id=1, last_run_at=datetime.utcnow() - timedelta(days=1))
        self.assertFalse(_already_ran_today(state))


if __name__ == "__main__":
    unittest.main(verbosity=2)
