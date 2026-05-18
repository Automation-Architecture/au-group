from app.persistence.s3 import S3Client


def test_content_hash_stable(tmp_path) -> None:
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"%PDF-1.4 test content")
    hash_a = S3Client.sha256_file(file_path)
    hash_b = S3Client.sha256_file(file_path)
    assert hash_a == hash_b
    assert len(hash_a) == 64
