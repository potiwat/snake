from analysis.freeze_gate import normalized_sha256


def test_normalized_sha256_is_independent_of_text_line_endings(tmp_path):
    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    lf.write_bytes(b"alpha\nbeta\n")
    crlf.write_bytes(b"alpha\r\nbeta\r\n")

    assert normalized_sha256(lf) == normalized_sha256(crlf)
