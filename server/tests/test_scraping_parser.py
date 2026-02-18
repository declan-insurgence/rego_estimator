from vic_rego_estimator.scraping.parser import _parse_html_tables


def test_parse_html_tables_fallbacks():
    html = '<html><body><table><tr><td>Registration fee</td><td>$990.50</td></tr><tr><td>TAC</td><td>$520.00</td></tr><tr><td>transfer</td><td>$48.80</td></tr><tr><td>plate</td><td>$42.20</td></tr></table></body></html>'
    parsed = _parse_html_tables(html)
    assert parsed['registration_fee_12'] == 990.5
    assert parsed['transfer_fee'] >= 48.8
