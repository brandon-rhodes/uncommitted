# -*- coding: utf-8 -*-

"""Test `uncommitted`'s implementation."""

import mock
import uncommitted.command

def test_run_chars_outside_default_charset():
    """Is `run` able to parse outputs containing chars outside the default charset?"""
    with mock.patch('uncommitted.command.check_output') as mock_check_output:
        mock_check_output.return_value = b'tsch\xfc\xdf' # 'tschüß' in latin1, outside UTF-8
        # No crash, unknown chars are converted to question marks:
        assert uncommitted.command.run(None) == [u'tsch\ufffd\ufffd'] # 'tsch??'
