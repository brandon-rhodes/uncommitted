# -*- coding: utf-8 -*-

import uncommitted.command

def test_run_can_handle_badly_encoded_output():
    some_bytes = b'tsch\xfc\xdf' # 'tschüß' in latin1, outside UTF-8
    output = uncommitted.command.run(['echo', some_bytes])
    assert output == [u'tsch\ufffd\ufffd']
