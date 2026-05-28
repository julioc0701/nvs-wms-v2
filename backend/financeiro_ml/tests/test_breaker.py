from financeiro_ml.throttle import SellerCircuitBreaker


def test_breaker_starts_closed():
    b = SellerCircuitBreaker(cooldown_sec=300)
    assert b.is_open(seller_id=1) is False


def test_breaker_opens_after_trip():
    b = SellerCircuitBreaker(cooldown_sec=300)
    b.trip(seller_id=1)
    assert b.is_open(seller_id=1) is True


def test_breaker_half_open_after_cooldown():
    now = {"t": 1000.0}
    b = SellerCircuitBreaker(cooldown_sec=300, clock=lambda: now["t"])
    b.trip(seller_id=1)
    assert b.is_open(seller_id=1) is True
    now["t"] += 301
    assert b.is_open(seller_id=1) is False  # cooldown passou → meio-aberto deixa passar


def test_breaker_reset_on_success():
    b = SellerCircuitBreaker(cooldown_sec=300)
    b.trip(seller_id=1)
    b.record_success(seller_id=1)
    assert b.is_open(seller_id=1) is False
